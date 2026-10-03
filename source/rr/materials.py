# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# materials.py - the ONE material database.  Everything else (the texture generator, the emitted
# config/materials.lua, the shader defaults, the validator) is derived from this table, so adding a
# material is a single edit here.
#
# Field meanings (all physical, no arbitrary "game" values):
#   base        sRGB albedo of clean, dry, dust-free aggregate mix (0..1).  Real asphalt is 0.05..0.14
#               linear (~0.25..0.40 sRGB); concrete 0.25..0.40 linear (~0.53..0.66 sRGB).
#   rough       perceptually linear roughness of the dry surface (0 = mirror, 1 = matte).
#   roughVar    amplitude of the per-texel roughness variation packed into the mask's R channel.
#   f0          normal-incidence reflectance (0.02 = asphalt/tar, 0.04 = concrete, 0.02 paint ~0.05).
#   wetRough    roughness of a fully flooded surface (water = 0.02, a thin film on aggregate ~0.08).
#   reflection  how strongly this surface shows the screen-space reflection when flooded.
#   puddle      puddle affinity: how easily water collects (drives the puddle mask threshold).
#   agg         aggregate size in texture units (1 = ~8 mm stones at the default world scale).
#   cracks / patches / oil / dirt / tire / pothole   damage + contamination amounts (0..1).
#   joints      0 none, 1 concrete slab joints, 2 asphalt expansion joints, 3 kerb / block pattern.
#   worldScale  metres covered by one albedo tile (the shader re-projects in world space).
#   detailScale detail tiles per albedo tile (micro detail is tiled much denser).
#   cat         asphalt | concrete | pavement | marking | shoulder | special
# -----------------------------------------------------------------------------

SIZE_ALBEDO = 512          # low frequency colour / damage - 512 is plenty, the detail maps carry the grain
SIZE_MASK = 512            # R = roughness, G = AO, B = damage, A = contamination (dirt / oil / rubber)
SIZE_DETAIL = 1024         # shared aggregate normal + ORM
SIZE_MICRO = 512           # shared fine grain normal
SIZE_MACRO = 512           # shared large scale colour / roughness variation
SIZE_PUDDLE = 1024         # shared irregular puddle mask
SIZE_MARKING = 512         # road marking sheets (alpha = paint coverage)


def mat(key, cat, label, base, rough, **kw):
    m = dict(key=key, cat=cat, label=label, base=base, rough=rough,
             roughVar=kw.pop('roughVar', 0.10), f0=kw.pop('f0', 0.02),
             wetRough=kw.pop('wetRough', 0.09), reflection=kw.pop('reflection', 0.80),
             puddle=kw.pop('puddle', 0.45), agg=kw.pop('agg', 1.0),
             cracks=kw.pop('cracks', 0.0), patches=kw.pop('patches', 0.0),
             oil=kw.pop('oil', 0.0), dirt=kw.pop('dirt', 0.0), tire=kw.pop('tire', 0.0),
             pothole=kw.pop('pothole', 0.0), joints=kw.pop('joints', 0),
             worldScale=kw.pop('worldScale', 4.0), detailScale=kw.pop('detailScale', 10.0),
             macro=kw.pop('macro', 1.0), normalScale=kw.pop('normalScale', 1.0),
             tint=kw.pop('tint', (1.0, 1.0, 1.0)), marking=kw.pop('marking', None),
             seed=kw.pop('seed', abs(hash(key)) % 100000))
    assert not kw, 'unknown material field(s): %s' % sorted(kw)
    return m


