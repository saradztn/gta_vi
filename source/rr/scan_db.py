# Created by: Arena.ai Agent Mode (AI) - RoadRealism MTA:SA road overhaul
# -----------------------------------------------------------------------------
# scan_db.py - the road texture discovery database: whitelist / review / blacklist / patterns.
#
# Tier meanings
#   apply    definitely a road surface -> the material is applied automatically on resource start
#   review   looks like a road but the name is ambiguous ("BLOCK", "sjmhoodlawn41") -> reported by
#            /roadscan and only applied with /roadapply <name> (never silently)
#   ban      must never be touched even though it matches a road pattern (drains, fences, walls)
#
# WHITELIST PROVENANCE - the names below were read out of the shipped GTA San Andreas texture
# dictionaries listed on the Prineside GTA SA texture index (dev.prineside.com/en/gtasa_samp_game_
# texture/view/<txd>/), TXDs: roads_lawn, roads_law, roads_cunte, cs_roads, roadlan2, laeroads,
# freeway_las, road2sfe, tunnel_sfe, vgssroads.  The comment on each line is the TXD it was read
# from.  Anything not read from a real TXD lives in PATTERNS or REVIEW, never in WHITELIST.
# -----------------------------------------------------------------------------

# name (lower case) : (material key, marking key or None)
WHITELIST = {
    # ---- the generic Los Santos / statewide road surfaces
    'snpedtest1':              ('asphalt_mid', None),            # roads_lawn, roads_law, laeroads, freeway_las, roadlan2
    'dt_road':                 ('asphalt_mid', None),            # vgssroads, freeway_las
    'road1256':                ('asphalt_mid', None),            # vgssroads
    'roadnew4_256':            ('asphalt_suburban', None),       # roads_lawn, roads_cunte
    'greyground256':           ('asphalt_old', None),            # roads_lawn
    'plaintarmac1':            ('asphalt_mid', None),            # cs_roads, freeway_las
    'vegasroad1_256':          ('asphalt_mid', None),            # vgssroads
    'vegasroad3_256':          ('asphalt_old', None),            # vgssroads
    'sf_road5':                ('asphalt_mid', None),            # road2sfe, tunnel_sfe
    'paveb256':                ('asphalt_old', None),            # roads_cunte
    # ---- freeway / motorway tar sheets (they carry the lane paint)
    'tar_1line256hv':          ('asphalt_highway', 'mark_line_white'),     # cs_roads
    'tar_1line256hvblenddrt':  ('asphalt_highway', 'mark_line_white'),     # cs_roads
    'tar_1linefreewy':         ('asphalt_highway', 'mark_broken_white'),   # roads_lawn
    'tar_freewyleft':          ('asphalt_highway', 'mark_edge_white'),     # cs_roads
    'tar_freewyright':        ('asphalt_highway', 'mark_edge_white'),     # cs_roads
    'cos_hiwaymid_256':        ('asphalt_highway', 'mark_double_yellow'),  # laeroads, freeway_las
    'cos_hiwayout_256':        ('asphalt_highway', 'mark_edge_white'),     # laeroads, freeway_las
    'hiwaymidlle_256':         ('asphalt_highway', 'mark_double_yellow'),  # laeroads
    'laroad_centre1':          ('asphalt_mid', 'mark_double_yellow'),      # roads_lawn
    'laroad_offroad1':         ('shoulder_gravel', None),                  # roads_lawn, laeroads
    'roadsback01_la':          ('asphalt_rural', None),                    # laeroads
    'cuntroad01_law':          ('asphalt_rural', None),                    # roads_law
    # ---- junctions, crossings, stop lines
    'dt_road_stoplinea':       ('asphalt_junction', 'mark_stopline'),      # roads_lawn, vgssroads
    'crossing_law':            ('asphalt_junction', 'mark_crosswalk'),     # roads_lawn, roads_law, roadlan2, freeway_las, vgssroads
    'crossing2_law':           ('asphalt_junction', 'mark_crosswalk'),     # roads_law
    'crossing_law2':           ('asphalt_junction', 'mark_crosswalk'),     # vgssroads
    'sf_junction3':            ('asphalt_junction', 'mark_hatching'),      # road2sfe
    'sf_junction5':            ('asphalt_junction', 'mark_hatching'),      # road2sfe
    'sf_tramline2':            ('asphalt_mid', None),                      # road2sfe
    # ---- bridges
    'macbrij1_lae':            ('asphalt_bridge', None),                   # laeroads
    'macbrij2_lae':            ('asphalt_bridge', None),                   # laeroads
    'macbrij3_lae':            ('asphalt_bridge', None),                   # laeroads
    'macbrij4_lae':            ('asphalt_bridge', None),                   # laeroads
    # ---- concrete
    'concretegroundl1_256':    ('concrete_road', None),                    # freeway_las
    'concretenewb256':         ('concrete_road', None),                    # freeway_las
    'concretemanky':           ('concrete_old', None),                     # laeroads
    'heliconcrete':            ('concrete_industrial', None),              # vgssroads
    # ---- sidewalks / pavements / kerbs
    'newpavement':             ('pavement_slab', None),                    # roads_lawn
    'sidewalk4_lae':           ('pavement_slab', None),                    # roads_lawn
    'kbpavement_test':         ('pavement_slab', None),                    # roads_lawn, vgssroads
    'blendpavement2_256':      ('pavement_slab', None),                    # vgssroads
    'blendpavement2b_256':     ('pavement_slab', None),                    # vgssroads
    'vegaspavement2_256':      ('pavement_tile', None),                    # vgssroads
    'ws_nicepave':             ('pavement_tile', None),                    # roads_law
    'starpave_law':            ('pavement_brick', None),                   # roads_lawn
    'starpaveb_law':           ('pavement_brick', None),                   # roads_lawn
    'starpave_lawblend':       ('pavement_brick', None),                   # roads_lawn
    'sf_pave2':                ('pavement_slab', None),                    # road2sfe
    'sf_pave3':                ('pavement_slab', None),                    # road2sfe
    'sf_pave4':                ('pavement_tile', None),                    # road2sfe
    'sf_pave5':                ('pavement_tile', None),                    # road2sfe
    'sf_pave6':                ('pavement_slab', None),                    # road2sfe, tunnel_sfe
    'easykerb':                ('kerb_concrete', None),                    # freeway_las
    # ---- parking / industrial / docks
    'gm_lacarpark1':           ('asphalt_carpark', None),                  # roads_lawn
    'dockpave_256':            ('asphalt_dock', None),                     # roads_lawn, roads_law, freeway_las
    # ---- rural / desert / shoulders
    'desertgravelgrassroad':   ('asphalt_gravel', None),                   # roads_lawn, roads_cunte
    'desertstones256':         ('shoulder_gravel', None),                  # cs_roads
    'dirttracksgrass256':      ('shoulder_dirt', None),                    # cs_roads
    'pavebsand256':            ('asphalt_dusty', None),                    # cs_roads
    'pavebsand256grassblended': ('asphalt_dusty', None),                   # cs_roads
    'pavemiddirt_law':         ('shoulder_dirt', None),                    # roads_lawn, roads_law, freeway_las
    'stones256128':            ('shoulder_gravel', None),                  # laeroads
}

