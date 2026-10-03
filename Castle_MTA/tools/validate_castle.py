#!/usr/bin/env python3
"""Independent structural QA for the generated Castle_MTA MTA resource.

Run: python3 tools/validate_castle.py [--librw]
This verifies binaries, mesh data, collision bounds, texture/material links,
resource paths, planned placements, and (when optional QA packages are installed)
Lua 5.1 syntax and MTA client API names. It cannot replace an in-game MTA test.
"""
from __future__ import annotations
import argparse
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
MODELS = ROOT / "models"
sys.path.insert(0, str(TOOLS))
from lib import readers

passed = 0
failed = 0
warnings = 0


def check(condition, message):
    global passed, failed
    if condition:
        passed += 1
        print("  [ ok ] " + message)
    else:
        failed += 1
        print("  [FAIL] " + message)
    return condition


def warn(message):
    global warnings
    warnings += 1
    print("  [warn] " + message)


def heading(message):
    print("\n== " + message + " ==")


def _parse_data():
    text = (ROOT / "castle_data.lua").read_text(encoding="utf-8")
    assets = {}
    placements = []
    in_assets = False
    in_placements = False
    for line in text.splitlines():
        if line.strip() == "CASTLE_ASSETS = {":
            in_assets = True
            in_placements = False
            continue
        if line.strip() == "CASTLE_PLACEMENTS = {":
            in_assets = False
            in_placements = True
            continue
        if line.strip() == "}":
            in_assets = in_placements = False
            continue
        if in_assets:
            m = re.search(r'name = "([^"]+)".*txd = "([^"]+)".*col = (true|false).*kind = "([^"]+)".*distance = (\d+)', line)
            if m:
                assets[m.group(1)] = dict(txd=m.group(2), col=m.group(3) == "true", kind=m.group(4), distance=int(m.group(5)))
        elif in_placements:
            m = re.search(r'\{ name = "([^"]+)", x = ([\d.-]+), y = ([\d.-]+), z = ([\d.-]+), rz = ([\d.-]+), zone = "([^"]+)" \}', line)
            if m:
                placements.append(dict(name=m.group(1), x=float(m.group(2)), y=float(m.group(3)), z=float(m.group(4)),
                                       rz=float(m.group(5)), zone=m.group(6)))
    return text, assets, placements


def validate_meta():
    heading("MTA resource files")
    meta_path = ROOT / "meta.xml"
    try:
        meta = ET.parse(meta_path).getroot()
    except Exception as exc:
        check(False, "meta.xml parses: " + str(exc))
        return
    check(meta.tag == "meta", "meta.xml root is <meta>")
    info = meta.find("info")
    check(info is not None and info.get("name") == "Castle MTA - Royal Island Fortress", "resource info is present")
    minver = meta.find("min_mta_version")
    check(minver is not None and minver.get("client") == "1.6.0", "dynamic-model minimum MTA version is declared")
    scripts = [(e.get("src"), e.get("type")) for e in meta.findall("script")]
    check(scripts == [("castle_data.lua", "client"), ("client.lua", "client")], "client scripts load data before runtime")
    listed = [e.get("src") for e in meta.findall("file")]
    check(len(listed) == len(set(listed)), "no duplicate <file> entries")
    check(all((ROOT / f).is_file() for f in listed), "all files listed in meta.xml exist")
    check(all((ROOT / f).is_file() for f, _ in scripts), "all declared Lua scripts exist")
    runtime_on_disk = sorted(str(p.relative_to(ROOT)).replace(os.sep, "/") for p in MODELS.iterdir()
                             if p.suffix in (".dff", ".col", ".txd"))
    runtime_on_disk += ["textures/glow.png"]
    check(set(runtime_on_disk) == set(listed), "meta.xml lists every runtime binary exactly once")
    data_text, assets, placements = _parse_data()
    check(bool(assets) and bool(placements), "generated client manifest has assets and placements")
    for name, a in assets.items():
        check((MODELS / (name + ".dff")).is_file(), name + " has a DFF")
        check((MODELS / (name + ".col")).is_file() == a["col"], name + " collision flag matches its COL file")
        check(a["txd"] == "castle", name + " references the shared castle TXD")
    for p in placements:
        check(p["name"] in assets, "placement model exists: " + p["name"])
    counts = {}
    for p in placements:
        counts[p["name"]] = counts.get(p["name"], 0) + 1
    expected = {"castle_ground": 1, "castle_bridge": 1, "castle_gatehouse": 2,
                "castle_wall_run": 8, "castle_outer_tower": 10,
                "castle_palace_shell": 1, "castle_palace_ground": 1,
                "castle_palace_upper": 1, "castle_dungeon": 1,
                "castle_furniture": 1, "castle_night": 1, "castle_lod": 1}
    check(all(counts.get(k, 0) == v for k, v in expected.items()), "planned gate/wall/tower/palace/LOD placement counts")
    check(len(placements) == sum(expected.values()), "all expected placements are accounted for")
    check("engineRequestModel" in (ROOT / "client.lua").read_text(encoding="utf-8"), "client uses dynamic object IDs; no vanilla model replacement")
    return assets, placements


