# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# pipeline.py - turns the material database into the files that ship in the resource:
#   textures/<cat>/<key>.dds        albedo, DXT1 + full mip chain
#   textures/roughness/<key>_mask.dds  DXT5 (R rough, G AO, B damage, A contamination)
#   textures/detail|normals|wet|puddles|markings/...
#   files/road_fallback.txd         RenderWare TXD with the ORIGINAL texture names, used only when
#                                   the shader cannot be created (see client.lua failsafe)
#   audio/rain_loop.wav             seamless rain bed (filtered periodic noise + droplet transients)
#   config/materials.lua            generated from materials.py
#   config/roads.lua                generated from scan_db.py
#
# Usage:  python3 build.py            (from source/)
# -----------------------------------------------------------------------------
import json
import os
import struct
import sys
import time
import wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from lib import dxt, rwtxd
from . import materials as MAT
from . import scan_db
from . import texgen as TG

# the fallback TXD keeps the ORIGINAL GTA SA names so engineImportTXD can drop it straight into the
# models that use them.  256 px is enough: it is only ever seen when the shader layer is dead.
FALLBACK = [
    ('snpedtest1', 'asphalt_mid'), ('dt_road', 'asphalt_mid'), ('road1256', 'asphalt_mid'),
    ('plaintarmac1', 'asphalt_mid'), ('vegasroad1_256', 'asphalt_mid'), ('sf_road5', 'asphalt_mid'),
    ('roadnew4_256', 'asphalt_suburban'), ('greyground256', 'asphalt_old'), ('paveb256', 'asphalt_old'),
    ('vegasroad3_256', 'asphalt_old'), ('Tar_1line256HV', 'asphalt_highway'),
    ('cos_hiwaymid_256', 'asphalt_highway'), ('concretegroundl1_256', 'concrete_road'),
    ('Newpavement', 'pavement_slab'), ('kbpavement_test', 'pavement_slab'),
    ('easykerb', 'kerb_concrete'), ('crossing_law', 'asphalt_junction'),
    ('desertgravelgrassroad', 'asphalt_gravel'),
]
FALLBACK_SIZE = 256


