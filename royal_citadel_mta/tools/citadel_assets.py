"""Parametric, modular European royal-citadel meshes. Z-up, metres, local origin at foot/centre."""
from __future__ import annotations
import math
from .rw_mesh import Mesh, add_box, add_frustum, add_multiring, add_gable_roof, add_arch_ring

# TXD names are shared across every modular DFF.  All bitmap source images are AI-generated.
TEX = {
    'stone':'stone_new', 'aged':'stone_old', 'slate':'roof_slate', 'marble':'marble_ivory',
    'copper':'copper_old', 'gold':'gold_bronze', 'wood':'royal_oak', 'cobble':'paving', 'cliff':'cliff_rock',
    'carpet':'hall_carpet', 'brocade':'throne_brocade', 'oak_panel':'carved_oak',
    'tracery':'gothic_tracery', 'trim':'gilded_trim', 'fresco':'vault_fresco',
    'books':'library_books', 'iron_grille':'iron_grille', 'rose_glass':'rose_window',
    'crest':'royal_crest', 'walnut':'walnut_parquet', 'velvet':'throne_velvet',
    'curtain':'curtain_silk', 'damask':'chamber_damask', 'chapel_tile':'chapel_tile',
    'hearth':'hearth_stone', 'iron':'black_iron', 'emerald':'emerald_damask',
    'leather':'royal_leather', 'parchment':'blank_parchment', 'wall_fresco':'wall_fresco',
    'black_marble':'black_onyx', 'grass':'garden_lawn', 'ivy':'ivy_stone',
    'bark':'pine_bark', 'foam':'waterfall_foam', 'chapel_border':'chapel_border',
    'mosaic':'royal_mosaic', 'stained':'stained_glass', 'moat_water':'moat_surface',
}
TINT = {
    'green':(80,142,71,255), 'deepgreen':(38,88,52,255), 'window':(18,34,54,255),
    'warmglass':(206,146,74,255), 'water':(38,111,143,215), 'bluecloth':(29,55,116,255),
    'redcloth':(132,34,40,255), 'night':(22,28,38,255), 'glow':(255,174,75,255),
}
DENSITY = {'stone':1/6,'aged':1/6,'slate':1/5,'marble':1/6,'copper':1/5,'gold':1/5,
           'wood':1/5,'cobble':1/8,'cliff':1/7,'carpet':1/2,'brocade':1/2,
           'oak_panel':1/3,'tracery':1/3,'trim':1/2,'books':1/2,'iron_grille':1/2,
           'rose_glass':1/2,'crest':1/2,'walnut':1/3,'velvet':1/2,'curtain':1/2,
           'damask':1/2,'chapel_tile':1/2,'hearth':1/5,'iron':1/2,'emerald':1/2,
           'leather':1/2,'parchment':1/2,'wall_fresco':1/2,'black_marble':1/5,
           'grass':1/2,'ivy':1/6,'bark':1/5,'foam':1/2,'chapel_border':1/2,
           'mosaic':1/2,'stained':1/2,'moat_water':1/4}


def mat(m: Mesh, key: str):
    if key in TEX:
        return m.material(key,TEX[key],(255,255,255,255))
    return m.material(key,None,TINT.get(key,(255,255,255,255)))


def box(m,x0,y0,z0,x1,y1,z1,material='stone'):
    add_box(m,x0,y0,z0,x1,y1,z1,mat(m,material),DENSITY.get(material,1/5))


def panel_y(m, colliders, y, x0, x1, z0, z1, openings=(), thickness=1.4, material='stone'):
    """Wall normal to Y, assembled from solid cells around rectangular door/window voids."""
    openings=[tuple(map(float,o)) for o in openings]
    xs=sorted(set([float(x0),float(x1)]+[v for o in openings for v in (max(x0,o[0]),min(x1,o[1])) if x0<v<x1]))
    zs=sorted(set([float(z0),float(z1)]+[v for o in openings for v in (max(z0,o[2]),min(z1,o[3])) if z0<v<z1]))
    for xa,xb in zip(xs,xs[1:]):
        for za,zb in zip(zs,zs[1:]):
            mx=(xa+xb)*0.5; mz=(za+zb)*0.5
            if any(a < mx < b and c < mz < d for a,b,c,d in openings):
                continue
            bounds=((xa,y-thickness*0.5,za),(xb,y+thickness*0.5,zb))
            box(m,*bounds[0],*bounds[1],material)
            colliders.append((bounds[0],bounds[1],0))


def panel_x(m, colliders, x, y0, y1, z0, z1, openings=(), thickness=1.4, material='stone'):
    """Wall normal to X, assembled from solid cells around rectangular door/window voids."""
    openings=[tuple(map(float,o)) for o in openings]
    ys=sorted(set([float(y0),float(y1)]+[v for o in openings for v in (max(y0,o[0]),min(y1,o[1])) if y0<v<y1]))
    zs=sorted(set([float(z0),float(z1)]+[v for o in openings for v in (max(z0,o[2]),min(z1,o[3])) if z0<v<z1]))
    for ya,yb in zip(ys,ys[1:]):
        for za,zb in zip(zs,zs[1:]):
            my=(ya+yb)*0.5; mz=(za+zb)*0.5
            if any(a < my < b and c < mz < d for a,b,c,d in openings):
                continue
            bounds=((x-thickness*0.5,ya,za),(x+thickness*0.5,yb,zb))
            box(m,*bounds[0],*bounds[1],material)
            colliders.append((bounds[0],bounds[1],0))


def floor_quad(m, x0, y0, x1, y1, z, material, density=0.25):
    """Textured upward-facing floor tile, with metres-per-repeat UVs."""
    m.quad(((x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)),mat(m,material),
           ((x1-x0)*density,(y1-y0)*density))


def two_sided_panel_y(m, x0, x1, y, z0, z1, material, uv=(1.0,1.0)):
    pts=((x0,y,z0),(x1,y,z0),(x1,y,z1),(x0,y,z1))
    mi=mat(m,material)
    m.quad(pts,mi,uv)
    m.quad(tuple(reversed(pts)),mi,uv)


def two_sided_panel_x(m, x, y0, y1, z0, z1, material, uv=(1.0,1.0)):
    pts=((x,y0,z0),(x,y1,z0),(x,y1,z1),(x,y0,z1))
    mi=mat(m,material)
    m.quad(pts,mi,uv)
    m.quad(tuple(reversed(pts)),mi,uv)


def cylinder(m,x,y,z0,z1,r,material='stone',sides=24,r1=None):
    add_frustum(m,x,y,z0,z1,r,r if r1 is None else r1,mat(m,material),sides,DENSITY.get(material,1/5))


def ring(m,x,y,z0,z1,r0,r1,material='gold',sides=24):
    # A solid tapered ring-like trim, intentionally shallow and made from a frustum.
    cylinder(m,x,y,z0,z1,r0,material,sides,r1)


