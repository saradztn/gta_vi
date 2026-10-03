"""Hand-planned, deterministic geometry for the playable Castle MTA asset.

The plan follows the supplied reference: an island fortress, bridge and gatehouse,
perimeter walls with round towers, a high Gothic keep, an organized courtyard,
connected palace floors, and a basement/secret route.  Units are GTA metres.
"""
import math
from mesh import Mesh, wall_x, wall_y

G = 1.0                 # finished courtyard / ground-floor datum
UPPER = 7.0             # first-floor datum
BASEMENT = -7.0         # cellar datum


def _add_box(m, lo, hi, mat="c_stone", coll=False, face_mats=None):
    m.box(lo, hi, mat, collision=coll, face_mats=face_mats)


def _door(at, width=3.2, height=5.4):
    return {"at": float(at), "width": float(width), "sill": G, "height": float(height), "kind": "door"}


def _window(at, sill=4.0, height=2.8, width=2.4):
    return {"at": float(at), "width": float(width), "sill": float(sill), "height": float(height), "kind": "window"}


def _elliptic_loft(m, rings, sides=32, mat="c_rock", collision=True):
    """Irregular island / rock shoulder built from measured polygon rings."""
    rings = [(float(rx), float(ry), float(z)) for rx, ry, z in rings]
    angles = [2 * math.pi * i / sides for i in range(sides)]
    polys = []
    for rx, ry, z in rings:
        # Slight deterministic faceting breaks the perfect-ellipse silhouette without random noise.
        p = []
        for i, a in enumerate(angles):
            wobble = 1.0 + 0.025 * math.sin(i * 4.7 + z * 0.17) + 0.018 * math.cos(i * 2.9 - z)
            p.append((rx * wobble * math.cos(a), ry * wobble * math.sin(a), z))
        polys.append(p)
    for k in range(len(polys) - 1):
        lo, hi = polys[k], polys[k + 1]
        for i in range(sides):
            j = (i + 1) % sides
            m.quad((lo[i], lo[j], hi[j], hi[i]), mat, tile=(10.0, 6.0), collision=collision)


def _garden_bed(m, x0, y0, x1, y1):
    _add_box(m, (x0, y0, G + 0.01), (x1, y1, G + 0.28), "c_arch", False)
    m.plane_xy(x0 + 0.28, y0 + 0.28, x1 - 0.28, y1 - 0.28, G + 0.30, "c_grass", tile=5.0)
    # Low clipped yew hedges; kept below chest-height so the courtyard remains legible.
    for x in (x0 + 0.35, x1 - 0.75):
        _add_box(m, (x, y0 + 0.35, G + 0.3), (x + 0.4, y1 - 0.35, G + 1.55), "c_grass")
    for y in (y0 + 0.35, y1 - 0.75):
        _add_box(m, (x0 + 0.35, y, G + 0.3), (x1 - 0.35, y + 0.4, G + 1.55), "c_grass")


def _tree(m, x, y, height=8.0):
    m.cylinder((x, y), 0.42, G, G + height * 0.42, 7, "c_wood", collision=False, smooth=False)
    for k, (h, r) in enumerate(((0.40, 2.0), (0.57, 1.62), (0.73, 1.24), (0.88, 0.82))):
        z0, z1 = G + height * (h - 0.19), G + height * (h + 0.08)
        m.cone((x, y), r, z0, z1, 7, "c_grass", theta0=0.16 * k)


def _lamp_post(m, x, y, z=G):
    m.cylinder((x, y), 0.22, z, z + 2.8, 8, "c_iron", collision=False, smooth=False)
    m.cylinder((x, y), 0.38, z + 2.55, z + 2.72, 8, "c_arch", collision=False, smooth=False)
    _add_box(m, (x - 0.56, y - 0.18, z + 2.75), (x + 0.56, y + 0.18, z + 3.5), "c_iron")
    _add_box(m, (x - 0.38, y - 0.10, z + 2.88), (x + 0.38, y + 0.10, z + 3.32), "c_glass")
    for dx in (-0.42, 0.42):
        m.cylinder((x + dx, y), 0.05, z + 2.75, z + 3.43, 6, "c_iron", collision=False, smooth=False)


def _fountain(m, x, y):
    # Three carved basin tiers around a shallow, blue water surface.
    m.cylinder((x, y), 6.6, G, G + 0.62, 24, "c_arch", collision=False, smooth=False)
    m.cylinder((x, y), 5.9, G + 0.62, G + 0.92, 24, "c_marble", collision=False, smooth=False)
    m.cylinder((x, y), 5.25, G + 0.91, G + 1.02, 24, "c_water", collision=False, smooth=False)
    m.cylinder((x, y), 1.45, G + 0.95, G + 3.1, 12, "c_arch", collision=False)
    m.cylinder((x, y), 2.15, G + 2.25, G + 2.55, 16, "c_marble", collision=False, smooth=False)
    m.cylinder((x, y), 1.0, G + 3.1, G + 4.0, 10, "c_arch", collision=False)
    m.cone((x, y), 1.35, G + 3.75, G + 5.35, 10, "c_arch")
    # Small corner jets are solid sculptural details (not animated particles).
    for a in range(0, 360, 90):
        r = math.radians(a)
        px, py = x + 3.4 * math.cos(r), y + 3.4 * math.sin(r)
        m.cylinder((px, py), 0.36, G + 1.0, G + 2.8, 8, "c_arch", collision=False)


def model_ground():
    m = Mesh("castle_ground")
    _elliptic_loft(m, ((76, 64, -18), (99, 82, -11), (118, 97, -3), (112, 92, 0.55)), 32, "c_rock", True)
    # Walkable stone apron and forecourt; the central palace footprint is deliberately left clear
    # so the real palace floor, basement stairwell and secret tunnel remain open.
    slabs = [((-105, -85, 0.50), (105, -39, G)),
             ((-105, -39, 0.50), (-54, 53, G)), ((54, -39, 0.50), (105, 53, G)),
             ((-105, 53, 0.50), (105, 85, G))]
    for lo, hi in slabs:
        _add_box(m, lo, hi, "c_stone", True, {"+z": "c_marble", "-z": "c_rock"})
    # Central processional walk from the drawbridge to the keep.
    m.plane_xy(-7.2, -85, 7.2, -39, G + 0.025, "c_marble", tile=3.5)
    for x in (-8.2, 7.2):
        _add_box(m, (x, -85, G + 0.03), (x + 0.28, -39, G + 0.18), "c_arch")
    # Formal gardens and stepped planting beds, arranged symmetrically.
    _garden_bed(m, -82, -34, -61, -9)
    _garden_bed(m, 61, -34, 82, -9)
    _garden_bed(m, -84, 20, -62, 45)
    _garden_bed(m, 62, 20, 84, 45)
    _garden_bed(m, -42, 58, -18, 77)
    _garden_bed(m, 18, 58, 42, 77)
    for x, y, h in ((-71, -22, 7), (71, -22, 7), (-74, 31, 8), (74, 31, 8),
                    (-31, 68, 7), (31, 68, 7), (-91, 0, 6), (91, 0, 6)):
        _tree(m, x, y, h)
    # Formal fountains: forecourt and rear garden.
    _fountain(m, 0, -60)
    _fountain(m, 0, 67)
    # Stone benches and low flower urns around the south garden.
    for x in (-72, 72):
        for y in (-6, 39):
            _add_box(m, (x - 2.0, y - 0.32, G + 0.3), (x + 2.0, y + 0.32, G + 0.8), "c_wood")
            _add_box(m, (x - 2.0, y + 0.23, G + 0.78), (x + 2.0, y + 0.40, G + 1.55), "c_arch")
            m.cylinder((x - 4.2, y), 0.55, G + 0.3, G + 1.8, 10, "c_arch", collision=False)
            m.cone((x - 4.2, y), 0.8, G + 1.6, G + 2.5, 9, "c_grass")
            m.cylinder((x + 4.2, y), 0.55, G + 0.3, G + 1.8, 10, "c_arch", collision=False)
            m.cone((x + 4.2, y), 0.8, G + 1.6, G + 2.5, 9, "c_grass")
    # Courtyard wall lanterns / bollards.
    for x in (-55, -32, 32, 55):
        _lamp_post(m, x, -53)
        _lamp_post(m, x, 49)
    for y in (-37, 0, 47):
        _lamp_post(m, -94, y)
        _lamp_post(m, 94, y)
    return m


