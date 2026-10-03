"""Small, independent RenderWare DFF/COL3 writer for the Royal Citadel build.

Only Python's standard library is required. Coordinates are local, Z-up, metres.
"""
from __future__ import annotations
import math
import struct

RW_VERSION = 0x1803FFFF
ID_STRUCT, ID_STRING, ID_EXT, ID_TEXTURE, ID_MATERIAL, ID_MATLIST = 0x01, 0x02, 0x03, 0x06, 0x07, 0x08
ID_FRAMELIST, ID_GEOMETRY, ID_CLUMP, ID_ATOMIC, ID_GEOLIST = 0x0E, 0x0F, 0x10, 0x14, 0x1A
ID_BINMESH, ID_FRAMENAME = 0x50E, 0x253F2FE


def chunk(cid: int, payload: bytes, version: int = RW_VERSION) -> bytes:
    return struct.pack('<III', cid, len(payload), version) + payload


def struct_chunk(payload: bytes) -> bytes:
    return chunk(ID_STRUCT, payload)


def ext(payload: bytes = b'') -> bytes:
    return chunk(ID_EXT, payload)


def string_chunk(value: str) -> bytes:
    raw = value.encode('ascii') + b'\0'
    raw += b'\0' * ((-len(raw)) % 4)
    return chunk(ID_STRING, raw)


class Mesh:
    """Triangle mesh that emits flat-shaded quads/triangles with independent UVs."""
    def __init__(self):
        self.positions = []
        self.normals = []
        self.uvs = []
        self.triangles = []  # (a,b,c,material_index)
        self.materials = []
        self._material_index = {}

    def material(self, name: str, texture: str | None = None,
                 color=(255, 255, 255, 255), surface=(1.0, 0.0, 1.0)) -> int:
        key = (name, texture, tuple(color), tuple(surface))
        if key not in self._material_index:
            self._material_index[key] = len(self.materials)
            self.materials.append(dict(name=name, texture=texture, color=tuple(color), surface=tuple(surface)))
        return self._material_index[key]

    @staticmethod
    def _normal(a, b, c):
        ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
        nx, ny, nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length < 1e-12:
            return (0.0, 0.0, 1.0)
        return (nx/length, ny/length, nz/length)

    def triangle(self, a, b, c, material: int, uvs=None):
        n = self._normal(a, b, c)
        base = len(self.positions)
        self.positions.extend((tuple(a), tuple(b), tuple(c)))
        self.normals.extend((n, n, n))
        self.uvs.extend(uvs or ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)))
        self.triangles.append((base, base+1, base+2, material))

    def quad(self, points, material: int, uv=(1.0, 1.0)):
        p0, p1, p2, p3 = [tuple(p) for p in points]
        n = self._normal(p0, p1, p2)
        u, v = float(uv[0]), float(uv[1])
        base = len(self.positions)
        self.positions.extend((p0, p1, p2, p3))
        self.normals.extend((n, n, n, n))
        self.uvs.extend(((0.0, 0.0), (u, 0.0), (u, v), (0.0, v)))
        self.triangles.extend(((base, base+1, base+2, material), (base, base+2, base+3, material)))

    def bounds(self):
        if not self.positions:
            return ((0, 0, 0), (0, 0, 0))
        return (tuple(min(p[i] for p in self.positions) for i in range(3)),
                tuple(max(p[i] for p in self.positions) for i in range(3)))


def add_box(m: Mesh, x0, y0, z0, x1, y1, z1, material: int, density=1/6):
    """Closed outward-wound rectangular prism. UV density is repeats per metre."""
    x0, y0, z0, x1, y1, z1 = map(float, (x0, y0, z0, x1, y1, z1))
    if x1-x0 <= 1e-5 or y1-y0 <= 1e-5 or z1-z0 <= 1e-5:
        return
    dx, dy, dz = x1-x0, y1-y0, z1-z0
    # Top, bottom, south, north, east, west; all normals point outwards.
    quads = [
        ((x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1), dx,dy),
        ((x0,y1,z0),(x1,y1,z0),(x1,y0,z0),(x0,y0,z0), dx,dy),
        ((x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1), dx,dz),
        ((x1,y1,z0),(x0,y1,z0),(x0,y1,z1),(x1,y1,z1), dx,dz),
        ((x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1), dy,dz),
        ((x0,y1,z0),(x0,y0,z0),(x0,y0,z1),(x0,y1,z1), dy,dz),
    ]
    for p0,p1,p2,p3,u,v in quads:
        m.quad((p0,p1,p2,p3), material, (u*density, v*density))


