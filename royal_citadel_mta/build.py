#!/usr/bin/env python3
"""Build the standalone Royal Citadel MTA:SA 1.6+ resource.

Inputs: nine AI-generated albedo PNGs in assets/albedo/.
Outputs: modular RenderWare DFFs, DXT1 TXD, COL3 collisions, paired low-LOD DFFs,
         generated MTA model/layout Lua, meta.xml and a build report.
Python standard library only; no files from the original source.zip are imported.
"""
from __future__ import annotations
import json
import math
import os
import shutil
import sys
import time

HERE=os.path.dirname(os.path.abspath(__file__))
RESOURCE=os.path.join(HERE,'resource','RoyalCitadel')
FILES=os.path.join(RESOURCE,'files')
DFF_DIR=os.path.join(FILES,'dff')
COL_DIR=os.path.join(FILES,'col')
sys.path.insert(0,HERE)
from tools.citadel_assets import BUILDERS, build_asset, terrain_height
from tools.rw_mesh import build_dff, build_col3
from tools.texture_pipeline import prepare_txd

WORLD={'x':2403.37817,'y':3569.52466,'z':37.82248}
TEXTURE_SOURCES=[
    ('stone_new','albedo/limestone_fresh.png'),
    ('stone_old','albedo/limestone_aged_moss.png'),
    ('roof_slate','albedo/slate_roof.png'),
    ('marble_ivory','albedo/ivory_marble.png'),
    ('copper_old','albedo/aged_copper.png'),
    ('gold_bronze','albedo/gilded_bronze.png'),
    ('royal_oak','albedo/oak_wood.png'),
    ('paving','albedo/courtyard_cobble.png'),
    ('cliff_rock','albedo/cliff_gneiss.png'),
    ('royal_mosaic','albedo/royal_marble_mosaic.png'),
    ('stained_glass','albedo/stained_glass_royal.png',256,512),
    ('moat_surface','albedo/reflective_courtyard_water.png'),
    ('hall_carpet','ai_textures/batch_01/01_great_hall_crimson_carpet.png'),
    ('throne_brocade','ai_textures/batch_01/02_throne_room_blue_brocade.png'),
    ('carved_oak','ai_textures/batch_01/03_gothic_carved_oak_panel.png'),
    ('gothic_tracery','ai_textures/batch_01/04_gothic_limestone_tracery.png'),
    ('gilded_trim','ai_textures/batch_01/05_gilded_gothic_molding.png',512,256),
    ('vault_fresco','ai_textures/batch_01/06_celestial_vault_fresco.png'),
    ('library_books','ai_textures/batch_01/07_library_book_spines.png',512,256),
    ('iron_grille','ai_textures/batch_01/08_forged_gothic_iron_grille.png'),
    ('rose_window','ai_textures/batch_01/09_royal_rose_window_glass.png'),
    ('royal_crest','ai_textures/batch_01/10_royal_heraldic_embroidery.png'),
    ('walnut_parquet','ai_textures/batch_02/01_private_chamber_walnut_parquet.png'),
    ('throne_velvet','ai_textures/batch_02/02_throne_velvet_upholstery.png'),
    ('curtain_silk','ai_textures/batch_02/03_royal_curtain_silk.png'),
    ('chamber_damask','ai_textures/batch_02/04_private_chamber_damask_wallcovering.png'),
    ('chapel_tile','ai_textures/batch_02/05_royal_chapel_encaustic_tile.png'),
    ('hearth_stone','ai_textures/batch_02/06_hearth_scorched_stone_albedo.png'),
    ('black_iron','ai_textures/batch_02/07_blacksmith_wrought_iron_albedo.png'),
    ('emerald_damask','ai_textures/batch_03/01_emerald_royal_velvet_damask.png'),
    ('royal_leather','ai_textures/batch_03/02_embossed_royal_leather.png'),
    ('blank_parchment','ai_textures/batch_03/03_blank_aged_parchment.png'),
    ('wall_fresco','ai_textures/batch_03/04_wall_fresco_mountain_citadel.png'),
    ('black_onyx','ai_textures/batch_03/05_black_onyx_gold_veined_marble.png'),
    ('garden_lawn','ai_textures/batch_03/06_formal_garden_lawn.png'),
    ('ivy_stone','ai_textures/batch_03/07_ivy_limestone_wall.png'),
    ('pine_bark','ai_textures/batch_03/08_pine_bark_albedo.png'),
    ('waterfall_foam','ai_textures/batch_03/09_waterfall_foam_surface.png'),
    ('chapel_border','ai_textures/batch_03/10_chapel_mosaic_border.png',512,256),
]

