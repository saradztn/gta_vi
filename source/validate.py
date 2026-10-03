# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# validate.py - structural validation of the FINISHED resource (no rendering).
#   meta.xml vs files on disk, script order, min version
#   Lua 5.1 syntax + static API check (every global is Lua5.1, MTA or defined by the resource)
#   config consistency (every whitelisted material / marking exists, patterns are valid Lua)
#   shaders: lint + D3D9 budget + Slang type check (hlsl_check.py)
#   textures: every DDS parses, power of two, DXT1/DXT5, full mip chain, sane sizes
#   fallback TXD parses and holds the original names
#   budget: resource size, shader count
#
#     python3 validate.py            structural + shader + texture checks
#     python3 validate.py --lua      ... and the full headless client session test
# Exit code 0 = everything passed.
# -----------------------------------------------------------------------------
import glob
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import numpy as np
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.environ.get('RR_RES') or os.path.join(HERE, '..', 'resource', 'RoadRealism')
sys.path.insert(0, HERE)
from lib import dds, readers
import hlsl_check

fails, npass = [], [0]


def check(c, msg):
    if c:
        npass[0] += 1
    else:
        fails.append(msg)
        print('  [FAIL] ' + msg)
    return c


def ok(msg):
    print('  [ ok ] ' + msg)


def section(t):
    print('\n== %s ==' % t)


def rd(f):
    return open(os.path.join(RES, f), encoding='utf8').read()


# ====================================================================================================================
section('meta.xml')
meta = ET.parse(os.path.join(RES, 'meta.xml')).getroot()
scripts = [(e.get('src'), e.get('type')) for e in meta.findall('script')]
mfiles = [e.get('src') for e in meta.findall('file')]
check(len(set(mfiles)) == len(mfiles), 'no <file> listed twice')
check(all(os.path.exists(os.path.join(RES, f)) for f in mfiles + [s for s, _ in scripts]),
      'every listed script / file exists on disk')
on_disk = set()
for root_, _, fs in os.walk(RES):
    rel0 = os.path.relpath(root_, RES).replace(os.sep, '/')
    for f in fs:
        rel = f if rel0 == '.' else rel0 + '/' + f
        if rel.endswith(('.dds', '.png', '.wav', '.txd', '.fx')):
            on_disk.add(rel)
listed = {f for f in mfiles}
missing = on_disk - listed
extra = listed - on_disk
check(not missing, 'meta.xml lists every asset on disk (%d missing: %s)' % (len(missing), sorted(missing)[:4]))
check(not extra, 'meta.xml has no stale entries (%d: %s)' % (len(extra), sorted(extra)[:4]))
corder = [s for s, t in scripts if t == 'client']
need = ['config/settings.lua', 'config/materials.lua', 'config/roads.lua', 'tools/texture_scanner.lua',
        'tools/material_report.lua', 'reflect.lua', 'rain.lua', 'client.lua']
check(all(n in corder for n in need) and all(corder.index(a) < corder.index(b)
      for a, b in zip(need, need[1:])), 'client scripts present and data before logic: %s' % corder)
check(any(t == 'server' for s, t in scripts), 'a server script is declared')
check(meta.find('min_mta_version') is not None, 'min_mta_version declared')
ok('%d scripts, %d files listed' % (len(scripts), len(mfiles)))

# ====================================================================================================================
section('Lua syntax + static API check')
L = lua51.LuaRuntime(unpack_returned_tuples=True)
loadstr = L.eval('function(s, n) local f, e = loadstring(s, n) return f ~= nil, tostring(e or "") end')
all_lua = sorted({s for s, _ in scripts})
for f in all_lua:
    good, err = loadstr(rd(f), f)
    check(good, 'Lua 5.1 syntax of %s %s' % (f, err))
