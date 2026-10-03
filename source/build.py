# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# build.py - one command build of the complete resource:      python3 build.py
#
#   materials.py / scan_db.py  ->  textures (DDS, DXT)  ->  config/*.lua  ->  meta.xml
#
# The Lua sources and the .fx shaders are hand written and live directly in the resource folder;
# this script generates everything that must stay in sync with the material database:
#
#   config/materials.lua   ROAD_MATERIALS, ROAD_MARKINGS, ROAD_QUALITY, ROAD_SHARED, ROAD_RAIN_TABLE,
#                          ROAD_SHADER_PACK, ROAD_SHADER_UNIFORMS (parsed out of the .fx files)
#   config/roads.lua       ROAD_TEXTURES, ROAD_BANNED, ROAD_PATTERNS, ROAD_PATTERN_REJECT, ROAD_TXDS,
#                          ROAD_FALLBACK_*
#   config/settings.lua    SETTINGS
#   meta.xml               every file of the resource, in the load order the scripts need
#
# Then run:  python3 validate.py            structural + shader + Lua checks
#            python3 validate.py --lua      ... and the full headless client session test
# -----------------------------------------------------------------------------
import os
import re
import sys
import time
import xml.sax.saxutils as sx

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rr import materials as MAT
from rr import pipeline
from rr import scan_db

RES = os.path.abspath(os.path.join(HERE, '..', 'resource', 'RoadRealism'))

# client scripts, in the order MTA must load them (data before logic, orchestrator last)
CLIENT_SCRIPTS = [
    'config/settings.lua',
    'config/materials.lua',
    'config/roads.lua',
    'tools/texture_scanner.lua',
    'tools/material_report.lua',
    'reflect.lua',
    'rain.lua',
    'client.lua',
]
SERVER_SCRIPTS = ['server.lua']
# files that are downloaded to the client but are not scripts
SHADERS = ['shaders/road.fx', 'shaders/wetroad.fx', 'shaders/reflection.fx', 'shaders/rain.fx', 'shaders/post.fx']

# the constant packing of the road shaders (must match the #define block of road.fx / wetroad.fx)
SHADER_PACK = {
    'gRoadA': ['wet', 'wetVar', 'puddleLevel', 'night'],
    'gRoadB': ['exposure', 'albedoLift', 'worldScale', 'detailScale'],
    'gRoadC': ['meshUVScale', 'useMeshUV', 'normalScale', 'parallax'],
    'gRoadD': ['markingRough', 'markingRetro', 'retroBoost', 'hasMarking'],
    'gRoadE': ['originalMix', 'reflectStrength', 'reflectBlur', 'reflectStretch'],
    'gRoadF': ['reflectAnglePow', 'sunSpec', 'time', 'reflTaps'],
}


# ---------------------------------------------------------------------------
def shader_uniforms(res):
    """parse the global uniform declarations out of every .fx, so the client only sets variables
    that the shader really declares (a driver optimises unused ones away)."""
    out = {}
    for rel in SHADERS:
        path = os.path.join(res, rel)
        if not os.path.exists(path):
            raise SystemExit('missing shader: %s' % path)
        src = open(path, encoding='utf8').read()
        src = re.sub(r'/\*.*?\*/', '', re.sub(r'//[^\n]*', '', src), flags=re.S)
        names = set()
        for m in re.finditer(r'^(float\d?(?:x\d)?|int|bool|texture)\s+([\w\s,]+?);', src, re.M):
            if 'sampler_state' in m.group(0):
                continue
            for n in m.group(2).split(','):
                n = n.strip()
                if n and not n.startswith('<'):
                    names.add(n)
        # engine provided uniforms are declared but never set from Lua
        names -= {'gWorldViewProjection', 'gViewProjection', 'gCameraPosition'}
        # textures bound by MTA itself
        names -= {'Tex0'}
        out[rel] = sorted(names)
    return out


def check_packing(res, uniforms):
    """the road shaders must declare every packed uniform the Lua fills, and their #define aliases
    must address each component of a pack at most once (a duplicate would silently shadow a value).
    The names the Lua puts into each component are checked against client.lua by validate.py."""
    bad = []
    for rel in ('shaders/road.fx', 'shaders/wetroad.fx'):
        src = open(os.path.join(res, rel), encoding='utf8').read()
        seen = {}
        for m in re.finditer(r'#define\s+(\w+)\s+(gRoad[A-F])\.([xyzw])', src):
            name, pack, comp = m.group(1), m.group(2), m.group(3)
            if (pack, comp) in seen:
                bad.append('%s: %s and %s both claim %s.%s' % (rel, seen[(pack, comp)], name, pack, comp))
            seen[(pack, comp)] = name
            if pack not in SHADER_PACK:
                bad.append('%s: #define %s uses the unknown pack %s' % (rel, name, pack))
        for pack, names in SHADER_PACK.items():
            if len(names) != 4:
                bad.append('%s must pack exactly 4 values' % pack)
            if pack not in uniforms[rel]:
                bad.append('%s does not declare %s' % (rel, pack))
    return bad


