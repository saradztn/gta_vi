#!/usr/bin/env python3
"""Dependency-free structural check for the generated Royal Citadel resource."""
from __future__ import annotations
import math
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET

HERE=os.path.dirname(os.path.abspath(__file__))
RES=os.path.join(HERE,'resource','RoyalCitadel')
FILES=os.path.join(RES,'files')
failures=[]; passed=0


def check(condition,message):
    global passed
    if condition: passed+=1
    else: failures.append(message); print('[FAIL]',message)


def read_chunk(data,pos,end=None):
    if end is None: end=len(data)
    if pos+12>end: raise ValueError('short RenderWare chunk header')
    cid,size,version=struct.unpack_from('<III',data,pos)
    start=pos+12; stop=start+size
    if stop>end: raise ValueError('RenderWare chunk extends beyond parent')
    return cid,size,version,start,stop


def children(data,start,end):
    pos=start
    while pos<end:
        c=read_chunk(data,pos,end)
        yield c
        pos=c[4]
    if pos!=end: raise ValueError('child chunk alignment error')


def string_value(data,start,end):
    return data[start:end].split(b'\0',1)[0].decode('ascii','replace')


def texture_name(data,start,end):
    names=[]
    for cid,size,ver,a,b in children(data,start,end):
        if cid==0x02: names.append(string_value(data,a,b))
    return names[0] if names else ''


def read_dff(path):
    data=open(path,'rb').read()
    root=read_chunk(data,0)
    if root[0]!=0x10 or root[4]!=len(data): raise ValueError('bad DFF root')
    top=list(children(data,root[3],root[4]))
    geolists=[c for c in top if c[0]==0x1A]
    framelists=[c for c in top if c[0]==0x0E]
    atomics=[c for c in top if c[0]==0x14]
    if len(geolists)!=1 or len(framelists)!=1 or len(atomics)!=1: raise ValueError('expected one frame/geolist/atomic')
    geom_chunks=[c for c in children(data,geolists[0][3],geolists[0][4]) if c[0]==0x0F]
    if len(geom_chunks)!=1: raise ValueError('expected one geometry')
    geom=geom_chunks[0]; sub=list(children(data,geom[3],geom[4]))
    st=next(c for c in sub if c[0]==1)
    flags,ntris,nverts,nmorph=struct.unpack_from('<IIII',data,st[3])
    if nverts==0 or ntris==0 or nmorph!=1: raise ValueError('empty or unexpected DFF geometry')
    uvsets=(flags>>16)&0xff
    if uvsets<1: raise ValueError('DFF has no UV set')
    ofs=st[3]+16+nverts*uvsets*8
    tri_data=data[ofs:ofs+ntris*8]
    if len(tri_data)!=ntris*8: raise ValueError('truncated triangle table')
    bad_index=0
    face_mats=set(); decoded_faces=[]
    for i in range(ntris):
        b,a,mi,c=struct.unpack_from('<HHHH',tri_data,i*8)
        if max(a,b,c)>=nverts: bad_index+=1
        face_mats.add(mi); decoded_faces.append((a,b,c))
    ofs+=ntris*8+24
    pbytes=nverts*12
    if ofs+pbytes*2>st[4]: raise ValueError('truncated vertex/normal arrays')
    floats=struct.unpack_from('<%df'%(nverts*3),data,ofs)
    normals=struct.unpack_from('<%df'%(nverts*3),data,ofs+pbytes)
    if not all(math.isfinite(v) for v in floats+normals): raise ValueError('non-finite vertex data')
    zero_normals=0; bad_winding=0
    for n in range(nverts):
        nn=math.sqrt(sum(normals[n*3+k]**2 for k in range(3)))
        if nn<0.5: zero_normals+=1
    for a,b,c in decoded_faces:
        if max(a,b,c)>=nverts: continue
        p=[floats[i*3:i*3+3] for i in (a,b,c)]
        u=[p[1][i]-p[0][i] for i in range(3)]; v=[p[2][i]-p[0][i] for i in range(3)]
        cr=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        ar=math.sqrt(sum(q*q for q in cr))
        if ar>1e-8:
            vn=[sum(normals[j*3+i] for j in (a,b,c)) for i in range(3)]
            if sum(cr[i]*vn[i] for i in range(3))<=0: bad_winding+=1
    if zero_normals or bad_winding: raise ValueError('invalid normals/winding (%d zero, %d reversed)'%(zero_normals,bad_winding))
    material_lists=[c for c in sub if c[0]==0x08]
    if len(material_lists)!=1: raise ValueError('missing material list')
    ml_children=list(children(data,material_lists[0][3],material_lists[0][4]))
    mlst=next(c for c in ml_children if c[0]==1)
    material_count=struct.unpack_from('<I',data,mlst[3])[0]
    materials=[c for c in ml_children if c[0]==0x07]
    if material_count!=len(materials) or not materials: raise ValueError('material list count mismatch')
    textures=[]
    for mat in materials:
        for cid,size,ver,a,b in children(data,mat[3],mat[4]):
            if cid==0x06: textures.append(texture_name(data,a,b))
    if bad_index or (face_mats and max(face_mats)>=material_count): raise ValueError('triangle index/material out of range')
    # Every geometry must carry a valid BinMesh extension and enough triangle indices.
    ext_chunk=next((c for c in sub if c[0]==3),None)
    if not ext_chunk: raise ValueError('missing geometry extension')
    plugins=list(children(data,ext_chunk[3],ext_chunk[4]))
    bm=next((c for c in plugins if c[0]==0x50e),None)
    if not bm: raise ValueError('missing BinMesh plugin')
    flags_bm,nmesh,total=struct.unpack_from('<III',data,bm[3])
    if total!=ntris*3 or nmesh<1: raise ValueError('BinMesh triangle count mismatch')
    return dict(vertices=nverts,triangles=ntris,textures=set(textures),materials=material_count)