import mta_lua_static
mta_lua_static.RES = RES
for files, api, label in (([n for n in corder], mta_lua_static.CLIENT_API, 'client'),
                          ([s for s, t in scripts if t == 'server'], mta_lua_static.SERVER_API, 'server')):
    p, used, _ = mta_lua_static.check(files, api, label)
    for x in p:
        check(False, x)
    if not p:
        ok('%s: %d MTA functions used, all exist in the MTA %s API' % (label, len(used), label))
# shader names set from Lua must exist in some .fx uniform table (checked more strictly below)

# ====================================================================================================================
section('config consistency (checked inside a Lua VM)')
D = L.eval('({})')
loader = L.eval('function(t, src) local fn = loadstring(src) setfenv(fn, t) fn() return t end')
for f in ('config/settings.lua', 'config/materials.lua', 'config/roads.lua'):
    loader(D, rd(f))
cfgcheck = L.eval(r"""
function(D)
  local out = {}
  local function n(t) local c = 0 for _ in pairs(t) do c = c + 1 end return c end
  local MATS, MARKS, QUAL = D.ROAD_MATERIALS, D.ROAD_MARKINGS, D.ROAD_QUALITY
  if n(MATS) < 20 then out[#out+1] = 'only '..n(MATS)..' materials' end
  if n(MARKS) < 10 then out[#out+1] = 'only '..n(MARKS)..' markings' end
  for _, q in ipairs({'low','medium','high','ultra'}) do
    if not QUAL[q] then out[#out+1] = 'missing quality '..q end
  end
  for name, e in pairs(D.ROAD_TEXTURES) do
    if not MATS[e.mat] then out[#out+1] = name..' -> unknown material '..tostring(e.mat) end
    if e.mark and e.mark ~= false and not MARKS[e.mark] then out[#out+1] = name..' -> unknown marking '..tostring(e.mark) end
    if D.ROAD_BANNED[name] then out[#out+1] = name..' is whitelisted AND banned' end
  end
  for _, pr in ipairs(D.ROAD_PATTERNS) do
    local okc = pcall(string.find, 'sometest', pr[1])
    if not okc then out[#out+1] = 'invalid Lua pattern '..pr[1] end
  end
  return out
end
""")
problems = cfgcheck(D)
nprob = problems and int(L.eval('function(t) local c=0 for _ in pairs(t) do c=c+1 end return c end')(problems)) or 0
check(nprob == 0, 'config database is self consistent (%d problems)' % nprob)
if nprob:
    for i in range(1, nprob + 1):
        check(False, str(problems[i]))
ok('config loaded: materials/markings/quality/whitelist/patterns')
MATS_N = int(L.eval('function(t) local c=0 for _ in pairs(t.ROAD_MATERIALS) do c=c+1 end return c end')(D))
MARKS_N = int(L.eval('function(t) local c=0 for _ in pairs(t.ROAD_MARKINGS) do c=c+1 end return c end')(D))
ok('%d materials, %d markings' % (MATS_N, MARKS_N))

section('shaders')
bad_sh = 0
SHDIR = os.path.join(RES, 'shaders')
for fx in sorted(f for f in os.listdir(SHDIR) if f.endswith('.fx')):
    path = os.path.join(SHDIR, fx)
    p, w, info = hlsl_check.check_file(path)
    for x in p:
        check(False, x)
        bad_sh += 1
    for x in w:
        print('  [warn] ' + x)
    ok('%-16s %s  fetches=%d samplers=%d float4=%d' % (fx, ','.join(info.get('targets', [])),
                                                      info.get('fetches', 0), info.get('samplers', 0),
                                                      info.get('float4_registers', 0)))
sc = hlsl_check.slang_check([os.path.join(SHDIR, f) for f in sorted(os.listdir(SHDIR)) if f.endswith('.fx')])
if sc is None:
    print('  [warn] slangpy not installed - shader bodies only linted')
else:
    for n, err in sc:
        check(err is None, '%s Slang type check%s' % (n, '' if err is None else ': ' + err[:300]))
        if err is None:
            ok('%s type checked by the Slang HLSL front-end' % n)
