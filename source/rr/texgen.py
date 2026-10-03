# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# texgen.py - procedural physically-inspired road material generator (numpy, no image downloads).
#
# Every field is derived from the same height / contamination model so albedo, normal, roughness, AO
# and the masks always agree with each other (no "painted on" detail that the lighting ignores):
#
#   aggregate  tileable cellular (worley) stones  -> height + albedo grain + roughness variation
#   pores      second, denser cellular pass       -> dark speckles, micro roughness spikes
#   cracks     polygonal veins (coarse cellular boundary) + hairlines
#   patches    repair blobs with their own aggregate scale, tone and roughness
#   oil        smooth dark blobs, very low roughness, high reflectance
#   dirt       low frequency film, accumulates in the crevices
#   rubber     tyre polish: roughness down, slight darkening
#   joints     slab / expansion / block patterns with a real chamfer in the height field
#
# Output channels
#   albedo  DDS DXT1  sRGB   RGB = base colour
#   mask    DDS DXT5  linear R = roughness, G = AO, B = damage, A = contamination (dirt + oil + rubber)
#   detail normal DDS DXT5nm A = nx, G = ny (nz is reconstructed in the shader)
#   detail data   DDS DXT1   R = roughness variation, G = AO, B = height
#   marking       DDS DXT5   RGB = aged paint colour, A = surviving paint coverage
# -----------------------------------------------------------------------------
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from lib import noise as N
from lib import dxt
from . import materials as MAT

FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def srgb_to_lin(c):
    return np.power(np.clip(c, 0, 1), 2.2)


def lin_to_srgb(c):
    return np.power(np.clip(c, 0, 1), 1.0 / 2.2)


def clamp01(a):
    return np.clip(a, 0.0, 1.0)


# ---------------------------------------------------------------------------
# aggregate: the stone / bitumen matrix every asphalt is built from
# ---------------------------------------------------------------------------
def aggregate(h, w, scale, seed, contrast=1.0):
    """returns dict(height 0..1, tone 0..1 (stone brightness), edge 0..1 (mortar / gap), fine grain)"""
    nx = int(round(w / 22.0 * scale))
    ny = int(round(h / 22.0 * scale))
    nx, ny = max(4, nx), max(4, ny)
    F1, F2, ID = N.worley(h, w, nx, ny, seed)
    # stone interior: distance to the cell boundary
    d = np.clip((F2 - F1) * 6.0 * contrast, 0, 1)
    dome = np.sqrt(np.clip(1 - (1 - d) ** 2, 0, 1))          # rounded stone tops
    # pores: a second, much denser cellular pass punches small holes
    p1, p2, _ = N.worley(h, w, nx * 4, ny * 4, seed + 7717)
    pore = 1.0 - N.smooth(0.0, 0.16, p2 - p1)
    height = 0.55 * dome + 0.30 * (1 - pore) + 0.15 * N.bnoise(h, w, 3.0, 3.0, seed + 91) * 0.5 + 0.075
    tone = 0.5 + 0.5 * np.clip(N._norm(ID) * 0.22 + N.bnoise(h, w, 6.0, 6.0, seed + 33) * 0.30, -1, 1)
    edge = 1.0 - N.smooth(0.35, 0.75, d)                     # 1 in the gaps between stones
    grain = clamp01(0.5 + 0.5 * N.bnoise(h, w, 1.4, 1.4, seed + 5) * 0.8 + 0.2 * N.white(h, w, seed + 6))
    return dict(height=clamp01(height), tone=tone, edge=edge, pore=pore, grain=grain)