def model_bridge():
    m = Mesh("castle_bridge")
    # 80 m processional causeway with a 14 m stone deck.
    _add_box(m, (-9.0, -40.0, 0.1), (9.0, 40.0, G), "c_stone", True, {"+z": "c_marble", "-z": "c_rock"})
    _add_box(m, (-10.0, -40.0, G), (10.0, 40.0, G + 0.65), "c_arch", True)
    for x in (-9.5, 8.7):
        _add_box(m, (x, -40, G + 0.65), (x + 0.8, 40, G + 3.1), "c_stone", True)
        for y in range(-38, 39, 5):
            _add_box(m, (x - 0.05, y, G + 3.1), (x + 0.9, y + 2.0, G + 4.0), "c_arch", True)
    # Seven broad crossing ribs underneath the bridge, with battered stone piers.
    for y in (-32, -21, -10, 1, 12, 23, 34):
        for x in (-7.2, 7.2):
            _add_box(m, (x - 1.0, y - 1.4, -9.0), (x + 1.0, y + 1.4, G), "c_rock", False)
        for x in (-7.0, 7.0):
            m.cylinder((x, y), 1.35, -9.0, G, 10, "c_arch", collision=False)
    # Entry lamps and carved heraldic stones along the bridge rails.
    for y in (-32, -14, 14, 32):
        for x in (-11.2, 11.2):
            m.cylinder((x, y), 0.48, G + 0.65, G + 2.0, 8, "c_arch", collision=False)
            _add_box(m, (x - 0.32, y - 0.3, G + 1.8), (x + 0.32, y + 0.3, G + 3.1), "c_iron")
            _add_box(m, (x - 0.21, y - 0.19, G + 2.05), (x + 0.21, y + 0.19, G + 2.75), "c_glass")
    return m


def model_wall_run():
    m = Mesh("castle_wall_run")
    x0, x1 = -46.5, 46.5
    _add_box(m, (x0 - 0.8, -5.2, G), (x1 + 0.8, 5.2, G + 2.4), "c_arch", True)
    _add_box(m, (x0, -4.0, G + 2.4), (x1, 4.0, G + 14.2), "c_stone", True)
    # Broad coping and a walkable fighting platform.
    _add_box(m, (x0 - 0.2, -4.8, G + 14.0), (x1 + 0.2, 4.8, G + 15.1), "c_arch", True,
            {"+z": "c_marble"})
    _add_box(m, (x0, -4.4, G + 15.0), (x1, -3.4, G + 17.5), "c_stone", True)
    _add_box(m, (x0, 3.4, G + 15.0), (x1, 4.4, G + 17.5), "c_stone", True)
    # Repeating merlons, evenly spaced along the top walk.
    for x in [x0 + 1.6 + i * 4.4 for i in range(22)]:
        if x + 1.5 > x1:
            break
        for y in (-3.9, 3.9):
            _add_box(m, (x, y - 0.7, G + 17.35), (x + 1.8, y + 0.7, G + 19.25), "c_arch", True)
    # Projecting buttresses, string courses and recessed arrow slits (paired inside/outside).
    for x in [x0 + 4.0 + i * 11.0 for i in range(9)]:
        _add_box(m, (x - 0.38, -4.7, G + 1.5), (x + 0.38, 4.7, G + 11.8), "c_arch")
        for y in (-4.06, 4.06):
            m.quad(((x - 0.16, y, G + 7.3), (x + 0.16, y, G + 7.3), (x + 0.16, y, G + 10.8), (x - 0.16, y, G + 10.8)), "c_iron", tile=1.0)
        _add_box(m, (x - 0.65, -4.8, G + 3.0), (x + 0.65, 4.8, G + 3.35), "c_arch")
    # Crenel-side lantern housings and stone shields.
    for x in (-35, -12, 12, 35):
        for y in (-4.25, 4.25):
            _add_box(m, (x - 0.45, y - 0.25, G + 9.0), (x + 0.45, y + 0.25, G + 11.0), "c_iron")
            _add_box(m, (x - 0.24, y - 0.30, G + 9.25), (x + 0.24, y + 0.30, G + 10.65), "c_glass")
    return m


def _outer_tower_windows(m, z0, z1):
    # narrow leaded slits on the eight compass points
    for deg in range(0, 360, 45):
        a = math.radians(deg)
        r = 9.22
        x, y = r * math.cos(a), r * math.sin(a)
        dx, dy = math.cos(a), math.sin(a)
        # A dark inset and a warm glass core; wall mass remains intact behind the slit.
        p = (x + 0.03 * dx, y + 0.03 * dy, z0)
        q = (x + 0.03 * dx, y + 0.03 * dy, z1)
        m.quad(((p[0] + 0.22 * dy, p[1] - 0.22 * dx, p[2]),
                (p[0] - 0.22 * dy, p[1] + 0.22 * dx, p[2]),
                (q[0] - 0.22 * dy, q[1] + 0.22 * dx, q[2]),
                (q[0] + 0.22 * dy, q[1] - 0.22 * dx, q[2])), "c_glass", tile=1.0)


def model_outer_tower():
    m = Mesh("castle_outer_tower")
    r0, ri = 9.6, 7.9
    top = G + 23.0
    m.hollow_cylinder_wall((0, 0), r0, ri, G, G + 4.8, sides=32, mat="c_stone", doorway_angle=-math.pi / 2,
                           doorway_width=2.5, collision=True)
    m.hollow_cylinder_wall((0, 0), r0, ri, G + 4.8, top, sides=32, mat="c_stone", doorway_angle=-math.pi / 2,
                           doorway_width=0.0, collision=True)
    # The real floors are annular so the central stairwell is not sealed by an upper slab.
    _add_box(m, (-ri, -ri, G - 0.28), (ri, ri, G), "c_arch", True, {"+z": "c_marble"})
    for level in (G + 5.4, G + 10.8, G + 16.2, G + 21.4):
        m.annulus((0, 0), 2.3, ri, level, sides=32, mat="c_marble", collision=True)
        # A low inner guard rail around the stair opening.
        m.cylinder((0, 0), 2.35, level, level + 0.85, 12, "c_iron", collision=False, smooth=False)
    for level in (G, G + 5.4, G + 10.8, G + 16.2):
        m.spiral_steps((0, 0), 2.55, 7.35, level + 0.02, level + 5.38, steps=24,
                       turns=1.0, mat="c_arch", collision=True, theta0=-math.pi / 2)
    _outer_tower_windows(m, G + 7.0, G + 10.0)
    _outer_tower_windows(m, G + 13.5, G + 16.2)
    # Machicolation band, corbels and square merlons at the crown.
    for z in (G + 2.5, G + 19.3):
        m.annulus((0, 0), r0 - 0.2, r0 + 0.55, z, 32, "c_arch", False)
    for i in range(16):
        a = 2 * math.pi * i / 16
        x, y = 9.55 * math.cos(a), 9.55 * math.sin(a)
        _add_box(m, (x - 0.8, y - 0.8, G + 22.6), (x + 0.8, y + 0.8, G + 25.0), "c_arch", True)
    m.cone((0, 0), 10.2, G + 24.2, G + 39.5, 16, "c_roof", theta0=0.12)
    m.cylinder((0, 0), 0.34, G + 39.2, G + 41.6, 8, "c_iron", collision=False, smooth=False)
    m.cone((0, 0), 0.65, G + 41.2, G + 42.8, 8, "c_gold")
    return m


