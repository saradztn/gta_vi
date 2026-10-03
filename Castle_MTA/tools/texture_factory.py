"""Deterministic, tileable texture set for the Castle_MTA resource.

Generated maps are intentionally compact and DXT1/mipmap friendly for SA/MTA.
"""
from pathlib import Path
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 512


def _noise(seed, size=SIZE, strength=1.0):
    rng = np.random.default_rng(seed)
    coarse = rng.normal(0.0, 1.0, (max(2, size // 16), max(2, size // 16))).astype(np.float32)
    img = Image.fromarray(np.uint8(np.clip(coarse * 32 + 128, 0, 255)), "L").resize((size, size), Image.Resampling.BICUBIC)
    low = (np.asarray(img, dtype=np.float32) - 128.0) / 32.0
    fine = rng.normal(0.0, 1.0, (size, size)).astype(np.float32)
    return (low * 1.6 + fine * 0.32) * strength


def _rgb_noise(base, seed, amount=9, size=SIZE):
    base = np.array(base, dtype=np.float32).reshape(1, 1, 3)
    n = _noise(seed, size, 1.0)[..., None]
    rng = np.random.default_rng(seed + 91)
    chroma = rng.normal(0.0, amount * 0.18, (size, size, 3)).astype(np.float32)
    return np.uint8(np.clip(base + n * amount + chroma, 0, 255))


def _stone(seed, base, mortar, block_noise=13):
    im = Image.fromarray(_rgb_noise(base, seed, block_noise), "RGB")
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    row_h = 64
    for row, y in enumerate(range(0, SIZE, row_h)):
        d.line((0, y, SIZE - 1, y), fill=mortar, width=3)
        widths = []
        remain = SIZE
        while remain > 0:
            if remain < 118:
                w = remain
            else:
                w = min(remain, rng.choice((68, 76, 84, 92, 100, 108, 116)))
            widths.append(w)
            remain -= w
        offset = -((row * 43) % SIZE)
        x = offset
        for bi, w in enumerate(widths):
            x0, x1 = x + 2, x + w - 2
            y0, y1 = y + 2, min(SIZE - 1, y + row_h - 2)
            shade = rng.randint(-17, 17)
            c = tuple(max(0, min(255, int(v + shade))) for v in base)
            if x1 >= 0 and x0 < SIZE:
                d.rectangle((x0, y0, x1, y1), fill=c)
                # chipped, hand-cut edges: a thin cool shadow and warm upper bevel
                d.line((x0, y0, x1, y0), fill=tuple(max(0, min(255, q + 17)) for q in c), width=1)
                d.line((x0, y0, x0, y1), fill=tuple(max(0, min(255, q + 7)) for q in c), width=1)
                d.line((x0, y1, x1, y1), fill=tuple(max(0, min(255, q - 19)) for q in c), width=2)
                # small pits/scratches, subtle after DXT compression
                for _ in range(9):
                    px = rng.randint(max(0, x0), min(SIZE - 1, x1))
                    py = rng.randint(y0, y1)
                    if rng.random() < 0.7:
                        d.ellipse((px, py, px + 1, py + 1), fill=tuple(max(0, q - 20) for q in c))
            x += w
        d.line((0, y + row_h - 1, SIZE - 1, y + row_h - 1), fill=mortar, width=2)
    # a subtle, tileable moss/weather veil
    arr = np.asarray(im, dtype=np.float32).copy()
    weather = np.maximum(0.0, np.sin(np.arange(SIZE, dtype=np.float32)[:, None] / 39.0 + seed) * 0.5 + 0.5)
    mask = np.clip((_noise(seed + 500, SIZE) + 0.7) * 0.035 * weather, 0.0, 0.12)
    moss = np.array([63.0, 78.0, 54.0], dtype=np.float32)
    arr = arr * (1 - mask[..., None]) + moss * mask[..., None]
    # Fine grain is added after the masonry pass so faces do not look like flat rectangles.
    arr += _noise(seed + 31, SIZE)[..., None] * 2.2
    return Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB")


def _roof(seed=21):
    im = Image.fromarray(_rgb_noise((68, 77, 91), seed, 8), "RGB")
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    sh = 48
    for row, y in enumerate(range(0, SIZE, sh)):
        off = -((row % 2) * 37)
        x = off
        while x < SIZE:
            w = rng.choice((54, 62, 70, 78))
            x0, x1 = x + 2, x + w - 2
            y0, y1 = y + 2, min(SIZE - 1, y + sh - 1)
            shade = rng.randint(-13, 13)
            col = tuple(max(0, min(255, v + shade)) for v in (68, 77, 91))
            d.rounded_rectangle((x0, y0, x1, y1 + 4), radius=8, fill=col)
            d.line((x0 + 4, y0 + 2, x1 - 4, y0 + 2), fill=tuple(min(255, v + 24) for v in col), width=2)
            d.line((x0 + 1, y1, x1 - 2, y1), fill=tuple(max(0, v - 22) for v in col), width=2)
            x += w
    return im


def _wood(seed=33):
    im = Image.fromarray(_rgb_noise((91, 58, 36), seed, 9), "RGB")
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    x = 0
    while x < SIZE:
        w = rng.choice((54, 64, 72, 88, 96))
        d.line((x, 0, x, SIZE - 1), fill=(55, 39, 29), width=3)
        d.line((x + 3, 0, x + 3, SIZE - 1), fill=(125, 82, 47), width=1)
        for y in range(18, SIZE, 54):
            kx = min(SIZE - 2, x + w // 2 + rng.randint(-5, 5))
            d.ellipse((kx - 8, y - 4, kx + 8, y + 4), outline=(68, 46, 32), width=2)
            d.ellipse((kx - 3, y - 2, kx + 3, y + 2), outline=(130, 89, 51), width=1)
        x += w
    return im


def _iron(seed=44):
    im = Image.fromarray(_rgb_noise((47, 50, 52), seed, 5), "RGB")
    d = ImageDraw.Draw(im)
    for y in range(0, SIZE, 64):
        d.line((0, y, SIZE - 1, y), fill=(31, 34, 36), width=2)
        d.line((0, y + 2, SIZE - 1, y + 2), fill=(76, 76, 72), width=1)
    for y in range(18, SIZE, 64):
        for x in range(18, SIZE, 64):
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(90, 80, 65), outline=(25, 28, 29))
    rng = random.Random(seed)
    for _ in range(80):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        d.line((x, y, x + rng.randrange(-14, 15), y + rng.randrange(3, 22)), fill=(79, 64, 49), width=1)
    return im


def _marble(seed=55):
    im = Image.fromarray(_rgb_noise((176, 162, 140), seed, 6), "RGB")
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    for _ in range(22):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        pts = [(x, y)]
        for k in range(8):
            x += rng.randint(-22, 22)
            y += rng.randint(20, 44)
            pts.append((x, y))
        col = rng.choice(((127, 119, 107), (202, 188, 165), (139, 130, 117)))
        d.line(pts, fill=col, width=rng.choice((1, 2)))
    return im.filter(ImageFilter.GaussianBlur(0.6))


def _carpet(seed=66):
    im = Image.new("RGB", (SIZE, SIZE), (89, 18, 27))
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    # woven ground and a repeated gold border
    for y in range(0, SIZE, 4):
        shade = rng.randint(-5, 5)
        d.line((0, y, SIZE, y), fill=(max(0, 89 + shade), max(0, 18 + shade), max(0, 27 + shade)))
    gold = (174, 132, 66)
    d.rectangle((13, 13, 498, 498), outline=gold, width=5)
    d.rectangle((23, 23, 488, 488), outline=(112, 78, 45), width=2)
    for x in range(35, 490, 42):
        d.polygon(((x, 27), (x + 8, 38), (x, 49), (x - 8, 38)), fill=gold)
        d.polygon(((x, 485), (x + 8, 474), (x, 463), (x - 8, 474)), fill=gold)
    for y in range(65, 470, 42):
        d.polygon(((27, y), (38, y + 8), (49, y), (38, y - 8)), fill=gold)
        d.polygon(((485, y), (474, y + 8), (463, y), (474, y - 8)), fill=gold)
    for x in range(75, 450, 50):
        for y in range(75, 450, 50):
            d.line((x - 9, y, x, y - 10, x + 9, y, x, y + 10, x - 9, y), fill=(130, 75, 45), width=2)
    return im


def _cloth(seed=77):
    im = Image.new("RGB", (SIZE, SIZE), (114, 20, 32))
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    for x in range(0, SIZE, 5):
        d.line((x, 0, x, SIZE), fill=(124 + rng.randrange(-8, 9), 24, 34), width=1)
    for y in range(18, SIZE, 80):
        for x in range(18, SIZE, 80):
            d.polygon(((x, y - 10), (x + 10, y), (x, y + 10), (x - 10, y)), fill=(195, 157, 83))
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(220, 194, 130))
    return im


def _gold(seed=89):
    im = Image.fromarray(_rgb_noise((184, 141, 63), seed, 7), "RGB")
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    for y in range(0, SIZE, 32):
        shade = rng.randint(-12, 12)
        d.line((0, y, SIZE - 1, y), fill=(max(0, 184 + shade), max(0, 141 + shade), max(0, 63 + shade)), width=2)
    for _ in range(70):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        d.line((x, y, x + rng.randrange(-18, 19), y + rng.randrange(2, 18)), fill=(214, 178, 91), width=1)
    return im


def _glass(seed=88):
    im = Image.new("RGB", (SIZE, SIZE), (25, 40, 58))
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    cell = 64
    colors = [(42, 69, 94), (65, 50, 73), (41, 77, 80), (88, 65, 42), (34, 52, 81)]
    for y in range(0, SIZE, cell):
        for x in range(0, SIZE, cell):
            c = rng.choice(colors)
            d.rectangle((x + 4, y + 4, x + cell - 4, y + cell - 4), fill=c, outline=(112, 101, 82), width=3)
            d.line((x + 6, y + 7, x + cell - 8, y + 7), fill=tuple(min(255, q + 28) for q in c), width=2)
            d.polygon(((x + cell // 2, y + 14), (x + cell - 14, y + cell // 2), (x + cell // 2, y + cell - 14), (x + 14, y + cell // 2)), outline=(150, 125, 77))
    return im


def _glow_window(seed=99):
    im = Image.new("RGB", (256, 256), (255, 178, 78))
    d = ImageDraw.Draw(im)
    # Deep amber edge and a dark lead lattice reads as a lit, inset window at night.
    d.rectangle((7, 7, 248, 248), fill=(252, 174, 74), outline=(255, 222, 142), width=8)
    d.rectangle((17, 17, 238, 238), outline=(146, 75, 30), width=8)
    d.line((128, 16, 128, 239), fill=(100, 62, 39), width=9)
    d.line((16, 128, 239, 128), fill=(100, 62, 39), width=9)
    d.ellipse((100, 100, 156, 156), fill=(255, 215, 113), outline=(124, 66, 31), width=5)
    return im


def _rock(seed=111):
    arr = _rgb_noise((79, 78, 72), seed, 22)
    im = Image.fromarray(arr, "RGB")
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    for _ in range(120):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        length = rng.randrange(5, 30)
        col = rng.choice(((46, 47, 46), (112, 105, 91), (66, 78, 69), (129, 119, 104)))
        d.line((x, y, x + rng.randint(-length, length), y + rng.randint(-length, length)), fill=col, width=1)
    return im


def _grass(seed=122):
    arr = _rgb_noise((47, 69, 42), seed, 11)
    im = Image.fromarray(arr, "RGB")
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    for _ in range(900):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        c = rng.choice(((73, 91, 51), (34, 55, 34), (103, 104, 57)))
        d.line((x, y, x + rng.randint(-2, 2), y - rng.randint(2, 6)), fill=c, width=1)
    return im


def _water(seed=133):
    arr = _rgb_noise((37, 76, 89), seed, 5)
    im = Image.fromarray(arr, "RGB")
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    for _ in range(80):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        d.arc((x, y, x + rng.randrange(20, 90), y + rng.randrange(4, 18)), 195, 345, fill=(78, 127, 137), width=1)
    return im


def _make_glow_png(path):
    n = 128
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    r = np.sqrt(((xx - 63.5) / 63.5) ** 2 + ((yy - 63.5) / 63.5) ** 2)
    a = np.uint8(np.clip((1 - r) ** 2 * 205, 0, 205))
    rgba = np.zeros((n, n, 4), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 1] = 161
    rgba[..., 2] = 65
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(path)


def generate_textures(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    maps = {
        "c_stone": _stone(2, (130, 124, 112), (73, 73, 70), 15),
        "c_arch": _stone(3, (165, 151, 126), (95, 83, 68), 11),
        "c_roof": _roof(),
        "c_wood": _wood(),
        "c_iron": _iron(),
        "c_marble": _marble(),
        "c_carpet": _carpet(),
        "c_cloth": _cloth(),
        "c_glass": _glass(),
        "c_gold": _gold(),
        "c_glow": _glow_window(),
        "c_rock": _rock(),
        "c_grass": _grass(),
        "c_water": _water(),
    }
    for name, image in maps.items():
        image.save(out / (name + ".png"), optimize=True)
    _make_glow_png(out / "glow.png")
    return maps
