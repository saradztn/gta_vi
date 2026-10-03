# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# tools/preview.py - decodes the DDS files that were actually written into the resource and lays
# them out as labelled PNG contact sheets, so the generated art can be looked at without a game.
#
#     python3 tools/preview.py            -> _work/preview_materials.png, preview_marks.png, preview_shared.png
# -----------------------------------------------------------------------------
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from lib import dds

RES = os.path.abspath(os.path.join(HERE, '..', '..', 'resource', 'RoadRealism', 'textures'))
OUT = os.path.abspath(os.path.join(HERE, '..', '_work'))
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def sheet(items, path, cols=4, tile=256, label=16):
    """items: list of (title, HxWxC uint8)"""
    rows = (len(items) + cols - 1) // cols
    im = Image.new('RGB', (cols * tile, rows * (tile + label)), (18, 18, 20))
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype(FONT, 12)
    except Exception:
        f = ImageFont.load_default()
    for i, (title, arr) in enumerate(items):
        cx, cy = (i % cols) * tile, (i // cols) * (tile + label)
        t = Image.fromarray(arr[..., :3]).resize((tile, tile), Image.LANCZOS)
        im.paste(t, (cx, cy))
        d.text((cx + 4, cy + tile + 1), title, fill=(210, 225, 240), font=f)
    im.save(path)
    return path


def load(rel, chans=None):
    a = dds.decode_top(os.path.join(RES, rel))
    if chans:
        a = a[..., chans]
    return np.ascontiguousarray(a)


def gray3(a, ch):
    g = a[..., ch]
    return np.stack([g, g, g], -1)


def main():
    os.makedirs(OUT, exist_ok=True)
    # ---- materials: albedo + roughness + AO + contamination side by side
    mats = [
        ('asphalt_new', 'asphalt/asphalt_new.dds'),
        ('asphalt_mid', 'asphalt/asphalt_mid.dds'),
        ('asphalt_old', 'asphalt/asphalt_old.dds'),
        ('asphalt_worn', 'asphalt/asphalt_worn.dds'),
        ('asphalt_highway', 'asphalt/asphalt_highway.dds'),
        ('asphalt_rural', 'asphalt/asphalt_rural.dds'),
        ('asphalt_industrial', 'asphalt/asphalt_industrial.dds'),
        ('asphalt_junction', 'asphalt/asphalt_junction.dds'),
        ('asphalt_cracked', 'asphalt/asphalt_cracked.dds'),
        ('asphalt_oil', 'asphalt/asphalt_oil.dds'),
        ('asphalt_patched', 'asphalt/asphalt_patched.dds'),
        ('asphalt_tunnel', 'asphalt/asphalt_tunnel.dds'),
        ('asphalt_bridge', 'asphalt/asphalt_bridge.dds'),
        ('asphalt_dusty', 'asphalt/asphalt_dusty.dds'),
        ('asphalt_gravel', 'asphalt/asphalt_gravel.dds'),
        ('asphalt_carpark', 'asphalt/asphalt_carpark.dds'),
        ('asphalt_dock', 'asphalt/asphalt_dock.dds'),
        ('asphalt_runway', 'asphalt/asphalt_runway.dds'),
        ('asphalt_suburban', 'asphalt/asphalt_suburban.dds'),
        ('asphalt_tirewear', 'asphalt/asphalt_tirewear.dds'),
        ('asphalt_wet_track', 'asphalt/asphalt_wet_track.dds'),
        ('concrete_road', 'concrete/concrete_road.dds'),
        ('concrete_old', 'concrete/concrete_old.dds'),
        ('concrete_industrial', 'concrete/concrete_industrial.dds'),
        ('pavement_slab', 'pavement/pavement_slab.dds'),
        ('pavement_brick', 'pavement/pavement_brick.dds'),
        ('pavement_tile', 'pavement/pavement_tile.dds'),
        ('kerb_concrete', 'pavement/kerb_concrete.dds'),
        ('shoulder_dirt', 'shoulder/shoulder_dirt.dds'),
        ('shoulder_gravel', 'shoulder/shoulder_gravel.dds'),
    ]
    items = []
    for key, rel in mats:
        items.append((key + ' albedo', load(rel)))
    p1 = sheet(items, os.path.join(OUT, 'preview_materials.png'), cols=6, tile=200)
    # ---- masks of four representative materials: R rough, G ao, B damage, A contamination
    items = []
    for key in ('asphalt_mid', 'asphalt_worn', 'asphalt_oil', 'concrete_road'):
        m = load('roughness/%s_mask.dds' % key)
        items.append((key + ' rough (R)', gray3(m, 0)))
        items.append((key + ' ao (G)', gray3(m, 1)))
        items.append((key + ' damage (B)', gray3(m, 2)))
        items.append((key + ' contam (A)', gray3(m, 3)))
    p2 = sheet(items, os.path.join(OUT, 'preview_masks.png'), cols=4, tile=200)
    # ---- markings: paint colour with the alpha over a neutral asphalt grey
    base = load('asphalt/asphalt_mid.dds').astype(np.float32)
    items = []
    for rel in sorted(os.listdir(os.path.join(RES, 'markings'))):
        mk = load('markings/' + rel).astype(np.float32)
        a = mk[..., 3:4] / 255.0
        comp = (mk[..., :3] * a + base * (1 - a)).astype(np.uint8)
        items.append((rel[:-4], comp))
    p3 = sheet(items, os.path.join(OUT, 'preview_markings.png'), cols=4, tile=220)
    # ---- shared maps
    items = [
        ('detail normal (A=nx G=ny)', load('normals/detail_agg.dds')),
        ('detail rough (R)', gray3(load('detail/detail_agg.dds'), 0)),
        ('detail ao (G)', gray3(load('detail/detail_agg.dds'), 1)),
        ('detail height (B)', gray3(load('detail/detail_agg.dds'), 2)),
        ('micro normal', load('normals/detail_micro.dds')),
        ('macro variation', load('detail/macro.dds')),
        ('puddle mask (R)', gray3(load('puddles/puddle_mask.dds'), 0)),
        ('puddle depth (G)', gray3(load('puddles/puddle_mask.dds'), 1)),
        ('puddle rim (B)', gray3(load('puddles/puddle_mask.dds'), 2)),
    ]
    p4 = sheet(items, os.path.join(OUT, 'preview_shared.png'), cols=3, tile=256)
    for p in (p1, p2, p3, p4):
        print(p)


if __name__ == '__main__':
    main()
