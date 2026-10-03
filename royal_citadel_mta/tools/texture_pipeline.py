"""AI source-image preparation and DXT1 / RenderWare TXD output (stdlib only).

The PNGs in assets/albedo are genuine AI-generated albedo images. This module only
resizes, mipmaps and compresses them; it does not synthesize or paint textures.
"""
from __future__ import annotations
import math
import os
import struct
import zlib

RW_VERSION = 0x1803FFFF
ID_STRUCT, ID_EXT, ID_TEXDICT, ID_TEXNATIVE = 0x01, 0x03, 0x16, 0x15
RASTER_565, RASTER_MIPMAP = 0x0200, 0x8000


def rw_chunk(cid: int, data: bytes) -> bytes:
    return struct.pack('<III', cid, len(data), RW_VERSION) + data


def _paeth(a, b, c):
    p=a+b-c
    pa=abs(p-a); pb=abs(p-b); pc=abs(p-c)
    return a if pa<=pb and pa<=pc else (b if pb<=pc else c)


def read_png_rgb(path: str):
    """Decode non-interlaced 8-bit RGB/RGBA PNGs without third-party packages."""
    data=open(path,'rb').read()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('not a PNG: '+path)
    pos=8; width=height=bit_depth=color_type=interlace=None; idat=[]
    while pos+12<=len(data):
        size=struct.unpack_from('>I',data,pos)[0]; kind=data[pos+4:pos+8]; start=pos+8; end=start+size
        if end+4>len(data): raise ValueError('truncated PNG chunk in '+path)
        payload=data[start:end]
        if kind==b'IHDR':
            width,height,bit_depth,color_type,compression,filter_method,interlace=struct.unpack('>IIBBBBB',payload)
            if compression or filter_method: raise ValueError('unsupported PNG compression/filter method')
        elif kind==b'IDAT': idat.append(payload)
        elif kind==b'IEND': break
        pos=end+4
    if bit_depth!=8 or color_type not in (2,6) or interlace!=0:
        raise ValueError('%s: expected non-interlaced 8-bit RGB/RGBA PNG, got depth=%s type=%s interlace=%s' %
                         (path,bit_depth,color_type,interlace))
    channels=3 if color_type==2 else 4
    bpp=channels; stride=width*channels
    raw=zlib.decompress(b''.join(idat))
    if len(raw)!=(stride+1)*height:
        raise ValueError('unexpected decompressed PNG size in '+path)
    out=bytearray(width*height*3); previous=bytearray(stride); rp=0; op=0
    for y in range(height):
        filt=raw[rp]; rp+=1
        row=bytearray(raw[rp:rp+stride]); rp+=stride
        if filt==1:
            for x in range(stride): row[x]=(row[x]+(row[x-bpp] if x>=bpp else 0))&255
        elif filt==2:
            for x in range(stride): row[x]=(row[x]+previous[x])&255
        elif filt==3:
            for x in range(stride): row[x]=(row[x]+((row[x-bpp] if x>=bpp else 0)+previous[x])//2)&255
        elif filt==4:
            for x in range(stride): row[x]=(row[x]+_paeth(row[x-bpp] if x>=bpp else 0,previous[x],previous[x-bpp] if x>=bpp else 0))&255
        elif filt!=0:
            raise ValueError('unknown PNG row filter %d'%filt)
        if channels==3:
            out[op:op+width*3]=row; op+=width*3
        else:
            for x in range(width):
                src=x*4; out[op:op+3]=row[src:src+3]; op+=3
        previous=row
    return width,height,out


def resize_box_rgb(rgb: bytearray, width: int, height: int, target: int):
    """Area-average to a square power-of-two image; preserves real source detail."""
    if width!=height:
        side=min(width,height)
        x0=(width-side)//2; y0=(height-side)//2
        cropped=bytearray(side*side*3)
        for y in range(side):
            a=(y+y0)*width*3+x0*3
            cropped[y*side*3:(y+1)*side*3]=rgb[a:a+side*3]
        rgb= cropped; width=height=side
    # Downscale by powers of two with a 2x2 box filter.
    while width>target and width%2==0 and height%2==0:
        nw,nh=width//2,height//2; dest=bytearray(nw*nh*3)
        for y in range(nh):
            row0=(2*y)*width*3; row1=row0+width*3; dst=y*nw*3
            for x in range(nw):
                a=row0+(2*x)*3; b=a+3; c=row1+(2*x)*3; d=c+3
                dest[dst]= (rgb[a]+rgb[b]+rgb[c]+rgb[d]+2)//4
                dest[dst+1]=(rgb[a+1]+rgb[b+1]+rgb[c+1]+rgb[d+1]+2)//4
                dest[dst+2]=(rgb[a+2]+rgb[b+2]+rgb[c+2]+rgb[d+2]+2)//4
                dst+=3
        rgb,width,height=dest,nw,nh
    if width!=target or height!=target:
        # Nearest resampling is only a fallback for a non-standard source size.
        dest=bytearray(target*target*3)
        for y in range(target):
            sy=min(height-1,int((y+0.5)*height/target))
            for x in range(target):
                sx=min(width-1,int((x+0.5)*width/target))
                src=(sy*width+sx)*3; dst=(y*target+x)*3
                dest[dst:dst+3]=rgb[src:src+3]
        rgb,width,height=dest,target,target
    return rgb


def _to565(rgb):
    r,g,b=rgb
    return ((r*31+127)//255<<11)|((g*63+127)//255<<5)|((b*31+127)//255)


def _from565(v):
    r=(v>>11)&31; g=(v>>5)&63; b=v&31
    return ((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2))


def _dxt1_block(pix):
    # Principal-axis endpoints preserve the dominant color variation better than
    # picking only min/max luminance; palette selection then chooses nearest RGB.
    n=len(pix); mean=[sum(p[k] for p in pix)/n for k in range(3)]
    cov=[[sum((p[i]-mean[i])*(p[j]-mean[j]) for p in pix)/n for j in range(3)] for i in range(3)]
    axis=[0.577350269,0.577350269,0.577350269]
    for _ in range(4):
        nxt=[sum(cov[i][j]*axis[j] for j in range(3)) for i in range(3)]
        length=math.sqrt(sum(v*v for v in nxt))
        if length<1e-8: break
        axis=[v/length for v in nxt]
    projected=[sum((p[k]-mean[k])*axis[k] for k in range(3)) for p in pix]
    p0=pix[max(range(n),key=lambda i:projected[i])]
    p1=pix[min(range(n),key=lambda i:projected[i])]
    c0,c1=_to565(p0),_to565(p1)
    if c0<c1: c0,c1=c1,c0
    if c0==c1:
        if c0<0xffff: c0+=1
        elif c1>0: c1-=1
    a,b=_from565(c0),_from565(c1)
    palette=(a,b,tuple((2*a[k]+b[k]+1)//3 for k in range(3)),tuple((a[k]+2*b[k]+1)//3 for k in range(3)))
    selectors=0
    for i,p in enumerate(pix):
        best=min(range(4),key=lambda j:sum((p[k]-palette[j][k])**2 for k in range(3)))
        selectors |= best<<(2*i)
    return struct.pack('<HHI',c0,c1,selectors)


def compress_dxt1(rgb: bytearray, width: int, height: int) -> bytes:
    out=bytearray(); row_stride=width*3
    for by in range(0,height,4):
        for bx in range(0,width,4):
            pix=[]
            for y in range(4):
                sy=min(height-1,by+y)
                for x in range(4):
                    sx=min(width-1,bx+x)
                    i=sy*row_stride+sx*3
                    pix.append((rgb[i],rgb[i+1],rgb[i+2]))
            out.extend(_dxt1_block(pix))
    return bytes(out)


def mip_chain(rgb: bytearray, width: int, height: int):
    levels=[]
    while True:
        levels.append((width,height,compress_dxt1(rgb,width,height)))
        if width==1 and height==1: break
        nw=max(1,width//2); nh=max(1,height//2)
        if nw==width or nh==height: break
        rgb=resize_box_rgb(rgb,width,height,nw)
        width,height=nw,nh
    return levels


def name32(name: str) -> bytes:
    raw=name.encode('ascii')
    if len(raw)>=32: raise ValueError('TXD name is 31 bytes maximum: '+name)
    return raw+b'\0'*(32-len(raw))


def native_texture(name: str, width: int, height: int, levels) -> bytes:
    # D3D9 native texture dictionary entry for a 16-bit DXT1 raster.
    st=struct.pack('<II',9,0x1106)+name32(name)+name32('')
    st+=struct.pack('<IIHHBBBB',RASTER_565|RASTER_MIPMAP,0x31545844,width,height,16,len(levels),4,0x08)
    for w,h,data in levels: st+=struct.pack('<I',len(data))+data
    return rw_chunk(ID_TEXNATIVE,rw_chunk(ID_STRUCT,st)+rw_chunk(ID_EXT,b''))


def build_txd(textures: list[dict]) -> bytes:
    payload=rw_chunk(ID_STRUCT,struct.pack('<HH',len(textures),9))
    for texture in textures:
        payload += native_texture(texture['name'],texture['width'],texture['height'],texture['levels'])
    payload += rw_chunk(ID_EXT,b'')
    return rw_chunk(ID_TEXDICT,payload)


def prepare_txd(source_dir: str, source_map: list[tuple[str,str]], target_size=512):
    textures=[]
    for txd_name,filename in source_map:
        path=os.path.join(source_dir,filename)
        width,height,rgb=read_png_rgb(path)
        rgb=resize_box_rgb(rgb,width,height,target_size)
        levels=mip_chain(rgb,target_size,target_size)
        textures.append(dict(name=txd_name,width=target_size,height=target_size,levels=levels))
    return build_txd(textures),textures