def model_gatehouse():
    m = Mesh("castle_gatehouse")
    z0, z1 = G, G + 31.0
    front, back = -11.4, 11.4
    # The front and rear walls are built around a clear 12.8 m wide, 17.5 m high passage.
    opening = [{"at": 0.0, "width": 12.8, "sill": G, "height": 17.5, "kind": "door"}]
    wall_x(m, -17, 17, front, 1.4, z0, z1, opening, "c_stone")
    wall_x(m, -17, 17, back, 1.4, z0, z1, opening, "c_stone")
    wall_y(m, -16.3, front + 0.6, back - 0.6, 1.4, z0, z1, (), "c_stone")
    wall_y(m, 16.3, front + 0.6, back - 0.6, 1.4, z0, z1, (), "c_stone")
    # An unobstructed stone tunnel floor and true intrados (curved inner vault).
    _add_box(m, (-6.35, front - 0.25, G - 0.1), (6.35, back + 0.25, G + 0.12), "c_marble", True)
    spring, rin, rout = G + 8.5, 6.4, 8.55
    m.arch_ring(0, front - 0.75, spring, rin, rout, 1.55, 14, "c_arch", True, facing=-1)
    m.arch_ring(0, back + 0.75, spring, rin, rout, 1.55, 14, "c_arch", True, facing=1)
    for i in range(16):
        a0 = math.pi - math.pi * i / 16
        a1 = math.pi - math.pi * (i + 1) / 16
        x0, zA = rin * math.cos(a0), spring + rin * math.sin(a0)
        x1, zB = rin * math.cos(a1), spring + rin * math.sin(a1)
        m.quad(((x0, front + 0.6, zA), (x0, back - 0.6, zA), (x1, back - 0.6, zB), (x1, front + 0.6, zB)),
               "c_stone", tile=4.0, collision=True)
    _add_box(m, (-rin, front + 0.5, G), (-rin + 0.5, back - 0.5, spring), "c_stone", True)
    _add_box(m, (rin - 0.5, front + 0.5, G), (rin, back - 0.5, spring), "c_stone", True)
    # Main gatehouse flanking towers are hollow, with their own narrow stair / guard-room interiors.
    for x in (-12.0, 12.0):
        m.hollow_cylinder_wall((x, 0), 5.4, 4.2, G, G + 4.6, sides=20, mat="c_stone",
                               doorway_angle=-math.pi / 2, doorway_width=1.5, collision=True)
        m.hollow_cylinder_wall((x, 0), 5.4, 4.2, G + 4.6, G + 29.0, sides=20, mat="c_stone",
                               doorway_angle=-math.pi / 2, doorway_width=0.0, collision=True)
        _add_box(m, (x - 4.15, -4.15, G - 0.2), (x + 4.15, 4.15, G), "c_arch", True)
        for level in (G + 5.3, G + 10.6, G + 15.9, G + 21.2, G + 26.2):
            m.annulus((x, 0), 1.7, 4.15, level, 20, "c_marble", True)
        for level in (G, G + 5.3, G + 10.6, G + 15.9, G + 21.2):
            m.spiral_steps((x, 0), 1.8, 3.8, level + 0.02, level + 5.28, 20, 1.0, "c_arch", True, -math.pi / 2)
        for a in range(0, 360, 60):
            r = math.radians(a)
            xx, yy = x + 5.2 * math.cos(r), 5.2 * math.sin(r)
            _add_box(m, (xx - 0.55, yy - 0.55, G + 28.4), (xx + 0.55, yy + 0.55, G + 31.4), "c_arch", True)
        m.cone((x, 0), 5.8, G + 30.7, G + 39.0, 12, "c_roof")
    # Open portcullis, raised above head-height; it is not a gameplay blocker.
    for x in [i * 0.75 for i in range(-7, 8)]:
        _add_box(m, (x - 0.065, -1.1, G + 11.3), (x + 0.065, -0.85, G + 17.3), "c_iron")
    for z in (G + 12.3, G + 14.6, G + 16.9):
        _add_box(m, (-5.5, -1.16, z - 0.07), (5.5, -0.8, z + 0.07), "c_iron")
    # Crown bridge over the gate with crenellated parapets.
    _add_box(m, (-12.0, -12.0, G + 18.0), (12.0, 12.0, G + 19.0), "c_marble", True)
    for x in range(-11, 12, 3):
        _add_box(m, (x, -11.8, G + 19.0), (x + 1.3, -10.7, G + 21.0), "c_arch", True)
        _add_box(m, (x, 10.7, G + 19.0), (x + 1.3, 11.8, G + 21.0), "c_arch", True)
    # Heraldic stonework over the opening.
    _add_box(m, (-2.2, front - 0.45, G + 18.1), (2.2, front + 0.1, G + 22.7), "c_arch")
    _add_box(m, (-1.4, front - 0.65, G + 19.1), (1.4, front - 0.45, G + 21.5), "c_cloth")
    return m


def _palace_square_tower(m, cx, cy, width, z0, shaft_top, roof_top, floors=6, entry=True, mat="c_stone"):
    """Hollow square Gothic turret with floor rings, working spiral staircase, slits and a steep cap."""
    h = shaft_top - z0
    floor_h = h / max(floors, 1)
    half = width / 2
    thick = max(0.9, width * 0.12)
    inner = half - thick
    # Four walls per level leave the room volume open; window voids are real wall cut-outs.
    for level in range(floors):
        a = z0 + level * floor_h
        b = z0 + (level + 1) * floor_h
        window_sill = a + max(1.0, floor_h * 0.34)
        window_h = min(2.8, floor_h * 0.45)
        south = [_door(cx, 2.2, 4.8)] if entry and level == 0 else [_window(cx, window_sill, window_h, 1.7)]
        north = [_window(cx, window_sill, window_h, 1.7)]
        west = [_window(cy, window_sill, window_h, 1.7)]
        east = [_window(cy, window_sill, window_h, 1.7)]
        wall_x(m, cx - half, cx + half, cy - half, thick, a, b, south, mat)
        wall_x(m, cx - half, cx + half, cy + half, thick, a, b, north, mat)
        wall_y(m, cx - half, cy - half, cy + half, thick, a, b, west, mat)
        wall_y(m, cx + half, cy - half, cy + half, thick, a, b, east, mat)
        if level == 0:
            _add_box(m, (cx - inner, cy - inner, a - 0.22), (cx + inner, cy + inner, a), "c_marble", True)
        else:
            m.annulus((cx, cy), max(1.2, 1.55), inner, a, 4, "c_marble", True, theta0=math.pi / 4)
        # Narrow cornice at each storey.
        _add_box(m, (cx - half - 0.38, cy - half - 0.38, b - 0.22), (cx + half + 0.38, cy + half + 0.38, b + 0.12), "c_arch")
    m.spiral_steps((cx, cy), 1.55, inner - 0.25, z0 + 0.04, shaft_top - 0.08,
                   steps=max(24, floors * 18), turns=float(floors), mat="c_arch", collision=True, theta0=-math.pi / 2)
    # Four corner pinnacles and a crisp stepped pyramid roof.
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = cx + sx * (half - 0.45), cy + sy * (half - 0.45)
            _add_box(m, (x - 0.42, y - 0.42, shaft_top - 0.3), (x + 0.42, y + 0.42, shaft_top + 1.2), "c_arch")
    m.pyramid((cx, cy), width + 1.3, shaft_top, roof_top, "c_roof")
    m.cylinder((cx, cy), 0.24, roof_top - 0.1, roof_top + 2.4, 8, "c_iron", collision=False, smooth=False)
    m.cone((cx, cy), 0.55, roof_top + 2.1, roof_top + 3.5, 8, "c_gold")


def model_palace_shell():
    m = Mesh("castle_palace_shell")
    # Outer residential range, 104 x 90 m.  Openings align with ground-floor passages.
    low, eave = G, G + 14.6
    front_windows = [_window(-40, G + 4.0, 3.0), _window(-26, G + 4.0, 3.0),
                     _door(0, 8.0, 7.2), _window(26, G + 4.0, 3.0), _window(40, G + 4.0, 3.0)]
    rear_open = [_window(-40, G + 4.0, 3.0), _window(-25, G + 4.0, 3.0), _door(0, 4.0, 5.2),
                 _window(25, G + 4.0, 3.0), _window(40, G + 4.0, 3.0)]
    wall_x(m, -53, 53, -38, 2.1, low, eave, front_windows, "c_stone")
    wall_x(m, -53, 53, 52, 2.1, low, eave, rear_open, "c_stone")
    for x in (-53, 53):
        ops = [_window(-22, G + 4.0, 3.0), _door(-30, 2.6, 5.0), _window(-4, G + 4.0, 3.0),
               _window(15, G + 4.0, 3.0), _door(42, 2.4, 5.0)]
        wall_y(m, x, -38, 52, 2.1, low, eave, ops, "c_stone")
    # Keep walls rise over the great hall; doorways open directly to the wings and north service rooms.
    keep_top = G + 22.0
    wall_x(m, -31, 31, -24, 2.0, G, keep_top,
           [_window(-23, G + 5.0, 3.0), _door(0, 5.8, 6.0), _window(23, G + 5.0, 3.0)], "c_stone")
    wall_x(m, -31, 31, 42, 2.0, G, keep_top,
           [_window(-21, G + 5.5, 3.0), _door(0, 4.0, 5.5), _window(21, G + 5.5, 3.0)], "c_stone")
    wall_y(m, -31, -24, 42, 2.0, G, keep_top,
           [_window(-10, G + 6.0, 3.0), _door(13, 4.0, 5.6), _window(30, G + 6.0, 3.0)], "c_stone")
    wall_y(m, 31, -24, 42, 2.0, G, keep_top,
           [_window(-10, G + 6.0, 3.0), _door(13, 4.0, 5.6), _window(30, G + 6.0, 3.0)], "c_stone")
    # Stone string courses, buttresses, tall lancet windows and carved arch frames.
    for y in (-38, 52):
        for x in range(-49, 50, 7):
            _add_box(m, (x - 0.32, y - 1.32, G + 0.4), (x + 0.32, y + 1.32, eave + 0.3), "c_arch")
        _add_box(m, (-54, y - 1.65, G + 2.2), (54, y + 1.65, G + 2.55), "c_arch")
        _add_box(m, (-54, y - 1.58, G + 13.9), (54, y + 1.58, G + 14.25), "c_arch")
    for x in (-53, 53):
        for y in range(-34, 49, 10):
            _add_box(m, (x - 1.35, y - 0.35, G + 0.5), (x + 1.35, y + 0.35, eave + 0.3), "c_arch")
        _add_box(m, (x - 1.6, -40, G + 2.2), (x + 1.6, 54, G + 2.55), "c_arch")
    # Steep slate roofs over the side ranges and the high central keep.
    m.gable_roof(-41.0, 7.0, 24.0, 90.0, G + 14.4, G + 22.5, "c_roof", "y", 0.8)
    m.gable_roof(41.0, 7.0, 24.0, 90.0, G + 14.4, G + 22.5, "c_roof", "y", 0.8)
    m.gable_roof(0.0, 9.0, 64.0, 70.0, G + 22.0, G + 31.0, "c_roof", "y", 1.0)
    # Roof-edge dormers and carved finials.
    for x in (-42, -28, 28, 42):
        for y in (-28, -7, 15, 37):
            _add_box(m, (x - 1.0, y - 0.9, G + 17.4), (x + 1.0, y + 0.9, G + 20.0), "c_stone")
            m.pyramid((x, y), 2.5, G + 19.8, G + 22.2, "c_roof")
    # Four accessible outer keep turrets. Entry doors and spiral stairwells line up with palace rooms.
    for cx, cy, top in ((-47, -31, G + 44), (47, -31, G + 44), (-47, 43, G + 39), (47, 43, G + 39)):
        _palace_square_tower(m, cx, cy, 11.2, G, top - 8.5, top, 6, True)
    # A central lantern tower and paired flanking towers lift the silhouette far above the roofs.
    _palace_square_tower(m, 0, 11, 13.2, G + 20.0, G + 59.0, G + 91.0, 7, True)
    _palace_square_tower(m, -20.8, 12, 9.7, G + 18.0, G + 48.0, G + 73.0, 6, True)
    _palace_square_tower(m, 20.8, 12, 9.7, G + 18.0, G + 48.0, G + 73.0, 6, True)
    # Two rear spires above the private wing.
    _palace_square_tower(m, -17.5, 39, 8.5, G + 15.0, G + 41.0, G + 61.0, 5, True)
    _palace_square_tower(m, 17.5, 39, 8.5, G + 15.0, G + 41.0, G + 61.0, 5, True)
    # Small flying buttresses and pinnacles along the central roofline.
    for x in (-29, -15, 15, 29):
        _add_box(m, (x - 0.65, -27, G + 20), (x + 0.65, -26, G + 29), "c_arch")
        m.cone((x, -26.5), 0.7, G + 28.5, G + 32.5, 7, "c_roof")
    return m