def read_txd(path):
    data=open(path,'rb').read(); root=read_chunk(data,0)
    if root[0]!=0x16 or root[4]!=len(data): raise ValueError('bad TXD root')
    kids=list(children(data,root[3],root[4]))
    st=next(c for c in kids if c[0]==1)
    count,device=struct.unpack_from('<HH',data,st[3])
    if device!=9: raise ValueError('TXD is not D3D9')
    native=[c for c in kids if c[0]==0x15]
    names=set()
    for tex in native:
        ns=list(children(data,tex[3],tex[4])); native_st=next(c for c in ns if c[0]==1)
        p=native_st[3]
        platform,filtering=struct.unpack_from('<II',data,p); p+=8
        name=data[p:p+32].split(b'\0',1)[0].decode('ascii'); p+=64
        raster,fourcc,w,h,depth,levels,rtype,flags=struct.unpack_from('<IIHHBBBB',data,p); p+=16
        if fourcc!=0x31545844 or depth!=16 or not levels: raise ValueError('not a DXT1 TXD texture: '+name)
        for level in range(levels):
            size=struct.unpack_from('<I',data,p)[0]; p+=4
            expected=max(1,(w+3)//4)*max(1,(h+3)//4)*8
            if size!=expected: raise ValueError('%s mip %d has %d bytes, expected %d'%(name,level,size,expected))
            p+=size; w=max(1,w//2); h=max(1,h//2)
        if p!=native_st[4]: raise ValueError('TXD mip payload size mismatch: '+name)
        if name in names: raise ValueError('duplicate TXD name: '+name)
        names.add(name)
    if count!=len(native): raise ValueError('TXD texture count mismatch')
    return names


def main():
    global passed
    try:
        meta=ET.parse(os.path.join(RES,'meta.xml')).getroot()
        listed={e.get('src') for e in meta.findall('file')}
        scripts={e.get('src') for e in meta.findall('script')}
        all_files=set()
        for root,dirs,files in os.walk(FILES):
            for f in files: all_files.add(os.path.relpath(os.path.join(root,f),RES).replace(os.sep,'/'))
        check(all(x and os.path.isfile(os.path.join(RES,x)) for x in listed|scripts),'all meta.xml assets exist')
        check(listed==all_files,'meta.xml file list exactly covers compiled assets')
        check({'client.lua','server.lua','models.lua','layout.lua'}<=scripts,'client/server/data scripts are declared')
        txd_names=read_txd(os.path.join(RES,'files','royal_citadel.txd'))
        check(len(txd_names)==9,'TXD contains nine AI-generated textures')
        models=[]
        for path in sorted(os.listdir(os.path.join(RES,'files','dff'))):
            if not path.endswith('.dff'): continue
            info=read_dff(os.path.join(RES,'files','dff',path))
            check(info['textures']<=txd_names,path+': DFF materials resolve in the shared TXD')
            models.append((path,info))
        check(len(models)==42,'high and LOD DFF files exist for all 21 modular model types')
        col_files=[p for p in os.listdir(os.path.join(RES,'files','col')) if p.endswith('.col')]
        for name in col_files:
            p=os.path.join(RES,'files','col',name); data=open(p,'rb').read()
            check(data[:4]==b'COL3' and struct.unpack_from('<I',data,4)[0]==len(data)-8,name+': COL3 signature and file size')
            nsphere,nbox,nface=struct.unpack_from('<HHH',data,8+22+2+10*4)
            offsets=struct.unpack_from('<6I',data,8+22+2+10*4+12)
            off_box,off_vertex,off_face=offsets[1],offsets[3],offsets[4]
            check(nsphere+nbox+nface>0,name+': non-empty collision')
            if nbox:
                check(off_box>0 and 4+off_box+nbox*28<=len(data),name+': COL3 box offset/range')
            if nface:
                check(off_vertex>0 and off_face>0 and 4+off_vertex<len(data) and 4+off_face+nface*8<=len(data),name+': COL3 mesh offsets/range')
                # Mesh vertex count is inferred from the face-stream offset and validated against every face index.
                vert_bytes=off_face-off_vertex
                nv=vert_bytes//6
                if nv*6+2==vert_bytes: nv=(vert_bytes-2)//6
                if nv*6 not in (vert_bytes,vert_bytes-2): raise ValueError(name+': invalid COL3 vertex padding')
                for i in range(nface):
                    a,b,c,material,flag=struct.unpack_from('<HHHBB',data,4+off_face+i*8)
                    if max(a,b,c)>=nv: raise ValueError(name+': COL3 face index out of range')
        layout=open(os.path.join(RES,'layout.lua'),encoding='utf8').read()
        placement_count=len(re.findall(r'\{ model="',layout))
        check(placement_count>150,'generated layout has a large modular scene (%d placements)'%placement_count)
        check(os.path.isfile(os.path.join(HERE,'build-report.json')),'build report exists')
        print('%d checks passed; %d model DFFs, %d collision files, %d TXD textures.'%(passed,len(models),len(col_files),len(txd_names)))
    except Exception as exc:
        failures.append(str(exc))
        print('[FAIL] validator error:',exc)
    if failures:
        print('%d check(s) failed:'%len(failures))
        for msg in failures: print(' -',msg)
        raise SystemExit(1)
    print('Royal Citadel resource structure: PASS')

if __name__=='__main__': main()