def add_frustum(m: Mesh, x, y, z0, z1, r0, r1, material: int, sides=24, density=1/6,
                cap_bottom=True, cap_top=True):
    """Circular tapered prism, with optional caps."""
    rings = []
    for z, radius in ((z0, r0), (z1, r1)):
        rings.append([(x + radius*math.cos(2*math.pi*i/sides),
                       y + radius*math.sin(2*math.pi*i/sides), z) for i in range(sides)])
    bottom, top = rings
    for i in range(sides):
        j = (i+1) % sides
        arc = 2*math.pi*((r0+r1)*0.5)/sides
        m.quad((bottom[i], bottom[j], top[j], top[i]), material, (arc*density, (z1-z0)*density))
    if cap_bottom:
        center = (x,y,z0)
        for i in range(sides):
            j = (i+1)%sides
            m.triangle(center, bottom[j], bottom[i], material)
    if cap_top:
        center = (x,y,z1)
        for i in range(sides):
            j = (i+1)%sides
            m.triangle(center, top[i], top[j], material)


def add_multiring(m: Mesh, x, y, rings, material: int, sides=24, density=1/6, caps=True):
    """rings is [(z,radius), ...], ordered from bottom to top."""
    circles = [[(x+r*math.cos(2*math.pi*i/sides), y+r*math.sin(2*math.pi*i/sides), z)
                for i in range(sides)] for z,r in rings]
    for k in range(len(circles)-1):
        lower, upper = circles[k], circles[k+1]
        z0, r0 = rings[k]
        z1, r1 = rings[k+1]
        arc = 2*math.pi*(r0+r1)*0.5/sides
        for i in range(sides):
            j=(i+1)%sides
            m.quad((lower[i], lower[j], upper[j], upper[i]), material,
                   (arc*density, max(0.05, (z1-z0)*density)))
    if caps and circles:
        base, top = circles[0], circles[-1]
        for i in range(sides):
            j=(i+1)%sides
            m.triangle((x,y,rings[0][0]), base[j], base[i], material)
            m.triangle((x,y,rings[-1][0]), top[i], top[j], material)


def add_gable_roof(m: Mesh, cx, cy, z, width, depth, rise, material: int, density=1/6):
    """Two-sided pitched roof with ridge running along X."""
    x0,x1=cx-width/2,cx+width/2
    y0,y1=cy-depth/2,cy+depth/2
    ridge=z+rise
    m.quad(((x0,cy,ridge),(x1,cy,ridge),(x1,y1,z),(x0,y1,z)), material,
           (width*density, math.sqrt((depth/2)**2+rise**2)*density))
    m.quad(((x1,cy,ridge),(x0,cy,ridge),(x0,y0,z),(x1,y0,z)), material,
           (width*density, math.sqrt((depth/2)**2+rise**2)*density))
    # Gable end infill triangles (front and rear).
    m.triangle((x0,y0,z),(x1,y0,z),(cx,y0,ridge), material)
    m.triangle((x1,y1,z),(x0,y1,z),(cx,y1,ridge), material)