ROOMS_LOCAL=[
    ('great_hall','Great Hall',0.0,-5.0,11.2,180.0),
    ('throne_room','Throne Room',0.0,22.0,11.2,180.0),
    ('armory','Armory',-31.0,-21.0,11.2,90.0),
    ('library','Royal Library',-31.0,-4.0,11.2,90.0),
    ('chapel','Royal Chapel',-31.0,17.0,11.2,90.0),
    ('west_solar','West Solar',-31.0,26.0,11.2,90.0),
    ('banquet_hall','Banquet Hall',31.0,-27.0,11.2,270.0),
    ('council','Council Chamber',31.0,1.0,11.2,270.0),
    ('treasury','Treasury',31.0,12.0,11.2,270.0),
    ('bedchamber','Royal Bedchamber',31.0,22.0,11.2,270.0),
]
PALACE_LAYOUT_ORIGIN=(0.0,13.0,62.0)

LOD_DIST={
    'island':1800,'mountain':1500,'palace':1100,'gate':850,'bridge':750,
    'tower_round':850,'tower_spire':1000,'wall':620,'wing':750,'stair':480,
    'fountain':480,'statue':450,'pavilion':600,'rock':650,'pine':650,
    'hedge':350,'banner':420,'plaza':480,'waterfall':800,'moat':800,'lamp':420,
}


def clamp(v,lo,hi): return max(lo,min(hi,v))


def placement(model,x,y,z=None,rz=0,scale=1.0,tag=''):
    if z is None: z=terrain_height(x,y)
    return dict(model=model,x=float(x),y=float(y),z=float(z),rz=float(rz),scale=float(scale),tag=tag)