# ---------------------------------------------------------------------------
def emit_shader_lua(res, uniforms):
    """append the shader interface tables to config/materials.lua"""
    p = os.path.join(res, 'config', 'materials.lua')
    L = ['', '-- shader constant packing: which named value goes into which component of which',
         '-- packed float4.  Generated from source/build.py, verified against the #define block of',
         '-- every road shader, so the Lua and the HLSL can never drift apart.',
         'ROAD_SHADER_PACK = {']
    for pack in sorted(SHADER_PACK):
        L.append('    %s = { "%s", "%s", "%s", "%s" },' % ((pack,) + tuple(SHADER_PACK[pack])))
    L.append('}')
    L.append('')
    L.append('-- the uniforms each shader really declares; the client never sets anything else')
    L.append('ROAD_SHADER_UNIFORMS = {')
    for rel in sorted(uniforms):
        L.append('    ["%s"] = {' % rel)
        for n in uniforms[rel]:
            L.append('        %s = true,' % n)
        L.append('    },')
    L.append('}')
    with open(p, 'a') as f:
        f.write('\n'.join(L) + '\n')


def write_meta(res, texture_files):
    scripts = [(s, 'client') for s in CLIENT_SCRIPTS] + [(s, 'server') for s in SERVER_SCRIPTS]
    for s, _ in scripts:
        if not os.path.exists(os.path.join(res, s)):
            raise SystemExit('meta.xml: script %s does not exist' % s)
    files = list(SHADERS) + sorted(texture_files)
    mx = ['<!-- Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA resource -->',
          '<meta>',
          '    <info author="Arena.ai Agent Mode" name="RoadRealism" version="1.0.0" type="script"',
          '          description="Photorealistic road materials, wet asphalt, puddles and rain for the',
          '                       ORIGINAL San Andreas map.  No new geometry, no new roads, no changed',
          '                       collisions - only the road materials and the lighting on them.',
          '                       Commands: /roadinfo /roadquality /roadrain /roadwet /roadfx /roadrefl',
          '                       /roadexposure /roadnight /roadpuddle /roadscan /roadtextures',
          '                       /roadreport /roadapply /roadremove /roadreload /roaddebug" />',
          '    <min_mta_version client="1.6.0-9.22676" />',
          '']
    for s, t in scripts:
        mx.append('    <script src="%s" type="%s" />' % (s, t))
    mx.append('')
    for f in files:
        mx.append('    <file src="%s" />' % f)
    mx.append('</meta>')
    open(os.path.join(res, 'meta.xml'), 'w').write('\n'.join(mx) + '\n')
    return scripts, files


def collect_files(res):
    """every non-script file that has to be downloaded"""
    out = []
    for root_, dirs, files in os.walk(res):
        dirs[:] = [d for d in dirs if d not in ('.git',)]
        for f in files:
            rel = os.path.relpath(os.path.join(root_, f), res).replace(os.sep, '/')
            if rel.endswith(('.lua', '.md', '.py', '.fx')) or rel == 'meta.xml':
                continue
            out.append(rel)
    return out


def main():
    t0 = time.time()
    print('[1/4] textures, fallback TXD, audio ...')
    stats = pipeline.build(RES, quiet=True)
    print('      %d texture files, %.1f MB' % (stats['files'], stats['bytes'] / 1048576))
    print('[2/4] shader interface ...')
    uniforms = shader_uniforms(RES)
    bad = check_packing(RES, uniforms)
    if bad:
        for b in bad:
            print('      FAIL', b)
        raise SystemExit('the shader constant packing does not match the material database')
    for rel in SHADERS:
        print('      %-24s %d uniforms' % (rel, len(uniforms[rel])))
    emit_shader_lua(RES, uniforms)
    print('[3/4] meta.xml ...')
    files = collect_files(RES)
    scripts, allf = write_meta(RES, files)
    print('      %d scripts, %d files' % (len(scripts), len(allf)))
    print('[4/4] done in %.1f s' % (time.time() - t0))
    total = sum(os.path.getsize(os.path.join(RES, f)) for f in allf)
    print('resource: %s  (%.1f MB, %d files)' % (RES, total / 1048576, len(allf)))
    print('next:  python3 validate.py --lua')


if __name__ == '__main__':
    main()
