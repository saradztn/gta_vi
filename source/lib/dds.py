# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# dds.py - reader for the DDS files the pipeline writes (header + DXT levels).
# Used by validate.py (structure / format / mip chain) and by tools/preview.py (PNG contact sheet).
import struct
import numpy as np
from . import dxt

FOURCC = {0x31545844: 'DXT1', 0x33545844: 'DXT3', 0x35545844: 'DXT5'}


def read_dds(path):
    buf = open(path, 'rb').read()
    if buf[:4] != b'DDS ':
        raise ValueError('%s is not a DDS file' % path)
    size, flags, h, w, pitch, depth, mips = struct.unpack_from('<IIIIIII', buf, 4)
    if size != 124:
        raise ValueError('%s: header size %d' % (path, size))
    ddsize, ddflags, fourcc, rgbbit = struct.unpack_from('<II4sI', buf, 76)
    fmt = FOURCC.get(struct.unpack('<I', fourcc)[0], fourcc.decode('ascii', 'replace'))
    caps = struct.unpack_from('<IIIII', buf, 108)
    if not (caps[0] & 0x1000):
        raise ValueError('%s: DDSCAPS_TEXTURE is not set' % path)
    if mips > 1 and not (caps[0] & 0x400000):
        raise ValueError('%s: has %d mip levels but DDSCAPS_MIPMAP is not set' % (path, mips))
    p = 128
    levels = []
    for i in range(max(1, mips)):
        lw, lh = max(1, w >> i), max(1, h >> i)
        n = dxt.level_size(lw, lh, fmt)
        levels.append((lw, lh, buf[p:p + n]))
        p += n
    if p != len(buf):
        raise ValueError('%s: %d bytes of pixel data declared, %d present' % (path, p - 128, len(buf) - 128))
    return dict(w=w, h=h, fmt=fmt, mips=len(levels), levels=levels, flags=flags, size=len(buf),
                pitch=pitch, depth=depth, caps=caps)


def decode_top(path):
    """decode the largest mip level back to uint8 pixels"""
    d = read_dds(path)
    lw, lh, data = d['levels'][0]
    return dxt.decode(data, lw, lh, d['fmt'])


def channels(path):
    """per channel mean of the top level (0..1)"""
    a = decode_top(path).astype(np.float32) / 255.0
    return [float(x) for x in a.reshape(-1, a.shape[-1]).mean(0)]
