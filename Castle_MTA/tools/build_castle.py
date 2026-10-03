#!/usr/bin/env python3
"""Build the Castle_MTA resource: procedural meshes -> RenderWare DFF/TXD/COL3.

Run from this folder or any working directory:
    python3 tools/build_castle.py
Requirements: Python 3.10+, numpy, Pillow. The emitted binaries are GTA SA PC
RenderWare 3.6 assets (not renamed OBJ files); independent readers are in lib/.
"""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from lib import dxt, rwdff, rwtxd, colfile
from texture_factory import generate_textures
from castle_models import MODELS, PLACEMENTS, LIGHTS

MODEL_DIR = ROOT / "models"
TEXTURE_DIR = ROOT / "textures"
SOURCE_TEX = TEXTURE_DIR / "source"
REPORT = ROOT / "tools" / "build_report.json"


def _compact(mesh):
    """Deduplicate identical position/normal/UV triples; keep hard edges split."""
    pos = np.asarray(mesh.pos, dtype=np.float64).reshape(-1, 3)
    nrm = np.asarray(mesh.nrm, dtype=np.float64).reshape(-1, 3)
    uv = np.asarray(mesh.uv, dtype=np.float64).reshape(-1, 2)
    tris = np.asarray(mesh.tris, dtype=np.int64).reshape(-1, 3)
    labels = np.asarray(mesh.tri_mat, dtype=object)
    if len(pos) == 0 or len(tris) == 0:
        raise ValueError("empty render mesh: " + mesh.name)
    mapping = {}
    new_pos, new_nrm, new_uv = [], [], []
    remap = np.empty(len(pos), dtype=np.int64)
    for i, (p, n, t) in enumerate(zip(pos, nrm, uv)):
        key = (tuple(np.round(p, 5)), tuple(np.round(n, 5)), tuple(np.round(t, 6)))
        j = mapping.get(key)
        if j is None:
            j = len(new_pos)
            mapping[key] = j
            new_pos.append(p)
            new_nrm.append(n)
            new_uv.append(t)
        remap[i] = j
    tris = remap[tris]
    raw_tris = np.asarray(mesh.tris, dtype=np.int64).reshape(-1, 3)
    area = np.linalg.norm(np.cross(pos[raw_tris[:, 1]] - pos[raw_tris[:, 0]],
                                   pos[raw_tris[:, 2]] - pos[raw_tris[:, 0]]), axis=1)
    keep = area > 1e-8
    tris, labels = tris[keep], labels[keep]
    material_names = sorted(set(str(x) for x in labels.tolist()))
    mat_ids = {name: i for i, name in enumerate(material_names)}
    tri_mat = np.asarray([mat_ids[str(x)] for x in labels], dtype=np.int64)
    p = np.asarray(new_pos, dtype=np.float32)
    n = np.asarray(new_nrm, dtype=np.float32)
    u = np.asarray(new_uv, dtype=np.float32)
    if len(p) >= 65536:
        raise ValueError("%s exceeds GTA SA's 16-bit vertex index limit: %d" % (mesh.name, len(p)))
    if not np.isfinite(p).all() or not np.isfinite(n).all() or not np.isfinite(u).all():
        raise ValueError("non-finite vertex data in " + mesh.name)
    lengths = np.linalg.norm(n, axis=1)
    if len(lengths) and np.max(np.abs(lengths - 1.0)) > 0.03:
        raise ValueError("non-unit normals in %s (max deviation %.4f)" % (mesh.name, np.max(np.abs(lengths - 1))))
    return dict(pos=p, nrm=n, uv=u, tris=tris, tri_mat=tri_mat, materials=material_names)