def _floor_rect(m, x0, y0, x1, y1, z, mat="c_marble", thickness=0.32, coll=True):
    _add_box(m, (x0, y0, z - thickness), (x1, y1, z), mat, coll, {"-z": "c_stone"})


def _stairs_up_y(m, x, y0, width, z0, z1, count=26, tread=0.34, mat="c_marble"):
    rise = (z1 - z0) / count
    for i in range(count):
        ya = y0 + i * tread
        top = z0 + (i + 1) * rise
        _add_box(m, (x - width / 2, ya, z0 - 0.08), (x + width / 2, ya + tread, top), mat, True)
    # Simple stone side stringers; no high handrail across the walking path.
    run = count * tread
    _add_box(m, (x - width / 2 - 0.18, y0, z0), (x - width / 2, y0 + run, z1 + 0.25), "c_arch")
    _add_box(m, (x + width / 2, y0, z0), (x + width / 2 + 0.18, y0 + run, z1 + 0.25), "c_arch")


def _stairs_down_y(m, x, y0, width, z_top, z_bottom, count=28, tread=0.34):
    rise = (z_top - z_bottom) / count
    for i in range(count):
        ya = y0 + i * tread
        top = z_top - (i + 1) * rise
        _add_box(m, (x - width / 2, ya, z_bottom - 0.06), (x + width / 2, ya + tread, top), "c_marble", True)


def model_palace_ground():
    m = Mesh("castle_palace_ground")
    # Ground-floor slabs surround a deliberate stairwell hole into the basement.
    floor_parts = [(-53, -38, -47, 52), (-41, -38, 53, 52), (-47, -38, -41, -36), (-47, -22, -41, 52)]
    for r in floor_parts:
        _floor_rect(m, *r, G, "c_marble", 0.38, True)
    # Interior room partitions and doorways (door gaps are real, not painted rectangles).
    z0, z1 = G, G + 6.4
    for x in (-22.0, 22.0):
        wall_y(m, x, -37.5, 27.0, 0.55, z0, z1,
               [_door(-13.0, 3.4, 5.3), _door(14.0, 3.4, 5.3)], "c_stone")
    wall_x(m, -22, 22, -17.0, 0.55, z0, z1, [_door(0, 4.6, 5.4)], "c_stone")
    wall_x(m, -22, 22, 27.0, 0.55, z0, z1, [_door(0, 3.8, 5.2)], "c_stone")
    # West and east room-corridor walls, arranged as a service passage rather than a maze of disconnected boxes.
    for x in (-28.5, 28.5):
        wall_y(m, x, -36.0, 27.0, 0.42, z0, z1,
               [_door(-26.0, 3.0, 5.0), _door(-2.0, 3.0, 5.0), _door(14.0, 3.0, 5.0)], "c_stone")
    for x0, x1 in ((-52, -28.5), (28.5, 52)):
        wall_x(m, x0, x1, -18.0, 0.42, z0, z1, [_door((x0 + x1) / 2, 2.6, 5.0)], "c_stone")
        wall_x(m, x0, x1, -4.0, 0.42, z0, z1, [_door((x0 + x1) / 2, 2.4, 5.0)], "c_stone")
        wall_x(m, x0, x1, 1.0, 0.42, z0, z1, [_door((x0 + x1) / 2, 2.4, 5.0)], "c_stone")
        wall_x(m, x0, x1, 28.0, 0.42, z0, z1, [_door((x0 + x1) / 2, 2.8, 5.0)], "c_stone")
    # Two-storey room partitions in the rear cross-wing.
    wall_y(m, -8.5, 28.0, 51.2, 0.42, z0, z1, [_door(39.0, 2.8, 5.0)], "c_stone")
    wall_y(m, 8.5, 28.0, 51.2, 0.42, z0, z1, [_door(39.0, 2.8, 5.0)], "c_stone")
    # Polished plinths and columns inside the Great Hall.
    for x in (-18, 18):
        for y in (-10, 2, 14, 24):
            m.cylinder((x, y), 1.15, G, G + 5.95, 12, "c_arch", collision=True, smooth=False)
            m.cylinder((x, y), 1.48, G + 0.1, G + 0.6, 12, "c_marble", collision=False, smooth=False)
            m.cylinder((x, y), 1.55, G + 5.5, G + 6.1, 12, "c_arch", collision=False, smooth=False)
    # West/east stairs rise to the first floor; central split flights give the hall a ceremonial route.
    _stairs_up_y(m, -39.5, -35.0, 3.2, G, UPPER, 26, 0.34)
    _stairs_up_y(m, 39.5, -35.0, 3.2, G, UPPER, 26, 0.34)
    _stairs_up_y(m, 0.0, -36.0, 4.2, G, UPPER, 26, 0.34)
    # The royal entrance receives a short marble threshold; the portal itself remains open.
    _add_box(m, (-4.2, -38.2, G - 0.05), (4.2, -36.8, G + 0.18), "c_marble", True)
    return m