# ambiguous: reported by /roadscan, applied only on explicit request
REVIEW = {
    'block':                   ('asphalt_mid', None),        # vgssroads, laeroads - "BLOCK" is also a building word
    'block2':                  ('asphalt_mid', None),        # vgssroads
    'block2bb':                ('asphalt_mid', None),        # roads_law
    'sjmhoodlawn41':           ('asphalt_old', None),        # roads_lawn, laeroads, freeway_las
    'sjmhoodlawn42':           ('asphalt_old', None),        # laeroads, freeway_las
    'snpdwargrn1':             ('asphalt_old', None),        # laeroads, freeway_las
    'sidelatino1_lae':         ('pavement_slab', None),      # roads_lawn, roads_law
    'rufwaldock1':             ('asphalt_dock', None),       # laeroads
    'floor_tileone_256':       ('pavement_tile', None),      # roads_lawn (also used indoors)
    'concretewall22_256':      ('concrete_old', None),       # tunnel_sfe (tunnel wall, not a road surface)
    'backstageceiling1_128':   ('concrete_old', None),       # roads_lawn (ceiling)
    'whitetile_plain_hi':      ('pavement_tile', None),      # freeway_las
}

# never touch, even if a road pattern matches
BLACKLIST = [
    'ws_drain_small',          # storm drain grate (roads_lawn, roadlan2, laeroads)
    'lasjmfence1', 'metpat64', 'metal_stair_64h', 'scaff2flas', 'weewall256',
    'dockwall1', 'bow_stained_wall', 'airportwall_2_2', 'ws_fluorescent1',
    'cj_sheetmetal',           # vgssroads - metal sheet, matched only by accident
    'grasstype4', 'grasstype4_mudblend', 'grass_128hv', 'desgreengrass', 'forestfloor3',
    'newhedgea', 'hedgealphad1', 'obhilltex1',
]