def add_arch_ring(m: Mesh, cx, cy, spring_z, inner_r, thickness, depth, material: int, segments=16):
    """Semicircular masonry arch in an X/Z plane, open underneath."""
    outer_r=inner_r+thickness
    y0,y1=cy-depth/2,cy+depth/2
    for i in range(segments):
        a0=math.pi*i/segments
        a1=math.pi*(i+1)/segments
        ix0,iz0=cx+inner_r*math.cos(a0),spring_z+inner_r*math.sin(a0)
        ix1,iz1=cx+inner_r*math.cos(a1),spring_z+inner_r*math.sin(a1)
        ox0,oz0=cx+outer_r*math.cos(a0),spring_z+outer_r*math.sin(a0)
        ox1,oz1=cx+outer_r*math.cos(a1),spring_z+outer_r*math.sin(a1)
        # Front voussoir strip and outer/back shell.
        m.quad(((ix0,y0,iz0),(ox0,y0,oz0),(ox1,y0,oz1),(ix1,y0,iz1)), material, (0.2,0.2))
        m.quad(((ox0,y0,oz0),(ox0,y1,oz0),(ox1,y1,oz1),(ox1,y0,oz1)), material, (0.2,depth/6))
        m.quad(((ix1,y0,iz1),(ox1,y0,oz1),(ox1,y1,oz1),(ix1,y1,iz1)), material, (0.2,depth/6))
    # Vertical jambs below the spring line.
    for side in (-1,1):
        x=cx+side*(inner_r+thickness/2)
        add_box(m,x-thickness/2,y0,spring_z-inner_r-thickness,x+thickness/2,y1,spring_z,material)


def _rw_texture(name: str) -> bytes:
    raw=name.encode('ascii')
    if len(raw)>=32:
        raise ValueError('RenderWare texture names must be under 32 ASCII bytes: '+name)
    raw=raw+b'\0'*(32-len(raw))
    filter_struct=struct_chunk(struct.pack('<I',0x1106))
    return chunk(ID_TEXTURE, filter_struct+string_chunk(name)+string_chunk('')+ext())


def _material_chunk(mat: dict) -> bytes:
    tex=mat.get('texture')
    r,g,b,a=mat.get('color',(255,255,255,255))
    amb,spec,diff=mat.get('surface',(1.0,0.0,1.0))
    payload=struct_chunk(struct.pack('<IBBBBIIfff',0,r,g,b,a,0,1 if tex else 0,amb,spec,diff))
    if tex:
        payload += _rw_texture(tex)
    payload += ext()
    return chunk(ID_MATERIAL,payload)


def build_dff(name: str, mesh: Mesh) -> bytes:
    n=len(mesh.positions)
    if not n or not mesh.triangles:
        raise ValueError('empty mesh: '+name)
    if n>=65536:
        raise ValueError('%s has too many DFF vertices (%d)'%(name,n))
    if len(mesh.materials)>255:
        raise ValueError('%s has too many materials'%(name,))
    lo,hi=mesh.bounds()
    center=tuple((lo[i]+hi[i])*0.5 for i in range(3))
    radius=max(math.sqrt(sum((p[i]-center[i])**2 for i in range(3))) for p in mesh.positions)
    # GTA SA RenderWare geometry flags: positions, one UV set, normals, material modulation.
    flags=0x02|0x04|0x10|0x40|(1<<16)
    data=struct.pack('<IIII',flags,len(mesh.triangles),n,1)
    for u,v in mesh.uvs:
        data += struct.pack('<ff',u,v)
    for a,b,c,mi in mesh.triangles:
        # RenderWare face layout is [v2,v1,material,v3].
        data += struct.pack('<HHHH',b,a,mi,c)
    data += struct.pack('<ffffII',center[0],center[1],center[2],radius,1,1)
    for p in mesh.positions:
        data += struct.pack('<fff',*p)
    for no in mesh.normals:
        data += struct.pack('<fff',*no)
    geometry=struct_chunk(data)
    matlist=struct.pack('<I',len(mesh.materials))+struct.pack('<%di'%len(mesh.materials),*([-1]*len(mesh.materials)))
    matlist=struct_chunk(matlist)+b''.join(_material_chunk(mat) for mat in mesh.materials)
    geometry += chunk(ID_MATLIST,matlist)
    # BinMesh plugin: triangle lists grouped by material.
    buckets=[]
    for mi in range(len(mesh.materials)):
        indices=[]
        for a,b,c,midx in mesh.triangles:
            if midx==mi:
                indices.extend((a,b,c))
        if indices:
            buckets.append((mi,indices))
    total=sum(len(ids) for _,ids in buckets)
    binmesh=struct.pack('<III',0,len(buckets),total)
    for mi,indices in buckets:
        binmesh += struct.pack('<II',len(indices),mi)
        binmesh += struct.pack('<%dI'%len(indices),*indices)
    geometry += ext(chunk(ID_BINMESH,binmesh))
    geo_list=struct_chunk(struct.pack('<I',1))+chunk(ID_GEOMETRY,geometry)
    # One root frame and one atomic.
    frame_struct=struct.pack('<I',1)
    frame_struct += struct.pack('<9f',1,0,0,0,1,0,0,0,1)
    frame_struct += struct.pack('<3f',0,0,0)
    frame_struct += struct.pack('<iI',-1,0x00020003)
    frame_list=struct_chunk(frame_struct)+ext(chunk(ID_FRAMENAME,name.encode('ascii')))
    atomic=struct_chunk(struct.pack('<IIII',0,0,0x5,0))+ext()
    clump=struct_chunk(struct.pack('<III',1,0,0))+chunk(ID_FRAMELIST,frame_list)+chunk(ID_GEOLIST,geo_list)+chunk(ID_ATOMIC,atomic)+ext()
    return chunk(ID_CLUMP,clump)