# ---------------------------------------------------------------------------
def _down(img, n):
    """box downsample by 2, n times (used to build the fallback TXD from a baked material)"""
    from PIL import Image
    a = img
    for _ in range(n):
        h, w = a.shape[:2]
        a = np.asarray(Image.fromarray(a).resize((w // 2, h // 2), Image.BOX))
    return a


def write_dds(path, img, fmt):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dxt.write_dds(path, img, fmt)
    return os.path.getsize(path)


# ---------------------------------------------------------------------------
def build_textures(res):
    t0 = time.time()
    log = []
    total = 0

    def rec(n, label):
        nonlocal total
        total += n
        log.append((label, n))
        return n

    # ---- shared maps first (every material needs them, so a failure here is fatal)
    nrm, orm = TG.bake_detail()
    rec(write_dds(os.path.join(res, 'textures/normals/detail_agg.dds'), nrm, 'DXT5'), 'detail normal')
    rec(write_dds(os.path.join(res, 'textures/detail/detail_agg.dds'), orm, 'DXT1'), 'detail orm')
    rec(write_dds(os.path.join(res, 'textures/normals/detail_micro.dds'), TG.bake_micro(), 'DXT5'), 'micro normal')
    rec(write_dds(os.path.join(res, 'textures/detail/macro.dds'), TG.bake_macro(), 'DXT1'), 'macro variation')
    rec(write_dds(os.path.join(res, 'textures/puddles/puddle_mask.dds'), TG.bake_puddle(), 'DXT1'), 'puddle mask')
    print('   shared maps: %d bytes in %.1f s' % (total, time.time() - t0))

    # ---- materials
    baked = {}
    for i, m in enumerate(MAT.MATERIALS):
        b = TG.bake_material(m)
        baked[m['key']] = b
        rec(write_dds(os.path.join(res, MAT.albedo_path(m)), b['albedo'], 'DXT1'), m['key'] + ' albedo')
        rec(write_dds(os.path.join(res, MAT.mask_path(m)), b['mask'], 'DXT5'), m['key'] + ' mask')
        if (i + 1) % 8 == 0:
            print('   %2d / %d materials  (%.1f MB so far, %.0f s)'
                  % (i + 1, len(MAT.MATERIALS), total / 1048576, time.time() - t0))
    # ---- markings
    mark_stats = {}
    for mk in MAT.MARKINGS:
        rgba, rough = TG.bake_marking(mk)
        rec(write_dds(os.path.join(res, MAT.marking_path(mk['key'])), rgba, 'DXT5'), mk['key'])
        mark_stats[mk['key']] = dict(alpha=float(rgba[..., 3].mean() / 255),
                                     rough=float(rough.mean() / 255))
    # ---- rain / droplets / splashes (PNG: they are small and MTA reads PNG with alpha directly)
    from PIL import Image
    os.makedirs(os.path.join(res, 'textures/wet'), exist_ok=True)
    Image.fromarray(TG.bake_droplets(), 'RGBA').save(os.path.join(res, 'textures/wet/droplets.png'))
    rec(os.path.getsize(os.path.join(res, 'textures/wet/droplets.png')), 'droplets')
    Image.fromarray(TG.bake_rain_streak(), 'RGBA').save(os.path.join(res, 'textures/wet/rain_streak.png'))
    rec(os.path.getsize(os.path.join(res, 'textures/wet/rain_streak.png')), 'rain streak')
    Image.fromarray(TG.bake_splash(), 'RGBA').save(os.path.join(res, 'textures/wet/splash.png'))
    rec(os.path.getsize(os.path.join(res, 'textures/wet/splash.png')), 'splash')
    # ---- a tiled "wet sheen" normal used for the thin film on top of the aggregate
    rec(write_dds(os.path.join(res, 'textures/wet/wet_normal.dds'), TG.bake_micro(), 'DXT5'), 'wet normal')
    print('   textures: %d files, %.1f MB in %.1f s' % (len(log), total / 1048576, time.time() - t0))
    return log, total, baked, mark_stats


def build_fallback_txd(res, baked):
    """RenderWare TXD holding new pixels under the ORIGINAL texture names (shader failsafe)."""
    lst = []
    for name, mkey in FALLBACK:
        b = baked[mkey]
        n = 0
        while MAT.SIZE_ALBEDO >> n > FALLBACK_SIZE:
            n += 1
        small = _down(b['albedo'], n)
        h, w = small.shape[:2]
        lst.append(dict(name=name, w=w, h=h, fmt='DXT1',
                        chain=dxt.compress_chain(small, 'DXT1'), alpha=False))
    os.makedirs(os.path.join(res, 'files'), exist_ok=True)
    p = os.path.join(res, 'files', 'road_fallback.txd')
    open(p, 'wb').write(rwtxd.build_txd(lst))
    return p, os.path.getsize(p), [t['name'] for t in lst]


def _load_ai(name):
    from PIL import Image
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_ai', name)
    return np.asarray(Image.open(p).convert('RGB'), np.float32) / 255.0


def build_base_txd(res):
    """TXD holding AI photo textures under the ORIGINAL SA surface names.

    This is the reliable, geometry-faithful base look (NightCity-style): the original
    DFF/COL are untouched, only the surface pixels are swapped per model at runtime via
    engineImportTXD, so the roads match San Andreas 100% in layout and collision."""
    from PIL import Image
    worn = _load_ai('asphalt_worn.png')
    variants = {
        'asphalt': [np.clip(worn * 0.55, 0, 1), worn, np.clip(worn * 1.30 + 0.03, 0, 1)],
        'concrete': [_load_ai('concrete_road.png')],
        'pavement': [_load_ai('sidewalk.png')],
        'shoulder': [_load_ai('dirt_shoulder.png')],
    }
    mat = {m['key']: m for m in MAT.MATERIALS}
    lst, names = [], []
    for name in sorted(scan_db.WHITELIST):
        mk, _mark = scan_db.WHITELIST[name]
        cat = mat[mk]['cat']
        if cat not in variants:
            continue
        pool = variants[cat]
        img = pool[hash(name) % len(pool)]
        im = Image.fromarray((img * 255).astype(np.uint8)).resize((256, 256), Image.BOX)
        arr = np.asarray(im, np.float32) / 255.0
        lst.append(dict(name=name, w=256, h=256, fmt='DXT1',
                        chain=dxt.compress_chain(arr, 'DXT1'), alpha=False))
        names.append(name)
    os.makedirs(os.path.join(res, 'files'), exist_ok=True)
    p = os.path.join(res, 'files', 'road_base.txd')
    open(p, 'wb').write(rwtxd.build_txd(lst))
    return p, os.path.getsize(p), names


def build_rain_audio(res, seconds=8.0, rate=22050):
    """seamless rain bed: periodic (loopable) filtered noise + sparse droplet transients."""
    n = int(seconds * rate)
    rng = np.random.default_rng(9)
    F = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / rate)
    # rain hiss: high passed white noise with a soft 6 kHz shelf, plus a low rumble bed
    shape = np.clip((f / 900.0) ** 0.9, 0, 1) * np.exp(-(f / 9000.0) ** 1.4)
    rumble = np.exp(-((f - 120) / 90.0) ** 2) * 0.5
    F = F * (shape * 0.9 + rumble)
    x = np.fft.irfft(F, n)
    x = x / (np.abs(x).max() + 1e-9)
    # droplet ticks: short exponentially decaying bursts on random samples (periodic by construction)
    for _ in range(int(seconds * 90)):
        i = int(rng.integers(0, n))
        L = min(int(rate * rng.uniform(0.004, 0.02)), n - i)
        if L < 4:
            continue
        t = np.arange(L)
        tick = rng.standard_normal(L) * np.exp(-t / (L / 5.0))
        x[i:i + L] += tick * rng.uniform(0.03, 0.13)
    x = np.tanh(x * 1.6)
    fade = int(rate * 0.01)
    x = x / (np.abs(x).max() + 1e-9) * 0.85
    pcm = (x * 32767).astype(np.int16)
    os.makedirs(os.path.join(res, 'audio'), exist_ok=True)
    p = os.path.join(res, 'audio', 'rain_loop.wav')
    with wave.open(p, 'wb') as wv:
        wv.setnchannels(1)
        wv.setsampwidth(2)
        wv.setframerate(rate)
        wv.writeframes(pcm.tobytes())
    return p, os.path.getsize(p)


# ---------------------------------------------------------------------------
# Lua emission
# ---------------------------------------------------------------------------
LUA_HDR = ('-- Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA resource\n'
           '-- GENERATED by source/build.py from source/rr/*.py - edit the database, then rebuild\n')


def _q(s):
    return '"%s"' % s


def emit_materials_lua(res, mark_stats):
    L = [LUA_HDR,
         '-- RoadRealism material database.  rough / f0 / wetRough are physical values (0..1),',
         '-- worldScale is the metres covered by one albedo tile (the shader re-projects in world space).',
         'ROAD_MATERIALS = {']
    for m in MAT.MATERIALS:
        L.append('    %s = {' % m['key'])
        L.append('        label = %s, cat = %s,' % (_q(m['label']), _q(m['cat'])))
        L.append('        albedo = %s,' % _q(MAT.albedo_path(m)))
        L.append('        mask = %s,' % _q(MAT.mask_path(m)))
        L.append('        rough = %.3f, roughVar = %.3f, f0 = %.3f, wetRough = %.3f,'
                 % (m['rough'], m['roughVar'], m['f0'], m['wetRough']))
        L.append('        reflection = %.2f, puddle = %.2f, normalScale = %.2f, macro = %.2f,'
                 % (m['reflection'], m['puddle'], m['normalScale'], m['macro']))
        L.append('        worldScale = %.2f, detailScale = %.1f, useMeshUV = false,'
                 % (m['worldScale'], m['detailScale']))
        L.append('        dirt = %.2f, damage = %.2f,' % (m['dirt'], max(m['cracks'], m['pothole'])))
        L.append('    },')
    L.append('}')
    L.append('')
    L.append('ROAD_MARKINGS = {')
    for mk in MAT.MARKINGS:
        st = mark_stats.get(mk['key'], {})
        L.append('    %s = { label = %s, file = %s, rough = %.3f, retro = %.2f, coverage = %.3f },'
                 % (mk['key'], _q(mk['label']), _q(MAT.marking_path(mk['key'])),
                    mk['rough'], mk['retro'], st.get('alpha', 0.0)))
    L.append('}')
    L.append('')
    L.append('ROAD_QUALITY = {')
    for k in ('low', 'medium', 'high', 'ultra'):
        q = MAT.QUALITY[k]
        L.append('    %s = { label = %s, road = %s, post = %s, detailTex = %s, parallax = %s, ssr = %s,'
                 % (k, _q(q['label']), _q(q['road']), _q(q['post']),
                    'true' if q['detailTex'] else 'false', 'true' if q['parallax'] else 'false',
                    'true' if q['ssr'] else 'false'))
        L.append('             puddles = %s, rainStreaks = %d, rainDrops = %s, screenW = %d, screenH = %d, reflectTaps = %d },'
                 % ('true' if q['puddles'] else 'false', q['rainStreaks'],
                    'true' if q['rainDrops'] else 'false', q['screenW'], q['screenH'], q['reflectTaps']))
    L.append('}')
    L.append('')
    L.append('-- shared texture set (one instance each, every shader samples the same objects)')
    L.append('ROAD_SHARED = {')
    L.append('    detailNormal = "textures/normals/detail_agg.dds",')
    L.append('    detailData = "textures/detail/detail_agg.dds",')
    L.append('    microNormal = "textures/normals/detail_micro.dds",')
    L.append('    macro = "textures/detail/macro.dds",')
    L.append('    puddle = "textures/puddles/puddle_mask.dds",')
    L.append('    wetNormal = "textures/wet/wet_normal.dds",')
    L.append('    droplets = "textures/wet/droplets.png",')
    L.append('    rainStreak = "textures/wet/rain_streak.png",')
    L.append('    splash = "textures/wet/splash.png",')
    L.append('}')
    L.append('')
    L.append('ROAD_RAIN_TABLE = {   -- rain level, resulting wetness, description')
    for r, w, d in MAT.RAIN_TABLE:
        L.append('    { %.2f, %.2f, %s },' % (r, w, _q(d)))
    L.append('}')
    open(os.path.join(res, 'config', 'materials.lua'), 'w').write('\n'.join(L) + '\n')


def emit_roads_lua(res):
    L = [LUA_HDR,
         '-- Road texture discovery database.  Tiers:',
         '--   apply  definitely a road surface, replaced automatically',
         '--   review name is ambiguous, reported by /roadscan, applied only with /roadapply <name>',
         '--   ban    never touched even when a road pattern matches',
         '-- The names in ROAD_TEXTURES were read out of the shipped GTA San Andreas TXDs listed in the',
         '-- comment of each entry (see source/rr/scan_db.py for the full provenance list).',
         'ROAD_TEXTURES = {']
    for name in sorted(scan_db.WHITELIST):
        mk, mark = scan_db.WHITELIST[name]
        L.append('    [%s] = { mat = %s, mark = %s, tier = "apply" },'
                 % (_q(name), _q(mk), _q(mark) if mark else 'false'))
    for name in sorted(scan_db.REVIEW):
        mk, mark = scan_db.REVIEW[name]
        L.append('    [%s] = { mat = %s, mark = %s, tier = "review" },'
                 % (_q(name), _q(mk), _q(mark) if mark else 'false'))
    L.append('}')
    L.append('')
    L.append('ROAD_BANNED = {')
    for name in sorted(scan_db.BLACKLIST):
        L.append('    [%s] = true,' % _q(name))
    L.append('}')
    L.append('')
    L.append('-- ordered Lua patterns on the lower case name; first hit wins.  Used to *suggest* a')
    L.append('-- material for unknown textures (applied automatically only if SETTINGS.autoApplyPatterns).')
    L.append('ROAD_PATTERNS = {')
    for pat, mk, mark in scan_db.PATTERNS:
        L.append('    { %s, %s, %s },' % (_q(pat), _q(mk), _q(mark) if mark else 'false'))
    L.append('}')
    L.append('')
    L.append('ROAD_PATTERN_REJECT = {')
    for pat in scan_db.PATTERN_REJECT:
        L.append('    %s,' % _q(pat))
    L.append('}')
    L.append('')
    L.append('-- TXD archives that are known to hold road surfaces (information only)')
    L.append('ROAD_TXDS = {')
    for t in scan_db.TXD_ROAD:
        L.append('    %s,' % _q(t))
    L.append('}')
    L.append('')
    L.append('-- original names that also get new pixels through engineImportTXD when the shader is dead')
    L.append('ROAD_FALLBACK_TXD = "files/road_fallback.txd"')
    L.append('ROAD_FALLBACK_NAMES = {')
    for n, _ in FALLBACK:
        L.append('    %s,' % _q(n))
    L.append('}')
    open(os.path.join(res, 'config', 'roads.lua'), 'w').write('\n'.join(L) + '\n')


def emit_settings_lua(res):
    s = MAT.SETTINGS
    L = [LUA_HDR,
         '-- RoadRealism runtime settings.  Everything here can also be changed from the chat box:',
         '--   /roadquality low|medium|high|ultra   /roadrain <0-1>   /roadwet <0-1>   /roadreload',
         '--   /roaddebug <0|1|2|3>   /roadfx <0-4>   /roadrefl <0-2>   /roadscan   /roadtextures',
         'SETTINGS = {']
    order = ['wetDryRate', 'wetRiseRate', 'wetMin', 'wetMax', 'puddleFrom', 'puddleFull',
             'rainWeather', 'rainWeatherDamp', 'rainOwnWeather', 'rainSound', 'rainVolume',
             'reflectStrength', 'reflectAnglePow', 'reflectBlur', 'reflectStretch',
             'nightRetro', 'nightSpecBoost', 'exposure',
             'maxShaders', 'scanInterval', 'scanPerStep', 'applyPerStep', 'lazyDistance', 'debug']
    for k in order:
        v = s[k]
        if isinstance(v, bool):
            L.append('    %s = %s,' % (k, 'true' if v else 'false'))
        elif isinstance(v, int):
            L.append('    %s = %d,' % (k, v))
        else:
            L.append('    %s = %s,' % (k, ('%.4f' % v).rstrip('0').rstrip('.')))
    L.append('    -- safety switches')
    L.append('    autoApplyPatterns = false,   -- apply pattern guesses to unknown textures (risky)')
    L.append('    autoApplyReview = false,     -- apply the ambiguous "review" tier on start')
    L.append('    fallbackTXD = true,          -- engineImportTXD fallback when a shader will not compile')
    L.append('    preserveWeatherOnStop = true,')
    L.append('    defaultQuality = "high",')
    L.append('}')
    open(os.path.join(res, 'config', 'settings.lua'), 'w').write('\n'.join(L) + '\n')


def build(res, quiet=False):
    t0 = time.time()
    for d in ('textures', 'config', 'shaders', 'audio', 'files'):
        os.makedirs(os.path.join(res, d), exist_ok=True)
    log, total, baked, mark_stats = build_textures(res)
    p, sz, names = build_fallback_txd(res, baked)
    total += sz
    bp, bsz, bnames = build_base_txd(res)
    total += bsz
    ap, asz = build_rain_audio(res)
    total += asz
    emit_materials_lua(res, mark_stats)
    emit_roads_lua(res)
    with open(os.path.join(res, 'config', 'roads.lua'), 'a') as f:
        f.write('\n-- AI photo textures bound to the ORIGINAL SA surface names (geometry-faithful base look)\n')
        f.write('ROAD_BASE_TXD = "files/road_base.txd"\nROAD_BASE = {\n')
        for n in bnames:
            f.write('    [%s] = true,\n' % _q(n))
        f.write('}\n')
    emit_settings_lua(res)
    stats = dict(files=len(log), bytes=total, materials=len(MAT.MATERIALS),
                 markings=len(MAT.MARKINGS), fallback=names, fallback_bytes=sz,
                 base=bnames, base_bytes=bsz,
                 audio=asz, seconds=round(time.time() - t0, 1))
    print('   fallback TXD %.2f MB (%d names) | base TXD %.2f MB (%d names) | rain loop %.2f MB'
          % (sz / 1048576, len(names), bsz / 1048576, len(bnames), asz / 1048576))
    if not quiet:
        os.makedirs(os.path.join(HERE, '..', '_work'), exist_ok=True)
        json.dump(stats, open(os.path.join(HERE, '..', '_work', 'texture_report.json'), 'w'), indent=1)
    return stats


if __name__ == '__main__':
    out = os.path.abspath(os.path.join(HERE, '..', '..', 'resource', 'RoadRealism'))
    print('RoadRealism texture pipeline -> %s' % out)
    s = build(out)
    print('done in %.1f s: %.1f MB in %d texture files' % (s['seconds'], s['bytes'] / 1048576, s['files']))