def _collision(mesh, name, bounds):
    boxes = list(mesh.boxes)
    verts, faces, vmap = [], [], {}

    def vertex_id(point):
        q = tuple(int(round(float(c) * 128.0)) for c in point)
        if max(abs(c) for c in q) > 32767:
            raise ValueError("COL coordinate outside signed 16-bit range in %s: %s" % (name, point))
        if q not in vmap:
            vmap[q] = len(verts)
            verts.append(tuple(c / 128.0 for c in q))
        return vmap[q]

    for p0, p1, p2, surf in mesh.col_triangles:
        ids = (vertex_id(p0), vertex_id(p1), vertex_id(p2))
        if len(set(ids)) == 3:
            faces.append((ids[0], ids[1], ids[2], int(surf)))
    if len(boxes) > 65535 or len(faces) > 65535 or len(verts) >= 32767:
        raise ValueError("COL3 shape limit exceeded in %s (boxes=%d verts=%d faces=%d)" % (name, len(boxes), len(verts), len(faces)))
    col = colfile.build_col3(name, 1337, [], boxes, verts or None, faces or None, bounds=bounds)
    return col, dict(boxes=len(boxes), vertices=len(verts), faces=len(faces))


def _build_dff(name, g, emissive=False):
    materials = [dict(tex=mat, env=0.0, color=(255, 255, 255, 255), surface=(1.0, 0.0, 1.0)) for mat in g["materials"]]
    geom = dict(pos=g["pos"], nrm=g["nrm"], uv=g["uv"], tris=g["tris"], tri_mat=g["tri_mat"],
                dyn_light=not emissive)
    if emissive:
        geom["prelit"] = np.full((len(g["pos"]), 4), 255, dtype=np.uint8)
    frames = [dict(name=name, pos=(0.0, 0.0, 0.0), parent=-1),
              dict(name=name + "_geo", pos=(0.0, 0.0, 0.0), parent=0)]
    return rwdff.build_clump(frames, [geom], [(1, 0, False)], [materials])


def _write_textures():
    maps = generate_textures(SOURCE_TEX)
    txd_textures = []
    info = []
    for name in sorted(maps):
        img = maps[name].convert("RGB")
        arr = np.asarray(img, dtype=np.uint8)
        h, w = arr.shape[:2]
        chain = dxt.compress_chain(arr, "DXT1")
        txd_textures.append(dict(name=name, w=w, h=h, fmt="DXT1", chain=chain, alpha=False))
        info.append(dict(name=name, size=[w, h], mipLevels=len(chain), dxt="DXT1"))
    blob = rwtxd.build_txd(txd_textures)
    (MODEL_DIR / "castle.txd").write_bytes(blob)
    return info, len(blob)


def _write_data_lua():
    lines = [
        "-- Generated by tools/build_castle.py; edit CASTLE_ORIGIN in client.lua, not placements.",
        "CASTLE_ASSETS = {",
    ]
    for name in MODELS:
        collision = (MODEL_DIR / (name + ".col")).exists()
        kind = "night" if name == "castle_night" else ("lod" if name == "castle_lod" else "high")
        dist = 1550 if kind in ("lod", "night") else 420
        lines.append('    { name = "%s", txd = "castle", col = %s, kind = "%s", distance = %d },' %
                     (name, "true" if collision else "false", kind, dist))
    lines += ["}", "", "CASTLE_PLACEMENTS = {"]
    for name, x, y, z, rz, zone in PLACEMENTS:
        lines.append('    { name = "%s", x = %.3f, y = %.3f, z = %.3f, rz = %.1f, zone = "%s" },' %
                     (name, x, y, z, rz, zone))
    lines += ["}", "", "CASTLE_LIGHTS = {"]
    for x, y, z, radius, r, g, b in LIGHTS:
        lines.append("    { %.2f, %.2f, %.2f, %.2f, %d, %d, %d }," % (x, y, z, radius, r, g, b))
    lines += ["}", "", "CASTLE_BOUNDS = { minX = -122, maxX = 122, minY = -166, maxY = 102, minZ = -18, maxZ = 96 }"]
    (ROOT / "castle_data.lua").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_meta(model_names):
    root = ET.Element("meta")
    ET.SubElement(root, "info", {
        "author": "Castle_MTA Project", "name": "Castle MTA - Royal Island Fortress", "version": "1.0.0",
        "type": "script", "description": "Large walkable Gothic castle with exterior, palace floors, cellar, LOD and time-based lighting."
    })
    ET.SubElement(root, "min_mta_version", {"client": "1.6.0"})
    ET.SubElement(root, "script", {"src": "castle_data.lua", "type": "client"})
    ET.SubElement(root, "script", {"src": "client.lua", "type": "client"})
    for name in model_names:
        ET.SubElement(root, "file", {"src": "models/" + name + ".dff"})
        if (MODEL_DIR / (name + ".col")).exists():
            ET.SubElement(root, "file", {"src": "models/" + name + ".col"})
    ET.SubElement(root, "file", {"src": "models/castle.txd"})
    ET.SubElement(root, "file", {"src": "textures/glow.png"})
    ET.indent(root, space="    ")
    ET.ElementTree(root).write(ROOT / "meta.xml", encoding="utf-8", xml_declaration=True)