# ---------------------------------------------------------------- asphalt families (1 - 22)
ASPHALT = [
    mat('asphalt_new', 'asphalt', 'New dark asphalt (recently laid)', (0.295, 0.293, 0.298), 0.70,
        agg=0.9, roughVar=0.08, wetRough=0.07, reflection=0.95, puddle=0.25, dirt=0.03, tire=0.05),
    mat('asphalt_mid', 'asphalt', 'Medium grey asphalt (standard city road)', (0.360, 0.356, 0.350), 0.76,
        agg=1.0, dirt=0.12, tire=0.15, cracks=0.10, patches=0.05),
    mat('asphalt_old', 'asphalt', 'Old faded asphalt (UV bleached, oxidised)', (0.460, 0.452, 0.438), 0.84,
        agg=1.1, dirt=0.22, cracks=0.30, patches=0.20, tire=0.10, roughVar=0.14),
    mat('asphalt_worn', 'asphalt', 'Heavily worn asphalt (aggregate exposed)', (0.440, 0.430, 0.412), 0.88,
        agg=1.25, dirt=0.28, cracks=0.45, patches=0.30, tire=0.20, pothole=0.25, roughVar=0.16),
    mat('asphalt_highway', 'asphalt', 'Motorway asphalt (tyre polished wheel bands)', (0.320, 0.318, 0.315), 0.62,
        agg=0.95, dirt=0.10, tire=0.55, reflection=0.95, wetRough=0.055, puddle=0.20, joints=2),
    mat('asphalt_rural', 'asphalt', 'Rural single carriageway (coarse mix, dusty verges)', (0.420, 0.402, 0.372), 0.85,
        agg=1.35, dirt=0.35, cracks=0.35, patches=0.25, tire=0.15, roughVar=0.15),
    mat('asphalt_industrial', 'asphalt', 'Industrial road (oil soaked, heavily patched)', (0.330, 0.324, 0.312), 0.72,
        agg=1.15, oil=0.45, dirt=0.30, patches=0.45, cracks=0.30, tire=0.35, pothole=0.20, roughVar=0.18),
    mat('asphalt_bridge', 'asphalt', 'Bridge deck asphalt (expansion joints, grit)', (0.340, 0.336, 0.330), 0.68,
        agg=0.85, joints=2, dirt=0.16, tire=0.35, reflection=0.92, puddle=0.30),
    mat('asphalt_tunnel', 'asphalt', 'Tunnel asphalt (soot film, sodium lamp grime)', (0.300, 0.292, 0.276), 0.66,
        agg=0.9, dirt=0.34, tire=0.45, cracks=0.10, tint=(1.06, 1.0, 0.86), reflection=0.95, puddle=0.35),
    mat('asphalt_patched', 'asphalt', 'Asphalt with repair sections', (0.380, 0.374, 0.366), 0.78,
        agg=1.05, patches=0.60, cracks=0.25, dirt=0.20, tire=0.20, roughVar=0.17, puddle=0.55),
    mat('asphalt_cracked', 'asphalt', 'Cracked asphalt (fatigue / alligator cracking)', (0.420, 0.410, 0.396), 0.86,
        agg=1.1, cracks=0.80, patches=0.20, dirt=0.24, tire=0.15, pothole=0.15, roughVar=0.16, puddle=0.6),
    mat('asphalt_oil', 'asphalt', 'Junction asphalt (oil and fuel contamination)', (0.300, 0.294, 0.288), 0.68,
        agg=1.0, oil=0.75, dirt=0.26, tire=0.40, patches=0.15, roughVar=0.14, puddle=0.5,
        wetRough=0.04, reflection=1.0),
    mat('asphalt_tirewear', 'asphalt', 'Asphalt with rubber build-up (braking zones)', (0.290, 0.287, 0.283), 0.58,
        agg=0.95, tire=0.80, dirt=0.18, oil=0.15, reflection=0.95, wetRough=0.05),
    mat('asphalt_dusty', 'asphalt', 'Dust filmed asphalt (desert / dry season)', (0.520, 0.494, 0.440), 0.92,
        agg=1.1, dirt=0.60, cracks=0.25, tire=0.12, roughVar=0.14, tint=(1.05, 1.0, 0.90)),
    mat('asphalt_gravel', 'asphalt', 'Gravel transition road (surface dressing breaking up)', (0.550, 0.516, 0.462), 0.94,
        agg=1.9, dirt=0.50, cracks=0.40, tire=0.10, roughVar=0.20, normalScale=1.35, puddle=0.35),
    mat('asphalt_carpark', 'asphalt', 'Car park asphalt (faded bays, oil drips)', (0.400, 0.394, 0.384), 0.80,
        agg=1.05, oil=0.40, dirt=0.30, patches=0.25, cracks=0.20, tire=0.30, puddle=0.6),
    mat('asphalt_dock', 'asphalt', 'Dock / yard asphalt (steel dust, heavy loads)', (0.360, 0.354, 0.340), 0.82,
        agg=1.2, dirt=0.38, oil=0.30, patches=0.35, cracks=0.35, tire=0.40, pothole=0.30, roughVar=0.18),
    mat('asphalt_junction', 'asphalt', 'Intersection asphalt (stops, turns, rubber, oil)', (0.340, 0.335, 0.328), 0.70,
        agg=1.0, oil=0.35, dirt=0.24, tire=0.65, patches=0.15, cracks=0.20, puddle=0.55,
        wetRough=0.055, reflection=0.95),
    mat('asphalt_runway', 'asphalt', 'Airport apron / runway asphalt (grooved, rubber)', (0.300, 0.298, 0.294), 0.64,
        agg=0.85, tire=0.70, dirt=0.12, oil=0.10, joints=2, reflection=0.95, puddle=0.15),
    mat('asphalt_suburban', 'asphalt', 'Suburban street asphalt (light mix, kerb wear)', (0.420, 0.414, 0.402), 0.80,
        agg=1.0, dirt=0.20, cracks=0.20, patches=0.15, tire=0.20, puddle=0.5),
    mat('asphalt_freeway_edge', 'asphalt', 'Freeway shoulder / rumble strip asphalt', (0.400, 0.392, 0.378), 0.84,
        agg=1.3, dirt=0.40, cracks=0.30, tire=0.10, roughVar=0.17),
    mat('asphalt_wet_track', 'asphalt', 'Low lying asphalt (permanent damp track, moss at edges)', (0.320, 0.320, 0.310), 0.74,
        agg=1.05, dirt=0.30, tire=0.30, cracks=0.20, puddle=0.95, wetRough=0.05, reflection=1.0,
        tint=(0.95, 1.0, 0.97)),
]