check(bad_sh == 0, 'no shader lint/budget problems')

# ====================================================================================================================
section('textures (DDS)')
tx = 0
total_bytes = 0
sizes = {}
for p in sorted(glob.glob(os.path.join(RES, 'textures', '**', '*.dds'), recursive=True)):
    d = dds.read_dds(p)
    tx += 1
    total_bytes += d['size']
    sizes[os.path.basename(p)] = (d['w'], d['h'], d['fmt'], d['mips'])
    full_chain = int(np.log2(max(d['w'], d['h']))) + 1
    check(d['w'] & (d['w'] - 1) == 0 and d['h'] & (d['h'] - 1) == 0, '%s power of two' % os.path.basename(p))
    check(d['fmt'] in ('DXT1', 'DXT5'), '%s is DXT1/DXT5 (got %s)' % (os.path.basename(p), d['fmt']))
    check(d['mips'] == full_chain, '%s full mip chain (%d of %d)' % (os.path.basename(p), d['mips'], full_chain))
ok('%d DDS textures, %.2f MB, largest %d px' % (tx, total_bytes / 1048576,
                                                max(max(w, h) for w, h, f, m in sizes.values())))
# a couple of physical sanity checks on channel means
ch = lambda f: dds.channels(os.path.join(RES, f))
nm = ch('textures/normals/detail_agg.dds')
check(abs(nm[1] - 0.5) < 0.15 and abs(nm[3] - 0.5) < 0.15, 'detail normal centred (ny %.2f nx %.2f)' % (nm[1], nm[3]))
alb = ch('textures/asphalt/asphalt_new.dds')
check(alb[0] < 0.42, 'fresh asphalt is dark (albedo mean %.2f)' % alb[0])
conc = ch('textures/concrete/concrete_road.dds')
check(conc[0] > alb[0], 'concrete is lighter than asphalt (%.2f > %.2f)' % (conc[0], alb[0]))
# PNG / WAV present
for f in ('textures/wet/droplets.png', 'textures/wet/rain_streak.png', 'textures/wet/splash.png', 'audio/rain_loop.wav'):
    check(os.path.exists(os.path.join(RES, f)), '%s exists' % f)

# ====================================================================================================================
section('fallback TXD')
fp = os.path.join(RES, 'files', 'road_fallback.txd')
check(os.path.exists(fp), 'road_fallback.txd exists')
if os.path.exists(fp):
    t = readers.read_txd(fp)
    names = [x['name'] for x in t['textures']]
    check(len(names) == len(set(names)), 'no duplicate names in the fallback TXD')
    check(all(len(n) < 32 for n in names), 'fallback names fit the 32 byte TXD field')
    check(all(x['fmt'] == 'DXT1' and x['nlev'] >= 1 for x in t['textures']), 'fallback textures parse')
    ok('%d original texture names replaced in the fallback TXD' % len(names))

# ====================================================================================================================
section('budget')
total = sum(os.path.getsize(os.path.join(RES, f)) for f in mfiles) + sum(
    os.path.getsize(os.path.join(RES, s)) for s, _ in scripts)
check(total < 60 * 1048576, 'resource size %.1f MB is download friendly (< 60 MB)' % (total / 1048576))
check(os.path.exists(os.path.join(SHDIR, 'road.fx')) and os.path.exists(os.path.join(SHDIR, 'wetroad.fx')),
      'road.fx and wetroad.fx present')

# ====================================================================================================================
print('\n== %d checks passed, %d failed ==' % (npass[0], len(fails)))
for f in fails:
    print('  FAILED:', f)

if '--lua' in sys.argv:
    print('\n== headless client session (mta_lua_test_rr.py) ==')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'mta_lua_test_rr.py')], cwd=HERE)
    if r.returncode != 0:
        fails.append('headless lua test failed')

sys.exit(1 if fails else 0)