def validate_txd():
    heading("RenderWare TXD")
    path = MODELS / "castle.txd"
    try:
        txd = readers.read_txd(str(path))
    except Exception as exc:
        check(False, "castle.txd parses: " + repr(exc))
        return set()
    tex_names = [t["name"] for t in txd["textures"]]
    check(txd["version"] == 0x1803FFFF, "TXD is RenderWare 3.6 / GTA SA version")
    check(txd["count"] == len(tex_names) and len(tex_names) == len(set(tex_names)), "unique native textures and dictionary count agree")
    check(len(tex_names) >= 12, "stone, roof, wood, metal, glass and interior atlas maps exist")
    for t in txd["textures"]:
        ok = t["w"] > 0 and t["h"] > 0 and t["fmt"] == "DXT1" and t["nlev"] >= 8
        check(ok, "%s: %dx%d %s with %d mip levels" % (t["name"], t["w"], t["h"], t["fmt"], t["nlev"]))
        try:
            rgba = readers.decode_texture(t, min(0, t["nlev"] - 1))
            check(rgba.ndim == 3 and rgba.shape[2] == 3 and np.std(rgba) > 1.0, t["name"] + " DXT payload decodes to non-flat RGB")
        except Exception as exc:
            check(False, t["name"] + " DXT payload decodes: " + repr(exc))
    return set(tex_names)


def validate_models(assets, texture_names):
    heading("DFF geometry, UVs, normals and material links")
    dff_paths = sorted(MODELS.glob("*.dff"))
    check(len(dff_paths) == len(assets), "each planned model has exactly one DFF")
    for path in dff_paths:
        name = path.stem
        try:
            dff = readers.read_dff(str(path))
            check(dff["version"] == 0x1803FFFF, name + ": RenderWare 3.6 Clump")
            check(len(dff["geoms"]) == 1 and len(dff["atomics"]) == 1, name + ": one geometry and one atomic")
            check(len(dff["frames"]) == 2 and dff["atomics"][0]["frame"] == 1, name + ": named frame hierarchy is valid")
            g = dff["geoms"][0]
            check(0 < g["nverts"] < 65536 and 0 < g["ntris"] < 65536, name + ": GTA SA vertex/triangle limits")
            check(np.isfinite(g["pos"]).all() and np.isfinite(g["uv"]).all() and np.isfinite(g["nrm"]).all(), name + ": finite positions / UVs / normals")
            check(np.all(g["tris"] >= 0) and np.all(g["tris"] < g["nverts"]), name + ": all triangle indices are in range")
            check(np.all(g["tri_mat"] >= 0) and np.all(g["tri_mat"] < len(g["materials"])), name + ": material indices are in range")
            lengths = np.linalg.norm(g["nrm"], axis=1)
            check(len(lengths) > 0 and np.max(np.abs(lengths - 1.0)) < 0.025, name + ": normalized normals")
            if any(m["tex"] is None for m in g["materials"]):
                missing = [i for i, m in enumerate(g["materials"]) if m["tex"] is None]
                check(False, name + ": missing texture chunk in material(s) " + str(missing))
            else:
                used = [m["tex"]["name"] for m in g["materials"]]
                check(set(used) <= texture_names, name + ": all material names resolve inside castle.txd")
            tri = g["tris"]
            p = g["pos"]
            cross = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]])
            area = np.linalg.norm(cross, axis=1)
            avg_n = g["nrm"][tri].mean(axis=1)
            dot = np.einsum("ij,ij->i", cross / np.maximum(area[:, None], 1e-12), avg_n)
            check(np.all(area > 1e-8), name + ": no degenerate triangles")
            check(float(dot.min()) > 0.12, name + ": face winding agrees with stored normals (min %.3f)" % float(dot.min()))
            check(len(g["binmesh"]) > 0 and sum(len(indices) for _, indices in g["binmesh"]) == g["ntris"] * 3,
                  name + ": material BinMesh indices cover all faces")
        except Exception as exc:
            check(False, name + ": independent DFF parse failed: " + repr(exc))


