# RoadRealism

A drop-in MTA:SA 1.6 resource that photorealistically upgrades the **original** San Andreas road
surfaces. It does not add a city, buildings, road geometry, map objects or collision — it only
replaces road **materials** and layers **effects** (wetness, reflections, rain, night response)
on top of the world that already ships with the game.

```
start RoadRealism
```

That is the whole installation. Copy this folder into
`server/mods/deathmatch/resources/` and start it.

---

## What it does

- **Replaces road materials only.** Every road surface keeps its original geometry, UVs,
  collision and position. Only the texture/shader bound to a road material name changes.
- **A physically-based material library.** 31 asphalt / concrete / pavement / shoulder families
  (new, medium, old, worn, highway, rural, industrial, concrete, bridge, tunnel, patched,
  cracked, oil-stained, tire-wear, muddy shoulder, dusty, gravel transition, …), each with an
  albedo map and a packed mask (roughness / AO / damage / contamination), plus shared detail
  normal, roughness, AO, height, micro- and macro-detail maps so tiling is never obvious.
- **Redesigned road markings.** 13 marking sheets (white/yellow lines, double lines, broken
  lines, stop lines, arrows, turn arrows, crosswalks, edge lines, hatching, highway markings)
  with faded paint, dirt, cracks, realistic roughness and retro-reflectivity at night.
- **Wet roads that react to rain.** Rain intensity drives a gradual wetness value (0.0 dry →
  1.0 soaked) that changes roughness, brightness, specular, reflection strength, colour and
  puddle coverage — not just a darkening filter.
- **Blurred, stretched, angle-dependent reflections** of street lights, headlights, traffic
  lights, neon, signs and sky on wet asphalt and markings. Never mirror-sharp.
- **Procedural irregular puddles** in depressions, edges, intersections and damaged/repaired
  asphalt, growing and shrinking with the rain.
- **Night response.** Lamps, headlights, neon and traffic lights read on the wet surface;
  markings are slightly retro-reflective. Nothing glows or blooms artificially.
- **A rain system** with world rain, screen rain, windshield/lens droplets, streaks, splashes
  and a matching wet-road response, all tied to the same intensity value.

## Two rendering layers (reliability first)

1. **Base layer (on by default, never depends on shaders).** A RenderWare TXD
   (`files/road_base.txd`) holds photographic, AI-generated asphalt / concrete / sidewalk /
   shoulder textures bound **under the original San Andreas texture names**. At start the
   resource scans `engineGetModelTextureNames` over the object model IDs and calls
   `engineImportTXD` on exactly the models that use a road surface. The original DFF geometry and
   COL collision are never touched, so the roads match San Andreas 100% in layout, UVs and
   collision — only the surface pixels are upgraded. This layer renders through the game's own
   pipeline, so it works on any driver.

2. **Effect layer (opt-in, `/roadfx 1-4`).** The PBR-style shader stack (wetness, reflections,
   rain, night response, grading) from `shaders/`. It is off by default (`/roadfx 0`) so a driver
   that cannot compile the shaders still shows correct upgraded roads; type `/roadfx 2` (or up to
   `4`) to add the full wet/reflection look. If a shader fails to compile, only that effect is
   disabled and the exact error is printed.

## What it deliberately does *not* do

- No new city, buildings, roads-as-objects, DFF geometry, extra map objects or COL changes.
- No recolouring or darkening of the original textures — these are genuinely new materials.
- No blanket "apply one shader to the whole world". Only whitelisted road materials are
  touched; buildings, vehicles, peds, vegetation, signs and interiors are left alone.

---

## Commands