def make_layout():
    objects=[]; lights=[]
    def add(model,x,y,z=None,rz=0,scale=1.0,tag=''):
        obj=placement(model,x,y,z,rz,scale,tag); objects.append(obj)
        if model=='lamp': lights.append((obj['x'],obj['y'],obj['z']+9.0,5.5,255,176,102))
        return obj

    # One continuous rugged island mesh is the ground/collision foundation.
    add('island',0,0,0,tag='mountain island / central mesa')
    add('mountain',0,190,terrain_height(0,190)-1,tag='northern alpine ridge')
    # Natural cliff shoulders and boulder fields, placed on the actual terrain contour.
    for x,y,s in [(-206,-128,1.15),(-195,-58,.92),(-210,18,1.18),(-198,95,.90),(-175,150,1.05),
                  (205,-126,1.05),(194,-52,.92),(211,28,1.2),(195,100,.88),(174,146,1.0),
                  (-142,-176,.9),(-82,-188,1.1),(76,-188,.94),(143,-169,1.15),
                  (-155,175,1.1),(92,177,.95)]:
        add('rock',x,y,terrain_height(x,y)-0.4,rz=(x*13+y*7)%360,scale=s,tag='cliff outcrop')

    # The outer bailey curtain: 28 m modular sections with gate openings left clear.
    ox,oy=152,137
    topxs=[-140+28*i for i in range(11)]
    for x in topxs: add('wall',x,oy,terrain_height(x,oy),0,tag='outer north curtain')
    for x in topxs: add('wall',x,-oy,terrain_height(x,-oy),0,tag='outer south curtain')
    sideys=[-126+28*i for i in range(10)]
    for y in sideys:
        add('wall',-ox,y,terrain_height(-ox,y),90,tag='outer west curtain')
        add('wall',ox,y,terrain_height(ox,y),90,tag='outer east curtain')
    # Southern gatehouse centered on the processional causeway; its arch stays open.
    add('gate',0,-oy,terrain_height(0,-oy),0,tag='great outer gate')
    for x in (-147,-119,-91,-63,-35,35,63,91,119,147):
        add('wall',x,-oy,terrain_height(x,-oy),0,tag='outer gate approach wall')
    # Bastion towers and tall spires anchor the perimeter silhouette.
    for x,y in [(-ox,-oy),(ox,-oy),(-ox,oy),(ox,oy),(0,oy),(-ox,0),(ox,0)]:
        add('tower_round',x,y,terrain_height(x,y),0,tag='outer bastion')
    add('tower_spire',0,-oy+3,terrain_height(0,-oy),0,tag='gate crown')
    add('tower_spire',-ox,0,terrain_height(-ox,0),0,tag='western skyline spire')
    add('tower_spire',ox,0,terrain_height(ox,0),0,tag='eastern skyline spire')

    # A 72 m rising stone causeway links the lower shoreline to the outer gate.
    add('bridge',0,-168,5,0,tag='grand arched approach bridge')

    # Inner royal ward: a second curtain protects the palace and formal gardens.
    ix,iy=106,84
    for x in (-84,-56,-28,0,28,56,84):
        add('wall',x,iy,terrain_height(x,iy),0,tag='inner royal curtain')
    for x in (-98,-70,-42,42,70,98):
        add('wall',x,-iy,terrain_height(x,-iy),0,tag='inner royal gate approach')
    for y in (-56,-28,0,28,56):
        add('wall',-ix,y,terrain_height(-ix,y),90,tag='inner royal curtain')
        add('wall',ix,y,terrain_height(ix,y),90,tag='inner royal curtain')
    add('gate',0,-iy,terrain_height(0,-iy),0,tag='inner palace gate')
    for x,y in [(-ix,-iy),(ix,-iy),(-ix,iy),(ix,iy)]:
        add('tower_spire',x,y,terrain_height(x,y),0,tag='inner ward spire')
    add('tower_round',0,iy,terrain_height(0,iy),0,tag='inner north keep tower')
    add('tower_round',-ix,0,terrain_height(-ix,0),0,tag='inner west keep tower')
    add('tower_round',ix,0,terrain_height(ix,0),0,tag='inner east keep tower')

    # Central palace - deliberately larger and taller than every other building.
    add('palace',0,13,62,0,tag='Royal Palace / dominant landmark')
    add('wing',-66,10,terrain_height(-66,10),0,tag='west palace wing')
    add('wing',66,10,terrain_height(66,10),180,tag='east palace wing')
    add('wing',-63,56,terrain_height(-63,56),0,tag='northwest royal gallery')
    add('wing',63,56,terrain_height(63,56),0,tag='northeast royal gallery')
    add('pavilion',-67,-45,terrain_height(-67,-45),0,tag='west garden pavilion')
    add('pavilion',67,-45,terrain_height(67,-45),0,tag='east garden pavilion')
    add('pavilion',0,68,terrain_height(0,68),0,tag='upper rose pavilion')

    # Processional stair and a broad mosaic court.
    add('stair',0,-111,terrain_height(0,-137),0,tag='great ceremonial staircase')
    for x in (-32,0,32): add('plaza',x,-42,61.5,0,tag='palace forecourt paving')
    for x in (-48,-16,16,48): add('plaza',x,49,61.5,0,tag='upper palace terrace')
    # Tiered fountains, heraldic statuary and restrained lighting in the royal gardens.
    for x,y,s in [(0,-43,1.0),(-42,-38,.70),(42,-38,.70),(-54,28,.62),(54,28,.62)]:
        add('fountain',x,y,62.0,0,s,'royal fountain')
    for x,y,s in [(-46,-53,1.0),(46,-53,1.0),(-78,22,.8),(78,22,.8),(0,72,.8),(-33,44,.65),(33,44,.65)]:
        add('statue',x,y,terrain_height(x,y),0,s,'gilded eagle monument')

    # Inner moat reaches, formal hedges and lamps create nested green/stone courts.
    add('moat',0,0,58.0,0,tag='still-water inner moat')
    for x in (-36,36):
        for y in (-58,-31,4,34): add('hedge',x,y,61.8,90,tag='clipped royal hedge')
    for x,y in [(-90,-68),(-58,-68),(58,-68),(90,-68),(-88,70),(88,70),
                (-136,-104),(136,-104),(-136,104),(136,104),(-80,-25),(80,-25),
                (-45,-15),(45,-15),(-45,66),(45,66),(0,-65),(0,78)]:
        add('lamp',x,y,terrain_height(x,y),0,tag='warm lantern')

    # Heraldic banners are distributed sparingly across gate towers and palace terraces.
    for x,y,z in [(-18,-135,terrain_height(-18,-135)),(18,-135,terrain_height(18,-135)),
                  (-106,-84,terrain_height(-106,-84)),(106,-84,terrain_height(106,-84)),
                  (-36,13,62),(36,13,62),(-62,54,terrain_height(-62,54)),(62,54,terrain_height(62,54)),
                  (-152,0,terrain_height(-152,0)),(152,0,terrain_height(152,0)),(0,137,terrain_height(0,137))]:
        add('banner',x,y,z,0,tag='royal standard')

    # Lower bailey and mountain-edge forest: trees, pavilions and cliff waterfalls.
    for x,y,s in [(-188,-154,.90),(-164,-179,.82),(-119,-177,1.05),(-48,-176,.86),(42,-180,1.08),(111,-178,.84),(167,-157,.92),
                  (-194,-84,.83),(-192,-8,1.02),(-193,70,.90),(-176,126,1.10),(-138,166,.88),
                  (193,-90,.92),(196,-10,1.08),(192,73,.88),(173,130,1.02),(138,165,.86),
                  (-117,174,.9),(-63,181,.8),(65,178,.96),(108,171,.85)]:
        add('pine',x,y,terrain_height(x,y),rz=(x*9-y*11)%360,scale=s,tag='mountain pine')
    # Waterfall curtains on the high cliff faces (render-only, kept away from the main route).
    for x,y,rz,z in [(-218,-15,0,0),(-218,62,0,0),(218,-54,180,0),(218,44,180,0)]:
        add('waterfall',x,y,z,rz,1.0,'cliff waterfall')
    # A small secondary bridge on the east garden terrace.
    add('bridge',129,8,terrain_height(129,8)-3,90,0.48,'east ravine bridge')

    return objects,lights