def build_col3(name: str, boxes=None, vertices=None, faces=None, model_id=1337) -> bytes:
    """Write a COL3 file. faces use local vertex indices and include material/flag bytes."""
    boxes=list(boxes or [])
    vertices=list(vertices or [])
    faces=list(faces or [])
    if not boxes and not vertices:
        raise ValueError('COL3 needs at least one box or mesh vertex: '+name)
    if len(boxes)>=65536 or len(faces)>=65536 or len(vertices)>=32768:
        raise ValueError('COL3 count limit exceeded for '+name)
    pts=[]
    for lo,hi,mat in boxes:
        pts.extend((tuple(lo),tuple(hi)))
    pts.extend(tuple(v) for v in vertices)
    lo=tuple(min(p[i] for p in pts) for i in range(3))
    hi=tuple(max(p[i] for p in pts) for i in range(3))
    center=tuple((lo[i]+hi[i])*0.5 for i in range(3))
    radius=math.sqrt(sum((hi[i]-center[i])**2 for i in range(3)))
    body=b''
    off_sphere=120-4
    # The castle generator uses boxes and triangle meshes; no spheres are required.
    off_box=off_sphere
    for blo,bhi,material in boxes:
        body += struct.pack('<6f',*(tuple(blo)+tuple(bhi)))+struct.pack('<BBBB',int(material)&255,0,0,0)
    off_vertices=off_sphere+len(body)
    for v in vertices:
        q=tuple(int(round(float(c)*128.0)) for c in v)
        if any(c<-32768 or c>32767 for c in q):
            raise ValueError('COL3 mesh vertex outside signed 16-bit / 128 range: '+name)
        body += struct.pack('<3h',*q)
    if len(vertices)*6%4:
        body += b'\0\0'
    off_faces=off_sphere+len(body)
    for a,b,c,material,flag in faces:
        body += struct.pack('<HHHBB',a,b,c,material&255,flag&255)
    if not boxes: off_box=0
    if not vertices: off_vertices=0
    if not faces: off_faces=0
    flags=0x02 if (boxes or faces) else 0
    header=struct.pack('<4sI',b'COL3',0)
    header += name.encode('ascii')[:21].ljust(22,b'\0')
    header += struct.pack('<H',model_id)
    header += struct.pack('<10f',*(lo+hi+center+(radius,)))
    header += struct.pack('<HHHBB',0,len(boxes),len(faces),0,0)
    header += struct.pack('<I',flags)
    header += struct.pack('<6I',0,off_box,0,off_vertices,off_faces,0)
    header += struct.pack('<III',0,0,0)
    if len(header)!=120:
        raise AssertionError('COL3 header is %d bytes, expected 120'%len(header))
    output=header+body
    return struct.pack('<4sI',b'COL3',len(output)-8)+output[8:]