def model_palace_upper():
    m = Mesh("castle_palace_upper")
    # Upper residential floor. The 38 x 53 m central void leaves the Great Hall open to its high roof.
    floors = [(-53, -38, -29, 52), (-24, -38, -19, -25), (19, -38, 24, -25),
              (-24, 25, -19, 52), (19, 25, 24, 52), (-24, -38, 24, -25), (-24, 25, 24, 52)]
    # Full west/east wings and narrow gallery strips, plus the front/rear cross galleries.
    floor_boxes = [(-53, -38, -29, 52), (29, -38, 53, 52), (-29, -38, -24, 52), (24, -38, 29, 52),
                   (-24, -38, 24, -25), (-24, 25, 24, 52)]
    for x0, y0, x1, y1 in floor_boxes:
        _floor_rect(m, x0, y0, x1, y1, UPPER, "c_marble", 0.38, True)
    z0, z1 = UPPER, UPPER + 5.8
    # The long inner walls form the gallery edges; door openings connect rooms into the corridor.
    for x in (-29.0, 29.0):
        wall_y(m, x, -37.0, 51.0, 0.45, z0, z1,
               [_door(-27.0, 3.0, 5.0), _door(-3.0, 3.0, 5.0), _door(14.0, 3.0, 5.0), _door(38.0, 3.0, 5.0)], "c_stone")
    # The west/east wings contain connected guest, guard, family and private rooms.
    for x0, x1 in ((-53, -29), (29, 53)):
        for y, center in ((-13.5, (x0 + x1) / 2), (5.0, (x0 + x1) / 2), (24.0, (x0 + x1) / 2)):
            wall_x(m, x0, x1, y, 0.42, z0, z1, [_door(center, 2.5, 5.0)], "c_stone")
    # North royal suite / private family rooms; all connect to the rear gallery.
    wall_x(m, -24, 24, 27.0, 0.48, z0, z1, [_door(0, 3.6, 5.0)], "c_stone")
    wall_y(m, -10.0, 27.0, 51.0, 0.42, z0, z1, [_door(40, 3.0, 5.0)], "c_stone")
    wall_y(m, 10.0, 27.0, 51.0, 0.42, z0, z1, [_door(40, 3.0, 5.0)], "c_stone")
    # Gallery balustrades around the open Great Hall; gaps at front/rear keep circulation continuous.
    for x in (-19.2, 19.2):
        _add_box(m, (x - 0.15, -19.5, UPPER), (x + 0.15, 24.0, UPPER + 0.55), "c_arch")
        for y in range(-18, 24, 2):
            m.cylinder((x, y), 0.10, UPPER + 0.55, UPPER + 1.35, 6, "c_arch", collision=False, smooth=False)
        _add_box(m, (x - 0.3, -19.5, UPPER + 1.35), (x + 0.3, 24.0, UPPER + 1.58), "c_wood")
    # A narrow elevated gallery bridge gives the central stair a real, traversable approach over the hall void.
    _floor_rect(m, -2.45, -25.0, 2.45, 7.2, UPPER, "c_marble", 0.28, True)
    for x in (-2.48, 2.48):
        _add_box(m, (x - 0.10, -25.0, UPPER), (x + 0.10, 5.2, UPPER + 1.05), "c_arch")
        _add_box(m, (x - 0.18, -25.0, UPPER + 1.05), (x + 0.18, 5.2, UPPER + 1.24), "c_wood")
    # Gallery staircases to the rooftop tower levels; holes in the gallery floor are left open by design.
    m.spiral_steps((0, 11), 1.75, 4.25, UPPER + 0.04, G + 20.0, 52, 2.35, "c_marble", True, -math.pi / 2)
    m.spiral_steps((-20.8, 12), 1.45, 3.45, UPPER + 0.04, G + 18.0, 44, 2.0, "c_marble", True, -math.pi / 2)
    m.spiral_steps((20.8, 12), 1.45, 3.45, UPPER + 0.04, G + 18.0, 44, 2.0, "c_marble", True, -math.pi / 2)
    # Balcony doors are clear and the window openings are kept out of the movement lanes.
    return m


def model_dungeon():
    m = Mesh("castle_dungeon")
    # Basement spans the footprint below ground-floor rooms; a separate staircase opening joins it to the kitchen wing.
    _floor_rect(m, -52, -38, 52, 52, BASEMENT, "c_stone", 0.42, True)
    z0, z1 = BASEMENT, -1.4
    wall_x(m, -52, 52, -38, 1.3, z0, z1, [], "c_stone")
    wall_x(m, -52, 52, 52, 1.3, z0, z1, [], "c_stone")
    wall_y(m, -52, -38, 52, 1.3, z0, z1, [], "c_stone")
    wall_y(m, 52, -38, 52, 1.3, z0, z1, [], "c_stone")
    # Main cross-corridor and store-room / wine-cellar partitions.
    wall_y(m, -14, -36, 48, 0.75, z0, z1, [_door(-29, 3.4, 4.8), _door(-2, 3.4, 4.8), _door(28, 3.4, 4.8)], "c_stone")
    wall_y(m, 14, -36, 48, 0.75, z0, z1, [_door(-2, 3.4, 4.8), _door(28, 3.4, 4.8)], "c_stone")
    wall_x(m, -50, -14, -25, 0.65, z0, z1, [_door(-36, 3.0, 4.8)], "c_stone")
    wall_x(m, 14, 50, -25, 0.65, z0, z1, [_door(32, 3.0, 4.8)], "c_stone")
    wall_x(m, -50, -14, 22, 0.65, z0, z1, [_door(-30, 3.0, 4.8)], "c_stone")
    wall_x(m, 14, 50, 22, 0.65, z0, z1, [_door(32, 3.0, 4.8)], "c_stone")
    # Prison cells: stone end walls, vertical iron bars and open gates; cell interiors remain traversable.
    for cell_y in (-18, -7, 4, 15):
        x0, x1 = -48.5, -29.5
        _add_box(m, (x0, cell_y - 4.6, z0), (x1, cell_y - 4.2, z1), "c_stone", True)
        _add_box(m, (x0, cell_y + 4.2, z0), (x1, cell_y + 4.6, z1), "c_stone", True)
        _add_box(m, (x0, cell_y - 4.6, z0), (x0 + 0.4, cell_y + 4.6, z1), "c_stone", True)
        _add_box(m, (x1 - 0.5, cell_y - 4.6, z0), (x1, cell_y + 4.6, z1), "c_stone", True)
        # Barred frontage along the room corridor with a clear door gap at one side.
        front_x = x1 - 0.15
        for y in [cell_y - 4.1 + i * 0.72 for i in range(12)]:
            if y > cell_y - 0.5 and y < cell_y + 1.2:
                continue
            _add_box(m, (front_x, y - 0.07, z0), (front_x + 0.18, y + 0.07, z1), "c_iron", True)
        _add_box(m, (front_x, cell_y - 4.0, z0), (front_x + 0.22, cell_y + 4.0, z0 + 0.14), "c_iron", True)
        _add_box(m, (front_x, cell_y - 4.0, z1 - 0.12), (front_x + 0.22, cell_y + 4.0, z1), "c_iron", True)
    # Stair down from the west service corridor; it fits the matching ground-floor void.
    _stairs_down_y(m, -44.0, -35.7, 4.2, G, BASEMENT + 0.2, 28, 0.34)
    # A low arched secret passage from the cellar to a concealed courtyard hatch.
    # It runs west under the palace wall, turns south under the garden, then climbs to grade.
    tunnel_floor = BASEMENT
    _floor_rect(m, -88, -29, -14, -25, tunnel_floor, "c_arch", 0.28, True)
    _floor_rect(m, -88, -64, -84, -29, tunnel_floor, "c_arch", 0.28, True)
    # Open entrance aligns with the central cellar; the south wall stops short of the bend to leave a real turn.
    _add_box(m, (-84, -29.0, BASEMENT), (-14, -28.65, -2.0), "c_stone", True)
    _add_box(m, (-88, -25.0, BASEMENT), (-14, -24.65, -2.0), "c_stone", True)
    _add_box(m, (-88.0, -64, BASEMENT), (-87.65, -29, -2.0), "c_stone", True)
    _add_box(m, (-84.0, -64, BASEMENT), (-83.65, -29, -2.0), "c_stone", True)
    _add_box(m, (-88, -29, -2.35), (-14, -25, -2.0), "c_rock")
    _add_box(m, (-88, -64, -2.35), (-84, -29, -2.0), "c_rock")
    # Hidden exit staircase to a low hatch at (-86,-66), below the yew hedge in the west garden.
    count, tread = 28, 0.34
    rise = (G - BASEMENT) / count
    for i in range(count):
        yy = -64.0 - i * tread
        top = BASEMENT + (i + 1) * rise
        _add_box(m, (-87.3, yy - tread, BASEMENT - 0.05), (-84.7, yy, top), "c_stone", True)
    _add_box(m, (-88.0, -74.0, G - 0.05), (-84.0, -70.0, G + 0.22), "c_wood", True)
    return m


def _table(m, x, y, z, w, d, h=0.95, mat="c_wood"):
    _add_box(m, (x - w / 2, y - d / 2, z + h - 0.18), (x + w / 2, y + d / 2, z + h), mat)
    for dx in (-w * 0.40, w * 0.40):
        for dy in (-d * 0.36, d * 0.36):
            _add_box(m, (x + dx - 0.10, y + dy - 0.10, z), (x + dx + 0.10, y + dy + 0.10, z + h - 0.18), "c_wood")


def _chair(m, x, y, z, scale=1.0, throne=False):
    mat = "c_wood"
    _add_box(m, (x - 0.55 * scale, y - 0.52 * scale, z + 0.48 * scale), (x + 0.55 * scale, y + 0.48 * scale, z + 0.70 * scale), mat)
    _add_box(m, (x - 0.55 * scale, y + 0.30 * scale, z + 0.70 * scale), (x + 0.55 * scale, y + 0.52 * scale, z + (1.75 if throne else 1.28) * scale), mat)
    for dx in (-0.42, 0.42):
        _add_box(m, (x + dx * scale - 0.07, y - 0.43 * scale, z), (x + dx * scale + 0.07, y - 0.30 * scale, z + 0.52 * scale), mat)
    if throne:
        for dx in (-0.72, 0.72):
            _add_box(m, (x + dx * scale - 0.11, y - 0.48 * scale, z + 0.62 * scale), (x + dx * scale + 0.11, y + 0.38 * scale, z + 1.05 * scale), "c_gold")
        _add_box(m, (x - 0.66, y + 0.50, z + 1.60), (x + 0.66, y + 0.56, z + 1.72), "c_gold")