def lua_quote(s):
    return '"'+str(s).replace('\\','\\\\').replace('"','\\"')+'"'


def write_models(models):
    rows=['-- Generated by build.py; model IDs are requested safely at runtime.','RC_MODEL_DEFS = {']
    for d in models:
        col=lua_quote(d['col']) if d['collision'] else 'false'
        rows.append('  { name=%s, dff=%s, lod=%s, col=%s, collision=%s, lodDistance=%d },' %
                    (lua_quote(d['name']),lua_quote(d['dff']),lua_quote(d['lod']),col,
                     'true' if d['collision'] else 'false',d['lodDistance']))
    rows.append('}')
    open(os.path.join(RESOURCE,'models.lua'),'w',encoding='utf8').write('\n'.join(rows)+'\n')


def write_layout(objects,lights):
    rows=['-- Generated by build.py. Local coordinates are metres; origin is the island centre.']
    rows += ['RC_WORLD = { x=%.5f, y=%.5f, z=%.5f }' % (WORLD['x'],WORLD['y'],WORLD['z'])]
    rows += ['RC_START = { x=0.0, y=-49.0, z=%.2f, rz=0.0 }' % (terrain_height(0,-49)+2.2)]
    rows += ['RC_OBJECTS = {']
    for o in objects:
        rows.append('  { model=%s, x=%.2f, y=%.2f, z=%.2f, rz=%.1f, scale=%.3f, tag=%s },' %
                    (lua_quote(o['model']),o['x'],o['y'],o['z'],o['rz'],o['scale'],lua_quote(o['tag'])))
    rows.append('}')
    rows += ['RC_ROOMS = {']
    ox,oy,oz=PALACE_LAYOUT_ORIGIN
    for key,name,x,y,z,rz in ROOMS_LOCAL:
        rows.append('  { id=%s, name=%s, x=%.2f, y=%.2f, z=%.2f, rz=%.1f },' %
                    (lua_quote(key),lua_quote(name),ox+x,oy+y,oz+z,rz))
    rows.append('}')
    rows += ['RC_LIGHTS = {']
    for x,y,z,r,red,green,blue in lights:
        rows.append('  { x=%.2f, y=%.2f, z=%.2f, size=%.2f, r=%d, g=%d, b=%d },' %
                    (x,y,z,r,red,green,blue))
    rows.append('}')
    open(os.path.join(RESOURCE,'layout.lua'),'w',encoding='utf8').write('\n'.join(rows)+'\n')


