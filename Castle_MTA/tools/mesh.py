"""Small procedural mesh kit for GTA San Andreas / RenderWare geometry.

Coordinates are metres, right-handed, Z-up. Quads are stored counter-clockwise
when seen from outside; collision is collected independently as COL3 boxes/triangles.
"""
import math
import numpy as np


def _v3(v):
    return np.asarray(v, dtype=np.float64).reshape(3)


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(v))
    return v / max(n, 1e-12)


def _tile_pair(tile):
    if tile is None:
        return 1.0, 1.0
    if isinstance(tile, (tuple, list)):
        return max(float(tile[0]), 1e-6), max(float(tile[1]), 1e-6)
    return max(float(tile), 1e-6), max(float(tile), 1e-6)


class Mesh:
    def __init__(self, name, emissive=False):
        self.name = name
        self.emissive = emissive
        self.pos = []
        self.nrm = []
        self.uv = []
        self.tris = []
        self.tri_mat = []
        self.boxes = []
        self.col_triangles = []

    def _uv_for(self, points, normal, tile):
        tu, tv = _tile_pair(tile)
        n = np.abs(normal)
        if n[2] >= n[0] and n[2] >= n[1]:
            return [(p[0] / tu, -p[1] / tv) for p in points]
        if n[0] >= n[1]:
            return [(p[1] / tu, -p[2] / tv) for p in points]
        return [(p[0] / tu, -p[2] / tv) for p in points]

    def quad(self, points, mat="c_stone", uv=None, tile=4.0, normals=None, collision=False, surface=0):
        p = np.asarray(points, dtype=np.float64).reshape(4, 3)
        face_n = np.cross(p[1] - p[0], p[3] - p[0])
        length = float(np.linalg.norm(face_n))
        if length < 1e-9:
            return
        face_n /= length
        if uv is None:
            uvs = self._uv_for(p, face_n, tile)
        else:
            uvs = np.asarray(uv, dtype=np.float64).reshape(4, 2)
        if normals is None:
            ns = [face_n] * 4
        else:
            ns = [_unit(n) for n in np.asarray(normals, dtype=np.float64).reshape(4, 3)]
        base = len(self.pos)
        self.pos.extend(tuple(float(x) for x in q) for q in p)
        self.nrm.extend(tuple(float(x) for x in q) for q in ns)
        self.uv.extend(tuple(float(x) for x in q) for q in uvs)
        self.tris.extend(((base, base + 1, base + 2), (base, base + 2, base + 3)))
        self.tri_mat.extend((mat, mat))
        if collision:
            self.col_triangles.append((tuple(p[0]), tuple(p[1]), tuple(p[2]), int(surface)))
            self.col_triangles.append((tuple(p[0]), tuple(p[2]), tuple(p[3]), int(surface)))

    def triangle(self, points, mat="c_stone", uv=None, tile=4.0, normals=None, collision=False, surface=0):
        p = np.asarray(points, dtype=np.float64).reshape(3, 3)
        face_n = np.cross(p[1] - p[0], p[2] - p[0])
        length = float(np.linalg.norm(face_n))
        if length < 1e-9:
            return
        face_n /= length
        if uv is None:
            uvs = self._uv_for(p, face_n, tile)
        else:
            uvs = np.asarray(uv, dtype=np.float64).reshape(3, 2)
        if normals is None:
            ns = [face_n] * 3
        else:
            ns = [_unit(n) for n in np.asarray(normals, dtype=np.float64).reshape(3, 3)]
        base = len(self.pos)
        self.pos.extend(tuple(float(x) for x in q) for q in p)
        self.nrm.extend(tuple(float(x) for x in q) for q in ns)
        self.uv.extend(tuple(float(x) for x in q) for q in uvs)
        self.tris.append((base, base + 1, base + 2))
        self.tri_mat.append(mat)
        if collision:
            self.col_triangles.append((tuple(p[0]), tuple(p[1]), tuple(p[2]), int(surface)))

    def box(self, lo, hi, mat="c_stone", collision=False, face_mats=None, skip=(), tile=4.0):
        x0, y0, z0 = map(float, lo)
        x1, y1, z1 = map(float, hi)
        if x1 - x0 < 1e-5 or y1 - y0 < 1e-5 or z1 - z0 < 1e-5:
            return
        faces = {
            "+x": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            "-x": [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)],
            "+y": [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)],
            "-y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            "+z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            "-z": [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
        }
        for side, pts in faces.items():
            if side in skip:
                continue
            self.quad(pts, (face_mats or {}).get(side, mat), tile=tile)
        if collision:
            self.boxes.append((tuple((x0, y0, z0)), tuple((x1, y1, z1)), 0))

    def plane_xy(self, x0, y0, x1, y1, z, mat="c_stone", tile=4.0, up=True, collision=False):
        pts = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
        if not up:
            pts = [pts[0], pts[3], pts[2], pts[1]]
        self.quad(pts, mat, tile=tile, collision=collision)

    def add_box_col(self, lo, hi):
        self.boxes.append((tuple(map(float, lo)), tuple(map(float, hi)), 0))

    def _surface_cyl(self, cx, cy, r, z, n, mat, up=True, collision=False, theta0=0.0, tile=4.0):
        angles = [theta0 + 2 * math.pi * i / n for i in range(n)]
        center = (cx, cy, z)
        points = [(cx + r * math.cos(a), cy + r * math.sin(a), z) for a in angles]
        for i in range(n):
            j = (i + 1) % n
            if up:
                self.triangle((center, points[i], points[j]), mat, tile=tile, collision=collision)
            else:
                self.triangle((center, points[j], points[i]), mat, tile=tile, collision=collision)

    def cylinder(self, center, radius, z0, z1, sides=12, mat="c_stone", top_mat=None,
                 bottom_mat=None, collision=False, smooth=True, theta0=0.0, tile=4.0):
        cx, cy = float(center[0]), float(center[1])
        r = float(radius)
        if r <= 0 or z1 <= z0:
            return
        angles = [theta0 + 2 * math.pi * i / sides for i in range(sides)]
        bottom = [(cx + r * math.cos(a), cy + r * math.sin(a), z0) for a in angles]
        top = [(cx + r * math.cos(a), cy + r * math.sin(a), z1) for a in angles]
        for i in range(sides):
            j = (i + 1) % sides
            normals = None
            if smooth:
                ni = (math.cos(angles[i]), math.sin(angles[i]), 0)
                nj = (math.cos(angles[j]), math.sin(angles[j]), 0)
                normals = (ni, nj, nj, ni)
            self.quad((bottom[i], bottom[j], top[j], top[i]), mat, normals=normals, tile=(2 * math.pi * r / sides, max(z1 - z0, 0.5)), collision=collision)
        self._surface_cyl(cx, cy, r, z1, sides, top_mat or mat, True, collision, theta0, tile)
        self._surface_cyl(cx, cy, r, z0, sides, bottom_mat or mat, False, collision, theta0, tile)
        if collision:
            self.add_box_col((cx - r, cy - r, z0), (cx + r, cy + r, z1))

    def cone(self, center, radius, z0, z1, sides=12, mat="c_roof", tip=None, theta0=0.0, collision=False):
        cx, cy = float(center[0]), float(center[1])
        top = tip if tip is not None else (cx, cy, z1)
        angles = [theta0 + 2 * math.pi * i / sides for i in range(sides)]
        base = [(cx + radius * math.cos(a), cy + radius * math.sin(a), z0) for a in angles]
        for i in range(sides):
            j = (i + 1) % sides
            self.triangle((base[i], base[j], top), mat, tile=4.0, collision=collision)
        self._surface_cyl(cx, cy, radius, z0, sides, mat, False, collision, theta0)

    def pyramid(self, center, width, z0, z1, mat="c_roof", depth=None, collision=False):
        cx, cy = float(center[0]), float(center[1])
        d = width if depth is None else depth
        corners = [(cx - width / 2, cy - d / 2, z0), (cx + width / 2, cy - d / 2, z0),
                   (cx + width / 2, cy + d / 2, z0), (cx - width / 2, cy + d / 2, z0)]
        apex = (cx, cy, z1)
        for i in range(4):
            self.triangle((corners[i], corners[(i + 1) % 4], apex), mat, tile=4.0, collision=collision)

    def gable_roof(self, cx, cy, width, depth, eave_z, ridge_z, mat="c_roof", ridge_axis="y", overhang=0.5):
        """Two pitched roof planes and triangular gable ends; non-collidable by default."""
        x0, x1 = cx - width / 2 - overhang, cx + width / 2 + overhang
        y0, y1 = cy - depth / 2 - overhang, cy + depth / 2 + overhang
        if ridge_axis == "y":
            xm = cx
            self.quad(((xm, y0, ridge_z), (xm, y1, ridge_z), (x0, y1, eave_z), (x0, y0, eave_z)), mat, tile=(7, 7))
            self.quad(((xm, y0, ridge_z), (x1, y0, eave_z), (x1, y1, eave_z), (xm, y1, ridge_z)), mat, tile=(7, 7))
            self.triangle(((x0, y0, eave_z), (x1, y0, eave_z), (xm, y0, ridge_z)), "c_stone", tile=5)
            self.triangle(((x1, y1, eave_z), (x0, y1, eave_z), (xm, y1, ridge_z)), "c_stone", tile=5)
            self.box((x0, y0, eave_z - 0.2), (x1, y1, eave_z + 0.1), "c_arch", collision=False, skip=("+z", "-z", "+x", "-x", "+y", "-y"))
            self.box((cx - 0.35, y0 - 0.1, ridge_z - 0.15), (cx + 0.35, y1 + 0.1, ridge_z + 0.28), "c_arch", collision=False)
        else:
            ym = cy
            self.quad(((x0, ym, ridge_z), (x1, ym, ridge_z), (x1, y0, eave_z), (x0, y0, eave_z)), mat, tile=(7, 7))
            self.quad(((x0, ym, ridge_z), (x0, y1, eave_z), (x1, y1, eave_z), (x1, ym, ridge_z)), mat, tile=(7, 7))
            self.triangle(((x0, y0, eave_z), (x0, y1, eave_z), (x0, ym, ridge_z)), "c_stone", tile=5)
            self.triangle(((x1, y1, eave_z), (x1, y0, eave_z), (x1, ym, ridge_z)), "c_stone", tile=5)
            self.box((x0, y0, eave_z - 0.2), (x1, y1, eave_z + 0.1), "c_arch", collision=False, skip=("+z", "-z", "+x", "-x", "+y", "-y"))
            self.box((x0 - 0.1, cy - 0.35, ridge_z - 0.15), (x1 + 0.1, cy + 0.35, ridge_z + 0.28), "c_arch", collision=False)

    def annulus(self, center, r_inner, r_outer, z, sides=24, mat="c_stone", collision=True, theta0=0.0):
        cx, cy = map(float, center[:2])
        ri, ro = float(r_inner), float(r_outer)
        for i in range(sides):
            a0 = theta0 + 2 * math.pi * i / sides
            a1 = theta0 + 2 * math.pi * (i + 1) / sides
            oi = (cx + ro * math.cos(a0), cy + ro * math.sin(a0), z)
            oj = (cx + ro * math.cos(a1), cy + ro * math.sin(a1), z)
            ij = (cx + ri * math.cos(a1), cy + ri * math.sin(a1), z)
            ii = (cx + ri * math.cos(a0), cy + ri * math.sin(a0), z)
            self.quad((oi, oj, ij, ii), mat, tile=3.5, collision=collision)

    def spiral_steps(self, center, r_inner, r_outer, z0, z1, steps=24, turns=1.0, mat="c_stone", collision=True, theta0=-math.pi / 2):
        cx, cy = map(float, center[:2])
        rise = (z1 - z0) / max(steps, 1)
        for i in range(steps):
            a0 = theta0 + 2 * math.pi * turns * i / steps
            a1 = theta0 + 2 * math.pi * turns * (i + 1) / steps
            z = z0 + rise * i
            oi = (cx + r_outer * math.cos(a0), cy + r_outer * math.sin(a0), z)
            oj = (cx + r_outer * math.cos(a1), cy + r_outer * math.sin(a1), z)
            ij = (cx + r_inner * math.cos(a1), cy + r_inner * math.sin(a1), z)
            ii = (cx + r_inner * math.cos(a0), cy + r_inner * math.sin(a0), z)
            self.quad((oi, oj, ij, ii), mat, tile=2.0, collision=collision)
            if i + 1 < steps:
                zn = z0 + rise * (i + 1)
                self.quad((oi, ii, (cx + r_inner * math.cos(a0), cy + r_inner * math.sin(a0), zn),
                           (cx + r_outer * math.cos(a0), cy + r_outer * math.sin(a0), zn)), mat, tile=2.0, collision=collision)

    def hollow_cylinder_wall(self, center, r_outer, r_inner, z0, z1, sides=24, mat="c_stone",
                             doorway_angle=-math.pi / 2, doorway_width=1.8, collision=True, theta0=0.0):
        """Hollow circular tower wall with a real ground-level doorway gap."""
        cx, cy = map(float, center[:2])
        for i in range(sides):
            a0 = theta0 + 2 * math.pi * i / sides
            a1 = theta0 + 2 * math.pi * (i + 1) / sides
            amid = (a0 + a1) / 2
            # A gap is omitted only at the ground-floor entry. Door width is measured at the outer radius.
            da = abs((amid - doorway_angle + math.pi) % (2 * math.pi) - math.pi)
            if da < doorway_width / max(2 * r_outer, 1) + 0.035:
                continue
            o0 = (cx + r_outer * math.cos(a0), cy + r_outer * math.sin(a0), z0)
            o1 = (cx + r_outer * math.cos(a1), cy + r_outer * math.sin(a1), z0)
            O0 = (o0[0], o0[1], z1)
            O1 = (o1[0], o1[1], z1)
            i0 = (cx + r_inner * math.cos(a0), cy + r_inner * math.sin(a0), z0)
            i1 = (cx + r_inner * math.cos(a1), cy + r_inner * math.sin(a1), z0)
            I0 = (i0[0], i0[1], z1)
            I1 = (i1[0], i1[1], z1)
            # outside and inside skins have opposite winding, with radial end caps closing the stone thickness
            self.quad((o0, o1, O1, O0), mat, tile=(2.3, 4.0), collision=collision)
            self.quad((i1, i0, I0, I1), mat, tile=(2.3, 4.0), collision=collision)
            self.quad((o1, i1, I1, O1), mat, tile=2.5, collision=collision)
            self.quad((i0, o0, O0, I0), mat, tile=2.5, collision=collision)

    def arch_ring(self, cx, plane_y, spring_z, inner_r, outer_r, depth, segments=12, mat="c_arch", collision=True, facing=-1):
        """Extruded semi-circular arch voussoirs around an open doorway in an X/Z wall plane."""
        # angles run left-to-right across the crown. The door itself remains empty.
        angles = [math.pi - math.pi * i / segments for i in range(segments + 1)]
        y0 = plane_y
        y1 = plane_y + (depth if facing < 0 else -depth)
        for i in range(segments):
            a0, a1 = angles[i], angles[i + 1]
            o0 = (cx + outer_r * math.cos(a0), y0, spring_z + outer_r * math.sin(a0))
            o1 = (cx + outer_r * math.cos(a1), y0, spring_z + outer_r * math.sin(a1))
            q0 = (cx + inner_r * math.cos(a0), y0, spring_z + inner_r * math.sin(a0))
            q1 = (cx + inner_r * math.cos(a1), y0, spring_z + inner_r * math.sin(a1))
            O0 = (o0[0], y1, o0[2]); O1 = (o1[0], y1, o1[2])
            Q0 = (q0[0], y1, q0[2]); Q1 = (q1[0], y1, q1[2])
            # A brick-shaped curved wedge; each surface is a real quad (not an alpha texture).
            self.quad((o0, o1, q1, q0), mat, tile=2.0, collision=collision)
            self.quad((Q0, Q1, O1, O0), mat, tile=2.0, collision=collision)
            self.quad((o0, O0, O1, o1), mat, tile=2.0, collision=collision)
            self.quad((q1, Q1, Q0, q0), mat, tile=2.0, collision=collision)
            self.quad((o1, O1, Q1, q1), mat, tile=2.0, collision=collision)
            self.quad((Q0, O0, o0, q0), mat, tile=2.0, collision=collision)