# ---------------------------------------------------------------- concrete
CONCRETE = [
    mat('concrete_road', 'concrete', 'Concrete road (PCC slabs with joints)', (0.700, 0.690, 0.664), 0.82,
        agg=1.6, f0=0.04, roughVar=0.12, joints=1, dirt=0.22, cracks=0.20, patches=0.10,
        wetRough=0.14, reflection=0.62, puddle=0.30, worldScale=5.0, normalScale=0.8),
    mat('concrete_old', 'concrete', 'Old concrete road (stained, spalled)', (0.640, 0.620, 0.580), 0.88,
        agg=1.7, f0=0.04, roughVar=0.16, joints=1, dirt=0.38, cracks=0.40, patches=0.25,
        wetRough=0.16, reflection=0.55, puddle=0.40, worldScale=5.0, normalScale=0.8),
    mat('concrete_industrial', 'concrete', 'Industrial concrete yard (steel trowelled)', (0.620, 0.614, 0.594), 0.70,
        agg=1.2, f0=0.04, roughVar=0.10, joints=1, dirt=0.25, oil=0.20, tire=0.25,
        wetRough=0.11, reflection=0.75, puddle=0.45, worldScale=6.0),
]

# ---------------------------------------------------------------- pavements / kerbs
PAVEMENT = [
    mat('pavement_slab', 'pavement', 'Concrete sidewalk slabs', (0.700, 0.684, 0.650), 0.80,
        agg=1.4, f0=0.04, joints=3, dirt=0.30, cracks=0.20, roughVar=0.12,
        wetRough=0.13, reflection=0.65, puddle=0.35, worldScale=2.5, detailScale=8.0, normalScale=0.9),
    mat('pavement_brick', 'pavement', 'Block paved sidewalk / plaza', (0.600, 0.564, 0.528), 0.78,
        agg=0.7, f0=0.04, joints=3, dirt=0.32, cracks=0.10, roughVar=0.14,
        wetRough=0.12, reflection=0.70, puddle=0.30, worldScale=2.0, detailScale=6.0, normalScale=1.2),
    mat('pavement_tile', 'pavement', 'Grey paving tiles (downtown)', (0.580, 0.574, 0.560), 0.72,
        agg=0.9, f0=0.04, joints=3, dirt=0.26, roughVar=0.10,
        wetRough=0.10, reflection=0.78, puddle=0.30, worldScale=2.0, detailScale=6.0, normalScale=1.0),
    mat('kerb_concrete', 'pavement', 'Kerb / curb stone (granite, tyre polished)', (0.640, 0.630, 0.614), 0.62,
        agg=1.0, f0=0.04, dirt=0.28, tire=0.35, roughVar=0.10,
        wetRough=0.09, reflection=0.85, puddle=0.20, worldScale=1.5, detailScale=6.0),
]