# Ordered LUA PATTERNS (string.find, not regex - Lua has no alternation or lookahead) on the lower
# case texture name; the first hit wins.  They only ever produce a *suggestion*: the client applies
# a pattern hit only when SETTINGS.autoApplyPatterns is true (default false), so an unknown texture
# can never silently wreck a building.
PATTERNS = [
    ('^tar_',        'asphalt_highway', 'mark_line_white'),
    ('crosswalk',    'asphalt_junction', 'mark_crosswalk'),
    ('zebra',        'asphalt_junction', 'mark_crosswalk'),
    ('stopline',     'asphalt_junction', 'mark_stopline'),
    ('stop_line',    'asphalt_junction', 'mark_stopline'),
    ('junction',     'asphalt_junction', None),
    ('crossing',     'asphalt_junction', 'mark_crosswalk'),
    ('carpark',      'asphalt_carpark', None),
    ('parking',      'asphalt_carpark', None),
    ('park_?lot',    'asphalt_carpark', None),
    ('freeway',      'asphalt_highway', None),
    ('motorway',     'asphalt_highway', None),
    ('highway',      'asphalt_highway', None),
    ('hi_?way',      'asphalt_highway', None),
    ('tunnel',       'asphalt_tunnel', None),
    ('bridge',       'asphalt_bridge', None),
    ('brij',         'asphalt_bridge', None),
    ('runway',       'asphalt_runway', None),
    ('taxiway',      'asphalt_runway', None),
    ('apron',        'asphalt_runway', None),
    ('dock',         'asphalt_dock', None),
    ('kerb',         'kerb_concrete', None),
    ('curb',         'kerb_concrete', None),
    ('sidewalk',     'pavement_slab', None),
    ('pavement',     'pavement_slab', None),
    ('paving',       'pavement_slab', None),
    ('pave[^m]',     'pavement_slab', None),
    ('gravel',       'shoulder_gravel', None),
    ('dirt',         'shoulder_dirt', None),
    ('mud',          'shoulder_dirt', None),
    ('soil',         'shoulder_dirt', None),
    ('concrete',     'concrete_road', None),
    ('asphalt',      'asphalt_mid', None),
    ('tarmac',       'asphalt_mid', None),
    ('bitumen',      'asphalt_mid', None),
    ('macadam',      'asphalt_mid', None),
    ('road',         'asphalt_mid', None),
    ('street',       'asphalt_mid', None),
    ('avenue',       'asphalt_mid', None),
    ('blvd',         'asphalt_mid', None),
    ('lane',         'asphalt_mid', None),
]