def write_meta(models):
    files=['files/royal_citadel.txd','wet.fx','water.fx',
           'files/maps/wetness_mask.png','files/maps/marble_roughness.png','files/maps/water_normal.png']
    for d in models:
        files.extend((d['dff'],d['lod']))
        if d['collision']: files.append(d['col'])
    lines=['<!-- Royal Citadel | standalone MTA:SA 1.6+ resource -->','<meta>',
           '  <info author="Royal Citadel build" name="Royal Citadel" version="1.2.0" type="map"',
           '        description="Axial Gothic royal citadel with accessible palace rooms and screen-space water/rain reflections." />',
           '  <min_mta_version client="1.6.0-9.22676" />',
           '  <script src="models.lua" type="client" />',
           '  <script src="layout.lua" type="shared" />',
           '  <script src="client.lua" type="client" />',
           '  <script src="server.lua" type="server" />']
    lines += ['  <file src="%s" />'%p for p in files]
    lines.append('</meta>')
    open(os.path.join(RESOURCE,'meta.xml'),'w',encoding='utf8').write('\n'.join(lines)+'\n')


def verify_assets(models,objects,txd_bytes):
    assert len(objects)>100, 'The environment should have over one hundred modular placements.'
    assert len(models)==len(BUILDERS), 'Model manifest does not cover all builders.'
    assert len(ROOMS_LOCAL)>=10, 'The palace must expose a named multi-room interior.'
    assert os.path.isfile(os.path.join(RESOURCE,'wet.fx')) and os.path.isfile(os.path.join(RESOURCE,'water.fx'))
    assert txd_bytes[:4]==b'\x16\0\0\0', 'TXD root chunk is not a RenderWare texture dictionary.'
    for d in models:
        for rel in (d['dff'],d['lod']):
            path=os.path.join(RESOURCE,rel)
            if not os.path.isfile(path) or os.path.getsize(path)<1000: raise RuntimeError('Missing/small DFF: '+path)
        if d['collision'] and not os.path.isfile(os.path.join(RESOURCE,d['col'])):
            raise RuntimeError('Missing collision file for '+d['name'])
    for model in models:
        if model['collision'] and model['name'] in ('island','bridge'):
            col=open(os.path.join(RESOURCE,model['col']),'rb').read()
            if col[:4]!=b'COL3': raise RuntimeError('Bad COL3 signature: '+model['name'])
    return True