def main():
    t0 = time.time()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_TEX.mkdir(parents=True, exist_ok=True)
    TEXTURE_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/5] Generate tileable stone, slate, timber, metal, glass and interior maps...")
    tex_info, txd_bytes = _write_textures()
    print("      castle.txd: %.2f MB, %d maps" % (txd_bytes / 1048576, len(tex_info)))
    print("[2/5] Build planned castle meshes and RenderWare DFF / optimized COL3...")
    report_models = []
    model_names = list(MODELS)
    total_dff = total_col = total_vertices = total_triangles = 0
    for i, (name, builder) in enumerate(MODELS.items(), 1):
        mesh = builder()
        g = _compact(mesh)
        bounds = (g["pos"].min(axis=0), g["pos"].max(axis=0))
        dff = _build_dff(name, g, emissive=mesh.emissive)
        dff_path = MODEL_DIR / (name + ".dff")
        dff_path.write_bytes(dff)
        col_info = {"boxes": 0, "vertices": 0, "faces": 0}
        col_bytes = 0
        if mesh.boxes or mesh.col_triangles:
            col_blob, col_info = _collision(mesh, name, (bounds[0].tolist(), bounds[1].tolist()))
            (MODEL_DIR / (name + ".col")).write_bytes(col_blob)
            col_bytes = len(col_blob)
        report_models.append({
            "name": name, "vertices": int(len(g["pos"])), "triangles": int(len(g["tris"])),
            "materials": g["materials"], "dff_bytes": len(dff), "col_bytes": col_bytes,
            "collision": col_info, "bounds": [bounds[0].round(2).tolist(), bounds[1].round(2).tolist()],
            "emissive": mesh.emissive,
        })
        total_dff += len(dff); total_col += col_bytes
        total_vertices += len(g["pos"]); total_triangles += len(g["tris"])
        print("      %2d/%d %-24s %6d verts %6d tris %5d COL boxes %5.2f MB DFF" %
              (i, len(MODELS), name, len(g["pos"]), len(g["tris"]), col_info["boxes"], len(dff) / 1048576))
    print("[3/5] Emit placement manifest and a minimal MTA resource meta.xml...")
    _write_data_lua()
    _write_meta(model_names)
    # Restore complete texture source set into resource folder. PNG sources are not needed at runtime except glow.png.
    glow = Image.open(SOURCE_TEX / "glow.png").convert("RGBA")
    glow.save(TEXTURE_DIR / "glow.png", optimize=True)
    total_bytes = sum(p.stat().st_size for p in MODEL_DIR.iterdir() if p.is_file())
    report = {
        "project": "Castle_MTA", "format": "RenderWare 3.6 GTA SA / MTA:SA",
        "models": report_models, "textures": tex_info,
        "placement_count": len(PLACEMENTS), "dynamic_light_points": len(LIGHTS),
        "totals": {"vertices": total_vertices, "triangles": total_triangles, "dff_bytes": total_dff,
                   "col_bytes": total_col, "txd_bytes": txd_bytes, "model_folder_bytes": total_bytes},
        "build_seconds": round(time.time() - t0, 2),
        "validation_note": "Structural checks are separate; an MTA client is required for runtime rendering/play-test."
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("[4/5] Finished binary build: %d vertices, %d triangles, %.2f MB DFF, %.2f MB COL" %
          (total_vertices, total_triangles, total_dff / 1048576, total_col / 1048576))
    print("[5/5] Resource ready at: %s" % ROOT)
    print("      run: python3 tools/validate_castle.py")


if __name__ == "__main__":
    main()