# ---------------------------------------------------------------- shoulders / verges
SHOULDER = [
    mat('shoulder_dirt', 'shoulder', 'Muddy / dirt road shoulder', (0.420, 0.346, 0.258), 0.95,
        agg=2.2, f0=0.03, dirt=0.65, cracks=0.25, roughVar=0.16,
        wetRough=0.28, reflection=0.35, puddle=0.75, worldScale=3.0, detailScale=8.0, normalScale=1.4),
    mat('shoulder_gravel', 'shoulder', 'Gravel shoulder / transition', (0.520, 0.478, 0.424), 0.93,
        agg=2.6, f0=0.03, dirt=0.45, roughVar=0.18,
        wetRough=0.32, reflection=0.30, puddle=0.55, worldScale=2.5, detailScale=7.0, normalScale=1.6),
]

MATERIALS = ASPHALT + CONCRETE + PAVEMENT + SHOULDER

# ---------------------------------------------------------------- road markings
# Each marking sheet is painted over an asphalt base: alpha = surviving paint, RGB = aged paint colour.
# rough  = roughness of the paint itself (thermoplastic paint is rougher than polished asphalt).
# retro  = retroreflection strength (glass beads bounce headlight light back to the driver).
MARKINGS = [
    dict(key='mark_line_white', label='White lane line (solid)', colour=(0.86, 0.86, 0.83),
         rough=0.55, retro=0.9, wear=0.25, dirt=0.20, kind='line', width=0.10),
    dict(key='mark_line_yellow', label='Yellow centre line', colour=(0.83, 0.70, 0.16),
         rough=0.55, retro=0.9, wear=0.28, dirt=0.22, kind='line', width=0.10),
    dict(key='mark_double_white', label='Double white line', colour=(0.86, 0.86, 0.83),
         rough=0.55, retro=0.9, wear=0.25, dirt=0.20, kind='double', width=0.075, gap=0.10),
    dict(key='mark_double_yellow', label='Double yellow line', colour=(0.83, 0.70, 0.16),
         rough=0.55, retro=0.9, wear=0.28, dirt=0.22, kind='double', width=0.075, gap=0.10),
    dict(key='mark_broken_white', label='Broken (dashed) white lane line', colour=(0.86, 0.86, 0.83),
         rough=0.55, retro=0.9, wear=0.30, dirt=0.22, kind='dash', width=0.10, dash=0.42, gap=0.58),
    dict(key='mark_edge_white', label='White edge line', colour=(0.82, 0.82, 0.79),
         rough=0.58, retro=0.8, wear=0.40, dirt=0.30, kind='edge', width=0.09),
    dict(key='mark_stopline', label='Transverse stop line', colour=(0.87, 0.87, 0.84),
         rough=0.55, retro=0.85, wear=0.30, dirt=0.24, kind='stop', width=0.28),
    dict(key='mark_crosswalk', label='Pedestrian crossing (zebra bars)', colour=(0.88, 0.88, 0.85),
         rough=0.52, retro=0.8, wear=0.35, dirt=0.26, kind='zebra', width=0.085, gap=0.075),
    dict(key='mark_arrow_straight', label='Straight ahead arrow', colour=(0.87, 0.87, 0.84),
         rough=0.55, retro=0.9, wear=0.32, dirt=0.25, kind='arrow', arrow='straight'),
    dict(key='mark_arrow_left', label='Left turn arrow', colour=(0.87, 0.87, 0.84),
         rough=0.55, retro=0.9, wear=0.32, dirt=0.25, kind='arrow', arrow='left'),
    dict(key='mark_arrow_right', label='Right turn arrow', colour=(0.87, 0.87, 0.84),
         rough=0.55, retro=0.9, wear=0.32, dirt=0.25, kind='arrow', arrow='right'),
    dict(key='mark_stop_word', label='Painted STOP / slow text', colour=(0.87, 0.87, 0.84),
         rough=0.55, retro=0.85, wear=0.35, dirt=0.28, kind='word', word='STOP'),
    dict(key='mark_hatching', label='Hatched / chevron no-drive area', colour=(0.85, 0.85, 0.82),
         rough=0.55, retro=0.7, wear=0.35, dirt=0.28, kind='hatch', width=0.055),
]