| Command | Effect |
| --- | --- |
| `/roadtextures [filter]` | List discovered road textures and their material category |
| `/roadscan` | Re-scan the visible world for road textures |
| `/roadinfo <texture>` | Full detail for one texture (category, material, models, state) |
| `/roadreport save` | Write `road_texture_report.txt` into the client resource folder |
| `/roadapply <texture>` | Force-apply an ambiguous "review" texture |
| `/roadremove <texture>` | Restore one texture to its original look |
| `/roadreload` | Re-create every shader and texture set |
| `/roadquality low\|medium\|high\|ultra` | Switch the quality preset |
| `/roadrain <0-1>` | Set the rain intensity (also drives wetness) |
| `/roadwet <0-1>` | Override the surface wetness directly |
| `/roadfx <0-4>` | Effect level: 0 off, 1 materials, 2 +reflection, 3 +rain, 4 +grade |
| `/roaddebug <0-3>` | Debug overlay and console verbosity |

Admins also get `/roadrain <0-1>` and `/roadreloadall` on the server, which broadcast to every
player.

---

## How it stays inside the original world

Road textures are discovered at runtime with `engineGetVisibleTextureNames` and matched against
an **explicit whitelist** of real San Andreas road texture names (read out of the shipped TXDs),
plus Lua-pattern families (`road`, `asphalt`, `motorway`, `highway`, `pavement`, `concrete`,
`tar`, `street`, `lane`, `marking`, `crosswalk`, `bridge`, `tunnel`, …) and an explicit
**blacklist**. A texture is only ever replaced when it is positively identified as a road
surface. Everything else is reported by `/roadscan` but never modified.

Replacement is done with `engineApplyShaderToWorldTexture(shader, "<original texture name>")`.
A custom-shader fog term (`gFog` / `gFogColor`) keeps the replaced surfaces blending with the
distance fog exactly like the originals, and the shader outputs `IN.Diffuse.a` so vertex alpha
is preserved.

If a shader cannot be compiled on a given machine, **only that effect is disabled**, the exact
error is printed, and the resource falls back to importing new road textures through a TXD
(`files/road_fallback.txd`, 18 original texture names) so the roads still look upgraded.

---

## Structure

```
meta.xml
client.lua            materials, shaders, discovery, commands, lifecycle
reflect.lua           screen-space wet-road reflections
rain.lua              world/screen rain, droplets, streaks, splashes, wetness
server.lua            admin rain/reload broadcast
config/
  settings.lua        tunables (default quality, exposure, limits)
  materials.lua       ROAD_MATERIALS / ROAD_MARKINGS / ROAD_QUALITY / shader packs
  roads.lua           ROAD_TEXTURES whitelist, patterns, blacklist, fallback list
shaders/
  road.fx             ps_3_0 full road material (13 fetches, 10 samplers, 19 float4)
  wetroad.fx          ps_2_0 compatibility road material (7/7/16)
  reflection.fx       ps_2_0 blurred screen reflection
  rain.fx             ps_2_0 rain / droplets / streaks
  post.fx             ps_2_0 grade pass
textures/
  asphalt concrete pavement shoulder   albedo + packed masks
  markings                             marking sheets
  normals roughness detail             shared detail maps
  wet puddles                          wetness, puddle, droplet, streak, splash maps
files/road_fallback.txd
audio/rain_loop.wav
tools/
  texture_scanner.lua  runtime discovery + report data
  material_report.lua  /roadreport writer
```

## Performance

- Shaders and textures are created once and cached; a failed shader is cached as failed so it is
  never recompiled every frame.
- Textures load lazily and are shared across materials.
- Distance-based quality: four presets trade detail textures, parallax, screen-source size,
  reflection taps and rain particle counts.
- All pixel shaders stay within D3D9 limits (`road.fx` targets ps_3_0, everything else ps_2_0),
  use packed `float4` constant registers, and provide a lower-end fallback technique.

## Extending

Add a family by appending one entry to `ROAD_MATERIALS` in `config/materials.lua` (category,
roughness, wet roughness, F0, reflection, puddle, scales, albedo file, mask file, label) and, if
it is a new texture name, whitelist it in `config/roads.lua`. No code changes are required — the
discovery, shader and report systems pick it up automatically.

---

*Generated and verified by the pipeline in `source/` (see the repository README). Every shader is
type-checked with the Slang HLSL front-end and budget-checked against D3D9 limits, and the whole
client is exercised headlessly before release.*