# sub-string blacklist applied to pattern hits (protects walls / props / vegetation that happen to
# contain a road word - "lantern" contains "lane", "startline decal" contains "tar", ...)
PATTERN_REJECT = [
    'wall', 'fence', 'gate', 'door', 'window', 'glass', 'roof', 'sign', 'neon', 'light', 'lamp',
    'lantern', 'glow', 'corona', 'shadow', 'metal', 'sheet', 'plate', 'stair', 'rail', 'grate',
    'manhole', 'hatch', 'drain', 'pipe', 'wire', 'cable', 'panel', 'vent', 'wood', 'plank',
    'brick', 'marble', 'granite_', 'plaster', 'stucco', 'carpet', 'curtain', 'ceiling', 'tile_',
    'hedge', 'grass', 'weed', 'tree', 'leaf', 'leaves', 'bark', 'bush', 'plant', 'crop', 'cactus',
    'palm', 'vine', 'moss', 'flower', 'forest', 'water', 'sea', 'river', 'lake', 'pool', 'sky',
    'cloud', 'smoke', 'fire', 'flame', 'steam', 'blood', 'skin', 'face', 'hand', 'hair', 'eye',
    'tattoo', 'gun', 'weapon', 'ammo', 'food', 'bottle', 'wheel', 'mirror', 'bumper', 'bonnet',
    'chassis', 'exhaust', 'engine', 'interior', 'dash', 'seat', 'decal', 'badge', 'logo',
    'billboard', 'poster', 'advert', 'crate', 'barrel', 'bin', 'tartan', 'start', 'plane',
    'vehicle', 'ped', 'cj_', 'xref', 'lod', 'alphabit',
]

# TXD names that are known to hold road surfaces (informational - shown by /roadinfo, used by the
# scanner to explain *why* a texture was accepted).  Read from the same index as the whitelist.
TXD_ROAD = [
    'roads_lawn', 'roads_law', 'roads_cunte', 'roads_lahills', 'roads_sfs', 'roads_tunnellahills',
    'roadlan2', 'road2sfe', 'roadsanfranse', 'roadsfe', 'roadslahills', 'roadbridge_sfse',
    'laeroads', 'laeroads2s', 'lae2roads', 'lae2roadscoast', 'lae2roadshub', 'lasroads_las',
    'lasroads_las2', 'lanroad', 'lan2freeway', 'law2_roadsb', 'lahillsla_roads', 'lahillslaroads',
    'lahillsroads6', 'lahillsroadscoast', 'freeway_las', 'freeway2_las', 'freeway2_las2',
    'freeway_sfs', 'freeway2_sfs', 'freeways_sfse', 'freeways2_sfse', 'freeways3_sfse',
    'sanfranfreeway', 'sfn_roadssfn', 'sfsroads', 'genroads_sfse', 'highway_sfn', 'oldfreeway_sfse',
    'fosterroads_sfse', 'mountroads_sfse', 'navyroad_sfse', 'dockroad_sfse', 'backroad_sfs',
    'vgssroads', 'vgseroads', 'vgsshiways', 'vgsehighways', 'vgsnhighway', 'vgssdrtyroads',
    'vgwstdirtyrd', 'vgwsthiway1', 'vgsroadbridge', 'cw_road', 'cunteroads1', 'cunteroads2',
    'cunteroads3', 'cunteroads4', 'cunteroads5', 'cunteroads6', 'cuntwroad', 'cs_roads',
    'desertroads', 'airoads_las', 'airportroads_sfse', 'tunnel_sfe', 'cuntwtunnel',
    'parktunnel_sfs', 'golftunnel_sfs', 'bendytunnel_sfse', 'stormdrain_las2', 'pinkcarpark_sfs',
]

# the same information as one flat list of *file names*, useful for the README and the report
if __name__ == '__main__':
    print('whitelist %d, review %d, blacklist %d, patterns %d, road TXDs %d'
          % (len(WHITELIST), len(REVIEW), len(BLACKLIST), len(PATTERNS), len(TXD_ROAD)))
    from . import materials as MAT
    bad = [k for k, v in WHITELIST.items() if MAT.by_key(v[0]) is None]
    print('materials referenced but missing:', bad)
    mk = {m['key'] for m in MAT.MARKINGS}
    bad = [(k, v[1]) for k, v in WHITELIST.items() if v[1] and v[1] not in mk]
    print('markings referenced but missing:', bad)