# ---------------------------------------------------------------- shader quality presets
# Emitted verbatim into config/settings.lua so the client and the pipeline never disagree.
QUALITY = {
    'low': dict(road='shaders/wetroad.fx', post='shaders/rain.fx',
                detailTex=False, parallax=False, ssr=False, puddles=True,
                rainStreaks=90, rainDrops=False, screenW=320, screenH=200,
                reflectTaps=1, shadowless=True, label='Low (integrated / old GPU)'),
    'medium': dict(road='shaders/wetroad.fx', post='shaders/rain.fx',
                   detailTex=True, parallax=False, ssr=True, puddles=True,
                   rainStreaks=220, rainDrops=True, screenW=480, screenH=300,
                   reflectTaps=2, shadowless=True, label='Medium'),
    'high': dict(road='shaders/road.fx', post='shaders/rain.fx',
                 detailTex=True, parallax=True, ssr=True, puddles=True,
                 rainStreaks=520, rainDrops=True, screenW=640, screenH=400,
                 reflectTaps=3, shadowless=False, label='High (default)'),
    'ultra': dict(road='shaders/road.fx', post='shaders/rain.fx',
                  detailTex=True, parallax=True, ssr=True, puddles=True,
                  rainStreaks=900, rainDrops=True, screenW=960, screenH=600,
                  reflectTaps=4, shadowless=False, label='Ultra'),
}

# ---------------------------------------------------------------- global tuning (config/settings.lua)
SETTINGS = dict(
    # wetness integration - rain level drives target wetness, drying is exponential
    wetDryRate=0.028,        # wetness units recovered per second with no rain
    wetRiseRate=0.20,        # wetness units gained per second at rain level 1
    wetMin=0.0, wetMax=1.0,
    puddleFrom=0.35,         # wetness at which puddles start to form
    puddleFull=0.90,         # wetness at which puddles are fully formed
    # rain
    rainWeather=8,           # GTA weather id used when the rain system owns the weather (8 = rainstorm)
    rainWeatherDamp=7,       # ... and for a damp / overcast look
    rainOwnWeather=True,     # setWeather / setRainLevel are driven by this resource
    rainSound=True,
    rainVolume=0.55,
    # reflection
    reflectStrength=1.0,     # global multiplier for the screen space reflection
    reflectAnglePow=2.6,     # fresnel exponent - low viewing angles reflect much more
    reflectBlur=1.6,         # screen-space blur radius (pixels of the screen source)
    reflectStretch=2.4,      # vertical stretch of the reflected image
    # night
    nightRetro=1.35,         # retroreflection gain for road markings at night
    nightSpecBoost=1.25,     # extra specular response when wet at night
    exposure=1.0,
    # safety
    maxShaders=48,           # hard cap on simultaneously created shader elements
    scanInterval=4000,       # ms between background texture rescans
    scanPerStep=90,          # texture names examined per scan step (keeps frames smooth)
    applyPerStep=40,         # shaders applied per frame during startup
    lazyDistance=0,          # 0 = apply to every road texture, >0 = only within N m of the camera
    debug=False,
)

# ---------------------------------------------------------------- rain level -> wetness map (documented behaviour)
RAIN_TABLE = [
    (0.00, 0.00, 'completely dry'),
    (0.10, 0.15, 'slight moisture'),
    (0.30, 0.40, 'damp roads'),
    (0.50, 0.68, 'wet roads'),
    (0.80, 0.90, 'heavy rain'),
    (1.00, 1.00, 'extremely wet, standing water'),
]


def by_key(k):
    for m in MATERIALS:
        if m['key'] == k:
            return m
    raise KeyError(k)


def albedo_path(m):
    return 'textures/%s/%s.dds' % (m['cat'] if m['cat'] != 'shoulder' else 'shoulder', m['key'])


def mask_path(m):
    return 'textures/roughness/%s_mask.dds' % m['key']


def marking_path(k):
    return 'textures/markings/%s.dds' % k


if __name__ == '__main__':
    print('%d materials, %d markings, %d quality presets' % (len(MATERIALS), len(MARKINGS), len(QUALITY)))
    for c in ('asphalt', 'concrete', 'pavement', 'shoulder'):
        print('  %-9s %2d' % (c, sum(1 for m in MATERIALS if m['cat'] == c)))