def dome(m,cx,cy,base_z,radius,height,material='slate',sides=28,steps=7):
    rings=[]
    for i in range(steps+1):
        t=i/steps
        rr=max(0.18,radius*math.sqrt(max(0.0,1.0-t*t)))
        rings.append((base_z+height*t,rr))
    add_multiring(m,cx,cy,rings,mat(m,material),sides,DENSITY.get(material,1/5),caps=False)
    cylinder(m,cx,cy,base_z-0.35,base_z+0.25,radius+0.45,'copper',sides,radius+0.45)
    # Gold ribs and lantern/finial draw the dome silhouette at medium distance.
    if sides>=16:
        rib_sides=max(8,sides//2)
        for i in range(rib_sides):
            a=2*math.pi*i/rib_sides
            x=cx+radius*0.74*math.cos(a); y=cy+radius*0.74*math.sin(a)
            cylinder(m,x,y,base_z+1.0,base_z+height*0.9,0.11,'gold',6,0.04)
    cylinder(m,cx,cy,base_z+height*0.86,base_z+height+2.3,0.32,'gold',10,0.06)
    cylinder(m,cx,cy,base_z+height+1.5,base_z+height+3.0,0.10,'copper',8,0.10)


def terrain_height(x,y):
    """Broad raised citadel mesa, stepped royal terraces and a southern approach saddle."""
    r=max(abs(x)/230.0,abs(y)/195.0)
    def smooth(t):
        t=max(0.0,min(1.0,t)); return t*t*(3.0-2.0*t)
    if r<=0.40:
        h=62.0
    elif r<=0.72:
        h=62.0-19.0*smooth((r-0.40)/0.32)
    else:
        h=43.0-46.0*smooth((r-0.72)/0.28)
    # A narrow, broad-based natural ramp carries the processional road up from the southern shore.
    if y < -100 and abs(x)<26:
        t=(y+220.0)/110.0
        h=max(h,43.0*smooth(t))
    # Two natural shoulders break the perfect mesa outline without roughening the palace plateau.
    for hx,hy,amp,sx,sy in ((-175,82,19,54,42),(173,104,16,46,38),(-165,-36,11,42,38)):
        h += amp*math.exp(-(((x-hx)/sx)**2+((y-hy)/sy)**2)*1.45)
    return h


def _terrain(lod=False):
    m=Mesh(); n=16 if lod else 38
    xs=[-230+460*i/n for i in range(n+1)]
    ys=[-195+390*j/n for j in range(n+1)]
    grid=[]
    for y in ys:
        grid.append([(x,y,terrain_height(x,y)) for x in xs])
    for j in range(n):
        for i in range(n):
            p00=grid[j][i]; p10=grid[j][i+1]; p11=grid[j+1][i+1]; p01=grid[j+1][i]
            slope=max(abs(p10[2]-p00[2]),abs(p01[2]-p00[2]))
            r=max(abs((xs[i]+xs[i+1])*0.5)/230.0,abs((ys[j]+ys[j+1])*0.5)/195.0)
            material='cliff' if slope>5 or r>0.72 else ('aged' if r>0.40 else 'aged')
            density=DENSITY[material]
            m.quad((p00,p10,p11,p01),mat(m,material),((xs[i+1]-xs[i])*density,(ys[j+1]-ys[j])*density))
    # Unique terrain collision grid, separate from the UV-split DFF vertices.
    verts=[grid[j][i] for j in range(n+1) for i in range(n+1)]
    faces=[]
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i; b=a+1; d=(j+1)*(n+1)+i; c=d+1
            faces.extend(((a,b,c,0,0),(a,c,d,0,0)))
    return m,[],(verts,faces)


def _wall(lod=False):
    m=Mesh(); boxes=[]
    # The repeated curtain wall module is walkable on top, braced, crenellated and textured on all faces.
    box(m,-14,-2.25,0,14,2.25,11.8,'aged')
    box(m,-14.5,-2.65,0,14.5,2.65,1.5,'stone')
    box(m,-14.7,-2.9,11.8,14.7,2.9,12.5,'stone')
    if not lod:
        box(m,-14.3,-2.6,10.5,14.3,2.6,11.2,'marble')
        # Wall walk and continuous inner coping.
        box(m,-13.7,-1.8,12.5,13.7,1.8,13.0,'cobble')
        step=2.8; count=10
        for i in range(count):
            x=-14+step*(i+0.5)
            if i%2==1: continue
            box(m,x-0.82,-2.6,12.5,x+0.82,2.6,16.2,'stone')
            box(m,x-0.94,-2.76,15.9,x+0.94,2.76,16.25,'marble')
        # Recessed arrow slits and stone pilasters.
        for x in (-10.5,-5.25,0,5.25,10.5):
            box(m,x-0.22,-2.29,5.8,x+0.22,-2.20,8.3,'window')
            box(m,x-0.54,-2.42,5.45,x-0.38,-2.28,8.55,'gold')
            box(m,x+0.38,-2.42,5.45,x+0.54,-2.28,8.55,'gold')
            box(m,x-0.62,-2.37,2.0,x+0.62,-2.25,2.45,'marble')
        for x in (-12.2,-6.1,0,6.1,12.2):
            box(m,x-0.5,-2.65,0.6,x+0.5,-2.25,10.7,'stone')
            box(m,x-0.75,-2.84,1.0,x+0.75,-2.45,1.45,'marble')
            box(m,x-0.75,-2.84,10.2,x+0.75,-2.45,10.65,'marble')
    else:
        for x in (-9,0,9): box(m,x-1.1,-2.6,12.5,x+1.1,2.6,16.0,'stone')
    boxes.extend([((-14.5,-2.65,0),(14.5,2.65,12.5),0)])
    return m,boxes,None


def _round_tower(lod=False):
    m=Mesh(); seg=12 if lod else 32
    cylinder(m,0,0,0,5,10.0,'stone',seg,9.6)
    cylinder(m,0,0,4.5,34,8.7,'aged',seg,7.8)
    ring(m,0,0,4.4,5.5,9.8,9.0,'marble',seg)
    ring(m,0,0,33.5,35.3,8.8,8.8,'stone',seg)
    ring(m,0,0,35.0,37.0,9.7,9.3,'gold',seg)
    cylinder(m,0,0,36.5,39.0,8.9,'aged',seg,8.9)
    if not lod:
        # Narrow arched slit windows on four faces; layered cornices and machicolation brackets.
        for a in (0,math.pi/2,math.pi,3*math.pi/2):
            x=8.02*math.cos(a); y=8.02*math.sin(a)
            box(m,x-0.42,y-0.42,13.0,x+0.42,y+0.42,20.0,'window')
            box(m,x-0.67,y-0.67,12.6,x-0.49,y+0.49,20.3,'gold')
            box(m,x+0.49,y-0.49,12.6,x+0.67,y+0.67,20.3,'gold')
            box(m,x-0.62,y-0.62,19.9,x+0.62,y+0.62,20.35,'marble')
        for k in range(12):
            a=2*math.pi*k/12
            x,y=8.9*math.cos(a),8.9*math.sin(a)
            box(m,x-1.0,y-1.0,38.5,x+1.0,y+1.0,42.3,'stone')
        # High blue slate conical crown and a gilded finial.
        cylinder(m,0,0,41.0,67.0,9.4,'slate',seg,0.18)
        ring(m,0,0,40.7,42.0,9.8,9.5,'copper',seg)
        cylinder(m,0,0,66.4,71.5,0.65,'gold',10,0.08)
    else:
        cylinder(m,0,0,39.0,65.0,9.4,'slate',seg,0.25)
        cylinder(m,0,0,64.0,69.0,0.5,'gold',8,0.08)
    return m,[((-9.5,-9.5,0),(9.5,9.5,39),0)],None


def _spire_tower(lod=False):
    m=Mesh(); seg=8 if lod else 12
    cylinder(m,0,0,0,4,7.7,'stone',seg,7.2)
    cylinder(m,0,0,3.8,33,6.7,'aged',seg,5.7)
    ring(m,0,0,32.5,34.0,7.4,7.1,'gold',seg)
    if not lod:
        for z in (8,17,26):
            ring(m,0,0,z,z+0.6,6.9,7.2,'marble',seg)
        for a in range(8):
            angle=2*math.pi*a/8
            x,y=5.9*math.cos(angle),5.9*math.sin(angle)
            box(m,x-0.55,y-0.55,33.5,x+0.55,y+0.55,37.8,'stone')
    cylinder(m,0,0,33.0,78.0,7.3,'slate',seg,0.12)
    ring(m,0,0,33.0,34.0,7.8,7.5,'copper',seg)
    cylinder(m,0,0,77.0,82.5,0.50,'gold',8,0.04)
    return m,[((-7.6,-7.6,0),(7.6,7.6,35),0)],None


def _palace(lod=False):
    m=Mesh(); boxes=[]
    if lod:
        # Far LOD keeps the same stepped silhouette, but is deliberately solid and inexpensive.
        box(m,-48,-39,0,48,39,5,'aged')
        box(m,-46,-37,5,46,37,9,'marble')
        box(m,-43,-34,9,43,34,34,'aged')
        box(m,-27,12,34,27,34,57,'stone')
        add_gable_roof(m,0,-10,34,86,48,20,mat(m,'slate'),DENSITY['slate'])
        add_gable_roof(m,0,23,57,54,22,17,mat(m,'slate'),DENSITY['slate'])
        for x in (-38,38):
            for y in (-29,29):
                cylinder(m,x,y,9,48,5.2,'stone',10,4.4)
                cylinder(m,x,y,47,73,5.4,'slate',10,0.12)
        dome(m,0,23,72,10.5,17,'slate',12,4)
        return m,[],None

    # Foundation plinth and a walkable floor slab; collision is a thin deck, not a solid block.
    box(m,-48,-39,0,48,39,5,'aged')
    box(m,-46,-37,5,46,37,8.4,'marble')
    box(m,-43,-34,8.45,43,34,9.0,'marble')
    boxes.append(((-43,-34,8.45),(43,34,9.0),0))

    # Thirty broad, shallow steps rise from the forecourt straight through the open portal.
    steps=30; run=21.0; rise=9.0; tread=run/steps; riser=rise/steps
    for i in range(steps):
        y=-55.0+i*tread; z=i*riser
        box(m,-7.5,y,z,7.5,y+tread+0.015,z+riser,'marble')
        if i%3==0:
            box(m,-7.7,y,z-0.06,7.7,y+0.10,z+0.06,'trim')
        boxes.append(((-7.5,y,z),(7.5,y+tread,z+riser),0))
    for side in (-1,1):
        x=side*8.4
        box(m,x-0.65,-55,0,x+0.65,-34,10.3,'stone')
        box(m,x-0.82,-55,10.0,x+0.82,-34,10.35,'marble')
        boxes.append(((x-0.65,-55,0),(x+0.65,-34,10.3),0))

    # Lower plinth bands. The centered south opening is kept visually clear above the stair.
    box(m,-48,-39,0,-6,-36,5,'aged'); box(m,6,-39,0,48,-36,5,'aged')
    box(m,-48,36,0,48,39,5,'aged')
    box(m,-48,-36,0,-45,36,5,'aged'); box(m,45,-36,0,48,36,5,'aged')
    box(m,-46,-37,5,-6,-34,8.35,'marble'); box(m,6,-37,5,46,-34,8.35,'marble')
    box(m,-46,34,5,46,37,8.35,'marble')
    box(m,-46,-34,5,-43,34,8.35,'marble'); box(m,43,-34,5,46,34,8.35,'marble')

    # Exterior shell uses explicit wall cells, with real open doorway and high window apertures.
    south_open=[(-5.5,5.5,9.0,21.0)]
    south_open += [(cx-1.55,cx+1.55,16.5,24.0) for cx in (-30,-15,15,30)]
    panel_y(m,boxes,-34,-43,43,9,34,south_open,1.6,'stone')
    north_open=[(-8,8,19,31),(-21,-18,16.5,24),(-12,-9,16.5,24),(9,12,16.5,24),(18,21,16.5,24)]
    panel_y(m,boxes,34,-43,43,9,34,north_open,1.6,'stone')
    side_windows=[(cy-1.45,cy+1.45,16.5,24) for cy in (-23,-8,8,23)]
    panel_x(m,boxes,-43,-34,34,9,34,side_windows,1.6,'stone')
    panel_x(m,boxes,43,-34,34,9,34,side_windows,1.6,'stone')
    for cx in (-30,-15,15,30):
        two_sided_panel_y(m,cx-1.45,cx+1.45,-34.04,16.6,23.9,'stained',(0.5,1.0))
    for cy in (-23,-8,8,23):
        two_sided_panel_x(m,-42.18,cy-1.35,cy+1.35,16.6,23.9,'stained',(0.4,1.0))
        two_sided_panel_x(m,42.18,cy-1.35,cy+1.35,16.6,23.9,'stained',(0.4,1.0))
    # Deep stone arch, ordered columns and measured horizontal string courses at the entrance.
    add_arch_ring(m,0,-34.0,14.4,5.5,1.6,1.8,mat(m,'tracery'),20)
    for x in (-22,-15,-7.3,7.3,15,22):
        cylinder(m,x,-36.3,9,26.0,0.72,'marble',16,0.68)
        ring(m,x,-36.3,9,10.0,1.0,0.85,'gold',12)
        ring(m,x,-36.3,25.3,26.3,1.0,0.76,'gold',12)
    for z in (9.5,14.5,25.0,33.2):
        box(m,-43,-35.0,z,43,-33.8,z+0.42,'trim')
    # A projecting ceremonial balcony sits above, never across, the entrance opening.
    box(m,-25,-38.0,25.8,25,-33.7,27.0,'marble')
    box(m,-24,-38.15,27.0,24,-37.8,27.35,'trim')
    for x in range(-22,23,2):
        if abs(x)<6: continue
        cylinder(m,x,-37.5,27.0,29.5,0.13,'gold',8,0.10)

    # Main roofs and rear keep are separated so the central keep reads as the tallest mass.
    add_gable_roof(m,0,-10,34,86,48,20,mat(m,'slate'),DENSITY['slate'])
    # Upper keep shell over the throne suite; lower doorway remains open to the Great Hall.
    keep_open=[(-8,8,34,46),(-20,-16,40,49),(16,20,40,49)]
    panel_y(m,boxes,12,-27,27,34,57,keep_open,2.0,'aged')
    panel_y(m,boxes,34,-27,27,34,57,[(-8,8,39,52)],2.0,'aged')
    panel_x(m,boxes,-27,12,34,34,57,[ (19,23,40,49) ],2.0,'aged')
    panel_x(m,boxes,27,12,34,34,57,[ (19,23,40,49) ],2.0,'aged')
    for cx in (-18,18):
        two_sided_panel_y(m,cx-1.8,cx+1.8,12.04,40.1,48.9,'stained',(0.5,1.0))
        two_sided_panel_x(m,-26.0 if cx<0 else 26.0,19.2,22.8,40.1,48.9,'stained',(0.5,1.0))
    two_sided_panel_y(m,-7.6,7.6,33.0,39.2,51.8,'rose_glass',(1.0,1.0))
    add_gable_roof(m,0,23,57,54,22,17,mat(m,'slate'),DENSITY['slate'])
    dome(m,0,23,72,10.5,17,'slate',24,7)
    # Four secondary spired turrets frame the keep without filling the rooms with collision boxes.
    for x in (-38,38):
        for y in (-29,29):
            cylinder(m,x,y,9,47,5.0,'stone',20,4.2)
            ring(m,x,y,44.8,47,5.5,5.0,'trim',16)
            cylinder(m,x,y,46.5,71.5,5.2,'slate',20,0.12)
            cylinder(m,x,y,71.0,74.0,0.4,'gold',8,0.04)

    # Interior flooring: each named room gets a deliberate material rather than one repeated slab.
    floor_quad(m,-41,-32,41,32,9.025,'marble',0.20)
    floor_quad(m,-16,-29,16,20,9.04,'mosaic',0.16)
    floor_quad(m,-7,-28,7,18,9.065,'carpet',0.30)
    floor_quad(m,-41,-29,-21,-12,9.045,'hearth',0.22)       # armory / guard room
    floor_quad(m,-41,-12,-21,4,9.045,'walnut',0.24)        # library / archive
    floor_quad(m,-41,4,-21,20,9.045,'chapel_tile',0.25)    # chapel
    floor_quad(m,-40.8,4.2,-40.1,19.8,9.055,'chapel_border',0.35)
    floor_quad(m,-21.9,4.2,-21.2,19.8,9.055,'chapel_border',0.35)
    floor_quad(m,-41,20,-21,34,9.045,'damask',0.20)        # west solar
    floor_quad(m,21,-29,41,-12,9.045,'walnut',0.24)        # banquet hall
    floor_quad(m,21,-12,41,4,9.045,'mosaic',0.20)          # council chamber
    floor_quad(m,21,4,41,20,9.045,'black_marble',0.20)     # treasury
    floor_quad(m,21,20,41,34,9.045,'walnut',0.24)          # royal bedchamber
    floor_quad(m,-15,20,15,34,9.045,'black_marble',0.20)   # throne room

    # Wall plan. Four side-room bays per wing open onto continuous covered corridors.
    for x in (-17,17):
        doors=[(c-2.1,c+2.1,9,19.5) for c in (-20,-4,12)]
        panel_x(m,boxes,x,-29,20,9,29,doors,1.0,'stone')
    for x in (-21,21):
        doors=[(c-2.2,c+2.2,9,19.5) for c in (-20,-4,12,26)]
        panel_x(m,boxes,x,-29,34,9,29,doors,1.0,'stone')
    for y in (-12,4):
        panel_y(m,boxes,y,-41,-21,9,27,[(-33,-29,9,19.5)],1.0,'stone')
        panel_y(m,boxes,y,21,41,9,27,[(29,33,9,19.5)],1.0,'stone')
    # Rear doors connect the Great Hall, throne room and two private suites.
    panel_y(m,boxes,20,-17,17,9,30,[(-5.4,5.4,9,21)],1.2,'tracery')
    panel_y(m,boxes,20,-41,-21,9,29,[(-33,-29,9,19.5)],1.0,'stone')
    panel_y(m,boxes,20,21,41,9,29,[(29,33,9,19.5)],1.0,'stone')
    for x in (-17,17):
        panel_x(m,boxes,x,20,34,9,29,[(24,28,9,19.5)],1.0,'stone')
    # Interior stairwell/service alcoves separate the rear suite from the outer walls.
    panel_x(m,boxes,-39.5,20,33,9,27,[(24,28,9,18)],0.7,'oak_panel')
    panel_x(m,boxes,39.5,20,33,9,27,[(24,28,9,18)],0.7,'oak_panel')

    # Foyer panelling, repeated carved ribs and a high vaulted Great Hall ceiling.
    for y in (-22,-10,2,14):
        for x in (-15.0,15.0):
            cylinder(m,x,y,9,24.5,0.7,'marble',14,0.62)
            ring(m,x,y,9.6,10.1,0.95,0.86,'trim',12)
        add_arch_ring(m,0,y,24.0,14.0,1.05,1.15,mat(m,'tracery'),18)
        add_arch_ring(m,0,y,24.0,13.55,0.28,1.2,mat(m,'gold'),18)
    # A single painted celestial ceiling panel belongs only to the tall throne suite.
    ceiling=(( -13,22,52),(-13,32,52),(13,32,52),(13,22,52))
    mi=mat(m,'fresco'); m.quad(ceiling,mi,(1.0,1.0)); m.quad(tuple(reversed(ceiling)),mi,(1.0,1.0))
    # Framed landscape mural in the west solar.
    two_sided_panel_x(m,-40.2,22.5,31.5,18.0,24.8,'wall_fresco',(1.0,1.0))
    two_sided_panel_x(m,42.18,22.5,31.5,13.0,24.0,'emerald',(1.0,1.0))

    # Room-specific set dressing: bookcases, armory racks, chapel pews, tables, chest and bed.
    # Armory: ordered wall racks with repeated iron uprights and a narrow central aisle.
    for y in (-25,-16):
        box(m,-40.1,y-0.28,10.0,-39.4,y+0.28,22.0,'iron')
        for z in (12,16,20): box(m,-39.3,y-4.0,z,-38.9,y+4.0,z+0.22,'wood')
    # Library: continuous shelves face the corridor; dark oak case with actual book-spine texture.
    for y in (-9.0,1.0):
        box(m,-40.3,y-0.48,9.2,-39.0,y+0.48,24.5,'oak_panel')
        box(m,-38.92,y-0.42,12.0,-38.80,y+0.42,23.8,'books')
        for z in (11.8,16.0,20.0,24.0): box(m,-39.0,y-0.5,z,-38.65,y+0.5,z+0.28,'trim')
        boxes.append(((-40.3,y-0.48,9.2),(-39.0,y+0.48,24.5),0))
    # Chapel: altar, six low choir benches, and a rose window facing the nave.
    box(m,-39.0,15.4,9.05,-33.5,18.0,10.8,'marble')
    box(m,-38.7,15.6,10.8,-33.8,17.8,11.2,'trim')
    boxes.append(((-39.0,15.4,9.05),(-33.5,18.0,10.8),0))
    for y in (6.2,8.5,10.8,13.1):
        box(m,-37.5,y,9.05,-24.0,y+0.65,10.0,'wood')
        box(m,-37.5,y-0.08,10.0,-24.0,y+0.73,10.22,'trim')
    two_sided_panel_x(m,-42.16,7.0,17.0,17.0,26.0,'rose_glass',(1.0,1.0))
    # Banquet room: paired tables and benches leave the entrance corridor clear.
    for y in (-25.5,-20.5,-15.5):
        box(m,24.0,y,9.15,38.0,y+1.35,10.25,'wood')
        for x in (25.0,36.7):
            box(m,x,y+0.1,9.05,x+0.55,y+1.15,9.25,'trim')
        box(m,24.5,y-0.75,9.05,37.5,y-0.2,9.65,'oak_panel')
        box(m,24.5,y+1.55,9.05,37.5,y+2.1,9.65,'oak_panel')
        boxes.append(((24.0,y,9.15),(38.0,y+1.35,10.25),0))
    # Council table and a parchment chart inset; no fake lettering.
    box(m,24.0,-6.2,9.15,38.0,-2.3,10.0,'oak_panel')
    floor_quad(m,28.0,-5.7,34.0,-2.8,10.02,'parchment',0.15)
    for x in (25.0,36.2):
        box(m,x,-1.3,9.05,x+1.0,0.2,10.6,'leather')
    boxes.append(((24.0,-6.2,9.15),(38.0,-2.3,10.0),0))
    # Treasury plinths, each set back from the door.
    for x in (24.5,32.0,37.0):
        box(m,x,8.0,9.05,x+1.6,15.0,10.0,'black_marble')
        box(m,x+0.12,8.15,10.0,x+1.48,14.85,12.8,'gold')
    # Royal bedchamber furniture; fabrics and carved wood use distinct AI albedos.
    box(m,27.0,25.0,9.1,37.5,31.5,10.0,'wood')
    box(m,27.3,25.3,10.0,37.2,31.2,11.0,'velvet')
    box(m,27.2,30.5,11.0,37.3,31.4,14.0,'curtain')
    box(m,25.5,23.8,9.05,39.0,24.5,9.7,'trim')
    boxes.append(((27.0,25.0,9.1),(37.5,31.5,10.0),0))
    # Throne room: a raised two-step dais, single throne, red runner and blue-gold wall hangings.
    box(m,-7.5,27.0,9.05,7.5,33.0,9.65,'marble')
    box(m,-6.5,28.0,9.65,6.5,32.7,10.25,'trim')
    box(m,-2.4,30.4,10.25,2.4,32.0,12.2,'velvet')
    box(m,-3.0,31.75,12.0,3.0,32.4,17.0,'brocade')
    for x in (-3.2,3.2):
        cylinder(m,x,31.8,12.0,16.8,0.28,'gold',10,0.18)
    floor_quad(m,-3.2,20.2,3.2,32.5,9.08,'carpet',0.45)
    two_sided_panel_y(m,-10.5,10.5,19.38,22.0,31.0,'crest',(1.0,1.0))
    boxes.append(((-7.5,27.0,9.05),(7.5,33.0,9.65),0))

    # North keep windows, facade pilasters and gilded parapet details.
    for x in (-24,-12,0,12,24):
        box(m,x-0.25,11.0,34,x+0.25,11.5,56,'tracery')
        box(m,x-0.18,33.3,34,x+0.18,33.8,56,'trim')
    for z in (35.0,43.0,55.5):
        box(m,-27,11.0,z,27,13.0,z+0.42,'trim')
        box(m,-27,33.0,z,27,35.0,z+0.42,'trim')

    return m,boxes,None


def _wing(lod=False):
    m=Mesh(); boxes=[]
    if lod:
        box(m,-19,-14,0,19,14,3,'aged')
        box(m,-18,-13,3,18,13,27,'stone')
        add_gable_roof(m,0,0,27,39,29,11,mat(m,'slate'),DENSITY['slate'])
        cylinder(m,-14,0,3,28,3.0,'stone',8,2.3)
        cylinder(m,-14,0,27,42,3.5,'slate',8,0.1)
        return m,[],None
    box(m,-19,-14,0,19,14,3,'aged')
    box(m,-18,-13,2.7,18,13,3.0,'marble')
    boxes.append(((-18,-13,2.7),(18,13,3.0),0))
    # Open south entry and four true window apertures, with textured glass kept out of the walk path.
    panel_y(m,boxes,-13,-18,18,3,25,[(-3.6,3.6,3,17.5),(-14,-11,9,17),(11,14,9,17)],1.2,'stone')
    panel_y(m,boxes,13,-18,18,3,25,[(-3.0,3.0,8,17)],1.2,'stone')
    panel_x(m,boxes,-18,-13,13,3,25,[(-9,-6,9,17),(6,9,9,17)],1.2,'stone')
    panel_x(m,boxes,18,-13,13,3,25,[(-9,-6,9,17),(6,9,9,17)],1.2,'stone')
    two_sided_panel_y(m,-13.8,-11.2,-13.04,9.1,16.9,'stained',(0.4,0.8))
    two_sided_panel_y(m,11.2,13.8,-13.04,9.1,16.9,'stained',(0.4,0.8))
    two_sided_panel_x(m,-17.38,-8.8,-6.2,9.2,16.8,'iron_grille',(0.4,0.8))
    two_sided_panel_x(m,17.38,6.2,8.8,9.2,16.8,'iron_grille',(0.4,0.8))
    for x in (-15.5,-7.5,7.5,15.5):
        cylinder(m,x,-13.7,3,22,0.55,'marble',12,0.45)
        ring(m,x,-13.7,3.5,4.0,0.78,0.70,'trim',10)
    # An intimate room with oak panelling, a continuous carpet runner and a painted ceiling panel.
    floor_quad(m,-16,-11,16,11,3.02,'walnut',0.25)
    floor_quad(m,-3,-12,3,12,3.05,'carpet',0.4)
    for side in (-1,1):
        box(m,side*17.25-0.12,-10,5,side*17.25+0.12,10,20,'oak_panel')
    ceiling=(( -10,-8,24.8),(-10,8,24.8),(10,8,24.8),(10,-8,24.8))
    mi=mat(m,'fresco'); m.quad(ceiling,mi,(1.0,1.0)); m.quad(tuple(reversed(ceiling)),mi,(1.0,1.0))
    # A clear path from the entrance; decorative side furnishings do not seal the doorway.
    box(m,-10.5,5.0,3.1,10.5,6.0,5.5,'wood')
    boxes.append(((-10.5,5.0,3.1),(10.5,6.0,5.5),0))
    add_gable_roof(m,0,0,25,37,27,12,mat(m,'slate'),DENSITY['slate'])
    cylinder(m,-14,0,3,28,3.0,'stone',16,2.3)
    cylinder(m,-14,0,27,42,3.5,'slate',16,0.1)
    return m,boxes,None


def _gate(lod=False):
    m=Mesh()
    # Gatehouse shoulders and arch leave a real walkable central portal.
    box(m,-22,-8,0,-5.6,8,26,'aged')
    box(m,5.6,-8,0,22,8,26,'aged')
    box(m,-22.5,-8.5,0,-5.2,8.5,2.6,'marble')
    box(m,5.2,-8.5,0,22.5,8.5,2.6,'marble')
    box(m,-22,-8,24,-5.6,8,27,'stone')
    box(m,5.6,-8,24,22,8,27,'stone')
    # Arch voussoirs face the approach (south).
    add_arch_ring(m,0,-0.2,11.7,5.3,1.75,15.5,mat(m,'stone'),18 if not lod else 10)
    # Parapet spans above portal; crenellations silhouette the roof.
    box(m,-22,-8.2,26,22,8.2,28,'marble')
    box(m,-22,-8.2,28,22,8.2,29.2,'gold')
    if not lod:
        for x in (-17,-12,12,17):
            box(m,x-0.45,-8.4,4,x+0.45,-8.1,23,'gold')
        # Paired octagonal gate towers with blue pointed roofs.
        for x in (-15.2,15.2):
            cylinder(m,x,0,0,22,7.7,'stone',20,6.0)
            ring(m,x,0,21,23,8.1,7.8,'gold',20)
            cylinder(m,x,0,22.5,44,7.3,'slate',20,0.15)
            cylinder(m,x,0,43,47,0.65,'gold',8,0.05)
            box(m,x-8.1,-4,7,x-7.7,4,14,'window')
    else:
        for x in (-15.2,15.2):
            cylinder(m,x,0,0,22,7.7,'stone',10,6.0)
            cylinder(m,x,0,22,43,7.3,'slate',10,0.2)
    # Portcullis is raised above head-height: a visible gate detail without blocking traversal.
    if not lod:
        for x in (-4.0,-2.7,-1.35,0,1.35,2.7,4.0):
            box(m,x-0.10,-7.65,12.5,x+0.10,-7.35,20.5,'gold')
        box(m,-4.2,-7.65,19.5,4.2,-7.35,19.8,'copper')
    boxes=[((-22,-8,0),(-6,8,27),0),((6,-8,0),(22,8,27),0)]
    if not lod:
        boxes.extend([((x-7.7,-7.7,0),(x+7.7,7.7,22),0) for x in (-15.2,15.2)])
    return m,boxes,None


def _bridge(lod=False):
    m=Mesh(); boxes=[]
    # 72 m processional bridge: gently rising deck from coastal approach to the outer gate.
    width=15.0; y0,y1=-36.0,36.0; z0,z1=2.0,39.5
    if lod:
        for x0,x1 in ((-width/2,width/2),): box(m,x0,y0,0,x1,y1,z1+2,'stone')
    else:
        # Deck split into dressed cobble panels and side cornices.
        ys=[y0,y0+12,y0+24,y0+36,y0+48,y0+60,y1]
        for a,b in zip(ys,ys[1:]):
            za=z0+(z1-z0)*(a-y0)/(y1-y0); zb=z0+(z1-z0)*(b-y0)/(y1-y0)
            m.quad(((-7.5,a,za),(7.5,a,za),(7.5,b,zb),(-7.5,b,zb)),mat(m,'cobble'),((b-a)/8,2.0))
            # Under-deck stone slab, aligned to the local ramp.
            box(m,-8.3,a,za-1.5,8.3,b,zb,'aged')
        # Decorative parapets follow the incline; repeated balusters and gilded coping.
        for side in (-1,1):
            x=side*8.0
            for k in range(13):
                y=y0+k*6.0
                z=z0+(z1-z0)*(y-y0)/(y1-y0)
                box(m,x-0.55,y,z,x+0.55,y+0.8,z+4.0,'stone')
                box(m,x-0.72,y-0.1,z+3.7,x+0.72,y+0.9,z+4.2,'marble')
                box(m,x-0.10,y+0.2,z+1.0,x+0.10,y+0.5,z+3.4,'gold')
            # Long handrail/coping rail; slanted quad.
            m.quad(((x-0.7,y0,z0+4.0),(x+0.7,y0,z0+4.0),(x+0.7,y1,z1+4.0),(x-0.7,y1,z1+4.0)),mat(m,'marble'),(9,0.5))
        # Three monumental supporting piers below the rising archway.
        for y in (-17,0,17):
            z=z0+(z1-z0)*(y-y0)/(y1-y0)
            box(m,-3.5,y-2,-2,3.5,y+2,z-1.2,'aged')
            ring(m,0,y-2,z-1.4,z-0.4,4.2,3.7,'marble',16)
        box(m,-8.5,y0,z0-1.8,8.5,y1,z1-0.2,'stone')
    # Sloped collision deck as a real two-triangle mesh; unlike a bounding box this
    # preserves the incline and leaves the arch/support bays open.
    verts=[(-7.5,y0,z0),(7.5,y0,z0),(7.5,y1,z1),(-7.5,y1,z1)]
    faces=[(0,1,2,0,0),(0,2,3,0,0)]
    return m,boxes,(verts,faces)


def _stair(lod=False):
    m=Mesh(); boxes=[]
    width=18.0; run=54.0; rise=18.0; count=60
    if lod:
        box(m,-width/2,-run/2,0,width/2,run/2,rise,'marble')
        box(m,-width/2-1.4,-run/2,0,-width/2,run/2,rise+2.5,'stone')
        box(m,width/2,-run/2,0,width/2+1.4,run/2,rise+2.5,'stone')
    else:
        depth=run/count; height=rise/count
        for i in range(count):
            y=-run/2+i*depth; z=i*height
            box(m,-width/2,y,z,width/2,y+depth+0.01,z+height,'marble')
            if i%5==0:
                box(m,-width/2-0.12,y,z-0.05,width/2+0.12,y+0.10,z+0.06,'trim')
            boxes.append(((-width/2,y,z),(width/2,y+depth,z+height),0))
        for side in (-1,1):
            x=side*(width/2+0.9)
            box(m,x-0.7,-run/2,0,x+0.7,run/2,rise+2.5,'stone')
            box(m,x-0.9,-run/2,rise+2.2,x+0.9,run/2,rise+2.6,'trim')
            boxes.append(((x-0.7,-run/2,0),(x+0.7,run/2,rise+2.5),0))
    return m,boxes,None


def _fountain(lod=False):
    m=Mesh(); seg=12 if lod else 28
    cylinder(m,0,0,0,1.3,8.3,'marble',seg,8.3)
    ring(m,0,0,1.15,2.3,8.5,7.7,'gold',seg)
    cylinder(m,0,0,2.2,3.1,7.0,'aged',seg,6.4)
    # Raised inner bowl with a visible dark-blue water basin.
    ring(m,0,0,3.0,4.6,6.6,5.6,'marble',seg)
    cylinder(m,0,0,4.45,4.6,5.45,'moat_water',seg,5.45)
    cylinder(m,0,0,4.5,6.8,1.2,'stone',16,0.8)
    ring(m,0,0,6.6,7.3,1.8,1.4,'gold',16)
    cylinder(m,0,0,7.2,8.0,0.8,'marble',12,0.65)
    cylinder(m,0,0,7.9,10.3,0.36,'gold',10,0.08)
    if not lod:
        for a in range(8):
            ang=2*math.pi*a/8
            x,y=6.95*math.cos(ang),6.95*math.sin(ang)
            cylinder(m,x,y,2.0,3.0,0.42,'gold',8,0.25)
            # low ornamental jets (static, deliberately not expensive particle systems)
            cylinder(m,x*0.74,y*0.74,4.6,5.4,0.12,'water',6,0.04)
    return m,[((-8.5,-8.5,0),(8.5,8.5,2.3),0)],None


def _statue(lod=False):
    m=Mesh()
    box(m,-4,-4,0,4,4,1.4,'marble')
    box(m,-3.4,-3.4,1.4,3.4,3.4,5.0,'aged')
    box(m,-3.8,-3.8,4.8,3.8,3.8,5.8,'gold')
    cylinder(m,0,0,5.8,9.0,1.8,'gold',12,1.5)
    # Abstract heraldic eagle / royal sunburst, made from sculptural bronze planes.
    cylinder(m,0,0,8.0,12.3,1.45,'gold',12,0.9)
    cylinder(m,0,-0.1,11.5,13.4,0.75,'copper',10,0.20)
    if not lod:
        for side in (-1,1):
            # Swept wings fan upward, each feather a separate sculpted tapered prism.
            for i in range(5):
                x=side*(1.2+i*0.65)
                z=10.2+i*0.42
                box(m,min(x,x+side*1.0)-0.45,-0.55,z,max(x,x+side*1.0)+0.45,0.55,z+1.0,'gold')
        cylinder(m,0,0,13.0,14.5,0.22,'gold',8,0.02)
    return m,[((-3.5,-3.5,0),(3.5,3.5,5.8),0)],None


def _pavilion(lod=False):
    m=Mesh(); n=8 if lod else 12
    cylinder(m,0,0,0,1.8,9.0,'marble',n,9.0)
    cylinder(m,0,0,1.8,3.0,7.5,'gold',n,7.0)
    if not lod:
        for i in range(8):
            a=2*math.pi*i/8; x,y=6.3*math.cos(a),6.3*math.sin(a)
            cylinder(m,x,y,3.0,14.0,0.75,'marble',12,0.68)
            ring(m,x,y,3.0,3.8,1.05,0.9,'gold',10)
            ring(m,x,y,13.2,14.3,1.0,0.72,'gold',10)
    else:
        cylinder(m,0,0,3,13.5,6.6,'stone',n,6.2)
    cylinder(m,0,0,13.8,15.0,9.0,'marble',n,8.7)
    dome(m,0,0,15.0,8.7,11.0,'slate',n,5 if not lod else 3)
    return m,[((-8,-8,0),(8,8,4),0)],None


def _rock(lod=False):
    m=Mesh(); sides=8 if lod else 11
    rings=[]
    for z,r,offset in ((0,7.0,0.0),(3,8.8,0.35),(10,6.7,0.0),(16,3.8,-0.2),(19,0.7,0.1)):
        ringpts=[]
        for i in range(sides):
            a=2*math.pi*i/sides+offset
            variation=1.0+0.12*math.sin(i*4.17+z)
            ringpts.append((r*variation*math.cos(a),r*variation*math.sin(a),z+0.45*math.sin(i*3.13)))
        rings.append(ringpts)
    rockmat=mat(m,'cliff')
    def outward_tri(a,b,c):
        ux,uy,uz=b[0]-a[0],b[1]-a[1],b[2]-a[2]
        vx,vy,vz=c[0]-a[0],c[1]-a[1],c[2]-a[2]
        nx,ny=uy*vz-uz*vy,uz*vx-ux*vz
        cx,cy=(a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3
        if nx*cx+ny*cy<0: b,c=c,b
        m.triangle(a,b,c,rockmat)
    for k in range(len(rings)-1):
        low,high=rings[k],rings[k+1]
        for i in range(sides):
            j=(i+1)%sides
            outward_tri(low[i],low[j],high[j])
            outward_tri(low[i],high[j],high[i])
    for i in range(sides): m.triangle((0,0,0),rings[0][(i+1)%sides],rings[0][i],mat(m,'cliff'))
    return m,[((-8.5,-8.5,0),(8.5,8.5,18),0)],None


def _pine(lod=False):
    m=Mesh(); seg=8 if lod else 12
    cylinder(m,0,0,0,12,0.8,'bark',seg,0.35)
    layers=((4.5,6.0,12),(8.0,4.9,17),(11.7,3.8,22),(15.2,2.7,27))
    if lod: layers=((5,6.2,17),(11,4.2,23),(17,2.5,29))
    for z0,r,z1 in layers:
        cylinder(m,0,0,z0,z1,r,'green' if lod else 'deepgreen',seg,0.12)
        if not lod:
            ring(m,0,0,z0,z0+0.7,r*1.02,r*0.94,'aged',seg)
    boxes=[((-0.7,-0.7,0),(0.7,0.7,11),0)]
    return m,boxes,None


def _hedge(lod=False):
    m=Mesh()
    box(m,-5,-1.4,0,5,1.4,2.8,'deepgreen')
    if not lod:
        box(m,-4.8,-1.5,2.4,4.8,1.5,3.2,'green')
        for x in range(-4,5,2):
            cylinder(m,x,0,2.2,3.5,0.38,'aged',8,0.22)
    return m,[],None


def _banner(lod=False):
    m=Mesh()
    cylinder(m,0,0,0,12,0.20,'gold',8,0.10)
    cylinder(m,0,0,10.5,11.0,2.2,'copper',8,2.2)
    if lod:
        box(m,0.2,-0.12,6.0,4.8,0.12,10.5,'crest')
    else:
        front=((0.22,-0.045,10.55),(4.82,-0.045,10.38),(4.65,-0.045,6.0),(0.22,-0.045,6.0))
        back=((4.82,0.045,10.38),(0.22,0.045,10.55),(0.22,0.045,6.0),(4.65,0.045,6.0))
        m.quad(front,mat(m,'crest'),(1.0,1.0))
        m.quad(back,mat(m,'crest'),(1.0,1.0))
        for x in (0.35,1.4,2.4,3.4,4.55):
            cylinder(m,x,0,6.0,10.7,0.055,'gold',6,0.04)
        cylinder(m,0,0,11.8,13.1,0.45,'gold',8,0.02)
    return m,[],None


def _plaza(lod=False):
    m=Mesh()
    box(m,-16,-16,-0.7,16,16,0,'aged')
    box(m,-15.4,-15.4,0,15.4,15.4,0.35,'cobble')
    if not lod:
        # Symmetric paving frame around four precisely placed lawn panels.
        for x in (-10.6,10.6):
            for y in (-10.6,10.6):
                floor_quad(m,x-3.3,y-3.3,x+3.3,y+3.3,0.365,'grass',0.35)
                box(m,x-3.55,y-3.55,0.36,x+3.55,y+3.55,0.48,'trim')
                floor_quad(m,x-3.3,y-3.3,x+3.3,y+3.3,0.49,'grass',0.35)
        # Central axis and compass rose remain clear and walkable.
        for x in (-12,12):
            for y in (-12,12):
                box(m,x-1.2,y-1.2,0.50,x+1.2,y+1.2,0.62,'gold')
                box(m,x-0.8,y-0.8,0.63,x+0.8,y+0.8,0.68,'marble')
        box(m,-0.3,-8,0.36,0.3,8,0.48,'marble')
        box(m,-8,-0.3,0.36,8,0.3,0.48,'marble')
        cylinder(m,0,0,0.36,0.55,2.0,'gold',8,1.2)
    return m,[((-16,-16,-0.8),(16,16,0.35),0)],None


def _waterfall(lod=False):
    m=Mesh(); c=mat(m,'foam' if not lod else 'water')
    # Faceted ribbons of pale water caught against the cliff, built as thin double-sided panels.
    for i in range(7 if not lod else 3):
        x=-6+i*(12/(6 if not lod else 2))
        width=0.62 if not lod else 1.3
        pts=((x-width,0,0),(x+width,0,0),(x+width*0.68,0,32),(x-width*0.72,0,32))
        m.quad(pts,c,(1.0,3.0))
        m.quad(tuple(reversed(pts)),c,(1.0,3.0))
    # A few white streaks keep the fall legible at medium range.
    if not lod:
        for x in (-3.7,0.4,3.1):
            pts=((x-0.12,-0.04,3),(x+0.12,-0.04,3),(x+0.10,-0.04,29),(x-0.10,-0.04,29))
            m.quad(pts,mat(m,'marble'),(0.2,3.0))
    return m,[],None


def _moat(lod=False):
    m=Mesh(); water=mat(m,'moat_water')
    # Four still-water reaches follow the inner fortification, leaving gates open.
    spans=[((-111,-104,0),(111,-95,0)),((-111,95,0),(111,104,0)),((-128,-95,0),(-119,95,0)),((119,-95,0),(128,95,0))]
    for (x0,y0,_),(x1,y1,_) in spans:
        m.quad(((x0,y0,0),(x1,y0,0),(x1,y1,0),(x0,y1,0)),water,((x1-x0)/12,(y1-y0)/12))
    return m,[],None


def _mountain(lod=False):
    m=Mesh()
    # Layered, angular alpine ridge.  Fan triangulation gives a readable skyline while
    # reusing the generated gneiss photograph as a true repeating material.
    front=-35.0; back=38.0
    peaks=[(-118,0),(-90,38),(-62,16),(-35,62),(-6,26),(22,84),(50,36),(82,72),(112,8)]
    if lod: peaks=[(-118,0),(-80,28),(-35,52),(15,74),(58,42),(105,4)]
    crest=[(x,front+((i%2)*4),z) for i,(x,z) in enumerate(peaks)]
    colverts=[]; colfaces=[]
    # Front/rear mountain faces are exported both visually and as a simplified COL3 shell.
    for i in range(len(crest)-1):
        a=crest[i]; b=crest[i+1]
        x0=-125+250*i/(len(crest)-1); x1=-125+250*(i+1)/(len(crest)-1)
        f0=(x0,front,0); f1=(x1,front,0); r0=(x0,back,0); r1=(x1,back,0)
        ar=(a[0],back,a[2]*0.72); br=(b[0],back,b[2]*0.72)
        m.triangle(f0,f1,b,mat(m,'cliff')); m.triangle(f0,b,a,mat(m,'cliff'))
        m.triangle(r0,ar,br,mat(m,'cliff')); m.triangle(r0,br,r1,mat(m,'cliff'))
        m.triangle(a,b,br,mat(m,'cliff')); m.triangle(a,br,ar,mat(m,'cliff'))
        base=len(colverts)
        colverts.extend((f0,f1,a,b,r0,r1,ar,br))
        colfaces.extend(((base,base+1,base+3,0,0),(base,base+3,base+2,0,0),
                         (base+4,base+6,base+7,0,0),(base+4,base+7,base+5,0,0),
                         (base+2,base+3,base+7,0,0),(base+2,base+7,base+6,0,0)))
    if not lod:
        # Snowless, moss-dark ledges provide tonal depth without an extra generated bitmap.
        for i in range(1,len(crest)-1,2):
            x,z=peaks[i]
            box(m,x-5,front-0.2,z*0.42,x+5,front+0.4,z*0.42+1.1,'aged')
    return m,[],(colverts,colfaces)


def _lamp(lod=False):
    m=Mesh()
    box(m,-1.0,-1.0,0,1.0,1.0,0.7,'marble')
    cylinder(m,0,0,0.7,7.4,0.28,'copper',10,0.18)
    ring(m,0,0,7.2,7.6,0.55,0.45,'gold',10)
    if not lod:
        # Four glazed lantern panes and peaked cap.
        box(m,-0.72,-0.72,7.4,0.72,0.72,10.0,'gold')
        box(m,-0.48,-0.50,7.8,0.48,0.50,9.55,'glow')
        box(m,-0.95,-0.95,9.8,0.95,0.95,10.15,'copper')
        cylinder(m,0,0,10.0,11.7,0.76,'gold',8,0.08)
    else:
        box(m,-0.7,-0.7,7.4,0.7,0.7,10.3,'glow')
    return m,[((-1,-1,0),(1,1,1),0)],None


BUILDERS={
    'island':_terrain,'wall':_wall,'tower_round':_round_tower,'tower_spire':_spire_tower,
    'palace':_palace,'wing':_wing,'gate':_gate,'bridge':_bridge,'stair':_stair,
    'fountain':_fountain,'statue':_statue,'pavilion':_pavilion,'rock':_rock,'pine':_pine,
    'hedge':_hedge,'banner':_banner,'plaza':_plaza,'waterfall':_waterfall,'moat':_moat,
    'mountain':_mountain,'lamp':_lamp,
}


def build_asset(kind: str, lod=False):
    if kind not in BUILDERS: raise KeyError(kind)
    mesh,boxes,colmesh=BUILDERS[kind](lod)
    if not mesh.triangles: raise ValueError('asset builder returned empty geometry: '+kind)
    collision=bool(boxes or colmesh) and not lod
    if collision and not boxes and not colmesh:
        lo,hi=mesh.bounds(); boxes=[(lo,hi,0)]
    return mesh,boxes,colmesh,collision