def _bed(m, x, y, z, scale=1.0, royal=False):
    w, d = (3.8, 5.1) if royal else (3.0, 4.2)
    w, d = w * scale, d * scale
    _add_box(m, (x - w / 2, y - d / 2, z + 0.35), (x + w / 2, y + d / 2, z + 0.8), "c_wood")
    _add_box(m, (x - w / 2 + 0.15, y - d / 2 + 0.16, z + 0.80), (x + w / 2 - 0.15, y + d / 2 - 0.16, z + 1.04), "c_cloth")
    _add_box(m, (x - w / 2 - 0.16, y + d / 2 - 0.22, z + 0.84), (x + w / 2 + 0.16, y + d / 2 + 0.18, z + 2.0 if royal else z + 1.6), "c_wood")
    for px in (x - w * 0.22, x + w * 0.22):
        _add_box(m, (px - 0.42, y - d / 2 + 0.45, z + 1.03), (px + 0.42, y - d / 2 + 1.28, z + 1.28), "c_marble")
    if royal:
        for dx in (-w / 2 - 0.12, w / 2 + 0.12):
            m.cylinder((x + dx, y + d / 2 - 0.15), 0.12, z + 0.8, z + 4.0, 8, "c_wood", collision=False)
        _add_box(m, (x - w / 2 - 0.12, y + d / 2 - 0.2, z + 3.8), (x + w / 2 + 0.12, y + d / 2 + 0.25, z + 4.05), "c_cloth")


def _bookcase(m, x, y, z, width=6.0, height=4.6, depth=0.5):
    _add_box(m, (x - width / 2, y - depth / 2, z), (x + width / 2, y + depth / 2, z + height), "c_wood")
    for level in range(1, 5):
        zz = z + level * height / 5
        _add_box(m, (x - width / 2 + 0.12, y - depth / 2 - 0.04, zz - 0.12), (x + width / 2 - 0.12, y + depth / 2 + 0.04, zz), "c_arch")
        for k in range(9):
            bx = x - width / 2 + 0.35 + k * (width - 0.7) / 9
            bw = (width - 0.9) / 10
            bh = 0.46 + 0.15 * ((k + level) % 3)
            _add_box(m, (bx, y - 0.20, zz + 0.01), (bx + bw, y + 0.19, min(z + height - 0.2, zz + bh)), "c_cloth" if (k + level) % 3 else "c_marble")


def _barrel(m, x, y, z, radius=0.55, height=1.25):
    for j in range(5):
        z0 = z + height * j / 5
        z1 = z + height * (j + 1) / 5
        r = radius * (0.84 + 0.16 * math.sin(math.pi * j / 5))
        m.cylinder((x, y), r, z0, z1, 12, "c_wood", collision=False, smooth=False)
    for f in (0.22, 0.78):
        m.cylinder((x, y), radius * 0.93, z + height * f, z + height * f + 0.10, 12, "c_iron", collision=False, smooth=False)


def _banner(m, x, y, z, width=3.0, height=5.0, face="south"):
    # A real cloth plane hanging from a horizontal rod, with a gold hem.
    _add_box(m, (x - width / 2, y - 0.08, z + height), (x + width / 2, y + 0.08, z + height + 0.18), "c_wood")
    if face == "south":
        m.quad(((x - width / 2, y, z + height), (x + width / 2, y, z + height),
                (x + width / 2, y, z), (x - width / 2, y, z)), "c_cloth", tile=1.0)
        m.quad(((x + width / 2, y + 0.03, z + height), (x - width / 2, y + 0.03, z + height),
                (x - width / 2, y + 0.03, z), (x + width / 2, y + 0.03, z)), "c_cloth", tile=1.0)
    else:
        m.quad(((x, y - width / 2, z + height), (x, y + width / 2, z + height),
                (x, y + width / 2, z), (x, y - width / 2, z)), "c_cloth", tile=1.0)


def model_furniture():
    m = Mesh("castle_furniture")
    # Throne hall: red-and-gold runner, dais, throne, benches and paired columns.
    m.plane_xy(-2.2, -16.0, 2.2, 20.0, G + 0.035, "c_carpet", tile=3.0)
    _add_box(m, (-6.2, 20.0, G), (6.2, 27.0, G + 0.75), "c_arch")
    _add_box(m, (-5.4, 20.7, G + 0.75), (5.4, 26.4, G + 1.18), "c_marble")
    _chair(m, 0, 23.2, G + 1.16, 1.35, True)
    for x in (-12, 12):
        for y in (-11, -2, 7, 16):
            _add_box(m, (x - 3.0, y - 0.34, G), (x + 3.0, y + 0.34, G + 0.62), "c_wood")
            _add_box(m, (x - 3.0, y + 0.2, G + 0.62), (x + 3.0, y + 0.42, G + 1.55), "c_wood")
    for x in (-26, 26):
        _banner(m, x, -23.2, G + 7.0, 3.2, 8.4, "south")
    # Great Hall chandeliers, chain supports and brass rims.
    for x, y, z in ((0, -3, G + 16.2), (0, 13, G + 16.2), (-39, 13, UPPER + 5.2), (39, 13, UPPER + 5.2)):
        m.cylinder((x, y), 0.10, z - 3.6, z, 8, "c_iron", collision=False)
        m.cylinder((x, y), 1.45, z - 0.5, z - 0.25, 16, "c_gold", collision=False, smooth=False)
        for a in range(0, 360, 45):
            r = math.radians(a)
            px, py = x + 1.15 * math.cos(r), y + 1.15 * math.sin(r)
            m.cylinder((px, py), 0.13, z - 1.0, z, 7, "c_gold", collision=False, smooth=False)
            _add_box(m, (px - 0.11, py - 0.11, z - 1.12), (px + 0.11, py + 0.11, z - 0.82), "c_glass")
    # Dining hall: long table, chairs, serving sideboard and candle sticks.
    _table(m, 39, 14, G, 16.0, 4.2, 1.0)
    for x in (32, 36, 40, 44, 48):
        _chair(m, x, 10.4, G, 0.78)
        _chair(m, x, 17.6, G, 0.78)
    _table(m, 48.5, 3.0, G, 4.0, 1.2, 0.95)
    for x in (34, 39, 44):
        _add_box(m, (x - 0.45, 13.5, G + 1.02), (x + 0.45, 14.5, G + 1.12), "c_marble")
        m.cylinder((x, 14.0), 0.08, G + 1.1, G + 1.8, 6, "c_gold", collision=False)
        _add_box(m, (x - 0.08, 13.92, G + 1.75), (x + 0.08, 14.08, G + 2.0), "c_glass")
    # Library: full-height bookcases, rolling ladders, tables and reading chairs.
    for y in (3, 9, 20, 25):
        _bookcase(m, -40, y, G, 16.0, 4.9, 0.60)
    _table(m, -40, 11.0, G, 8.0, 2.0, 0.86)
    for x in (-43.2, -36.8):
        _chair(m, x, 8.8, G, 0.8)
    # Kitchen / pantry: hearths, counters, shelving, baskets and casks.
    for x in (-47.5, -39.5, -31.5):
        _add_box(m, (x - 1.6, -33.2, G), (x + 1.6, -31.5, G + 1.25), "c_wood")
        _add_box(m, (x - 1.1, -31.45, G + 1.25), (x + 1.1, -31.15, G + 1.45), "c_marble")
    _add_box(m, (-50.0, -23.4, G), (-45.0, -18.2, G + 2.9), "c_stone")
    _add_box(m, (-49.0, -22.8, G + 0.7), (-45.0, -18.1, G + 2.35), "c_iron")
    _add_box(m, (-48.6, -22.6, G + 1.0), (-45.5, -18.05, G + 2.1), "c_iron")
    for x, y in ((-34, -28), (-30, -30), (-47, -12), (-34, -12)):
        _barrel(m, x, y, G, 0.60, 1.45)
    _table(m, -41, -25, G, 7.2, 2.2, 0.9)
    # Guard / council rooms: weapon racks, shields, map table and benches.
    _table(m, 40, -25, G, 7.5, 2.4, 0.92)
    for x in (32, 48):
        _add_box(m, (x - 0.12, -34.0, G + 0.9), (x + 0.12, -19.2, G + 2.3), "c_wood")
        for y in (-32, -29, -26, -23, -20):
            _add_box(m, (x - 0.12, y - 0.06, G + 1.8), (x + 0.12, y + 0.06, G + 3.3), "c_iron")
        for y in (-30.5, -25.5):
            _add_box(m, (x - 0.25, y - 0.65, G + 2.4), (x + 0.25, y + 0.65, G + 3.0), "c_iron")
    for x in (35, 45):
        _add_box(m, (x - 0.8, -29.0, G + 1.2), (x + 0.8, -27.3, G + 3.7), "c_wood")
        m.cylinder((x, -28.0), 0.75, G + 3.7, G + 3.85, 10, "c_iron", collision=False)
    # Rear council / chapel space and sideboard.
    _table(m, 0, 39, G, 9.0, 2.5, 0.95, "c_marble")
    for x in (-14, 14):
        _banner(m, x, 50.2, G + 1.0, 2.8, 4.8, "south")
    # First-floor king's bedchamber and royal family / guest rooms.
    _bed(m, 0, 40, UPPER, 1.0, True)
    _table(m, -7.5, 34.0, UPPER, 2.6, 1.4, 0.82)
    _table(m, 7.5, 34.0, UPPER, 2.6, 1.4, 0.82)
    _bed(m, -41, 37, UPPER, 0.82, True)
    _bed(m, 41, 37, UPPER, 0.82, True)
    _bed(m, -41, -26, UPPER, 0.82)
    _bed(m, 41, -26, UPPER, 0.82)
    _bed(m, -41, 12, UPPER, 0.82)
    _bed(m, 41, 12, UPPER, 0.82)
    for x in (-48, -34, 34, 48):
        _table(m, x, -4, UPPER, 2.2, 1.1, 0.82)
        _chair(m, x, -5.5, UPPER, 0.65)
    # Cellar: wine casks, shelves, storage tables and low work benches.
    for x in (24, 30, 36, 42):
        for y in (-31, -24, -17):
            _barrel(m, x, y, BASEMENT, 0.65, 1.65)
    for x in (-40, -33, -26):
        for y in (28, 35, 42):
            _barrel(m, x, y, BASEMENT, 0.58, 1.4)
    _table(m, 30, 3, BASEMENT, 11, 2.8, 0.86)
    # Torches represented as durable wall fixtures; actual glow is in the separate, time-switched night mesh.
    for x, y, z in ((-20, 3, G + 3.4), (20, 3, G + 3.4), (-39, 12, G + 3.3), (39, 12, G + 3.3),
                    (-39, -24, G + 3.1), (39, -24, G + 3.1), (0, 22, G + 4.0), (0, 39, G + 3.0),
                    (-40, 12, UPPER + 3.0), (40, 12, UPPER + 3.0), (0, 39, UPPER + 3.0),
                    (-34, 2, BASEMENT + 3.2), (-22, 12, BASEMENT + 3.2), (23, 10, BASEMENT + 3.2)):
        _add_box(m, (x - 0.16, y - 0.16, z), (x + 0.16, y + 0.16, z + 0.7), "c_iron")
        _add_box(m, (x - 0.28, y - 0.23, z + 0.45), (x + 0.28, y + 0.23, z + 1.2), "c_glass")
    return m