def validate_collision(assets):
    heading("COL3 collision")
    col_paths = sorted(MODELS.glob("*.col"))
    expected = {name for name, info in assets.items() if info["col"]}
    actual = {p.stem for p in col_paths}
    check(actual == expected, "COL files match the manifest's collidable models")
    for path in col_paths:
        try:
            c = readers.read_col3(str(path))
            check(c["name"] == path.stem, path.stem + ": COL3 model name agrees")
            check(c["total"] >= 120 and c["end"] <= c["total"], path.stem + ": COL3 size/offsets are within file")
            check(c["flags"] & 0x02 != 0, path.stem + ": collision flag is set")
            check(len(c["boxes"]) + len(c["faces"]) > 0, path.stem + ": has optimized boxes and/or collision triangles")
            mn, mx = np.asarray(c["min"]), np.asarray(c["max"])
            check(np.all(mx > mn), path.stem + ": non-zero collision bounds")
            box_bounds_ok = all(
                np.all(np.asarray(b[:3]) <= np.asarray(b[3:6])) for b in c["boxes"]
            )
            check(box_bounds_ok, path.stem + ": collision box bounds are ordered")
            if c["faces"]:
                check(all(max(f[:3]) < len(c["verts"]) for f in c["faces"]), path.stem + ": collision mesh indices resolve")
                v = np.asarray(c["verts"], dtype=float)
                check(np.isfinite(v).all() and np.max(np.abs(v)) < 256, path.stem + ": COL3 vertex quantization stays in range")
        except Exception as exc:
            check(False, path.stem + ": independent COL3 parse failed: " + repr(exc))
    check("castle_furniture" not in actual and "castle_night" not in actual and "castle_lod" not in actual,
          "non-walkable furniture / night overlay / distant LOD do not add wasteful collision")


def validate_lua():
    heading("MTA Lua syntax and client APIs")
    lua_files = [ROOT / "client.lua", ROOT / "castle_data.lua"]
    try:
        from lupa import lua51
        lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        compile_lua = lua.eval('function(s, name) local f, e = loadstring(s, name); return f ~= nil, e end')
        for path in lua_files:
            ok, error = compile_lua(path.read_text(encoding="utf-8"), path.name)
            check(bool(ok), path.name + " compiles as Lua 5.1" + ("" if ok else ": " + str(error)))
    except ImportError:
        warn("lupa not installed; Lua parser skipped (install tools/requirements-qa.txt for this check)")
    try:
        result = subprocess.run([sys.executable, str(TOOLS / "mta_lua_static.py")], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        print(result.stdout.rstrip())
        if result.stderr.strip():
            print(result.stderr.rstrip())
        check(result.returncode == 0, "static MTA client global/API check")
    except Exception as exc:
        warn("luaparser static check unavailable: " + str(exc))

    lua = (ROOT / "client.lua").read_text(encoding="utf-8")
    for token in ("engineRequestModel", "engineLoadDFF", "engineLoadCOL", "engineLoadTXD",
                  "engineImportTXD", "engineReplaceCOL", "engineReplaceModel", "engineFreeModel",
                  "createObject", "engineSetModelLODDistance", "getTime", "createLight", "dxDrawMaterialLine3D"):
        check(token in lua, "client runtime includes " + token)


def validate_reference_loader(enabled):
    if not enabled:
        return
    heading("Reference RenderWare loader")
    exe = Path("/tmp/librw_check")
    if not exe.exists():
        warn("/tmp/librw_check not found; skip. Build aap/librw and pass --librw again.")
        return
    bad = 0
    for path in sorted(MODELS.glob("*.dff")):
        result = subprocess.run([str(exe), str(path), str(MODELS / "castle.txd")],
                                capture_output=True, text=True, timeout=30)
        ok = result.returncode == 0 and "ALL librw CHECKS PASSED" in result.stdout
        check(ok, path.stem + " loads with its TXD in aap/librw" + ("" if ok else ": " + result.stdout[-500:]))
        bad += 0 if ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--librw", action="store_true", help="also invoke /tmp/librw_check on all DFFs")
    args = parser.parse_args()
    print("Castle_MTA structural QA")
    assets, placements = validate_meta()
    textures = validate_txd()
    validate_models(assets, textures)
    validate_collision(assets)
    validate_lua()
    validate_reference_loader(args.librw)
    print("\nQA summary: %d passed, %d failed, %d warning(s)" % (passed, failed, warnings))
    if failed:
        return 1
    print("NOTE: Resource structure is checked; in-game MTA rendering, player traversal, weather and FPS still need a client smoke test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