def wall_x(mesh, x0, x1, y, thickness, z0, z1, openings=(), mat="c_stone", frame=True, glass=True):
    """Full-thickness wall parallel to X, split around rectangular windows/door openings.

    openings are dictionaries: {at, width, sill, height, kind='window'|'door'}.
    Door openings start at z0; window openings keep a raised stone sill.
    """
    x0, x1, y, thickness, z0, z1 = map(float, (x0, x1, y, thickness, z0, z1))
    ordered = sorted((dict(o) for o in openings), key=lambda o: float(o["at"]))
    cursor = x0
    for o in ordered:
        center, width = float(o["at"]), float(o["width"])
        left, right = max(x0, center - width / 2), min(x1, center + width / 2)
        if left > cursor:
            mesh.box((cursor, y - thickness / 2, z0), (left, y + thickness / 2, z1), mat, collision=True)
        sill = z0 if o.get("kind") == "door" else max(z0, float(o.get("sill", z0 + 2.1)))
        head = min(z1, sill + float(o.get("height", 2.8)))
        if sill > z0:
            mesh.box((left, y - thickness / 2, z0), (right, y + thickness / 2, sill), mat, collision=True)
        if head < z1:
            mesh.box((left, y - thickness / 2, head), (right, y + thickness / 2, z1), mat, collision=True)
        # Narrow stone jambs are modeled as real geometry and share the wall collision.
        if frame:
            mesh.box((left - 0.12, y - thickness / 2 - 0.11, sill), (left + 0.12, y + thickness / 2 + 0.11, head + 0.1), "c_arch")
            mesh.box((right - 0.12, y - thickness / 2 - 0.11, sill), (right + 0.12, y + thickness / 2 + 0.11, head + 0.1), "c_arch")
            mesh.box((left - 0.2, y - thickness / 2 - 0.13, head), (right + 0.2, y + thickness / 2 + 0.13, head + 0.25), "c_arch")
        if o.get("kind") == "window" and glass:
            gy = y - thickness / 2 - 0.025
            pts = ((left + 0.13, gy, sill), (right - 0.13, gy, sill), (right - 0.13, gy, head), (left + 0.13, gy, head))
            mesh.quad(pts, "c_glass", tile=1.0)
            gy = y + thickness / 2 + 0.025
            mesh.quad(((right - 0.13, gy, sill), (left + 0.13, gy, sill), (left + 0.13, gy, head), (right - 0.13, gy, head)), "c_glass", tile=1.0)
            # Leaded-glass crossbars and a central vertical mullion.
            mesh.box((center - 0.055, y - thickness / 2 - 0.08, sill + 0.1), (center + 0.055, y + thickness / 2 + 0.08, head - 0.1), "c_arch")
            mesh.box((left + 0.13, y - thickness / 2 - 0.08, (sill + head) / 2 - 0.055), (right - 0.13, y + thickness / 2 + 0.08, (sill + head) / 2 + 0.055), "c_arch")
        cursor = max(cursor, right)
    if cursor < x1:
        mesh.box((cursor, y - thickness / 2, z0), (x1, y + thickness / 2, z1), mat, collision=True)