def crack_network(h, w, amount, seed, scale=1.0):
    """polygonal alligator cracking: thin veins along the boundaries of a coarse cellular field"""
    if amount <= 0:
        return np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)
    nx = int(round(w / 128.0 * scale)) + 2
    F1, F2, _ = N.worley(h, w, nx, nx, seed)
    v = F2 - F1
    wide = 1.0 - N.smooth(0.0, 0.045 + 0.05 * amount, v)      # main cracks
    # hairlines: warped secondary network
    warp = N.bnoise(h, w, 40, 40, seed + 11) * 0.02
    v2 = (F2 - F1) + warp
    hair = 1.0 - N.smooth(0.0, 0.02, v2 * 0.6)
    m = clamp01(wide * 0.85 + hair * 0.35) * amount
    return m, wide * amount


def blobs(h, w, count, seed, size=90.0, soft=0.5, irregular=1.0):
    """irregular smooth blobs (patches / oil), tileable"""
    nx = max(2, int(round(w / size)))
    F1, F2, ID = N.worley(h, w, nx, nx, seed)
    idn = clamp01((ID - (1.0 - count)) / max(1e-6, count))     # keep the `count` brightest cells
    shape = N.smooth(0.05, 0.05 + soft * 0.35, F2 - F1)
    wob = 1.0 + irregular * 0.35 * N.bnoise(h, w, size * 0.35, size * 0.35, seed + 21)
    return clamp01(idn * N.smooth(0.25, 0.75, shape * wob))


def streaks(h, w, amount, seed, angle=np.pi / 2.0):
    """directional smearing (dirt dragged by traffic, water run-off)"""
    if amount <= 0:
        return np.zeros((h, w), np.float32)
    s = N.scratches(h, w, int(w * 0.55 * amount), w * 0.08, w * 0.42, seed,
                    angle=angle, spread=0.12, ss=1, width=2.0)
    s = np.asarray(Image.fromarray((clamp01(s) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0)), np.float32) / 255.0
    return clamp01(s * amount * 1.6)


# ---------------------------------------------------------------------------
# joints (concrete slabs, expansion strips, block paving, kerbs)
# ---------------------------------------------------------------------------
def slab_joints(h, w, per_tile=3, seed=0, width=0.012):
    """returns (mask 0..1 at the joint, height offset, running-bond variant)"""
    yy = np.arange(h)[:, None] / h * per_tile
    xx = np.arange(w)[None, :] / w * per_tile
    fy = np.abs((yy % 1.0) - 0.5) * 2.0            # 0 at the cell centre, 1 at the boundary
    fx = np.abs((xx % 1.0) - 0.5) * 2.0
    row = np.floor(yy)
    off = np.where(np.mod(row, 2) == 0, 0.0, 0.5 / per_tile * w / w)
    xx2 = np.abs((((xx + off * per_tile) % 1.0) - 0.5) * 2.0)
    d = np.minimum(1 - fy, 1 - fx) if False else np.minimum(fy, xx2)
    m = 1.0 - N.smooth(1.0 - width * per_tile * 4, 1.0 - width * per_tile * 2, d)
    cham = N.smooth(1.0 - width * per_tile * 8, 1.0, d)        # wider, shallower chamfer
    return clamp01(m), cham, np.minimum(fy, xx2)


def expansion_joints(h, w, per_tile=2.0):
    yy = np.arange(h)[:, None] / h * per_tile
    f = np.abs((yy % 1.0) - 0.5) * 2.0
    m = 1.0 - N.smooth(0.965, 0.995, f)
    return clamp01(m)


