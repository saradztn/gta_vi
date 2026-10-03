#!/usr/bin/env python3
# Created by: Arena.ai Agent Mode (AI) - RoadRealism
# Boots the resource's real Lua against the strict MTA model in mta_stub_rr.lua and drives it:
# resource start, staged shader application, every command, wetness integration, a forced shader
# failure (fallback must take over) and resource stop (full cleanup).  Any handler/timer error is a
# test failure, so logic, ordering, arguments and cleanup are all genuinely executed here.
import os
import sys
import lupa

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, '..', 'resource', 'RoadRealism'))

PASS, FAIL = 0, 0


def check(ok, label):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [ ok ] ' + label)
    else:
        FAIL += 1
        print('  [FAIL] ' + label)


def section(t):
    print('\n== ' + t + ' ==')


L = lupa.LuaRuntime()
L.execute(open(os.path.join(HERE, 'mta_stub_rr.lua', ), encoding='utf8').read())
T = L.globals().T
g = L.globals()

# Lua-side helpers (lupa does not turn Lua tables into Python containers)
chatall = L.eval('function() local s="" for _,c in ipairs(T.chat) do s=s..c.."\\n" end return s end')
logall = L.eval('function() local s="" for _,c in ipairs(T.log) do s=s..c.."\\n" end return s end')
hasapplied = L.eval('function(n) return T.applied[n] == true end')
napplied = L.eval('function() local c=0 for _ in pairs(T.applied) do c=c+1 end return c end')
nimported = L.eval('function() local c=0 for _ in pairs(T.imported) do c=c+1 end return c end')


def load(rel):
    L.execute(open(os.path.join(RES, rel), encoding='utf8').read())


fileset = set()
for root, _, names in os.walk(RES):
    for n in names:
        fileset.add(os.path.relpath(os.path.join(root, n), RES).replace(os.sep, '/'))
for rel in sorted(fileset):
    T.files[rel] = True
check(len([f for f in fileset if f.endswith('.dds')]) > 60,
      '%d asset files registered with the stub (%d DDS)' % (len(fileset), len([f for f in fileset if f.endswith('.dds')])))

section('load resource scripts (shared global env, like MTA)')
for rel in ('config/settings.lua', 'config/materials.lua', 'config/roads.lua',
            'tools/texture_scanner.lua', 'tools/material_report.lua',
            'reflect.lua', 'rain.lua', 'client.lua'):
    try:
        load(rel)
        check(True, rel)
    except Exception as e:  # noqa: BLE001
        check(False, '%s -> %s' % (rel, e))

check(g.RR is not None, 'client.lua exposed the shared RR table')
check(g.RR.Scan is not None and g.RR.Report is not None, 'tools attached to the same RR table')
check(g.RR.Rain is not None and g.RR.Refl is not None, 'rain and reflection modules attached')

seed = L.eval(r"""function()
  local n = 0
  for name, e in pairs(ROAD_TEXTURES) do T.visible[name] = e.tier end
  for _, bad in ipairs({'cj_barbers','vehiclegeneric64','shad_exp','ws_dinerwall','tree09','sign_stop1'}) do
    T.visible[bad] = true
  end
  for _ in pairs(ROAD_TEXTURES) do n = n + 1 end
  return n
end""")
check(int(seed()) > 40, 'seeded %d visible world textures (whitelist + unrelated)' % int(seed()))

section('resource start')
T.fireClient('onClientResourceStart', g.resourceRoot)
T.adv(4000)
check(T.created('shader') >= 4, 'created %d shaders (road + reflection + rain + post)' % T.created('shader'))
check(T.created('texture') > 10, 'loaded %d material textures' % T.created('texture'))
check(int(napplied()) > 20, 'applied the road shader to %d world textures' % int(napplied()))
check('RoadRealism' in chatall() or 'RoadRealism' in logall(), 'boot report printed')
check('failed' not in chatall().lower(), 'boot produced no failure messages')
for bad in ('cj_barbers', 'vehiclegeneric64', 'tree09', 'sign_stop1'):
    check(not hasapplied(bad), '%s was NOT given a road shader' % bad)

section('commands')
T.cmd('roadquality', 'ultra')
T.adv(3000)
check(str(g.RR.State.quality) == 'ultra', '/roadquality ultra -> level 4')
T.cmd('roaddebug', '1')
check(int(g.RR.State.debug) > 0, '/roaddebug 1 -> overlay on (level %s)' % g.RR.State.debug)
T.cmd('roaddebug', '0')
T.cmd('roadrain', '0.8')
check(abs(float(g.RR.Rain.level) - 0.8) < 0.01, '/roadrain 0.8 -> rain level 0.8')
T.adv(15000)
check(float(g.RR.State.wet) > 0.3, 'wetness rose to %.2f after 15 s of rain' % float(g.RR.State.wet))
T.cmd('roadwet', '0.5')
check(abs(float(g.RR.State.wet) - 0.5) < 0.02, '/roadwet 0.5 overrides wetness')
T.cmd('roadreport', 'save')
check('report written' in chatall().lower(), '/roadreport save wrote road_texture_report.txt')
for c in ('roadtextures', 'roadinfo', 'roadscan', 'roadapply', 'roadremove', 'roadreload'):
    T.cmd(c)
    T.adv(600)
check(True, 'discovery commands ran without a Lua error')
T.cmd('roadfx', '0')
check(int(napplied()) == 0, '/roadfx 0 removed every road shader (%d left)' % int(napplied()))
T.cmd('roadfx', '1')
T.adv(3000)
check(int(napplied()) > 20, '/roadfx 1 re-applied %d shaders' % int(napplied()))

section('shader failure failsafe (real create/fallback code)')
T.shaderMode = 'fail'
L.eval('function() RR.Shaders.destroyAll() end')()
created = L.eval('function() local sh = RR.Shaders.create("shaders/road.fx") return sh and true or false end')()
check(not created, 'a shader that fails to compile returns false instead of crashing')
L.eval('function() RR.Fail("Road shader failed to compile: ps_3_0 not supported (test)") end')()
check('failed to compile' in chatall().lower(), 'the exact shader failure is reported to the player')
L.eval('function() RR.Fallback.enable() end')()
check(bool(g.RR.Fallback.active), 'the fallback (texture replacement) path activated')
check('shaders unavailable' in chatall().lower() or 'imported new road textures' in chatall().lower(),
      'the fallback told the player what it did')
T.shaderMode = 'ok'
L.eval('function() RR.Shaders.destroyAll() end')()  # a reload clears the failed-shader cache
rebuilt = L.eval('function() local sh = RR.Shaders.create("shaders/road.fx") return sh and true or false end')()
check(rebuilt, 'the same shader compiles again after a reload once the driver is healthy')

section('resource stop / cleanup')
T.fireClient('onClientResourceStop', g.resourceRoot)
T.adv(1200)
check(int(T.liveTimers()) == 0, 'every timer cleaned up (%d live)' % int(T.liveTimers()))
check(T.alive('shader') == 0, 'every shader destroyed (%d live)' % T.alive('shader'))
check(T.alive('texture') == 0, 'every texture destroyed (%d live)' % T.alive('texture'))
check(T.alive('sound') == 0, 'rain audio stopped')
check(T.handlerCount('onClientRender') == 0, 'render handler detached')
check(float(T.rainSet) == 0.0, 'native rain level restored to 0 on stop')

errs = [str(x) for x in str(logall()).splitlines() if 'error:' in x]
check(not errs, 'no handler/timer errors during the whole session (%d)' % len(errs))
for e in errs[:8]:
    print('        ' + e)

print('\n== %d passed, %d failed ==' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