def wall_y(mesh, x, y0, y1, thickness, z0, z1, openings=(), mat="c_stone", frame=True, glass=True):
    """Full-thickness wall parallel to Y. Opening dictionaries use an `at` Y coordinate."""
    x, y0, y1, thickness, z0, z1 = map(float, (x, y0, y1, thickness, z0, z1))
    ordered = sorted((dict(o) for o in openings), key=lambda o: float(o["at"]))
    cursor = y0
    for o in ordered:
        center, width = float(o["at"]), float(o["width"])
        low, high = max(y0, center - width / 2), min(y1, center + width / 2)
        if low > cursor:
            mesh.box((x - thickness / 2, cursor, z0), (x + thickness / 2, low, z1), mat, collision=True)
        sill = z0 if o.get("kind") == "door" else max(z0, float(o.get("sill", z0 + 2.1)))
        head = min(z1, sill + float(o.get("height", 2.8)))
        if sill > z0:
            mesh.box((x - thickness / 2, low, z0), (x + thickness / 2, high, sill), mat, collision=True)
        if head < z1:
            mesh.box((x - thickness / 2, low, head), (x + thickness / 2, high, z1), mat, collision=True)
        if frame:
            mesh.box((x - thickness / 2 - 0.11, low - 0.12, sill), (x + thickness / 2 + 0.11, low + 0.12, head + 0.1), "c_arch")
            mesh.box((x - thickness / 2 - 0.11, high - 0.12, sill), (x + thickness / 2 + 0.11, high + 0.12, head + 0.1), "c_arch")
            mesh.box((x - thickness / 2 - 0.13, low - 0.2, head), (x + thickness / 2 + 0.13, high + 0.2, head + 0.25), "c_arch")
        if o.get("kind") == "window" and glass:
            gx = x - thickness / 2 - 0.025
            mesh.quad(((gx, low + 0.13, sill), (gx, high - 0.13, sill), (gx, high - 0.13, head), (gx, low + 0.13, head)), "c_glass", tile=1.0)
            gx = x + thickness / 2 + 0.025
            mesh.quad(((gx, high - 0.13, sill), (gx, low + 0.13, sill), (gx, low + 0.13, head), (gx, high - 0.13, head)), "c_glass", tile=1.0)
            mesh.box((x - thickness / 2 - 0.08, center - 0.055, sill + 0.1), (x + thickness / 2 + 0.08, center + 0.055, head - 0.1), "c_arch")
            mesh.box((x - thickness / 2 - 0.08, low + 0.13, (sill + head) / 2 - 0.055), (x + thickness / 2 + 0.08, high - 0.13, (sill + head) / 2 + 0.055), "c_arch")
        cursor = max(cursor, high)
    if cursor < y1:
        mesh.box((x - thickness / 2, cursor, z0), (x + thickness / 2, y1, z1), mat, collision=True)