def _double_sided_glow(m, points, mat="c_glow"):
    p = tuple(points)
    m.quad(p, mat, tile=1.0)
    m.quad((p[1], p[0], p[3], p[2]), mat, tile=1.0)


def _glow_window_y(m, x, y, z, width=2.2, height=3.0, facing=-1):
    # Paired inner/outer planes sit just proud of the two glass faces in the 2.1 m wall.
    sign = -1 if facing < 0 else 1
    for yy in (y + sign * 1.13, y - sign * 0.97):
        p = ((x - width / 2, yy, z), (x + width / 2, yy, z),
             (x + width / 2, yy, z + height), (x - width / 2, yy, z + height))
        _double_sided_glow(m, p)


def _glow_window_x(m, x, y, z, width=2.2, height=3.0, facing=-1):
    sign = -1 if facing < 0 else 1
    for xx in (x + sign * 1.13, x - sign * 0.97):
        p = ((xx, y - width / 2, z), (xx, y + width / 2, z),
             (xx, y + width / 2, z + height), (xx, y - width / 2, z + height))
        _double_sided_glow(m, p)


def model_night():
    m = Mesh("castle_night", emissive=True)
    # Warm emissive panes sit inside genuine window reveals and are faded by client.lua from 06:00 to 18:00.
    for x in (-40, -26, 26, 40):
        _glow_window_y(m, x, -38, G + 4.0, 2.1, 2.8, -1)
    for x in (-40, -25, 25, 40):
        _glow_window_y(m, x, 52, G + 4.0, 2.1, 2.8, 1)
    for x in (-53, 53):
        for y in (-22, -4, 15, 33, 45):
            _glow_window_x(m, x, y, G + 4.0, 2.1, 2.8, -1 if x < 0 else 1)
    for x in (-23, 23):
        _glow_window_y(m, x, -24, G + 5.0, 2.5, 3.2, -1)
        _glow_window_y(m, x, 42, G + 5.0, 2.5, 3.2, 1)
    for x in (-31, 31):
        for y in (-10, 30):
            _glow_window_x(m, x, y, G + 6.0, 2.3, 3.2, -1 if x < 0 else 1)
    # Tower slit lights: evenly spaced rows reinforce the high central silhouette at distance.
    for cx, cy, zbase, n, radius in ((0, 11, G + 24, 6, 5.9), (-20.8, 12, G + 22, 5, 4.3),
                                     (20.8, 12, G + 22, 5, 4.3), (-17.5, 39, G + 18, 4, 3.8),
                                     (17.5, 39, G + 18, 4, 3.8), (-47, -31, G + 7, 4, 4.9),
                                     (47, -31, G + 7, 4, 4.9), (-47, 43, G + 7, 4, 4.9), (47, 43, G + 7, 4, 4.9)):
        for level in range(n):
            a = math.radians(45 + (level % 2) * 45)
            x, y = cx + radius * math.cos(a), cy + radius * math.sin(a)
            m.quad(((x - 0.28, y - 0.28, zbase + level * 5.1), (x + 0.28, y + 0.28, zbase + level * 5.1),
                    (x + 0.28, y + 0.28, zbase + 2.0 + level * 5.1), (x - 0.28, y - 0.28, zbase + 2.0 + level * 5.1)), "c_glow", tile=1)
    # Gatehouse lantern panels and wall-walk torch points.
    for x in (-8, 8):
        _double_sided_glow(m, ((x - 0.26, -96.2, G + 10), (x + 0.26, -96.2, G + 10), (x + 0.26, -96.2, G + 11.4), (x - 0.26, -96.2, G + 11.4)))
    # Time-switched housings match the practical lanterns on the bridge, wall-walks and garden paths.
    def placed_xy(px, py, rz, lx, ly):
        a = math.radians(rz)
        return px + lx * math.cos(a) - ly * math.sin(a), py + lx * math.sin(a) + ly * math.cos(a)

    for name, px, py, pz, rz, zone in PLACEMENTS:
        if name == "castle_bridge":
            for lx in (-11.2, 11.2):
                for ly in (-32, -14, 14, 32):
                    wx, wy = placed_xy(px, py, rz, lx, ly)
                    _double_sided_glow(m, ((wx - 0.22, wy, G + 2.0), (wx + 0.22, wy, G + 2.0),
                                           (wx + 0.22, wy, G + 2.85), (wx - 0.22, wy, G + 2.85)))
        elif name == "castle_wall_run":
            for lx in (-35, -12, 12, 35):
                for ly in (-4.25, 4.25):
                    wx, wy = placed_xy(px, py, rz, lx, ly)
                    ux, uy = 0.26 * math.cos(math.radians(rz)), 0.26 * math.sin(math.radians(rz))
                    _double_sided_glow(m, ((wx - ux, wy - uy, G + 9.3), (wx + ux, wy + uy, G + 9.3),
                                           (wx + ux, wy + uy, G + 10.55), (wx - ux, wy - uy, G + 10.55)))
        elif name == "castle_gatehouse":
            for lx in (-8, 8):
                for ly in (-11.9, 11.9):
                    wx, wy = placed_xy(px, py, rz, lx, ly)
                    _double_sided_glow(m, ((wx - 0.25, wy, G + 10), (wx + 0.25, wy, G + 10),
                                           (wx + 0.25, wy, G + 11.35), (wx - 0.25, wy, G + 11.35)))
        elif name == "castle_outer_tower":
            for deg in range(0, 360, 45):
                a = math.radians(deg + rz)
                nx, ny = math.cos(a), math.sin(a)
                tx, ty = -ny, nx
                wx, wy = placed_xy(px, py, rz, 9.38 * math.cos(math.radians(deg)), 9.38 * math.sin(math.radians(deg)))
                z = G + 8.0
                _double_sided_glow(m, ((wx - tx * 0.24, wy - ty * 0.24, z), (wx + tx * 0.24, wy + ty * 0.24, z),
                                       (wx + tx * 0.24, wy + ty * 0.24, z + 1.45), (wx - tx * 0.24, wy - ty * 0.24, z + 1.45)))
        elif name == "castle_ground":
            for lx, ly in ((-55, -53), (-32, -53), (32, -53), (55, -53), (-55, 49), (-32, 49), (32, 49), (55, 49),
                           (-94, -37), (-94, 0), (-94, 47), (94, -37), (94, 0), (94, 47)):
                wx, wy = placed_xy(px, py, rz, lx, ly)
                _double_sided_glow(m, ((wx - 0.24, wy, G + 2.9), (wx + 0.24, wy, G + 2.9),
                                       (wx + 0.24, wy, G + 3.45), (wx - 0.24, wy, G + 3.45)))
    # Warm ceiling panels in the real rooms: throne hall, library, dining room, royal suite and cellar.
    for x, y, z, sx, sy in ((0, -2, G + 16.0, 2.5, 1.5), (0, 14, G + 16.0, 2.5, 1.5),
                             (-40, 12, G + 5.9, 2.2, 1.4), (40, 13, G + 5.9, 2.2, 1.4),
                             (0, 40, UPPER + 5.4, 2.0, 1.3), (-40, 12, UPPER + 5.4, 1.7, 1.2),
                             (40, 12, UPPER + 5.4, 1.7, 1.2), (30, 1, BASEMENT + 5.3, 1.5, 1.0)):
        m.plane_xy(x - sx, y - sy, x + sx, y + sy, z, "c_glow", tile=1.0, up=False)
    return m