# ---------------------------------------------------------------------------
# material bake
# ---------------------------------------------------------------------------
def bake_material(m):
    """material dict -> dict(albedo uint8 HxWx3, mask uint8 HxWx4, height float)"""
    h = w = MAT.SIZE_ALBEDO
    seed = m['seed']
    ag = aggregate(h, w, m['agg'], seed)
    cr, cr_wide = crack_network(h, w, m['cracks'], seed + 400)
    patch = blobs(h, w, m['patches'], seed + 500, size=w * 0.45, soft=0.7)
    oil = blobs(h, w, m['oil'], seed + 600, size=w * 0.30, soft=0.4, irregular=1.4)
    oil = clamp01(oil * 0.8 + streaks(h, w, m['oil'] * 0.5, seed + 601) * 0.6)
    dirt = clamp01(0.55 * blobs(h, w, m['dirt'] * 1.2, seed + 700, size=w * 0.6, soft=0.9)
                   + 0.45 * clamp01(0.5 + 0.5 * N.bnoise(h, w, w * 0.10, w * 0.10, seed + 701)) * m['dirt'])
    dirt = clamp01(dirt * (0.45 + 0.55 * ag['edge']))          # dirt collects between the stones
    rubber = clamp01(m['tire'] * (0.55 + 0.45 * clamp01(0.5 + 0.5 * N.bnoise(h, w, w * 0.14, w * 0.14, seed + 801)))
                     * (0.5 + 0.5 * (1 - ag['edge'])))
    pit = blobs(h, w, m['pothole'], seed + 900, size=w * 0.20, soft=0.35, irregular=1.6)
    pit = pit * cr_wide * 2.0 + pit * 0.35                     # potholes start from the cracks

    joints_m = np.zeros((h, w), np.float32)
    joints_c = np.zeros((h, w), np.float32)
    height = ag['height'].copy()
    if m['joints'] == 1:                                        # concrete slabs
        jm, jc, _ = slab_joints(h, w, 3, seed)
        joints_m, joints_c = jm, jc
    elif m['joints'] == 2:                                      # expansion strips
        jm = expansion_joints(h, w, 2.0)
        joints_m = jm
        joints_c = jm
    elif m['joints'] == 3:                                      # block paving / kerb blocks
        jm, jc, _ = slab_joints(h, w, 5, seed)
        joints_m, joints_c = jm, jc

    # ---- height
    height = height * (1.0 - 0.85 * cr_wide)                    # cracks sink in
    height = height * (1.0 - 0.35 * patch) + 0.06 * patch       # patches sit slightly proud
    height = height - 0.55 * pit                                # potholes
    height = height - 0.30 * joints_c                           # joints / chamfers
    height = clamp01(height + 0.35)
    # ---- albedo (linear)
    base = np.array(m['base'], np.float32)
    base = srgb_to_lin(base) * np.array(m['tint'], np.float32)
    a = np.ones((h, w, 3), np.float32) * base
    # stone vs bitumen: stones are lighter and slightly warmer, bitumen darker
    tone = (0.88 + 0.24 * ag['tone']) * (0.93 + 0.14 * ag['grain'])
    a *= tone[..., None]
    a *= (1.0 - 0.22 * ag['edge'])[..., None]                   # subtle mortar shading
    a *= (1.0 - 0.55 * patch * 0.5)[..., None]
    a *= (1.0 + 0.22 * patch * N.smooth(0.3, 0.8, N.bnoise(h, w, w * 0.06, w * 0.06, seed + 12)))[..., None]
    a *= (1.0 - 0.72 * oil)[..., None]
    a *= (1.0 - 0.30 * dirt)[..., None] * (np.array((1.06, 1.02, 0.94), np.float32) * dirt[..., None] + (1 - dirt[..., None]))
    a *= (1.0 - 0.40 * rubber)[..., None]
    a *= (1.0 - 0.55 * cr)[..., None] * (np.array((0.85, 0.83, 0.80), np.float32) * cr[..., None] + (1 - cr[..., None]))
    a *= (1.0 - 0.80 * pit)[..., None]
    a *= (1.0 - 0.45 * joints_m)[..., None]
    albedo = clamp01(a)
    # ---- roughness
    rough = np.full((h, w), m['rough'], np.float32)
    rough += m['roughVar'] * (ag['tone'] - 0.5) * 2.0 * 0.55    # stones polish differently
    rough += 0.16 * ag['edge']                                  # mortar / crevices are rougher
    rough -= 0.30 * oil                                         # oil is glossy
    rough -= 0.26 * rubber                                      # tyre polish
    rough -= 0.10 * cr                                          # wet-looking crack bottoms
    rough += 0.30 * dirt                                        # dust is matte
    rough += 0.18 * pit
    rough += 0.12 * joints_m
    rough += m['roughVar'] * 0.5 * N.bnoise(h, w, w * 0.05, w * 0.05, seed + 21)
    rough = clamp01(np.clip(rough, 0.03, 1.0))
    # ---- AO
    ao = clamp01(1.0 - 0.55 * ag['edge'] - 0.5 * cr - 0.7 * pit - 0.45 * joints_c
                 - 0.25 * (1 - N.smooth(0.2, 0.8, N.bnoise(h, w, w * 0.08, w * 0.08, seed + 31)) * 0.5))
    # ---- damage / contamination channels
    damage = clamp01(np.maximum(cr, np.maximum(pit * 1.6, patch * 0.7 + joints_m * 0.5)))
    contam = clamp01(np.maximum(oil, np.maximum(dirt * 0.9, rubber * 0.8)))

    albedo8 = (lin_to_srgb(albedo) * 255 + 0.5).astype(np.uint8)
    mask = np.zeros((h, w, 4), np.uint8)
    mask[..., 0] = (rough * 255 + 0.5).astype(np.uint8)
    mask[..., 1] = (ao * 255 + 0.5).astype(np.uint8)
    mask[..., 2] = (damage * 255 + 0.5).astype(np.uint8)
    mask[..., 3] = (contam * 255 + 0.5).astype(np.uint8)
    return dict(albedo=albedo8, mask=mask, height=height, oil=oil, dirt=dirt, rubber=rubber,
                crack=cr, pit=pit, joints=joints_m)