def main():
    t0=time.time()
    os.makedirs(DFF_DIR,exist_ok=True); os.makedirs(COL_DIR,exist_ok=True)
    os.makedirs(RESOURCE,exist_ok=True)
    # Remove only files owned by this build; never clear arbitrary files/directories.
    for directory,ext in ((DFF_DIR,'.dff'),(COL_DIR,'.col')):
        for filename in os.listdir(directory):
            path=os.path.join(directory,filename)
            if os.path.isfile(path) and filename.endswith(ext): os.remove(path)
    texture_root=os.path.join(HERE,'assets')
    txd,texture_data=prepare_txd(texture_root,TEXTURE_SOURCES,512)
    map_dir=os.path.join(FILES,'maps'); os.makedirs(map_dir,exist_ok=True)
    shader_maps={
        'wetness_mask.png':'assets/ai_textures/batch_02/09_rain_wetness_puddle_mask.png',
        'marble_roughness.png':'assets/ai_textures/batch_02/08_polished_marble_roughness_map.png',
        'water_normal.png':'assets/ai_textures/batch_02/10_courtyard_water_normal_map.png',
    }
    for dest,src in shader_maps.items(): shutil.copyfile(os.path.join(HERE,src),os.path.join(map_dir,dest))
    txd_path=os.path.join(FILES,'royal_citadel.txd')
    with open(txd_path,'wb') as f: f.write(txd)
    print('AI texture TXD: %d textures, %.2f MB' % (len(texture_data),len(txd)/1048576))
    models=[]; report=[]
    for i,name in enumerate(BUILDERS):
        mesh,boxes,colmesh,collision=build_asset(name,False)
        dff=build_dff(name,mesh)
        dff_rel='files/dff/%s.dff'%name
        with open(os.path.join(RESOURCE,dff_rel),'wb') as f: f.write(dff)
        lod_mesh,_,_,_=build_asset(name,True)
        lod_name=name+'_lod'
        lod=build_dff(lod_name,lod_mesh)
        lod_rel='files/dff/%s.dff'%lod_name
        with open(os.path.join(RESOURCE,lod_rel),'wb') as f: f.write(lod)
        col_rel='files/col/%s.col'%name
        col_size=0
        if collision:
            col=build_col3(name,boxes,colmesh[0] if colmesh else None,colmesh[1] if colmesh else None)
            with open(os.path.join(RESOURCE,col_rel),'wb') as f: f.write(col)
            col_size=len(col)
        definition=dict(name=name,dff=dff_rel,lod=lod_rel,col=col_rel,collision=collision,
                        lodDistance=LOD_DIST.get(name,550))
        models.append(definition)
        report.append(dict(name=name,vertices=len(mesh.positions),triangles=len(mesh.triangles),materials=len(mesh.materials),
                           dff_bytes=len(dff),lod_bytes=len(lod),col_bytes=col_size,collision=collision))
        print('  %-14s %6d verts %6d tris | DFF %.1f KB | LOD %.1f KB%s' %
              (name,len(mesh.positions),len(mesh.triangles),len(dff)/1024,len(lod)/1024,' + COL' if collision else ''))
    objects,lights=make_layout()
    write_models(models); write_layout(objects,lights); write_meta(models)
    verify_assets(models,objects,txd)
    report_obj={'project':'Royal Citadel for MTA:SA 1.6+','world_origin':WORLD,'models':report,
                'model_count':len(models),'placement_count':len(objects),'light_coronas':len(lights),
                'room_count':len(ROOMS_LOCAL),'interior_entry':'open 11 m portal with 30 shallow collision-tested steps',
                'reflection_system':'wet.fx + water.fx screen-source reflections with graceful fallback',
                'ai_textures':[spec[0] for spec in TEXTURE_SOURCES],'texture_count':len(TEXTURE_SOURCES),
                'texture_dimensions':'512 square, with purpose-made 512x256 and 256x512 maps',
                'build_seconds':round(time.time()-t0,2)}
    with open(os.path.join(HERE,'build-report.json'),'w',encoding='utf8') as f: json.dump(report_obj,f,indent=2)
    print('\nBuilt %d modular model types, %d placements, %d light coronas in %.1fs.' %
          (len(models),len(objects),len(lights),time.time()-t0))
    print('MTA resource: '+RESOURCE)


if __name__=='__main__': main()