def model_lod():
    m = Mesh("castle_lod", emissive=False)
    # Distant silhouette only: island shoulder, continuous wall, gate mass and recognizable spires.
    _elliptic_loft(m, ((78, 66, -15), (112, 92, -3), (108, 88, 1.0)), 20, "c_rock", False)
    _add_box(m, (-105, -85, 0.0), (105, 85, G + 1.4), "c_stone")
    for y in (-85, 85):
        _add_box(m, (-105, y - 3, G), (105, y + 3, G + 17), "c_stone")
    for x in (-105, 105):
        _add_box(m, (x - 3, -85, G), (x + 3, 85, G + 17), "c_stone")
    # Heavy corner and flank turrets.
    for x, y in ((-105, -85), (105, -85), (-105, 85), (105, 85), (-105, 0), (105, 0), (-60, -85), (60, -85), (-60, 85), (60, 85)):
        m.cylinder((x, y), 10.0, G, G + 28, 10, "c_stone", collision=False, smooth=False)
        m.cone((x, y), 10.5, G + 27, G + 42, 10, "c_roof")
    # Causeway silhouette.
    _add_box(m, (-10, -165, 0), (10, -82, G + 1.6), "c_stone")
    # Palace massing, wings, keep and six tall rooflines.
    _add_box(m, (-53, -38, G), (53, 52, G + 16), "c_stone")
    _add_box(m, (-32, -25, G + 10), (32, 43, G + 28), "c_stone")
    m.gable_roof(-41, 7, 26, 90, G + 15, G + 23, "c_roof", "y", 0.5)
    m.gable_roof(41, 7, 26, 90, G + 15, G + 23, "c_roof", "y", 0.5)
    m.gable_roof(0, 9, 66, 72, G + 27, G + 36, "c_roof", "y", 0.8)
    for x, y, base, h, roof in ((0, 11, G + 35, 39, 91), (-20, 12, G + 30, 36, 73), (20, 12, G + 30, 36, 73),
                               (-17, 39, G + 24, 31, 61), (17, 39, G + 24, 31, 61)):
        _add_box(m, (x - 6, y - 6, base), (x + 6, y + 6, base + h), "c_stone")
        m.pyramid((x, y), 13.5, base + h, G + roof, "c_roof")
    return m


MODELS = {
    "castle_ground": model_ground,
    "castle_bridge": model_bridge,
    "castle_wall_run": model_wall_run,
    "castle_gatehouse": model_gatehouse,
    "castle_outer_tower": model_outer_tower,
    "castle_palace_shell": model_palace_shell,
    "castle_palace_ground": model_palace_ground,
    "castle_palace_upper": model_palace_upper,
    "castle_dungeon": model_dungeon,
    "castle_furniture": model_furniture,
    "castle_night": model_night,
    "castle_lod": model_lod,
}

# Fixed local-coordinate positions for scripted, warm point lights and DX glow cards.
# createLight is used only for player/ped illumination; MTA does not dynamically light map objects.
LIGHTS = [
    # causeway + main/secondary gates
    (0, -142, G + 4, 8, 255, 170, 92), (-10, -101, G + 9, 11, 255, 177, 94), (10, -101, G + 9, 11, 255, 177, 94),
    (-12, -81, G + 8, 10, 255, 178, 99), (12, -81, G + 8, 10, 255, 178, 99), (0, 83, G + 8, 8, 255, 180, 105),
    # wall walks and courtyard
    (-72, -85, G + 10, 9, 255, 167, 87), (72, -85, G + 10, 9, 255, 167, 87),
    (-72, 85, G + 10, 9, 255, 167, 87), (72, 85, G + 10, 9, 255, 167, 87),
    (-105, -42, G + 10, 9, 255, 167, 87), (-105, 42, G + 10, 9, 255, 167, 87),
    (105, -42, G + 10, 9, 255, 167, 87), (105, 42, G + 10, 9, 255, 167, 87),
    (-60, -50, G + 3, 12, 255, 186, 104), (60, -50, G + 3, 12, 255, 186, 104),
    (-73, 7, G + 3, 11, 255, 178, 92), (73, 7, G + 3, 11, 255, 178, 92),
    (-50, 57, G + 3, 10, 255, 178, 96), (50, 57, G + 3, 10, 255, 178, 96),
    # Palace exterior and upper spires
    (-40, -38, G + 7, 12, 255, 181, 105), (-26, -38, G + 7, 12, 255, 181, 105),
    (26, -38, G + 7, 12, 255, 181, 105), (40, -38, G + 7, 12, 255, 181, 105),
    (-53, -4, G + 7, 12, 255, 178, 101), (53, 15, G + 7, 12, 255, 178, 101),
    (0, 11, G + 41, 15, 255, 192, 120), (-20, 12, G + 32, 12, 255, 192, 112), (20, 12, G + 32, 12, 255, 192, 112),
    # real room sources; warm at different radii by zone
    (0, -3, G + 14.5, 12, 255, 176, 98), (0, 14, G + 14.5, 12, 255, 176, 98),
    (-40, 12, G + 5.5, 8, 255, 172, 96), (40, 13, G + 5.5, 9, 255, 178, 102),
    (-39, -24, G + 5.2, 7, 255, 175, 98), (39, -24, G + 5.2, 7, 255, 175, 98),
    (0, 40, UPPER + 5.1, 7, 255, 180, 115), (-40, 12, UPPER + 5.1, 6, 255, 180, 115), (40, 12, UPPER + 5.1, 6, 255, 180, 115),
    (-34, 2, BASEMENT + 2.7, 5, 255, 142, 77), (-22, 12, BASEMENT + 2.7, 5, 255, 142, 77),
    (23, 10, BASEMENT + 2.7, 5, 255, 142, 77),
]

# Local geometry placements. `interior` objects are activated only near the palace.
PLACEMENTS = [
    ("castle_ground", 0, 0, 0, 0, "exterior"),
    ("castle_bridge", 0, -125, 0, 0, "exterior"),
    ("castle_gatehouse", 0, -84, 0, 0, "exterior"),
    ("castle_gatehouse", 0, 84, 0, 180, "exterior"),
    # South and north walls flank the processional gates.
    ("castle_wall_run", -58.5, -85, 0, 0, "exterior"), ("castle_wall_run", 58.5, -85, 0, 0, "exterior"),
    ("castle_wall_run", -58.5, 85, 0, 180, "exterior"), ("castle_wall_run", 58.5, 85, 0, 180, "exterior"),
    # Side walls: two runs per side overlap beneath the corner towers for a sealed perimeter.
    ("castle_wall_run", -105, -38, 0, 90, "exterior"), ("castle_wall_run", -105, 38, 0, 90, "exterior"),
    ("castle_wall_run", 105, -38, 0, 90, "exterior"), ("castle_wall_run", 105, 38, 0, 90, "exterior"),
    # Ten walkable round towers: four corners, four gate flanks, two mid-wall bastions.
    ("castle_outer_tower", -105, -85, 0, 0, "exterior"), ("castle_outer_tower", 105, -85, 0, 0, "exterior"),
    ("castle_outer_tower", -105, 85, 0, 0, "exterior"), ("castle_outer_tower", 105, 85, 0, 0, "exterior"),
    ("castle_outer_tower", -58.5, -85, 0, 0, "exterior"), ("castle_outer_tower", 58.5, -85, 0, 0, "exterior"),
    ("castle_outer_tower", -58.5, 85, 0, 0, "exterior"), ("castle_outer_tower", 58.5, 85, 0, 0, "exterior"),
    ("castle_outer_tower", -105, 0, 0, 0, "exterior"), ("castle_outer_tower", 105, 0, 0, 0, "exterior"),
    # Palace is one planned shell plus separately streamable floors, basement and furnishing set.
    ("castle_palace_shell", 0, 0, 0, 0, "exterior"),
    ("castle_palace_ground", 0, 0, 0, 0, "interior"),
    ("castle_palace_upper", 0, 0, 0, 0, "interior"),
    ("castle_dungeon", 0, 0, 0, 0, "interior"),
    ("castle_furniture", 0, 0, 0, 0, "interior"),
    ("castle_night", 0, 0, 0, 0, "night"),
    ("castle_lod", 0, 0, 0, 0, "lod"),
]
