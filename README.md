# RoadRealism — build pipeline and resource

This repository contains **RoadRealism**, a production-ready MTA:SA 1.6 resource that
photorealistically upgrades the original San Andreas road surfaces, together with the Python
pipeline that generates and verifies it.

- **The finished, installable resource:** [`resource/RoadRealism/`](resource/RoadRealism) —
  copy it into `server/mods/deathmatch/resources/` and `start RoadRealism`.
  See [`resource/RoadRealism/README.md`](resource/RoadRealism/README.md) for what it does,
  the commands, and how it stays inside the original world.

## Repository layout

```
source.zip                 the reference material the resource was modelled on
source/
  build.py                 generate the whole resource (textures, TXD, audio, config, meta.xml)
  validate.py              full verification suite (run with --lua for the headless client)
  hlsl_check.py            HLSL linter + D3D9 budget checker + Slang type check
  rr/                      the material/texture database and bakers
    materials.py           MATERIALS (31) / MARKINGS (13) / QUALITY / SETTINGS / SHARED
    texgen.py              procedural bakers for every map
    scan_db.py             road-texture whitelist / review / blacklist (with provenance)
    pipeline.py            turns the database into files on disk
  lib/                     DDS / TXD / DXT / noise readers and writers
  tools/preview.py         decode the baked DDS into PNG contact sheets
  mta_stub_rr.lua          strict headless model of the MTA client/server API
  mta_lua_test_rr.py       boots the real Lua against that model and drives it
resource/RoadRealism/      the generated resource (the deliverable)
```

## Regenerating the resource

```bash
python source/build.py        # ~41 s -> resource/RoadRealism  (textures, TXD, audio, config, meta)
python source/validate.py     # structural + shader + texture + config checks
python source/validate.py --lua   # also boots the resource headlessly and drives every command
```

`build.py` bakes every texture from the database in `source/rr/`, writes the fallback TXD and the
rain audio, emits the `config/*.lua` tables (including the shader constant packs parsed straight
out of the `.fx` files) and writes `meta.xml`. Edit the database, re-run `build.py`.

## Verification

`validate.py` checks, and the suite currently reports **279 structural checks passing**:

- `meta.xml` lists every asset on disk exactly once, and every script in load order.
- Every Lua file parses, and every MTA function it calls exists in the 1.6 client/server API.
- The generated config loads in a clean Lua VM and is self-consistent (every whitelisted texture
  maps to a real material/marking, nothing is both whitelisted and banned, every Lua pattern is
  valid).
- All five shaders pass the HLSL linter, stay within D3D9 fetch/sampler/register budgets, and
  type-check under the Slang HLSL front-end.
- Every DDS is power-of-two, correctly compressed, with a full mip chain, and the channel ranges
  are sane (normal maps centred, asphalt dark, concrete lighter).
- The fallback TXD really contains the 18 original texture names.
- Total download size stays under 60 MB.

With `--lua` it additionally runs `mta_lua_test_rr.py`, which boots the **real** `client.lua`,
`rain.lua`, `reflect.lua` and tools against a strict MTA model and drives resource start, staged
shader application, every command, wetness integration, a forced shader-compile failure (the
fallback must take over) and resource stop (full cleanup) — **43 checks, zero handler/timer
errors**.

## Output

| | |
| --- | --- |
| Material textures | 81 DDS, ~23 MB, largest 1024 px |
| Rain overlays | 3 PNG (droplets, streak, splash) |
| Fallback TXD | 18 original texture names |
| Shaders | 5 (road, wetroad, reflection, rain, post) |
| Scripts | 9 Lua |
| Total | ~26 MB, download friendly |