# ---------------------------------------------------------------------------
# shared detail / micro / macro / puddle maps
# ---------------------------------------------------------------------------
def bake_detail():
    """the aggregate detail every material tiles over: normal (A=nx,G=ny) + orm (R=rough,G=ao,B=height)"""
    h = w = MAT.SIZE_DETAIL
    ag = aggregate(h, w, 3.4, 1337, contrast=1.25)
    height = clamp01(ag['height'] * 0.85 + 0.15 * ag['grain'] * 0.4)
    fine = N.bnoise(h, w, 2.2, 2.2, 99) * 0.12
    height = clamp01(height + fine)
    nx, ny, nz = N.normal_from_height(height, 3.2)
    nrm = np.zeros((h, w, 4), np.uint8)
    nrm[..., 1] = ((ny * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)      # G = ny
    nrm[..., 3] = ((nx * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)      # A = nx
    nrm[..., 0] = 128
    nrm[..., 2] = 128
    rough = clamp01(0.5 + 0.5 * (0.7 * (ag['tone'] - 0.5) * 2 + 0.6 * ag['edge'] - 0.3 * (1 - ag['pore'])))
    ao = clamp01(1.0 - 0.75 * ag['edge'] - 0.35 * ag['pore'])
    orm = np.stack([rough, ao, height], -1)
    orm8 = (orm * 255 + 0.5).astype(np.uint8)
    return nrm, orm8


def bake_micro():
    h = w = MAT.SIZE_MICRO
    g = N.white(h, w, 4242) * 0.5 + N.bnoise(h, w, 1.7, 1.7, 84) * 0.5
    height = clamp01(0.5 + g * 0.55)
    nx, ny, _ = N.normal_from_height(height, 1.6)
    nrm = np.zeros((h, w, 4), np.uint8)
    nrm[..., 0] = 128
    nrm[..., 1] = ((ny * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)
    nrm[..., 2] = 128
    nrm[..., 3] = ((nx * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)
    return nrm


def bake_macro():
    """large scale colour + roughness variation so long roads never read as one repeated tile"""
    h = w = MAT.SIZE_MACRO
    v1 = N.bnoise(h, w, w * 0.30, w * 0.30, 555)
    v2 = N.bnoise(h, w, w * 0.12, w * 0.12, 556)
    v3 = N.bnoise(h, w, w * 0.45, w * 0.45, 557)
    warm = clamp01(0.5 + 0.5 * v3)
    r = clamp01(0.5 + 0.16 * v1 + 0.10 * v2 + 0.06 * (warm - 0.5))
    g = clamp01(0.5 + 0.16 * v1 + 0.09 * v2)
    b = clamp01(0.5 + 0.16 * v1 + 0.08 * v2 - 0.07 * (warm - 0.5))
    img = np.stack([r, g, b], -1)
    return (img * 255 + 0.5).astype(np.uint8)


def bake_puddle():
    """irregular puddle mask + depth.  No circles: cellular boundaries warped by low frequency noise,
    so water collects along the road edges, joints and damaged areas."""
    h = w = MAT.SIZE_PUDDLE
    nx = 7
    F1, F2, ID = N.worley(h, w, nx, nx, 31337)
    # basins: inside the cells, deepest away from the boundaries
    basin = N.smooth(0.02, 0.28, F2 - F1)
    warp = N.bnoise(h, w, w * 0.18, w * 0.18, 77) * 0.42
    basin = clamp01(basin + warp * basin)
    # long shallow sheets along one axis (road camber / drainage direction)
    sheet = clamp01(0.5 + 0.5 * N.bnoise(h, w, w * 0.55, w * 0.10, 78))
    m = clamp01(0.70 * basin + 0.35 * sheet * basin + 0.15 * N.smooth(0.35, 0.85, ID))
    m = N.smooth(0.75, 0.95, m)   # sparse: only genuine depressions hold standing water
    # rim of every puddle (the wet line the water leaves behind) from the mask gradient
    gx = np.roll(m, -1, 1) - np.roll(m, 1, 1)
    gy = np.roll(m, -1, 0) - np.roll(m, 1, 0)
    edge = clamp01((np.abs(gx) + np.abs(gy)) * 3.0)
    ripple = 0.5 + 0.5 * N.bnoise(h, w, 6.0, 6.0, 79)
    depth = clamp01(m * 0.85 + 0.15 * ripple)
    out = np.stack([m, depth, edge], -1)
    return (out * 255 + 0.5).astype(np.uint8)


# ---------------------------------------------------------------------------
# road markings
# ---------------------------------------------------------------------------
def _paint_sheet(kind, **kw):
    h = w = MAT.SIZE_MARKING
    ss = 2                                                     # supersample for clean vector edges
    im = Image.new('L', (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    W, H = w * ss, h * ss

    def box(x0, y0, x1, y1):
        d.rectangle([x0 * W, y0 * H, x1 * W, y1 * H], fill=255)

    if kind == 'line':
        c = 0.5 - kw['width'] / 2
        box(0.0, c, 1.0, c + kw['width'])
    elif kind == 'double':
        g = kw['gap']
        c = 0.5 - g / 2 - kw['width']
        box(0.0, c, 1.0, c + kw['width'])
        c2 = 0.5 + g / 2
        box(0.0, c2, 1.0, c2 + kw['width'])
    elif kind == 'dash':
        c = 0.5 - kw['width'] / 2
        n = 4
        for i in range(n):
            x0 = i / n
            box(x0 + (kw['gap'] / n) * 0.5, c, x0 + kw['dash'] / n, c + kw['width'])
    elif kind == 'edge':
        box(0.0, 0.02, 1.0, 0.02 + kw['width'])
        box(0.0, 0.98 - kw['width'], 1.0, 0.98)
    elif kind == 'stop':
        c = 0.5 - kw['width'] / 2
        box(0.0, c, 1.0, c + kw['width'])
    elif kind == 'zebra':
        x = 0.0
        per = kw['width'] + kw['gap']
        while x < 1.0:
            box(x, 0.10, x + kw['width'], 0.90)
            x += per
    elif kind == 'hatch':
        ww = kw['width']
        for i in range(-4, 9):
            off = i / 6.0
            d.line([(off * W, 0), ((off + 0.5) * W, H)], fill=255, width=max(2, int(ww * W)))
            d.line([(off * W, 0), ((off - 0.5) * W, H)], fill=255, width=max(2, int(ww * W)))
        box(0.0, 0.0, 1.0, 0.045)
        box(0.0, 0.955, 1.0, 1.0)
    elif kind == 'word':
        try:
            f = ImageFont.truetype(FONT_BOLD, int(H * 0.42))
        except Exception:
            f = ImageFont.load_default()
        txt = kw['word']
        bb = d.textbbox((0, 0), txt, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.text(((W - tw) / 2 - bb[0], (H - th) / 2 - bb[1]), txt, font=f, fill=255)
        box(0.0, 0.80, 1.0, 0.80 + 0.09)
    elif kind == 'arrow':
        cx = W * 0.5
        u = lambda f: f * H                                # vertical units
        t = u(0.045)                                       # shaft half thickness
        which = kw['arrow']
        if which == 'straight':
            d.polygon([(cx - t, u(0.86)), (cx - t, u(0.40)), (cx - u(0.13), u(0.40)),
                       (cx, u(0.10)), (cx + u(0.13), u(0.40)), (cx + t, u(0.40)),
                       (cx + t, u(0.86))], fill=255)
        else:
            sign = 1.0 if which == 'right' else -1.0
            d.polygon([(cx - t, u(0.88)), (cx - t, u(0.52)), (cx - sign * u(0.10), u(0.52)),
                       (cx - sign * u(0.10), u(0.60)), (cx - sign * u(0.30), u(0.40)),
                       (cx - sign * u(0.10), u(0.20)), (cx - sign * u(0.10), u(0.30)),
                       (cx + t, u(0.30)), (cx + t, u(0.88))], fill=255)
    im = im.resize((w, h), Image.LANCZOS)
    return np.asarray(im, np.float32) / 255.0


def bake_marking(mk):
    """marking dict -> (rgba uint8 with alpha = surviving paint, rough uint8)"""
    h = w = MAT.SIZE_MARKING
    seed = abs(hash(mk['key'])) % 99991
    paint = _paint_sheet(mk['kind'], **{k: v for k, v in mk.items() if k in
                                        ('width', 'gap', 'dash', 'arrow', 'word')})
    # ---- wear: the paint erodes from the edges inwards (tyre scrub + weathering)
    er = clamp01(0.5 + 0.5 * N.bnoise(h, w, w * 0.09, w * 0.09, seed + 1))
    er2 = clamp01(0.5 + 0.5 * N.bnoise(h, w, w * 0.02, w * 0.02, seed + 2))
    thresh = 0.30 + 0.55 * mk['wear']
    survive = N.smooth(thresh - 0.22, thresh + 0.30, 0.62 * er + 0.38 * er2)
    # scuff streaks across the marking (tyre paths)
    scuff = streaks(h, w, 0.5, seed + 3, angle=np.pi / 2)
    survive = clamp01(survive * (1.0 - 0.55 * scuff))
    cov = clamp01(paint * (0.35 + 0.65 * survive))
    # ---- hairline cracking inside the paint
    cr, _ = crack_network(h, w, 0.6, seed + 40, scale=1.5)
    cov = clamp01(cov * (1.0 - 0.5 * cr * paint))
    # ---- dirt film over the paint
    dirt = clamp01(0.6 * blobs(h, w, 0.8, seed + 50, size=w * 0.5, soft=0.9) * mk['dirt'] * 2.0)
    cov = clamp01(cov * (1.0 - 0.45 * dirt))
    # ---- colour: paint yellows / greys with age, and the exposed edges are thinner (more transparent)
    col = np.array(mk['colour'], np.float32)
    age = clamp01(0.5 + 0.5 * N.bnoise(h, w, w * 0.07, w * 0.07, seed + 6))
    tint = np.array((1.0, 0.985, 0.94), np.float32)
    aged = col[None, None, :] * (0.82 + 0.18 * age)[..., None] * tint
    aged = aged * (1 - 0.35 * dirt[..., None]) + np.array((0.30, 0.28, 0.25), np.float32) * (0.35 * dirt[..., None])
    rgb = (clamp01(aged) * 255 + 0.5).astype(np.uint8)
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = rgb
    out[..., 3] = (cov * 255 + 0.5).astype(np.uint8)
    # paint roughness: worn paint is rougher, dirt is rougher still
    rough = clamp01(mk['rough'] + 0.18 * (1 - survive) * paint + 0.25 * dirt - 0.12 * (1 - dirt) * paint * 0.0)
    return out, (rough * 255 + 0.5).astype(np.uint8)


# ---------------------------------------------------------------------------
# rain / droplet maps (used by the screen-space rain shader and the 3D streaks)
# ---------------------------------------------------------------------------
def bake_droplets():
    """windshield droplets, DXT5nm packing: A = coverage, R = nx, G = ny (a real droplet lens, not
    a transparency map - the shader refracts the screen through the stored normal)."""
    h = w = 512
    F1, F2, ID = N.worley(h, w, 26, 26, 2024)
    # droplets sit inside the cells, sized by the cell id (many small, a few big)
    size = 0.10 + 0.30 * ID
    d = np.sqrt(np.clip(1 - (F1 / np.maximum(size, 1e-3)) ** 2, 0, 1))       # dome profile
    # the big ones slide downwards and leave a wet tail behind
    big = N.smooth(0.55, 0.80, ID) * d
    ker = np.exp(-np.linspace(0, 6, 24))
    ker = ker / ker.sum()
    sm = np.zeros_like(big)
    for k, kv in enumerate(ker):
        sm += np.roll(big, k, axis=0) * kv
    tail = N.smooth(0.05, 0.35, sm) * N.smooth(0.35, 0.65, ID)
    cov = clamp01(np.maximum(N.smooth(0.02, 0.30, d * (0.4 + 0.9 * ID)), tail * 0.75))
    # static film of micro droplets
    micro = N.smooth(0.45, 0.85, N.bnoise(h, w, 3.0, 3.0, 2025)) * 0.35
    cov = clamp01(cov + micro * (1 - cov))
    # height -> normal (droplet lens)
    hgt = clamp01(0.5 * cov + 0.5 * d * cov)
    nx, ny, _ = N.normal_from_height(hgt, 6.0)
    out = np.zeros((h, w, 4), np.uint8)
    out[..., 0] = ((nx * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)
    out[..., 1] = ((ny * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)
    out[..., 2] = 128
    out[..., 3] = (cov * 255 + 0.5).astype(np.uint8)
    return out


def bake_rain_streak():
    """a single falling drop streak, drawn as a line material (dxDrawMaterialLine3D)"""
    w, h = 32, 256
    x = np.arange(w)[None, :] / (w - 1) - 0.5
    y = np.arange(h)[:, None] / (h - 1)
    core = 1.0 - N.smooth(0.0, 0.16, np.abs(x) * 2)
    fade = np.sin(np.pi * np.clip(y, 0, 1)) ** 0.6
    head = N.smooth(0.72, 0.99, y) * 0.6
    a = clamp01(core * fade * (0.55 + head))
    rgb = np.ones((h, w, 3), np.float32) * 0.85
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = (rgb * 255).astype(np.uint8)
    out[..., 3] = (a * 255 + 0.5).astype(np.uint8)
    return out


def bake_splash():
    """ground splash / spray puff sprite"""
    h = w = 128
    y, x = np.mgrid[0:h, 0:w] / (h - 1) - 0.5
    r = np.sqrt(x * x + y * y) * 2
    a = (1 - N.smooth(0.35, 1.0, r)) * (0.6 + 0.4 * N.bnoise(h, w, 6, 6, 17))
    a = clamp01(a)
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = 200
    out[..., 3] = (a * 255 + 0.5).astype(np.uint8)
    return out
