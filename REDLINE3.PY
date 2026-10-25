#!/usr/bin/env python3
"""
REDLINE HORIZON - a pseudo-3D arcade racer in Pygame (v2)
=========================================================
Race rivals and traffic across four procedurally built tracks.

  * Real software-rendered 3D cars: lofted bodywork, spinning rims, glass
    reflections, shadows, brake / signal / head lights, body roll and pitch
  * Three cameras (chase, hood, cockpit) with FOV kick and camera lag
  * Tunnels, bridges, guardrails, grandstands, wind turbines, swaying trees,
    skid marks, road seams and patches, birds, lightning, rain and snow
  * 6-speed gearbox, turbo spool + blow-off, slipstream drafting, drifting,
    nitro, damage, rumble strips, prize money, garage upgrades, minimap
  * Fully synthesized engine, turbo, skid, rumble, wind and thunder audio

Run:      pip install pygame
          python redline_horizon.py

Controls
  Accelerate ..... Up / W            Brake ........... Down / S
  Steer .......... Left / Right or A / D
  Nitro .......... Left Shift         Drift ........... Space (while steering)
  Camera ......... C                  Pause ........... P or Esc     Mute ... M
  Menus .......... Arrows + Enter, Esc to go back

Tips: Drifting charges your nitro tank, and a long drift releases a free
boost when you let go. Clipping roadside objects or traffic costs speed.
Finish on the podium to unlock the next track.
"""
import array
import json
import math
import os
import random
import sys

import pygame

# --------------------------------------------------------------------------
# Rendering / physics constants (classic segment-based road projection)
# --------------------------------------------------------------------------
W, H = 1024, 640
FPS = 60
SEGL = 200                 # length of one road segment
ROADW = 2000               # half road width in world units
RUMBLE = 3                 # segments per rumble-strip colour band
LANES = 3
FOV = 100
CAMH = 1000                # camera height above road
DRAW = 230                 # draw distance in segments
RAIL_H = 150               # guard rail height
TUN_W, TUN_H = 2300, 3040  # tunnel half width / height (height matches the portal sprite's aspect)
FOGD = 5.0
CAMD = 1.0 / math.tan(math.radians(FOV / 2))
PLAYERZ = CAMH * CAMD      # distance from camera to the player car
MAXSPEED = SEGL * 60.0
CENTRIF = 0.3
PLAYER_W = 0.28
HALF_W, HALF_H = W / 2, H / 2
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "redline_save.json")

CAR_COLORS = [(214, 40, 40), (240, 130, 30), (240, 210, 50), (60, 190, 90),
              (40, 150, 230), (140, 80, 220), (235, 235, 240), (30, 30, 36)]
RIVAL_NAMES = ["Vex", "Nova", "Rook", "Echo", "Blitz"]

TRACKS = [
    dict(name="Coastal Sprint", theme="coast", seed=11, laps=3, diff=0.78, traffic=16,
         length=2000, curve=0.6, hill=0.5, blurb="Sunny seaside sweepers. A gentle start."),
    dict(name="Mesa Canyon", theme="mesa", seed=23, laps=3, diff=0.85, traffic=20,
         length=2300, curve=0.85, hill=0.95, blurb="Desert sunset, big crests, blind drops."),
    dict(name="Alpine Pass", theme="alpine", seed=37, laps=3, diff=0.91, traffic=18,
         length=2500, curve=1.05, hill=1.0, blurb="Snowy switchbacks at dusk. Don't overcook it."),
    dict(name="Neon Harbor", theme="city", seed=41, laps=3, diff=0.96, traffic=26,
         length=2600, curve=1.2, hill=0.55, blurb="Night, rain, chicanes and heavy traffic."),
]

THEMES = {
    "coast": dict(name="Coastal", sky=((60, 130, 225), (205, 232, 255)), fog=(176, 214, 246),
                  road=((107, 107, 107), (99, 99, 99)), grass=((72, 172, 82), (60, 156, 72)),
                  rumble=((225, 225, 225), (205, 45, 45)), lane=(238, 238, 238),
                  bg="coast", weather=None, night=False,
                  pool=["palm", "palm", "palm", "bush", "rock", "ad"]),
    "mesa": dict(name="Mesa", sky=((70, 40, 120), (252, 178, 96)), fog=(240, 172, 112),
                 road=((128, 106, 92), (118, 98, 86)), grass=((214, 148, 88), (200, 134, 76)),
                 rumble=((232, 212, 182), (152, 62, 42)), lane=(240, 225, 190),
                 bg="mesa", weather=None, night=False,
                 pool=["cactus", "cactus", "rock", "rock", "bush", "ad"]),
    "alpine": dict(name="Alpine", sky=((26, 36, 98), (244, 164, 176)), fog=(196, 178, 210),
                   road=((90, 94, 106), (82, 86, 98)), grass=((232, 240, 250), (212, 224, 240)),
                   rumble=((236, 236, 242), (64, 92, 205)), lane=(235, 235, 240),
                   bg="alpine", weather="snow", night=False,
                   pool=["pine", "pine", "pine", "pine", "rock", "ad"]),
    "city": dict(name="Harbor", sky=((4, 4, 18), (70, 24, 88)), fog=(38, 20, 58),
                 road=((46, 48, 60), (40, 42, 54)), grass=((20, 28, 40), (16, 22, 34)),
                 rumble=((200, 200, 212), (222, 30, 120)), lane=(232, 232, 120),
                 bg="city", weather="rain", night=True,
                 pool=["building", "building", "neon", "bush", "rock"]),
}

# width of every roadside object as a fraction of the road half-width
SPRITE_W = {"turbine": 0.5, "tires": 0.6, "stand": 2.2, "bridge": 3.0, "portal": 3.6, "palm": 0.85, "pine": 0.75, "cactus": 0.45, "rock": 0.65, "bush": 0.55,
            "lamp": 0.14, "building": 2.0, "neon": 1.2, "ad": 1.1,
            "chev_l": 0.35, "chev_r": 0.35, "gantry": 2.6}
NON_SOLID = {"gantry", "bridge", "portal", "turbine"}
CAR_W = {"coupe": 0.28, "sports": 0.28, "sedan": 0.28, "van": 0.30, "truck": 0.36}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def ease_in(a, b, p):
    return a + (b - a) * p * p


def ease_io(a, b, p):
    return a + (b - a) * (-math.cos(p * math.pi) / 2 + 0.5)


def mix(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def shade(c, f):
    return (clamp(int(c[0] * f), 0, 255), clamp(int(c[1] * f), 0, 255), clamp(int(c[2] * f), 0, 255))


def overlap(x1, w1, x2, w2, pct=1.0):
    half = pct / 2
    return not ((x1 + w1 * half) < (x2 - w2 * half) or (x1 - w1 * half) > (x2 + w2 * half))


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def fmt_time(t):
    if t is None:
        return "--:--.--"
    m, s = divmod(t, 60)
    return f"{int(m):d}:{s:05.2f}"


# --------------------------------------------------------------------------
# Track: segments, curves, hills, scenery
# --------------------------------------------------------------------------
class Seg:
    __slots__ = ("idx", "y1", "y2", "curve", "flag", "sprites", "cars", "rail", "tunnel", "decals", "hue", "v",
                 "sx1", "sy1", "sw1", "ss1", "sx2", "sy2", "sw2", "ss2", "clip", "fog", "ok")

    def __init__(self, idx, y1, y2, curve):
        self.idx, self.y1, self.y2, self.curve = idx, y1, y2, curve
        self.flag = (idx // RUMBLE) % 2
        self.sprites, self.cars, self.decals = [], [], []
        self.rail, self.tunnel, self.hue, self.v = 0, False, 1.0, False
        self.clip = H
        self.fog = 0.0
        self.ok = False
        self.sx1 = self.sy1 = self.sw1 = self.ss1 = 0.0
        self.sx2 = self.sy2 = self.sw2 = self.ss2 = 0.0


class Track:
    def __init__(self, spec):
        self.spec = spec
        self.name = spec["name"]
        self.theme = THEMES[spec["theme"]]
        rng = random.Random(spec["seed"])
        segs = self.segs = []

        def last_y():
            return segs[-1].y2 if segs else 0.0

        def add(curve, y):
            segs.append(Seg(len(segs), last_y(), y, curve))

        def road(enter, hold, leave, curve, y):
            start, end = last_y(), last_y() + int(y) * SEGL
            total = enter + hold + leave
            for n in range(enter):
                add(ease_in(0, curve, n / enter), ease_io(start, end, n / total))
            for n in range(hold):
                add(curve, ease_io(start, end, (enter + n) / total))
            for n in range(leave):
                add(ease_io(curve, 0, n / leave), ease_io(start, end, (enter + hold + n) / total))

        k, hs = spec["curve"], spec["hill"]
        road(25, 25, 25, 0, 0)
        while len(segs) < spec["length"]:
            r = rng.random()
            ly = last_y() / SEGL
            sign = -1 if ly > 45 * hs else (1 if ly < 4 else rng.choice((-1, 1)))
            direction = rng.choice((-1, 1))
            cmag = rng.choice((2, 2, 4, 4, 6) if k < 1 else (2, 4, 4, 6, 6))
            if r < 0.14:
                road(25, rng.choice((25, 50)), 25, 0, 0)
            elif r < 0.30:
                n = rng.choice((25, 50))
                road(n, n, n, 0, sign * rng.choice((20, 40, 60)) * hs)
            elif r < 0.56:
                n = rng.choice((25, 50, 75))
                road(n, n, n, direction * cmag, sign * rng.choice((0, 0, 20, 40)) * hs)
            elif r < 0.68:
                n = 25
                road(n, n, n, 0, sign * 20 * hs)
                road(n, n, n, 0, -sign * 36 * hs)
                road(n, n, n, direction * 2, sign * 16 * hs)
                road(n, n, n, 0, 0)
            elif r < 0.80:
                c = 2 + 2 * k
                road(25, 25, 25, direction * c, 0)
                road(25, 25, 25, -direction * c * 1.2, 0)
            elif r < 0.88:
                road(15, 15, 15, direction * (3 + 2 * k), 0)      # chicane
                road(15, 15, 15, -direction * (3 + 2 * k), 0)
                road(15, 15, 15, direction * (3 + 2 * k), 0)
            elif r < 0.94:
                for _ in range(4):
                    road(8, 8, 8, 0, rng.choice((3, -2, 4)))
            else:
                n = rng.choice((50, 75, 100))
                road(n, n, n, direction * 6, 0)                    # long hard bend
        road(100, 100, 100, -2, -last_y() / SEGL)                   # roll back down to y = 0
        segs[-1].y2 = 0.0
        self.length = len(segs) * SEGL

        # start / finish stripe + gantry
        segs[0].flag, segs[1].flag = 2, 3
        segs[0].sprites.append(("gantry", 0.0, -0.5))
        self.place_scenery(rng)
        self.place_features(rng)
        self.build_map()

    def place_scenery(self, rng):
        segs, th = self.segs, self.theme
        n = len(segs)
        i = 6
        while i < n - 6:
            side = rng.choice((-1, 1))
            key = rng.choice(th["pool"])
            off = side * (1.25 + rng.random() * 3.2) if key not in ("building",) else side * (2.4 + rng.random() * 3)
            if key in ("ad", "neon"):
                off = side * (1.6 + rng.random() * 0.8)
            segs[i].sprites.append((key, off, -1 if off < 0 else 0))
            if rng.random() < 0.35:       # grove: a second one on the same stretch
                off2 = side * (1.3 + rng.random() * 4.5)
                k2 = rng.choice([p for p in th["pool"] if p not in ("ad", "neon")] or ["rock"])
                segs[i].sprites.append((k2, off2, -1 if off2 < 0 else 0))
            i += rng.randint(3, 7)
        if th["night"]:
            for j in range(4, n, 7):
                segs[j].sprites.append(("lamp", -1.12, -1))
                segs[j].sprites.append(("lamp", 1.12, 0))
        for j in range(2, n):                       # chevron signs before hard bends
            if abs(segs[j].curve) >= 3.2 and abs(segs[j - 1].curve) < 3.2:
                side = -1 if segs[j].curve > 0 else 1
                key = "chev_r" if segs[j].curve > 0 else "chev_l"
                for d in (14, 8, 2):
                    if j - d >= 0:
                        segs[j - d].sprites.append((key, side * 1.18, -1 if side < 0 else 0))

    def place_features(self, rng):
        segs, th = self.segs, self.theme
        n, bg = len(segs), th["bg"]
        for s in segs:
            s.hue = rng.uniform(0.95, 1.05)
        # tunnels: a few straight, gentle stretches
        want = {"alpine": 2, "city": 2, "mesa": 1}.get(bg, 0)
        placed = 0
        for _ in range(500):
            if placed >= want:
                break
            ln = 70
            i = rng.randint(400, n - ln - 150)
            win = segs[i:i + ln + 1]
            if any(s.tunnel for s in segs[i - 30:i + ln + 30]):
                continue
            if max(abs(s.curve) for s in win) > 1.6 or max(abs(s.y2 - s.y1) for s in win) > SEGL * 0.9:
                continue
            for s in segs[i:i + ln]:
                s.tunnel, s.sprites = True, []
            segs[i].sprites.append(("portal", 0.0, -0.5))
            segs[i + ln - 1].sprites.append(("portal", 0.0, -0.5))
            placed += 1
        for s in segs:                                  # guard rails on the outside of hard bends
            if not s.tunnel and abs(s.curve) >= 2.4:
                s.rail = 1 if s.curve > 0 else 2
        for s in segs:                                  # road seams and tar patches
            r = rng.random()
            if r < 0.05:
                s.decals.append(("seam", rng.random()))
            elif r < 0.08:
                s.decals.append(("patch", rng.uniform(-0.8, 0.8), rng.random()))
        for i in (8, 11):                               # grandstands at the start line
            segs[i].sprites.append(("stand", -1.45, -1))
            segs[i].sprites.append(("stand", 1.45, 0))
        for i in range(30, n - 30, 5):                  # tyre barriers on the outside of tight bends
            s = segs[i]
            if abs(s.curve) >= 4.0 and not s.tunnel:
                side = -1 if s.curve > 0 else 1
                s.sprites.append(("tires", side * 1.32, -1 if side < 0 else 0))
        if bg in ("coast", "mesa"):
            for i in range(40, n, 95):
                side = rng.choice((-1, 1))
                if not segs[i].tunnel:
                    off = side * rng.uniform(6.5, 10)
                    segs[i].sprites.append(("turbine", off, -1 if off < 0 else 0))
        if bg in ("coast", "alpine", "city"):
            for i in range(300, n - 200, 520):
                if not any(s.tunnel for s in segs[i - 10:i + 10]):
                    segs[i].sprites.append(("bridge", 0.0, -0.5))

    def build_map(self):
        pts, x, y, ang = [], 0.0, 0.0, 0.0
        for s in self.segs:
            ang += s.curve * 0.0016
            x += math.cos(ang)
            y += math.sin(ang)
            pts.append((x, y))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        sc = 1.0 / max(maxx - minx, maxy - miny, 1e-6)
        ox = (1 - (maxx - minx) * sc) / 2
        oy = (1 - (maxy - miny) * sc) / 2
        self.map_pts = [((px - minx) * sc + ox, (py - miny) * sc + oy) for px, py in pts]

    def seg_at(self, z):
        return self.segs[int(z // SEGL) % len(self.segs)]


# --------------------------------------------------------------------------
# A tiny software 3D engine for the cars (lofted meshes, shading, painter's sort)
# --------------------------------------------------------------------------
def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def v_norm(a):
    ln = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) or 1.0
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def rot_matrix(yaw, pitch, roll):
    cy, sy, cp, sp, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll)
    rz = [[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]]
    rx = [[1, 0, 0], [0, cp, -sp], [0, sp, cp]]
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    return mat_mul(ry, mat_mul(rx, rz))


def m_apply(m, p):
    return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2],
            m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2],
            m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2])


class Face:
    __slots__ = ("pts", "color", "mat", "n", "c")

    def __init__(self, pts, color, mat, center=None):
        self.pts, self.color, self.mat = pts, color, mat
        a, b, c = pts[0], pts[1], pts[2]
        n = v_norm(v_cross(v_sub(b, a), v_sub(c, a)))
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        cz = sum(p[2] for p in pts) / len(pts)
        self.c = (cx, cy, cz)
        if center is not None and v_dot(n, v_sub(self.c, center)) < 0:
            n = (-n[0], -n[1], -n[2])
        self.n = n


def ring6(z, wb, ws, wt, y0, ys, yt):
    return [(-wb, y0, z), (wb, y0, z), (ws, ys, z), (wt, yt, z), (-wt, yt, z), (-ws, ys, z)]


def ring4(z, wb, wr, yb, yr):
    return [(-wb, yb, z), (wb, yb, z), (wr, yr, z), (-wr, yr, z)]


def loft(rings, mat_fn, color, center, caps=True):
    faces = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        n = len(a)
        for j in range(n):
            k = (j + 1) % n
            mat, col = mat_fn(i, j, color)
            if mat:
                faces.append(Face([a[j], a[k], b[k], b[j]], col, mat, center))
    if caps:
        faces.append(Face(rings[0][:], color, "body", center))
        faces.append(Face(rings[-1][:], color, "body", center))
    return faces


def box(cx, cy, cz, sx, sy, sz, color, mat, center=None):
    x0, x1, y0, y1, z0, z1 = cx - sx, cx + sx, cy - sy, cy + sy, cz - sz, cz + sz
    ctr = center or (cx, cy, cz)
    q = [((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)), ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
         ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)), ((x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)),
         ((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)), ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))]
    return [Face(list(p), color, mat, ctr) for p in q]


WHEEL_CACHE = {}


def wheel(cx, cy, cz, r, half_w, phase, steer, outward, n=12):
    """Tire tread + sidewall + star-shaped rim. outward = +1 (right side) / -1 (left side).
    Meshes are cached on a quantised (phase, steer) grid, since the rim pattern repeats every 2*pi/(n/2)."""
    period = 2 * math.pi / (n / 2)
    pq = int(round((phase % period) / period * 24)) % 24
    sq = round(steer * 20) / 20.0
    key = (cx, cy, cz, r, outward, pq, sq, n)
    hit = WHEEL_CACHE.get(key)
    if hit is not None:
        return hit
    phase, steer = pq / 24.0 * period, sq
    faces = []
    cs, sn = math.cos(steer), math.sin(steer)

    def P(x, y, z):                       # wheel-local -> car space with steering about the wheel's vertical axis
        return (cx + x * cs + z * sn, cy + y, cz - x * sn + z * cs)

    ctr = (cx, cy, cz)
    ang = [phase + 2 * math.pi * i / n for i in range(n)]
    xo, xi = outward * half_w, -outward * half_w
    for i in range(n):
        j = (i + 1) % n
        a, b = ang[i], ang[j]
        ya, za, yb, zb = r * math.sin(a), r * math.cos(a), r * math.sin(b), r * math.cos(b)
        faces.append(Face([P(xo, ya, za), P(xo, yb, zb), P(xi, yb, zb), P(xi, ya, za)], (18, 18, 20), "tire", ctr))
        r2 = r * 0.66
        ya2, za2, yb2, zb2 = r2 * math.sin(a), r2 * math.cos(a), r2 * math.sin(b), r2 * math.cos(b)
        faces.append(Face([P(xo, ya, za), P(xo, yb, zb), P(xo, yb2, zb2), P(xo, ya2, za2)], (26, 26, 30), "tire", ctr))
    star = []
    for i in range(n):
        rr = r * 0.66 if i % 2 == 0 else r * 0.30
        star.append(P(xo + outward * 0.01, rr * math.sin(ang[i]), rr * math.cos(ang[i])))
    faces.append(Face(star, (176, 182, 196), "rim", ctr))
    faces.append(Face([P(xo + outward * 0.02, r * 0.16 * math.sin(a), r * 0.16 * math.cos(a)) for a in ang],
                      (70, 72, 80), "rim", ctr))
    WHEEL_CACHE[key] = faces
    return faces


# body definitions: (sections for body ring6, cabin sections, length, wheel layout)
SPORTS_BODY = [(-2.20, .78, .93, .84, .26, .52, .86), (-2.05, .84, .95, .88, .24, .55, .92), (-1.20, .88, .97, .86, .22, .58, .95),
               (-0.20, .86, .94, .80, .22, .56, .84), (0.90, .86, .94, .80, .22, .52, .74), (1.80, .82, .90, .76, .24, .46, .60),
               (2.25, .74, .82, .68, .26, .42, .48)]
SPORTS_CABIN = [(-1.25, .82, .70, .93, .98), (-0.75, .80, .66, .92, 1.20), (0.15, .80, .64, .86, 1.24), (1.25, .78, .60, .72, .80)]
SEDAN_BODY = [(-2.25, .80, .90, .82, .26, .58, .96), (-2.10, .84, .92, .86, .24, .60, 1.00), (-1.30, .88, .94, .88, .22, .62, 1.02),
              (-0.20, .88, .94, .84, .22, .60, .94), (1.10, .88, .94, .82, .22, .58, .84), (2.00, .84, .90, .78, .24, .52, .68),
              (2.35, .76, .84, .70, .26, .46, .56)]
SEDAN_CABIN = [(-1.45, .84, .72, 1.00, 1.08), (-0.85, .82, .70, .99, 1.42), (0.35, .82, .68, .94, 1.46), (1.10, .80, .62, .86, .94)]
VAN_BODY = [(-2.30, .86, .95, .90, .30, .70, 1.65), (-2.15, .88, .96, .92, .28, .72, 1.72), (1.40, .88, .96, .92, .28, .74, 1.72),
            (2.05, .84, .92, .86, .28, .66, 1.30), (2.30, .78, .86, .78, .30, .56, .90)]
FLAT_FACE = {"body": 1.0}



def catmull(keys, sub=3):
    """Smoothly interpolate rows of numbers (first column = z) with Catmull-Rom; returns sub*(n-1)+1 rows."""
    out = []
    n = len(keys)
    for i in range(n - 1):
        p0, p1, p2, p3 = keys[max(0, i - 1)], keys[i], keys[i + 1], keys[min(n - 1, i + 2)]
        for k in range(sub):
            t = k / sub
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                                    + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in range(len(p1))))
    out.append(tuple(keys[-1]))
    return out


SUB = 3
STATIC = {}


def build_static(kind, color):
    """Body / glass / fixed details. Cached per (kind, color)."""
    key = (kind, color)
    if key in STATIC:
        return STATIC[key]
    faces = []
    body_sections = {"sports": SPORTS_BODY, "coupe": SPORTS_BODY, "sedan": SEDAN_BODY, "van": VAN_BODY, "truck": VAN_BODY}[kind]
    ctr_body = (0, 0.55, 0)
    if kind == "van" or kind == "truck":
        rings = [ring6(*s) for s in body_sections]            # boxy: no smoothing
    else:
        rings = [ring6(*s) for s in catmull(body_sections, SUB)]

    def body_mat(i, j, col):
        if j == 0:
            return "under", (10, 10, 12)
        return "body", col

    if kind == "truck":
        cab = [ring6(-0.60, .86, .95, .90, .30, .70, 1.55), ring6(0.0, .88, .96, .92, .28, .72, 1.62),
               ring6(1.0, .84, .92, .86, .28, .66, 1.30), ring6(1.5, .78, .86, .78, .30, .56, .90)]
        faces += loft(cab, body_mat, color, (0, .9, 0.4))
        faces += box(0, 1.50, -1.62, .98, 1.08, 1.5, (212, 214, 222), "cargo", (0, 1.5, -1.6))
        faces += box(0, 0.42, -1.62, .90, .10, 1.5, (24, 24, 28), "under", (0, .4, -1.6))
    else:
        faces += loft(rings, body_mat, color, ctr_body)
    if kind in ("sports", "coupe", "sedan"):
        secs = SEDAN_CABIN if kind == "sedan" else SPORTS_CABIN
        if kind == "coupe":
            secs = [(z, a, b, c, d + (0.04 if i in (1, 2) else 0)) for i, (z, a, b, c, d) in enumerate(SPORTS_CABIN)]
        cabin = [ring4(*s) for s in catmull(secs, SUB + 1)]
        sub = SUB + 1

        def cab_mat(i, j, col):
            if j == 0:
                return None, col
            if j == 2:
                return ("glass", col) if (i // sub) in (0, 2) else ("body", col)
            return "glass", col

        faces += loft(cabin, cab_mat, color, (0, 1.0, 0), caps=False)
        yb = secs[0][3]
        faces.append(Face([(-.68, yb + .05, secs[0][0] - 0.01), (.68, yb + .05, secs[0][0] - 0.01),
                           (.60, secs[1][4] - .02, secs[1][0] - 0.05), (-.60, secs[1][4] - .02, secs[1][0] - 0.05)],
                          (10, 14, 22), "glass", (0, 1.0, 0.0)))
    elif kind == "van":
        faces += box(0, 1.28, 1.55, .80, .26, .03, (14, 20, 30), "glass", (0, 1.3, 0))
        faces += box(0, 1.30, -2.31, .70, .30, .02, (14, 20, 30), "glass", (0, 1.3, 0))
    rz = {"sports": -2.215, "coupe": -2.215, "sedan": -2.265, "van": -2.315, "truck": -3.14}[kind]
    ty = {"sports": .78, "coupe": .78, "sedan": .84, "van": 1.0, "truck": .85}[kind]
    if kind == "truck":
        faces.append(Face([(-.85, .52, -3.13), (.85, .52, -3.13), (.85, .64, -3.13), (-.85, .64, -3.13)], color, "body", (0, .5, -2)))
    faces.append(Face([(-.26, ty - .20, rz - .005), (.26, ty - .20, rz - .005), (.26, ty - .06, rz - .005), (-.26, ty - .06, rz - .005)],
                      (236, 236, 230), "plate", (0, ty, rz + 1)))
    if kind in ("sports", "coupe"):
        faces += box(0, .30, -2.12, .70, .07, .10, (20, 20, 24), "carbon")
        wing_h = 1.07 if kind == "coupe" else 1.0
        faces += box(0, wing_h + .02, -2.10, .98, .025, .20, (22, 22, 26), "carbon")
        for sgn in (-1, 1):
            faces += box(sgn * 0.98, wing_h - .04, -2.10, .02, .12, .22, (22, 22, 26), "carbon")
            faces += box(sgn * 0.45, wing_h - .22, -2.08, .025, .20, .03, (30, 30, 34), "carbon")
    for ex in ((-.42, .42) if kind in ("sports", "coupe") else (.62,)):
        ey = .33 if kind in ("sports", "coupe") else .30
        faces.append(Face([(ex + .08 * math.cos(a), ey + .08 * math.sin(a), rz - .02) for a in [i * math.pi / 4 for i in range(8)]],
                          (190, 194, 204), "chrome", (ex, ey, rz + 1)))
        faces.append(Face([(ex + .055 * math.cos(a), ey + .055 * math.sin(a), rz - .025) for a in [i * math.pi / 4 for i in range(8)]],
                          (8, 8, 10), "under", (ex, ey, rz + 1)))
    fz = {"sports": 2.255, "coupe": 2.255, "sedan": 2.375, "van": 2.32, "truck": 1.52}[kind]
    fy = {"sports": .38, "coupe": .38, "sedan": .50, "van": .65, "truck": .62}[kind]
    faces.append(Face([(-.34, fy - .12, fz + .005), (.34, fy - .12, fz + .005), (.34, fy + .0, fz + .005), (-.34, fy + .0, fz + .005)],
                      (14, 14, 16), "under", (0, fy, fz - 1)))
    if kind in ("sports", "coupe", "sedan"):
        for sgn in (-1, 1):
            faces += box(sgn * .98, .96 if kind != "sedan" else 1.08, .78, .07, .05, .09, color, "body")
    STATIC[key] = faces
    return faces


def build_dynamic(kind, st):
    faces = []
    steer, wph = st.get("steer", 0.0), st.get("wphase", 0.0)
    brake, sig, boost, lights = st.get("brake", False), st.get("sig", 0), st.get("boost", False), st.get("lights", False)
    rz = {"sports": -2.215, "coupe": -2.215, "sedan": -2.265, "van": -2.315, "truck": -3.14}[kind]
    ty = {"sports": .78, "coupe": .78, "sedan": .84, "van": 1.0, "truck": .85}[kind]
    tail_on = (255, 70, 60) if brake else (178, 24, 24)
    for sgn in (-1, 1):
        x0, x1 = (0.20, 0.84) if sgn > 0 else (-0.84, -0.20)
        if kind == "van":
            x0, x1 = (0.70, 0.92) if sgn > 0 else (-0.92, -0.70)
        faces.append(Face([(x0, ty - .08, rz - .004), (x1, ty - .08, rz - .004), (x1, ty + .06, rz - .004), (x0, ty + .06, rz - .004)],
                          tail_on, "light", (0, ty, rz + 1)))
        if sig and ((sig == 1 and sgn < 0) or (sig == 2 and sgn > 0)):
            xa, xb = (0.60, 0.84) if sgn > 0 else (-0.84, -0.60)
            faces.append(Face([(xa, ty - .16, rz - .006), (xb, ty - .16, rz - .006), (xb, ty - .09, rz - .006), (xa, ty - .09, rz - .006)],
                              (255, 170, 20), "light", (0, ty, rz + 1)))
    if boost:
        for ex in ((-.42, .42) if kind in ("sports", "coupe") else (.62,)):
            ey = .33 if kind in ("sports", "coupe") else .30
            fl = 0.9 + 0.35 * random.random()
            faces.append(Face([(ex - .07, ey, rz - .03), (ex + .07, ey, rz - .03), (ex, ey + .01, rz - fl)], (255, 140, 40), "light", (ex, ey, rz + 1)))
            faces.append(Face([(ex - .04, ey, rz - .035), (ex + .04, ey, rz - .035), (ex, ey + .01, rz - fl * .6)], (150, 200, 255), "light", (ex, ey, rz + 1)))
    fz = {"sports": 2.255, "coupe": 2.255, "sedan": 2.375, "van": 2.32, "truck": 1.52}[kind]
    fy = {"sports": .38, "coupe": .38, "sedan": .50, "van": .65, "truck": .62}[kind]
    for sgn in (-1, 1):
        xa, xb = (0.40, 0.74) if sgn > 0 else (-0.74, -0.40)
        faces.append(Face([(xa, fy - .04, fz + .004), (xb, fy - .04, fz + .004), (xb, fy + .06, fz + .004), (xa, fy + .06, fz + .004)],
                          (255, 250, 220) if lights else (200, 206, 214), "light" if lights else "chrome", (0, fy, fz - 1)))
    if kind == "truck":
        axles, xw = [(-2.7, .44), (-1.35, .44), (1.0, .42)], .98
    elif kind == "van":
        axles, xw = [(-1.3, .38), (1.35, .38)], .98
    else:
        axles, xw = [(-1.30, .36), (1.35, .34)], (1.02 if kind != "sedan" else 1.0)
    for ai, (az, ar) in enumerate(axles):
        front = ai == len(axles) - 1
        for sgn in (-1, 1):
            faces += wheel(sgn * (xw - .15), ar, az, ar, .15, wph, steer if front else 0.0, sgn, n=10)
    return faces


def light_spots(kind, st):
    rz = {"sports": -2.22, "coupe": -2.22, "sedan": -2.27, "van": -2.32, "truck": -3.15}[kind]
    ty = {"sports": .78, "coupe": .78, "sedan": .84, "van": 1.0, "truck": .85}[kind]
    res = []
    k = 1.0 if st.get("brake") else 0.4
    res += [((-.52, ty, rz), "red", 0.85 * k, (0, 0, -1)), ((.52, ty, rz), "red", 0.85 * k, (0, 0, -1))]
    if st.get("sig"):
        sgn = -1 if st["sig"] == 1 else 1
        res.append(((sgn * .72, ty - .12, rz), "amber", 0.6, (0, 0, -1)))
    if st.get("lights"):
        fz = {"sports": 2.26, "coupe": 2.26, "sedan": 2.38, "van": 2.33, "truck": 1.53}[kind]
        fy = {"sports": .38, "coupe": .38, "sedan": .50, "van": .65, "truck": .62}[kind]
        res += [((-.57, fy, fz), "white", 0.8, (0, 0, 1)), ((.57, fy, fz), "white", 0.8, (0, 0, 1))]
    return res


class Car3D:
    """Renders car meshes to surfaces, with lighting taken from the current theme."""

    SUN = v_norm((-0.45, 0.85, -0.40))

    def __init__(self):
        self.glow = {}
        for name, col in (("red", (255, 40, 30)), ("amber", (255, 170, 30)), ("white", (255, 250, 220))):
            g = pygame.Surface((96, 96))
            for r in range(48, 2, -2):
                a = (1 - r / 48) ** 2.2
                pygame.draw.circle(g, (int(col[0] * a), int(col[1] * a), int(col[2] * a)), (48, 48), r)
            self.glow[name] = g

    def render(self, kind, color, st, view, theme, shadow=True):
        """Returns (surface, anchor_xy, ref_width_px). anchor = where the car's ground centre lies in the surface."""
        faces = build_static(kind, color) + build_dynamic(kind, st)
        yaw, pitch, roll = view.get("yaw", 0.0), view.get("pitch", 0.0), view.get("roll", 0.0)
        R = rot_matrix(yaw, -pitch, roll)
        cam_d, cam_h, cam_p, f = view.get("cam_d", 8.4), view.get("cam_h", 2.1), view.get("cam_pitch", 0.14), view.get("f", 900.0)
        cp, sp = math.cos(-cam_p), math.sin(-cam_p)
        bob = view.get("bob", 0.0)
        night = theme["night"]
        amb_c = {"coast": (1.0, 1.0, 1.0), "mesa": (1.12, 0.88, 0.7), "alpine": (0.88, 0.88, 1.06), "city": (0.5, 0.55, 0.95)}[theme["bg"]]
        amb = 0.32 if night else 0.50
        kd = 0.50 if night else 0.66
        sky = mix(theme["sky"][0], theme["sky"][1], 0.5)
        sun = self.SUN
        cam = (0.0, cam_h, -cam_d)
        R0, R1, R2 = R
        out = []
        for fc in faces:
            n = (R0[0] * fc.n[0] + R0[1] * fc.n[1] + R0[2] * fc.n[2], R1[0] * fc.n[0] + R1[1] * fc.n[1] + R1[2] * fc.n[2],
                 R2[0] * fc.n[0] + R2[1] * fc.n[1] + R2[2] * fc.n[2])
            c = (R0[0] * fc.c[0] + R0[1] * fc.c[1] + R0[2] * fc.c[2], R1[0] * fc.c[0] + R1[1] * fc.c[1] + R1[2] * fc.c[2] + bob,
                 R2[0] * fc.c[0] + R2[1] * fc.c[1] + R2[2] * fc.c[2])
            vx, vy, vz = cam[0] - c[0], cam[1] - c[1], cam[2] - c[2]
            vl = math.sqrt(vx * vx + vy * vy + vz * vz) or 1.0
            vv = (vx / vl, vy / vl, vz / vl)
            nv = n[0] * vv[0] + n[1] * vv[1] + n[2] * vv[2]
            if nv <= 0.0:
                continue
            sc = []
            depth = 0.0
            bad = False
            for p in fc.pts:
                x = R0[0] * p[0] + R0[1] * p[1] + R0[2] * p[2] - cam[0]
                y = R1[0] * p[0] + R1[1] * p[1] + R1[2] * p[2] + bob - cam[1]
                z = R2[0] * p[0] + R2[1] * p[1] + R2[2] * p[2] - cam[2]
                y2 = y * cp - z * sp
                z2 = y * sp + z * cp
                if z2 < 0.5:
                    bad = True
                    break
                depth += z2
                sc.append((f * x / z2, -f * y2 / z2))
            if bad:
                continue
            depth /= len(fc.pts)
            mat, col = fc.mat, fc.color
            nl = n[0] * sun[0] + n[1] * sun[1] + n[2] * sun[2]
            nl = nl if nl > 0 else 0.0
            if mat == "light":
                rgb = col
            elif mat == "glass":
                fres = (1 - nv) ** 1.8
                refl = mix((10, 14, 22), sky, 0.22 + 0.45 * fres)
                lit = 0.55 + 0.6 * nl
                rgb = (clamp(int(refl[0] * lit + 30 * fres), 0, 255), clamp(int(refl[1] * lit + 32 * fres), 0, 255),
                       clamp(int(refl[2] * lit + 38 * fres), 0, 255))
            else:
                li = amb + (kd * 0.4 if mat == "tire" else kd) * nl
                r, g, b = col[0] * li * amb_c[0], col[1] * li * amb_c[1], col[2] * li * amb_c[2]
                if mat in ("body", "rim", "chrome", "carbon", "cargo"):
                    hx, hy, hz = sun[0] + vv[0], sun[1] + vv[1], sun[2] + vv[2]
                    hl = math.sqrt(hx * hx + hy * hy + hz * hz) or 1.0
                    nh = (n[0] * hx + n[1] * hy + n[2] * hz) / hl
                    spec = (nh if nh > 0 else 0.0) ** (30 if mat in ("body", "chrome", "rim") else 10)
                    spec *= 0.5 if mat in ("body", "cargo") else (0.9 if mat in ("chrome", "rim") else 0.22)
                    if night:
                        spec *= 0.4
                    fr = (1 - nv) ** 3 * (0.12 if mat == "body" else 0.08)
                    r, g, b = r + 255 * spec + sky[0] * fr, g + 255 * spec + sky[1] * fr, b + 255 * spec + sky[2] * fr
                rgb = (clamp(int(r), 0, 255), clamp(int(g), 0, 255), clamp(int(b), 0, 255))
            out.append((depth, sc, rgb))
        out.sort(key=lambda o: -o[0])

        def proj(p):
            x = R0[0] * p[0] + R0[1] * p[1] + R0[2] * p[2] - cam[0]
            y = R1[0] * p[0] + R1[1] * p[1] + R1[2] * p[2] + bob - cam[1]
            z = R2[0] * p[0] + R2[1] * p[1] + R2[2] * p[2] - cam[2]
            y2 = y * cp - z * sp
            z2 = y * sp + z * cp
            return (f * x / z2, -f * y2 / z2, z2)

        # glows only for lights that face the camera
        glows = []
        for pos, name, size, nrm in light_spots(kind, st):
            nz = (R0[2] * 0 + R0[2] * 0, 0, 0)
            nn = (R0[0] * nrm[0] + R0[1] * nrm[1] + R0[2] * nrm[2], R1[0] * nrm[0] + R1[1] * nrm[1] + R1[2] * nrm[2],
                  R2[0] * nrm[0] + R2[1] * nrm[1] + R2[2] * nrm[2])
            p = proj(pos)
            if p[2] < 0.5:
                continue
            vv = v_norm((cam[0] - (R0[0] * pos[0] + R0[1] * pos[1] + R0[2] * pos[2]), cam[1] - (R1[0] * pos[0] + R1[1] * pos[1] + R1[2] * pos[2] + bob),
                         cam[2] - (R2[0] * pos[0] + R2[1] * pos[1] + R2[2] * pos[2])))
            if v_dot(nn, vv) > 0.15:
                glows.append((p, name, size * (0.5 + 0.5 * v_dot(nn, vv))))
        gpts = []
        if shadow:
            ln, wd = (2.5, 1.15) if kind != "truck" else (3.4, 1.15)
            cz0 = 0.0 if kind != "truck" else -1.0
            Ry = rot_matrix(yaw, 0, 0)
            for a in range(16):
                t = a / 16 * math.tau
                q = m_apply(Ry, (wd * math.cos(t), 0.02, cz0 + ln * math.sin(t)))
                p = proj(q)
                if p[2] > 0.5:
                    gpts.append((p[0], p[1]))
        xs = [p[0] for _, sc, _ in out for p in sc] + [g[0][0] for g in glows] + [g[0] for g in gpts]
        ys = [p[1] for _, sc, _ in out for p in sc] + [g[0][1] for g in glows] + [g[1] for g in gpts]
        if not xs:
            return pygame.Surface((4, 4), pygame.SRCALPHA), (2, 2), 1.0
        pad = 46
        minx, miny = min(xs) - pad, min(ys) - pad
        wsur, hsur = int(max(xs) - minx + pad), int(max(ys) - miny + pad)
        surf = pygame.Surface((wsur, hsur), pygame.SRCALPHA)
        if len(gpts) > 3:
            pygame.draw.polygon(surf, (0, 0, 0, 125), [(x - minx, y - miny) for x, y in gpts])
        for depth, sc, rgb in out:
            pts = [(x - minx, y - miny) for x, y in sc]
            pygame.draw.polygon(surf, rgb, pts)
            pygame.draw.polygon(surf, rgb, pts, 1)
        for p, name, size in glows:
            g = self.glow[name]
            s2 = max(8, int(size * f / p[2] * 1.4))
            gg = pygame.transform.scale(g, (s2, s2))
            surf.blit(gg, (p[0] - minx - s2 / 2, p[1] - miny - s2 / 2), special_flags=pygame.BLEND_RGB_ADD)
        g0 = proj((0.0, 0.0, 0.0))
        ref_w = f * 1.9 / max(0.5, cam_d - 2.2)
        return surf, (g0[0] - minx, g0[1] - miny), ref_w


# --------------------------------------------------------------------------
# Procedural art: backgrounds, roadside sprites, cars
# --------------------------------------------------------------------------
class Assets:
    def __init__(self):
        names = "dejavusansmono,consolas,menlo,couriernew,monospace"
        self.f_small = pygame.font.SysFont(names, 15)
        self.f_mid = pygame.font.SysFont(names, 22, bold=True)
        self.f_big = pygame.font.SysFont(names, 44, bold=True)
        self.f_huge = pygame.font.SysFont(names, 110, bold=True)
        self.f_title = pygame.font.SysFont(names, 76, bold=True)
        self.bg_cache, self.spr_cache, self.car_cache = {}, {}, {}
        self.car3d = Car3D()

    # ---- backgrounds -----------------------------------------------------
    @staticmethod
    def ridge(w2, height, color, seed, amp, snow=False):
        rnd = random.Random(seed)
        waves = [(k, rnd.uniform(0.3, 1.0) * amp / (k ** 0.7), rnd.uniform(0, 6.28)) for k in (2, 3, 5, 8, 13, 21)]
        pts = [(0, height)]
        for x in range(0, w2 + 1, 6):
            y = height * 0.55 - sum(a * math.sin(2 * math.pi * k * x / w2 + ph) for k, a, ph in waves)
            pts.append((x, clamp(y, 4, height - 2)))
        pts.append((w2, height))
        s = pygame.Surface((w2, height), pygame.SRCALPHA)
        if snow:
            pygame.draw.polygon(s, (240, 244, 255), pts)
            pygame.draw.polygon(s, color, [(x, y + 22 if 0 < y < height - 2 else y) for x, y in pts])
        else:
            pygame.draw.polygon(s, color, pts)
        return s

    def background(self, key):
        if key in self.bg_cache:
            return self.bg_cache[key]
        th, rnd, w2 = THEMES[key], random.Random(3), W * 2
        top, bot = th["sky"]
        sky = pygame.Surface((W, H))
        hz = H // 2 + 40
        for y in range(hz):
            pygame.draw.line(sky, mix(top, bot, (y / hz) ** 1.15), (0, y), (W, y))
        sky.fill(bot, (0, hz, W, H - hz))
        layers = []
        bgk = th["bg"]
        if th["night"]:
            for _ in range(160):
                c = rnd.randint(120, 255)
                sky.set_at((rnd.randrange(W), rnd.randrange(0, 280)), (c, c, c))
            pygame.draw.circle(sky, (230, 230, 240), (780, 90), 34)
            pygame.draw.circle(sky, (top[0] + 8, top[1] + 8, top[2] + 20), (766, 82), 30)
        elif bgk == "mesa":
            for r, a in ((120, 30), (90, 50), (64, 90), (46, 255)):
                s = pygame.Surface((300, 300), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 230, 150, a), (150, 150), r)
                sky.blit(s, (420 - 150, 300 - 150))
        else:
            for r, a in ((70, 40), (50, 70), (34, 255)):
                s = pygame.Surface((200, 200), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 250, 220, a), (100, 100), r)
                sky.blit(s, (760 - 100, 120 - 100))
        base_y = HALF_H + 8

        def clouds(seed, tint, alpha):
            s = pygame.Surface((w2, 200), pygame.SRCALPHA)
            r2 = random.Random(seed)
            for _ in range(14):
                cx, cy = r2.randrange(w2), r2.randrange(30, 150)
                for _ in range(6):
                    pygame.draw.ellipse(s, (*tint, alpha), (cx + r2.randint(-60, 60), cy + r2.randint(-12, 12),
                                                          r2.randint(80, 160), r2.randint(26, 46)))
            return s

        if bgk == "coast":
            layers.append((clouds(2, (255, 255, 255), 190), 40, 0.012))
            layers.append((self.ridge(w2, 150, (120, 150, 200), 1, 60), base_y - 150, 0.04))
            sea = pygame.Surface((W, 40))
            for y in range(40):
                pygame.draw.line(sea, mix((60, 150, 215), (30, 100, 190), y / 40), (0, y), (W, y))
            sky.blit(sea, (0, base_y - 30))
            layers.append((self.ridge(w2, 110, (70, 140, 90), 4, 36), base_y - 110, 0.09))
        elif bgk == "mesa":
            layers.append((clouds(3, (255, 190, 140), 120), 50, 0.012))
            layers.append((self.ridge(w2, 120, (150, 80, 100), 8, 36), base_y - 120, 0.04))
            m = pygame.Surface((w2, 190), pygame.SRCALPHA)
            for i in range(11):
                x, wd, h = int(i * w2 / 11 + rnd.randint(-30, 30)), rnd.randint(130, 260), rnd.randint(70, 170)
                pygame.draw.polygon(m, (170, 82, 62), [(x, 190), (x + 18, 190 - h), (x + wd - 18, 190 - h), (x + wd + 26, 190)])
                pygame.draw.rect(m, (196, 104, 70), (x + 18, 190 - h, wd - 36, 10))
                pygame.draw.rect(m, (140, 66, 52), (x + 26, 190 - h + 34, wd - 44, 6))
            layers.append((m, base_y - 190, 0.08))
        elif bgk == "alpine":
            layers.append((clouds(5, (255, 200, 210), 110), 50, 0.012))
            layers.append((self.ridge(w2, 210, (84, 90, 150), 2, 90, snow=True), base_y - 210, 0.04))
            layers.append((self.ridge(w2, 140, (46, 62, 96), 6, 55, snow=True), base_y - 140, 0.09))
        else:
            far = pygame.Surface((w2, 230), pygame.SRCALPHA)
            near = pygame.Surface((w2, 170), pygame.SRCALPHA)
            for surf, hmax, col, wcol in ((far, 210, (30, 22, 58), (170, 110, 200)), (near, 150, (16, 12, 34), (255, 210, 110))):
                x = 0
                while x < w2 - 70:
                    bw, bh = rnd.randint(28, 66), rnd.randint(40, hmax)
                    pygame.draw.rect(surf, col, (x, surf.get_height() - bh, bw, bh))
                    for wy in range(surf.get_height() - bh + 6, surf.get_height() - 4, 9):
                        for wx in range(x + 5, x + bw - 5, 9):
                            if rnd.random() < 0.28:
                                surf.fill(wcol, (wx, wy, 3, 4))
                    if rnd.random() < 0.18:
                        neon = rnd.choice(((255, 40, 150), (40, 230, 255), (255, 170, 40)))
                        pygame.draw.rect(surf, neon, (x, surf.get_height() - bh, bw, 3))
                    x += bw + rnd.randint(0, 12)
            layers.append((far, base_y - 230, 0.04))
            layers.append((near, base_y - 170, 0.09))
        self.bg_cache[key] = (sky, layers)
        return self.bg_cache[key]

    # ---- roadside sprites ---------------------------------------------------
    def sprites(self, key):
        if key in self.spr_cache:
            return self.spr_cache[key]
        th = THEMES[key]
        d, out = pygame.draw, {}

        def surf(w, h):
            return pygame.Surface((w, h), pygame.SRCALPHA)

        s = surf(150, 300)                                   # palm
        d.polygon(s, (118, 84, 52), [(66, 300), (84, 300), (96, 96), (86, 96)])
        top = (92, 96)
        for ang, ln in ((-165, 64), (-130, 70), (-95, 58), (-55, 68), (-20, 62), (15, 52), (-195, 52)):
            a = math.radians(ang)
            tip = (top[0] + math.cos(a) * ln, top[1] + math.sin(a) * ln + 26)
            mid = (top[0] + math.cos(a) * ln * 0.55, top[1] + math.sin(a) * ln * 0.55 - 6)
            n = (-math.sin(a) * 9, math.cos(a) * 9)
            d.polygon(s, (46, 140, 62), [top, (mid[0] + n[0], mid[1] + n[1]), tip, (mid[0] - n[0], mid[1] - n[1])])
            d.line(s, (30, 100, 44), top, tip, 2)
        d.circle(s, (90, 60, 30), (88, 102), 6)
        d.circle(s, (90, 60, 30), (97, 104), 6)
        out["palm"] = s

        snowy = th["bg"] == "alpine"                         # pine
        s = surf(112, 250)
        d.rect(s, (88, 60, 38), (50, 200, 12, 50))
        for tri, col in (([(56, 8), (18, 96), (94, 96)], (24, 98, 60)), ([(56, 52), (8, 150), (104, 150)], (28, 112, 66)),
                         ([(56, 100), (0, 208), (112, 208)], (32, 126, 72))):
            d.polygon(s, col, tri)
            if snowy:
                x0, y0 = tri[0]
                d.polygon(s, (240, 245, 255), [(x0, y0), (x0 - (y0 and 16), y0 + 30), (x0 + 16, y0 + 30)])
        out["pine"] = s

        s = surf(80, 190)                                    # cactus
        d.rect(s, (60, 140, 78), (30, 10, 22, 180), border_radius=11)
        d.rect(s, (60, 140, 78), (6, 78, 40, 12), border_radius=6)
        d.rect(s, (60, 140, 78), (6, 44, 13, 44), border_radius=6)
        d.rect(s, (60, 140, 78), (46, 98, 28, 12), border_radius=6)
        d.rect(s, (60, 140, 78), (62, 62, 13, 48), border_radius=6)
        d.line(s, (34, 100, 54), (41, 18), (41, 186), 2)
        out["cactus"] = s

        s = surf(130, 90)                                    # rock
        rc = (150, 150, 158) if th["bg"] != "mesa" else (170, 98, 66)
        d.polygon(s, rc, [(4, 90), (20, 38), (52, 10), (90, 26), (124, 64), (126, 90)])
        d.polygon(s, shade(rc, 1.25), [(20, 38), (52, 10), (90, 26), (60, 44)])
        d.polygon(s, shade(rc, 0.7), [(60, 44), (90, 26), (124, 64), (126, 90), (70, 90)])
        if snowy:
            d.polygon(s, (240, 245, 255), [(34, 24), (52, 10), (90, 26), (76, 34), (58, 26)])
        out["rock"] = s

        s = surf(110, 64)                                    # bush
        bc = (60, 150, 70) if th["bg"] != "mesa" else (150, 140, 70)
        if th["night"]:
            bc = (24, 70, 56)
        for cx, cy, r in ((28, 40, 24), (56, 32, 28), (84, 42, 22), (50, 46, 22)):
            d.circle(s, bc, (cx, cy), r)
            d.circle(s, shade(bc, 1.2), (cx - 6, cy - 7), r // 2)
        out["bush"] = s

        s = surf(44, 300)                                    # street lamp (emissive)
        for r, a in ((34, 30), (26, 50), (18, 90), (10, 255)):
            d.circle(s, (255, 220, 130, a), (30, 24), r)
        d.rect(s, (40, 42, 52), (20, 28, 5, 272))
        d.rect(s, (40, 42, 52), (20, 22, 22, 5))
        out["lamp"] = s

        rnd = random.Random(9)                               # building
        s = surf(240, 500)
        body = (24, 26, 46)
        d.rect(s, body, (10, 40, 220, 460))
        d.rect(s, (14, 16, 30), (10, 40, 220, 460), 3)
        d.rect(s, (60, 64, 90), (100, 4, 6, 40))
        for wy in range(56, 490, 22):
            for wx in range(22, 220, 22):
                lit = rnd.random() < 0.45
                d.rect(s, (255, 214, 120) if lit else (36, 38, 62), (wx, wy, 12, 14))
        d.rect(s, (255, 50, 150), (10, 40, 220, 5))
        out["building"] = s

        def board(fill, text, tcol, glow):                  # billboard
            b = surf(230, 190)
            d.rect(b, (60, 62, 72), (40, 120, 10, 70))
            d.rect(b, (60, 62, 72), (180, 120, 10, 70))
            d.rect(b, fill, (4, 10, 222, 112), border_radius=8)
            d.rect(b, (230, 230, 235) if not glow else tcol, (4, 10, 222, 112), 4, border_radius=8)
            t = self.f_big.render(text, True, tcol)
            if glow:
                for off in (-2, 2):
                    b.blit(self.f_big.render(text, True, shade(tcol, 0.5)), (115 - t.get_width() // 2 + off, 40))
            b.blit(t, (115 - t.get_width() // 2, 40))
            return b

        word = random.Random(key).choice(["TURBO", "NITRO", "OCEAN", "REDLINE", "APEX"])
        out["ad"] = board((236, 236, 240) if not th["night"] else (20, 20, 40), word, (210, 40, 40), False)
        out["neon"] = board((12, 8, 28), random.Random(key + "n").choice(["RAMEN", "ARCADE", "HOTEL", "SHIPYARD"]),
                            (60, 240, 255), True)

        for k, flip in (("chev_l", -1), ("chev_r", 1)):      # chevron warning signs
            s = surf(70, 100)
            d.rect(s, (70, 70, 78), (32, 60, 6, 40))
            d.rect(s, (240, 200, 30), (4, 4, 62, 62), border_radius=6)
            d.rect(s, (20, 20, 20), (4, 4, 62, 62), 3, border_radius=6)
            cx = 35
            d.polygon(s, (20, 20, 20), [(cx - 16 * flip, 14), (cx + 6 * flip, 35), (cx - 16 * flip, 56),
                                        (cx - 6 * flip, 56), (cx + 16 * flip, 35), (cx - 6 * flip, 14)])
            out[k] = s

        s = surf(520, 230)                                   # start / finish gantry
        d.rect(s, (88, 92, 108), (0, 20, 24, 210))
        d.rect(s, (88, 92, 108), (496, 20, 24, 210))
        d.rect(s, (30, 32, 44), (0, 6, 520, 64), border_radius=6)
        for i in range(26):
            for j in range(2):
                d.rect(s, (240, 240, 240) if (i + j) % 2 == 0 else (20, 20, 20), (8 + i * 19.6, 10 + j * 8, 19, 8))
        t = self.f_big.render("START / FINISH", True, (255, 230, 90))
        s.blit(t, (260 - t.get_width() // 2, 30))
        out["gantry"] = s


        def sway_frames(src, amt):
            sw, sh = src.get_size()
            frames = []
            for k in (-1.0, -0.5, 0.0, 0.5, 1.0):
                f = pygame.Surface((sw, sh), pygame.SRCALPHA)
                for y in range(0, sh, 6):
                    dx = int(k * amt * max(0.0, 1 - (y + 6) / sh) ** 2)
                    f.blit(src, (dx, y), area=(0, y, sw, min(6, sh - y)))
                frames.append(f)
            return frames

        out["palm"] = sway_frames(out["palm"], 9)
        out["pine"] = sway_frames(out["pine"], 6)
        out["bush"] = sway_frames(out["bush"], 3)
        dim = out["neon"].copy()
        dim.fill((100, 100, 118, 255), special_flags=pygame.BLEND_RGBA_MULT)
        out["neon"] = [out["neon"], dim]

        frames = []                                           # wind turbine, 8 rotation frames (blades repeat every 120 deg)
        for k in range(8):
            s = surf(160, 340)
            d.polygon(s, (232, 234, 238), [(76, 340), (84, 340), (82, 86), (78, 86)])
            for b in range(3):
                a = math.radians(k * 15) + b * 2 * math.pi / 3 - math.pi / 2
                tip = (80 + math.cos(a) * 78, 82 + math.sin(a) * 78)
                nx, ny = -math.sin(a) * 5, math.cos(a) * 5
                d.polygon(s, (244, 246, 248), [(80 + nx, 82 + ny), tip, (80 - nx * 0.4, 82 - ny * 0.4)])
            d.circle(s, (200, 204, 210), (80, 84), 7)
            frames.append(s)
        out["turbine"] = frames

        s = surf(130, 80)                                     # tyre barrier
        for row in range(2):
            for col in range(3 if row == 0 else 2):
                x, y = 8 + col * 40 + (20 if row else 0), 46 - row * 30
                d.ellipse(s, (20, 20, 24), (x, y, 36, 28))
                d.ellipse(s, (50, 50, 58), (x + 8, y + 7, 20, 14))
                d.arc(s, (230, 40, 40) if (row + col) % 2 == 0 else (240, 240, 240), (x, y, 36, 28), 0.3, 2.8, 4)
        out["tires"] = s

        rnd2 = random.Random(31)                              # grandstand with a crowd
        s = surf(460, 240)
        d.rect(s, (70, 74, 88), (0, 60, 460, 180))
        for r in range(5):
            y = 70 + r * 34
            d.rect(s, (96, 100, 118), (0, y + 24, 460, 10))
            for x in range(8, 452, 13):
                if rnd2.random() < 0.85:
                    cc = rnd2.choice([(230, 60, 60), (240, 220, 70), (70, 140, 240), (240, 240, 240), (90, 200, 110), (240, 140, 50)])
                    d.circle(s, cc, (x, y + 14), 5)
                    d.rect(s, shade(cc, 0.7), (x - 4, y + 18, 8, 8))
        d.rect(s, (190, 60, 50), (0, 8, 460, 44))
        d.rect(s, (240, 240, 240), (0, 48, 460, 6))
        t = self.f_mid.render("REDLINE GP", True, (255, 255, 255))
        s.blit(t, (230 - t.get_width() // 2, 18))
        out["stand"] = s

        s = surf(760, 300)                                    # road bridge
        d.rect(s, (150, 152, 160), (0, 0, 760, 56))
        d.rect(s, (100, 102, 112), (0, 40, 760, 16))
        d.rect(s, (190, 192, 200), (0, 0, 760, 8))
        for x in range(10, 750, 40):
            d.rect(s, (120, 122, 132), (x, 8, 4, 18))
        for px0 in (0, 700):
            d.rect(s, (136, 138, 148), (px0, 56, 60, 244))
            d.rect(s, (110, 112, 122), (px0 + 44, 56, 16, 244))
        out["bridge"] = s

        rnd3 = random.Random(5)                               # tunnel portal
        rock = {"mesa": (122, 78, 58), "alpine": (96, 100, 114), "city": (52, 54, 66)}.get(th["bg"], (92, 84, 76))
        s = surf(720, 340)
        s.fill((*rock, 255))
        for _ in range(520):
            cc = rnd3.randint(-18, 18)
            d.circle(s, (clamp(rock[0] + cc, 0, 255), clamp(rock[1] + cc, 0, 255), clamp(rock[2] + cc, 0, 255)),
                     (rnd3.randrange(720), rnd3.randrange(340)), rnd3.randint(2, 7))
        d.rect(s, (160, 160, 168), (116, 136, 488, 230), border_radius=44)
        d.rect(s, (0, 0, 0, 0), (130, 150, 460, 220), border_radius=36)
        for i in range(8):
            d.circle(s, (255, 220, 120), (150 + i * 60, 158), 5)
        out["portal"] = s

        self.spr_cache[key] = out
        return out

    # ---- cars (software 3D, cached by yaw / lights / theme) -------------------
    def car_sprite(self, kind, color, yawq, brake, sig, theme_key):
        key = (kind, color, yawq, brake, sig, theme_key)
        c = self.car_cache.get(key)
        if c is None:
            th = THEMES[theme_key]
            st = dict(brake=brake, sig=sig, lights=th["night"], wphase=(hash(key) % 100) * 0.1)
            c = self.car3d.render(kind, color, st, dict(yaw=yawq * 0.1), th)
            self.car_cache[key] = c
        return c


# --------------------------------------------------------------------------
# Audio (all synthesized, optional)
# --------------------------------------------------------------------------
SR = 22050


class Audio:
    def __init__(self):
        self.ok = False
        self.muted = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 1, 512)
            pygame.mixer.set_num_channels(12)
            self.eng = [self._tone_loop(f) for f in (48, 80, 130, 200)]
            self.skid = self._noise_loop(0.22, 6500)
            self.wind = self._noise_loop(0.06, 9000)
            self.rumble = self._rumble()
            self.turbo = self._turbo()
            self.sfx = {"crash": self._crash(), "boost": self._sweep(), "beep": self._beep(660, 0.18),
                        "go": self._beep(1040, 0.45), "lap": self._beep(880, 0.3), "blow": self._burst(0.35, 0.5, 0.11, 13000),
                        "pop": self._burst(0.14, 0.3, 0.03, 15000, 90), "thunder": self._burst(1.9, 0.04, 0.8, 17000, 38),
                        "bump": self._burst(0.22, 0.3, 0.07, 9000, 64)}
            self.ch = [pygame.mixer.Channel(i) for i in range(12)]
            self.started = False
            self.rr = 0
            self.ok = True
        except Exception:
            self.ok = False

    @staticmethod
    def _snd(samples):
        return pygame.mixer.Sound(buffer=array.array("h", samples).tobytes())

    def _tone_loop(self, f):
        n, buf = SR, []
        two_pi = 2 * math.pi
        for i in range(n):
            a = two_pi * f * i / SR
            v = (math.sin(a) + 0.55 * math.sin(2 * a + 0.4) + 0.38 * math.sin(3 * a) + 0.26 * math.sin(4 * a + 1.1)
                 + 0.16 * math.sin(5 * a) + 0.1 * math.sin(7 * a))
            buf.append(int(v * 3400))
        return self._snd(buf)

    def _noise_loop(self, k, amp):
        rnd, lp, buf = random.Random(1), 0.0, []
        for _ in range(SR):
            lp += (rnd.uniform(-1, 1) - lp) * k
            buf.append(int(lp * amp))
        return self._snd(buf)

    def _rumble(self):
        rnd, lp, buf = random.Random(3), 0.0, []
        for i in range(SR):
            lp += (rnd.uniform(-1, 1) - lp) * 0.10
            env = 0.35 + 0.65 * max(0.0, math.sin(2 * math.pi * 30 * i / SR)) ** 2
            buf.append(int(lp * 15000 * env))
        return self._snd(buf)

    def _turbo(self):
        rnd, buf = random.Random(4), []
        for i in range(SR):
            t = i / SR
            v = 0.6 * math.sin(2 * math.pi * 1500 * t) + 0.3 * math.sin(2 * math.pi * 2250 * t) + 0.1 * rnd.uniform(-1, 1)
            buf.append(int(v * 3200))
        return self._snd(buf)

    def _burst(self, dur, k, tau, amp, tone=0):
        rnd, lp, buf = random.Random(7), 0.0, []
        for i in range(int(SR * dur)):
            lp += (rnd.uniform(-1, 1) - lp) * k
            env = math.exp(-i / (SR * tau))
            v = lp * amp + (math.sin(2 * math.pi * tone * i / SR) * amp * 0.5 if tone else 0)
            buf.append(int(clamp(v * env, -32000, 32000)))
        return self._snd(buf)

    def _crash(self):
        rnd, buf, lp = random.Random(2), [], 0.0
        for i in range(int(SR * 0.4)):
            lp += (rnd.uniform(-1, 1) - lp) * 0.5
            env = math.exp(-i / (SR * 0.09))
            buf.append(int((lp * 14000 + math.sin(2 * math.pi * 55 * i / SR) * 9000) * env))
        return self._snd(buf)

    def _sweep(self):
        buf, ph = [], 0.0
        n = int(SR * 0.7)
        for i in range(n):
            f = 120 + 700 * (i / n)
            ph += 2 * math.pi * f / SR
            buf.append(int(((ph % (2 * math.pi)) / math.pi - 1) * 5000 * math.sin(math.pi * i / n)))
        return self._snd(buf)

    def _beep(self, f, dur):
        n = int(SR * dur)
        return self._snd([int(math.sin(2 * math.pi * f * i / SR) * 9000 * min(1, (n - i) / (SR * 0.05))) for i in range(n)])

    def start(self):
        if not self.ok or self.started:
            return
        loops = list(self.eng) + [self.skid, self.wind, self.rumble, self.turbo]
        for i, snd in enumerate(loops):
            self.ch[i].play(snd, loops=-1)
            self.ch[i].set_volume(0)
        self.started = True

    def silence(self):
        if self.ok and self.started:
            for i in range(8):
                self.ch[i].set_volume(0)

    def stop(self):
        if self.ok:
            pygame.mixer.stop()
            self.started = False

    def update(self, rpm_frac, throttle, speed_pct, skid, boosting, turbo=0.0, rumble=0.0):
        if not self.ok or not self.started:
            return
        m = 0.0 if self.muted else 1.0
        load = 0.35 + 0.65 * throttle
        for i in range(4):
            v = max(0.0, 1.0 - abs(rpm_frac - i / 3.0) * 2.6)
            self.ch[i].set_volume(min(1.0, v * load * 0.42 * m))
        self.ch[4].set_volume(min(1.0, skid * 0.35 * m))
        self.ch[5].set_volume(min(1.0, (speed_pct ** 2) * (0.5 + 0.4 * boosting) * m))
        self.ch[6].set_volume(min(1.0, rumble * 0.5 * m))
        self.ch[7].set_volume(min(1.0, turbo * 0.10 * m))

    def play(self, name):
        if self.ok and not self.muted:
            self.rr = 8 + (self.rr - 7) % 4
            self.ch[self.rr].play(self.sfx[name])


# --------------------------------------------------------------------------
# Race simulation
# --------------------------------------------------------------------------
class Car:
    __slots__ = ("z", "offset", "speed", "w", "kind", "color", "rival", "top", "name", "lap", "seg", "percent",
                 "finished", "finish_t", "brake", "progress", "dx", "sig", "sig_t", "yaw")

    def __init__(self, z, offset, speed, kind, color, rival=False, top=0.0, name=""):
        self.z, self.offset, self.speed = z, offset, speed
        self.kind, self.color, self.rival, self.top, self.name = kind, color, rival, top, name
        self.w = CAR_W[kind]
        self.lap = 0
        self.seg = None
        self.percent = 0.0
        self.finished = False
        self.finish_t = None
        self.brake = False
        self.progress = 0.0
        self.dx = 0.0
        self.sig = 0
        self.sig_t = 0.0
        self.yaw = 0.0


GEAR_LO = [0.0, 0.13, 0.28, 0.44, 0.62, 0.80]
GEAR_HI = [0.13, 0.28, 0.44, 0.62, 0.80, 1.0]
GEAR_MUL = [1.45, 1.2, 1.0, 0.9, 0.82, 0.74]


class Race:
    def __init__(self, game, ti):
        self.g = game
        self.ti = ti
        self.track = game.tracks[ti]
        self.spec = self.track.spec
        self.up = game.save["up"]
        tr = self.track
        for s in tr.segs:
            s.cars = []
            s.decals = [d for d in s.decals if d[0] != "skid"]
        rng = random.Random()
        self.rng = rng
        L = tr.length
        self.laps = self.spec["laps"]
        # --- player
        self.pos = 0.0
        self.px = 0.0
        self.speed = 0.0
        self.steer = 0.0
        self.gear, self.rpm, self.shift_t = 1, 1100.0, 0.0
        self.cap = 100 + 25 * self.up["nitro"]
        self.nitro = self.cap * 0.4
        self.drifting, self.drift_t, self.boost_t, self.boosting = False, 0.0, 0.0, False
        self.shake = 0.0
        self.lap = 0
        self.last_z = (self.pos + PLAYERZ) % L
        self.lap_t0 = 0.0
        self.lap_times = []
        self.best_lap = None
        self.banner = ("", 0.0)
        self.state = "countdown"
        self.cd = 3.6
        self.cd_last = 4
        self.t = 0.0
        self.finished = False
        self.finish_t = None
        self.rank_final = None
        self.bg_off = 0.0
        self.crashes = 0
        self.top_speed_seen = 0.0
        self.particles = []
        self.weather = []
        self.brake_on = False
        self.throttle = 0.0
        self.crash_cd = 0.0
        # --- vehicle dynamics / visuals
        self.pitch = self.roll = self.slip = self.yaw_v = 0.0
        self.bounce = self.bounce_v = 0.0
        self.wphase = 0.0
        self.damage = 0.0
        self.turbo = 0.0
        self.draft = 0.0
        self.blow_cd = 0.0
        self.rumble = 0.0
        self.last_slope = 0.0
        self.cam_px = 0.0
        self.fov_k = 0.0
        self.cam_mode = 0
        self.flash = 0.0
        self.next_flash = rng.uniform(4, 9)
        self.thunder_t = -1.0
        self.delta = None
        self.cam_banner = ("", 0.0)
        # --- rivals on the grid ahead of the player
        pz = PLAYERZ
        names = RIVAL_NAMES[:]
        rng.shuffle(names)
        palette = [c for i, c in enumerate(CAR_COLORS) if i != game.save["color"]]
        rng.shuffle(palette)
        self.cars = []
        self.rivals = []
        for i in range(5):
            row, col = i // 2, i % 2
            z = pz + 700 + row * 650
            top = MAXSPEED * (self.spec["diff"] + rng.uniform(-0.035, 0.035))
            c = Car(z, (-0.45 if col == 0 else 0.45), 0.0, rng.choice(("sports", "coupe")), palette[i % len(palette)],
                    rival=True, top=top, name=names[i])
            self.add_car(c)
            self.rivals.append(c)
        # --- traffic
        kinds = ["sedan", "sedan", "van", "truck", "sedan"]
        for _ in range(self.spec["traffic"]):
            z = rng.uniform(4000, L - 2000)
            c = Car(z, rng.choice((-0.8, -0.4, 0.0, 0.4, 0.8)),
                    rng.uniform(MAXSPEED * 0.2, MAXSPEED * 0.45), rng.choice(kinds),
                    rng.choice([(150, 150, 160), (90, 110, 150), (160, 90, 80), (90, 130, 100),
                                (200, 190, 150), (70, 70, 80)]))
            self.add_car(c)
        for c in self.rivals:
            c.speed = 0.0
        wth = tr.theme["weather"]
        if wth:
            n = 140 if wth == "rain" else 90
            self.weather = [[rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.7, 1.3)] for _ in range(n)]
        self.drops = [[rng.uniform(0, W), rng.uniform(0, H * 0.7), rng.uniform(2, 6), rng.uniform(0, 1)] for _ in range(26)] \
            if wth == "rain" else []
        game.audio.start()

    # ---- helpers ----------------------------------------------------------
    def add_car(self, c):
        c.z %= self.track.length
        c.seg = self.track.seg_at(c.z)
        c.percent = (c.z % SEGL) / SEGL
        c.seg.cars.append(c)
        self.cars.append(c)

    def seg_at(self, z):
        return self.track.seg_at(z)

    @property
    def top0(self):
        return MAXSPEED * (1 + 0.05 * self.up["engine"])

    @property
    def kph(self):
        return self.speed / MAXSPEED * 255

    @property
    def progress(self):
        return self.lap * self.track.length + (self.pos + PLAYERZ) % self.track.length

    def standings(self):
        L = self.track.length
        order = [("YOU", self.progress, True)] + [(r.name, r.lap * L + r.z, False) for r in self.rivals]
        order.sort(key=lambda r: -r[1])
        return order

    def rank(self):
        return [i for i, r in enumerate(self.standings()) if r[2]][0] + 1

    # ---- player -----------------------------------------------------------
    def step_player(self, dt, inp):
        up, L = self.up, self.track.length
        segs = self.track.segs
        N = len(segs)
        z = self.pos + PLAYERZ
        seg = self.seg_at(z)
        pct = (z % SEGL) / SEGL
        racing = self.state == "racing"
        top0 = self.top0 * (1.0 - 0.15 * self.damage / 100.0)
        sp = self.speed / top0
        self.brake_on = bool(inp["brk"])
        self.throttle = 1.0 if (inp["thr"] and racing) else 0.0
        prev_speed = self.speed

        # slipstream behind fast cars
        drafting = False
        if self.speed > MAXSPEED * 0.45:
            for i in range(2, 12):
                for c in segs[(seg.idx + i) % N].cars:
                    if c.speed > MAXSPEED * 0.5 and abs(c.offset - self.px) < 0.35:
                        drafting = True
        self.draft = clamp(self.draft + dt * (1.0 if drafting else -1.5), 0.0, 1.0)

        wants_boost = inp["nitro"] and self.nitro > 0 and self.speed > top0 * 0.2 and racing
        if wants_boost:
            self.nitro = max(0.0, self.nitro - dt * 30)
        if self.boost_t > 0:
            self.boost_t -= dt
        self.boosting = bool(wants_boost or self.boost_t > 0)
        top = top0 * (1.28 if self.boosting else 1.0) * (1 + 0.05 * self.draft)

        # steering + drift
        target = (1 if inp["right"] else 0) - (1 if inp["left"] else 0)
        self.steer += (target - self.steer) * min(1.0, dt * (9 if target else 12))
        was_drift = self.drifting
        self.drifting = bool(inp["hand"] and sp > 0.35 and abs(self.steer) > 0.2 and racing)
        dx = dt * 2 * clamp(self.speed / MAXSPEED, 0, 1.3) * (1 + 0.07 * up["tires"])
        self.px += self.steer * dx * (1.3 if self.drifting else 1.0)
        cf = CENTRIF * (1 - 0.06 * up["tires"]) * (1.35 if self.drifting else 1.0)
        self.px -= dx * (self.speed / MAXSPEED) * seg.curve * cf
        if self.damage > 60:                                   # a damaged car pulls to one side
            self.px += 0.012 * dt * 60 * (self.damage - 60) / 40 * clamp(self.speed / MAXSPEED, 0, 1) * 0.1
        if self.drifting:
            self.drift_t += dt
            self.nitro = min(self.cap, self.nitro + dt * 16 * (1 + 0.15 * up["nitro"]) * (0.4 + sp))
        elif was_drift and self.drift_t > 0.9:
            self.boost_t = min(1.6, self.drift_t * 0.4)
            self.g.audio.play("boost")
            self.drift_t = 0.0
        else:
            self.drift_t = 0.0

        # gearbox
        gear = 1
        for i in range(6):
            if sp >= GEAR_LO[i]:
                gear = i + 1
        if gear != self.gear:
            if gear > self.gear:
                self.shift_t = 0.14
                if self.throttle and self.rpm > 5200 and self.rng.random() < 0.7 and self.cam_mode == 0:
                    self.g.audio.play("pop")
                    for sx in (-1, 1):
                        for _ in range(6):
                            self.particles.append(["flame", HALF_W + sx * 44 + self.rng.uniform(-6, 6), H - 40,
                                                   self.rng.uniform(-60, 60), self.rng.uniform(30, 160),
                                                   self.rng.uniform(0.08, 0.2), (255, 170, 60), 5])
            self.gear = gear
        self.shift_t = max(0.0, self.shift_t - dt)
        lo, hi = GEAR_LO[gear - 1], GEAR_HI[gear - 1]
        r = clamp((sp - lo) / (hi - lo), 0, 1)
        target_rpm = 1300 + r * 6200 + (400 if self.throttle else 0)
        if self.shift_t > 0:
            target_rpm -= 1800
        self.rpm += (target_rpm - self.rpm) * min(1.0, dt * 11)

        # turbo spool and blow-off
        tgt = self.throttle * clamp((self.rpm - 2600) / 4200, 0, 1)
        old_t = self.turbo
        self.turbo += (tgt - self.turbo) * min(1.0, dt * (1.8 if tgt > self.turbo else 5.0))
        self.blow_cd = max(0.0, self.blow_cd - dt)
        if old_t > 0.55 and not self.throttle and self.blow_cd <= 0:
            self.g.audio.play("blow")
            self.blow_cd = 0.8

        tq = 1.0 - 0.4 * abs(r - 0.7)
        acc = (MAXSPEED / 3.0) * GEAR_MUL[gear - 1] * tq * max(0.0, 1 - sp ** 2) * (1 + 0.08 * up["engine"])
        acc *= (1 + 0.14 * self.turbo) * (1 + 0.12 * self.draft)
        if self.boosting:
            acc = acc * 2.2 + MAXSPEED * 0.25
        if self.shift_t > 0:
            acc *= 0.3

        if inp["brk"]:
            self.speed -= MAXSPEED * 1.1 * (1 + 0.12 * up["brakes"]) * dt
        elif self.throttle:
            self.speed += acc * dt
        else:
            self.speed -= (MAXSPEED / 6.0) * dt
        if inp["hand"] and not self.drifting:
            self.speed -= MAXSPEED * 0.45 * dt
        if self.drifting:
            self.speed -= MAXSPEED * 0.04 * dt
        if abs(self.px) > 1.0 and self.speed > MAXSPEED / 4:
            self.speed -= (MAXSPEED / 2) * (1 - 0.08 * up["tires"]) * dt
            if self.cam_mode == 0:
                self.dust(dt, (120, 100, 80) if self.track.theme["bg"] != "alpine" else (240, 240, 250))
        if self.speed > top:
            self.speed = max(top, self.speed - MAXSPEED * 0.5 * dt)
        self.speed = clamp(self.speed, 0.0, MAXSPEED * 1.5)

        # rumble strips
        edge = 0.93 < abs(self.px) < 1.08 and self.speed > MAXSPEED * 0.15
        self.rumble = 1.0 if edge else 0.0
        if edge:
            self.shake = max(self.shake, 0.06)

        # collisions: roadside scenery
        if abs(self.px) > 1.0:
            for key, off, anchor in seg.sprites:
                if key in NON_SOLID:
                    continue
                sw = SPRITE_W[key]
                ox = off + sw / 2 * (1 if off > 0 else -1)
                if overlap(self.px, PLAYER_W, ox, sw):
                    self.crash(min(self.speed, MAXSPEED), 0.9)
                    self.speed = MAXSPEED / 5
                    self.pos = (seg.idx * SEGL - PLAYERZ) % L
                    self.px = 0.9 if self.px > 0 else -0.9
                    break
        # collisions: other cars
        for car in seg.cars:
            if self.speed > car.speed and overlap(self.px, PLAYER_W, car.offset, car.w, 0.8):
                rel = (self.speed - car.speed) / MAXSPEED
                self.crash(rel * MAXSPEED, rel)
                self.speed = car.speed * (car.speed / max(self.speed, 1.0))
                self.pos = (car.z - PLAYERZ) % L
                self.boost_t = 0.0
                break
        self.px = clamp(self.px, -2.6, 2.6)
        self.pos = (self.pos + dt * self.speed) % L
        self.top_speed_seen = max(self.top_speed_seen, self.kph)
        self.bg_off += seg.curve * (self.speed / MAXSPEED) * dt * 160

        # ---- visual dynamics
        slope = (seg.y2 - seg.y1) / SEGL
        acc_n = clamp((self.speed - prev_speed) / max(dt, 1e-3) / MAXSPEED, -2, 2)
        pitch_t = math.atan(slope) * 0.9 - acc_n * 0.012 + (0.025 if (inp["brk"] and self.speed > MAXSPEED * 0.2) else 0.0)
        self.pitch += (pitch_t - self.pitch) * min(1.0, dt * 6)
        lat = self.steer * clamp(sp, 0, 1.2) * 0.85 + seg.curve * clamp(sp, 0, 1.2) ** 2 * 0.16
        roll_t = clamp(lat, -1.2, 1.2) * 0.07 * (1.25 if self.drifting else 1.0)
        self.roll += (roll_t - self.roll) * min(1.0, dt * 7)
        slip_t = self.steer * 0.32 * clamp(sp, 0, 1.2) if self.drifting else 0.0
        self.slip += (slip_t - self.slip) * min(1.0, dt * 5)
        self.yaw_v = self.steer * 0.05 + self.slip
        sch = slope - self.last_slope
        self.last_slope = slope
        if sp > 0.2:
            self.bounce_v += -sch * 45.0 * sp
        self.bounce_v += self.rng.uniform(-1, 1) * 0.5 * self.rumble
        self.bounce_v += -(180.0 * self.bounce + 13.0 * self.bounce_v) * dt
        self.bounce = clamp(self.bounce + self.bounce_v * dt, -0.2, 0.2)
        self.wphase = (self.wphase + dt * self.speed / 295.0 / 0.36 * 0.5) % (2 * math.pi)

        # skid marks and smoke
        if self.speed > MAXSPEED * 0.3 and (self.drifting or (inp["brk"] and sp > 0.55)):
            if len(seg.decals) < 40:
                seg.decals.append(("skid", self.px - 0.1, pct))
                seg.decals.append(("skid", self.px + 0.1, pct))
            if self.cam_mode == 0:
                self.smoke(dt)
        if self.damage > 50 and self.cam_mode == 0 and self.rng.random() < 0.6:
            self.particles.append(["smoke", HALF_W + self.rng.uniform(-30, 30), H - 175, self.rng.uniform(-20, 20),
                                   self.rng.uniform(-110, -50), self.rng.uniform(0.5, 1.1), (60, 60, 66), self.rng.uniform(10, 20)])
        self.g.audio.update(clamp((self.rpm - 1000) / 6800, 0, 1), self.throttle, clamp(sp, 0, 1.3),
                            1.0 if self.drifting else (0.5 if abs(self.px) > 1 and self.speed > MAXSPEED * 0.2 else 0.0),
                            1.0 if self.boosting else 0.0, self.turbo, self.rumble)

    def crash(self, impact, severity):
        if self.crash_cd > 0:
            return
        self.crash_cd = 0.5
        self.crashes += 1
        self.damage = min(100.0, self.damage + severity * 22)
        self.shake = max(self.shake, 0.3 + 0.7 * severity)
        self.g.audio.play("crash")
        for _ in range(int(14 + 24 * severity)):
            a = self.rng.uniform(math.pi * 1.05, math.pi * 1.95)
            v = self.rng.uniform(120, 460)
            self.particles.append(["spark", HALF_W + self.rng.uniform(-90, 90), H - 80, math.cos(a) * v,
                                   math.sin(a) * v, self.rng.uniform(0.25, 0.6), (255, 220, 120), 3])

    def dust(self, dt, color):
        if self.rng.random() < 0.9:
            for sx in (-1, 1):
                self.particles.append(["dust", HALF_W + sx * 105 + self.rng.uniform(-14, 14), H - 56,
                                       self.rng.uniform(-80, 80) + sx * 40, self.rng.uniform(-90, -20),
                                       self.rng.uniform(0.3, 0.7), color, self.rng.uniform(6, 14)])

    def smoke(self, dt):
        for sx in (-1, 1):
            if self.rng.random() < 0.8:
                self.particles.append(["smoke", HALF_W + sx * 108 + self.rng.uniform(-10, 10), H - 52,
                                       self.rng.uniform(-50, 50), self.rng.uniform(-60, -10),
                                       self.rng.uniform(0.4, 0.9), (210, 210, 220), self.rng.uniform(8, 18)])

    # ---- traffic and rivals -----------------------------------------------
    def avoid(self, car, seg, pseg):
        segs, N = self.track.segs, len(self.track.segs)
        for i in range(1, 21):
            s = segs[(seg.idx + i) % N]
            if s is pseg and car.speed > self.speed and overlap(car.offset, car.w, self.px, PLAYER_W, 1.2):
                if self.px > 0.5:
                    d = -1
                elif self.px < -0.5:
                    d = 1
                else:
                    d = -1 if car.offset > self.px else 1
                return d / i * (car.speed - self.speed) / MAXSPEED
            for o in s.cars:
                if car.speed > o.speed and overlap(car.offset, car.w, o.offset, o.w, 1.2):
                    if o.offset > 0.5:
                        d = -1
                    elif o.offset < -0.5:
                        d = 1
                    else:
                        d = -1 if car.offset > o.offset else 1
                    return d / i * (car.speed - o.speed) / MAXSPEED
        return 0.0

    def update_cars(self, dt):
        tr = self.track
        L, N = tr.length, len(tr.segs)
        pseg = self.seg_at(self.pos + PLAYERZ)
        player_prog = self.progress
        for car in self.cars:
            old = car.seg
            off0 = car.offset
            car.offset += self.avoid(car, old, pseg) * dt * 60
            if car.rival:
                ahead = tr.segs[(old.idx + 12) % N]
                car.offset += clamp(ahead.curve, -6, 6) * 0.0032 * dt * 60
                lim = car.top * (1 - min(0.30, abs(ahead.curve) * 0.045))
                gap = (car.lap * L + car.z) - player_prog
                if gap > 9000:
                    lim *= 0.9
                elif gap < -7000:
                    lim *= 1.07
                if car.finished:
                    lim = car.top * 0.5
                if self.state == "countdown":
                    lim = 0.0
                step = MAXSPEED * 0.55 * dt
                car.speed += clamp(lim - car.speed, -step, step)
                car.brake = lim < car.speed - 50
            car.offset = clamp(car.offset, -0.95, 0.95)
            vx = (car.offset - off0) / max(dt, 1e-3)
            car.dx += (vx - car.dx) * min(1.0, dt * 6)
            if abs(car.dx) > 0.15:
                car.sig_t, car.sig = 1.0, (1 if car.dx < 0 else 2)
            elif car.sig_t > 0:
                car.sig_t -= dt
            else:
                car.sig = 0
            car.yaw += (clamp(car.dx * 0.25, -0.3, 0.3) - car.yaw) * min(1.0, dt * 5)
            nz = car.z + dt * car.speed
            if nz >= L:
                nz -= L
                car.lap += 1
                if car.rival and car.lap >= self.laps and not car.finished:
                    car.finished, car.finish_t = True, self.t
            car.z = nz
            car.percent = (car.z % SEGL) / SEGL
            new = tr.segs[int(car.z // SEGL) % N]
            if new is not old:
                old.cars.remove(car)
                new.cars.append(car)
                car.seg = new

    # ---- main step ------------------------------------------------------------
    def update(self, dt, inp):
        self.t += dt
        self.crash_cd = max(0.0, self.crash_cd - dt)
        L = self.track.length
        # camera helpers (smooth lateral lag + FOV kick)
        self.cam_px += (self.px - self.cam_px) * min(1.0, dt * 5.5)
        sp = clamp(self.speed / MAXSPEED, 0, 1.4)
        fk = 0.16 * clamp((sp - 0.55) / 0.6, 0, 1) + (0.10 if self.boosting else 0.0)
        self.fov_k += (fk - self.fov_k) * min(1.0, dt * 3.0)
        if self.track.theme["weather"] == "rain":
            self.next_flash -= dt
            if self.next_flash <= 0:
                self.flash, self.next_flash = 1.0, self.rng.uniform(7, 18)
                self.thunder_t = self.rng.uniform(0.5, 1.8)
            self.flash = max(0.0, self.flash - dt * 4.0)
            if self.thunder_t > 0:
                self.thunder_t -= dt
                if self.thunder_t <= 0:
                    self.g.audio.play("thunder")
        if self.state == "countdown":
            self.cd -= dt
            n = int(math.ceil(self.cd - 0.6))
            if n != self.cd_last and n >= 1:
                self.g.audio.play("beep")
            self.cd_last = n
            self.rpm += ((3000 if inp["thr"] else 1100) - self.rpm) * min(1.0, dt * 6)
            self.g.audio.update(clamp((self.rpm - 1000) / 6800, 0, 1), 1.0 if inp["thr"] else 0.0, 0, 0, 0)
            self.update_cars(dt)
            if self.cd <= 0.0:
                self.state = "racing"
                self.g.audio.play("go")
                self.lap_t0 = self.t
                self.banner = ("GO!", 1.0)
            return
        if self.finished:
            inp = self.autopilot(brake_after=True)
        self.step_player(dt, inp)
        self.update_cars(dt)
        z = (self.pos + PLAYERZ) % L
        if z < self.last_z - L / 2:
            self.lap += 1
            if self.lap <= self.laps and not self.finished:
                lt = self.t - self.lap_t0
                self.lap_t0 = self.t
                self.lap_times.append(lt)
                if self.best_lap is None or lt < self.best_lap:
                    self.best_lap = lt
                if self.lap >= self.laps:
                    self.finished = True
                    self.finish_t = self.t
                    self.rank_final = 1 + sum(1 for r in self.rivals if r.finished)
                    self.banner = (f"FINISH! {ordinal(self.rank_final)}", 4.0)
                    self.g.audio.play("go")
                else:
                    ref = self.g.save["best"].get(str(self.ti))
                    d = f"   {lt - ref:+.2f}" if ref else ""
                    self.banner = (f"LAP {self.lap + 1}/{self.laps}   {fmt_time(lt)}{d}", 2.4)
                    self.g.audio.play("lap")
        elif z > self.last_z + L / 2:
            self.lap = max(0, self.lap - 1)
        self.last_z = z
        self.shake = max(0.0, self.shake - dt * 2.2)
        txt, tm = self.banner
        if tm > 0:
            self.banner = (txt, tm - dt)

    def autopilot(self, brake_after=False):
        seg = self.seg_at(self.pos + PLAYERZ)
        ahead = self.track.segs[(seg.idx + 14) % len(self.track.segs)]
        target = clamp(ahead.curve * 0.1, -0.5, 0.5)
        sp = self.speed / MAXSPEED
        steer = clamp((target - self.px) * 3.0 + sp * seg.curve * CENTRIF * 2.2, -1, 1)
        slow = abs(ahead.curve) > 4.5 and self.speed > MAXSPEED * 0.72
        brake = brake_after or slow
        for i in range(2, 16):
            for c in self.track.segs[(seg.idx + i) % len(self.track.segs)].cars:
                if overlap(self.px, PLAYER_W, c.offset, c.w, 1.5) and c.speed < self.speed:
                    if i < 9:
                        steer = -1 if c.offset >= self.px else 1
                    if i < 4 and self.speed > c.speed * 1.2:
                        brake = True
        return dict(thr=not brake, brk=brake_after and self.speed > MAXSPEED * 0.1 or (brake and not brake_after and self.speed > MAXSPEED * 0.8),
                    left=steer < -0.1, right=steer > 0.1, nitro=(not brake_after and sp > 0.85 and abs(ahead.curve) < 1.5),
                    hand=False)


# --------------------------------------------------------------------------
# The game: rendering, HUD, menus, main loop
# --------------------------------------------------------------------------
UPGRADES = [("Engine", "engine", "+5% top speed, +8% acceleration"),
            ("Tires", "tires", "+7% steering, less slide, less off-road drag"),
            ("Nitro Tank", "nitro", "+25 capacity, faster drift charging"),
            ("Brakes", "brakes", "+12% braking power")]
PRIZES = [1000, 600, 350, 150, 80, 40]
CAM_NAMES = ["Chase cam", "Hood cam", "Cockpit cam"]


def upgrade_cost(level):
    return int(round(250 * (level + 1) ** 1.5 / 50.0)) * 50


class Game:
    def __init__(self):
        pygame.mixer.pre_init(SR, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Redline Horizon")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.assets = Assets()
        self.audio = Audio()
        self.tracks = [Track(s) for s in TRACKS]
        self.save = self.load_save()
        self.state = "title"
        self.menu_i = 0
        self.track_i = 0
        self.garage_i = 0
        self.race = None
        self.results = None
        self.demo_pos = 0.0
        self.demo_t = 0.0
        self.msg = ("", 0.0)
        self.cone = self.make_cone()
        self.vig = self.make_vignette()
        self.sb = pygame.Surface((W, H), pygame.SRCALPHA)
        self.turn = 0.0
        self.lowq = False
        self.dt_avg = 0.016
        self.slow_t = 0.0

    # ---- persistence ------------------------------------------------------
    def load_save(self):
        data = dict(money=600, up=dict(engine=0, tires=0, nitro=0, brakes=0), color=0, unlocked=1,
                    best={}, wins=0, races=0)
        try:
            with open(SAVE_FILE) as f:
                loaded = json.load(f)
            for k, v in loaded.items():
                if k == "up":
                    data["up"].update(v)
                else:
                    data[k] = v
        except Exception:
            pass
        return data

    def write_save(self):
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump(self.save, f)
        except OSError:
            pass

    def make_cone(self):
        s = pygame.Surface((W, H))
        pygame.draw.polygon(s, (70, 64, 36), [(HALF_W - 60, H - 90), (HALF_W + 60, H - 90), (HALF_W + 330, H), (HALF_W - 330, H)])
        pygame.draw.polygon(s, (48, 44, 26), [(HALF_W - 18, HALF_H + 30), (HALF_W + 18, HALF_H + 30), (HALF_W + 150, H - 80), (HALF_W - 150, H - 80)])
        return pygame.transform.smoothscale(pygame.transform.smoothscale(s, (W // 8, H // 8)), (W, H))

    def make_vignette(self):
        sm = pygame.Surface((64, 40), pygame.SRCALPHA)
        for y in range(40):
            for x in range(64):
                d = min(1.0, math.hypot((x - 31.5) / 32, (y - 19.5) / 20) / 1.12)
                sm.set_at((x, y), (0, 0, 0, min(255, int(150 * max(0.0, d - 0.5) / 0.5))))
        return pygame.transform.smoothscale(sm, (W, H))

    # ---- text helpers -------------------------------------------------------
    def text(self, s, x, y, color=(235, 235, 240), font=None, anchor="l", shadow=True):
        font = font or self.assets.f_mid
        img = font.render(str(s), True, color)
        r = img.get_rect()
        if anchor == "c":
            r.midtop = (x, y)
        elif anchor == "r":
            r.topright = (x, y)
        else:
            r.topleft = (x, y)
        if shadow:
            self.screen.blit(font.render(str(s), True, (0, 0, 0)), r.move(2, 2))
        self.screen.blit(img, r)
        return r

    def arc(self, cx, cy, r, a0, a1, color, width):
        n = max(2, int(abs(a1 - a0) / 4))
        pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        pygame.draw.lines(self.screen, color, False, pts, width)

    # ---- sprite blitting ---------------------------------------------------------
    def blit_scaled(self, img, dw, dh, x, y, clip, fogt, fade=True):
        """Draw img scaled to dw x dh with its top-left at (x, y), clipped above `clip`."""
        if dw < 2 or dh < 2 or dw > W * 2.4 or x > W or x + dw < 0:
            return
        if y >= clip:
            return
        sp = pygame.transform.scale(img, (int(dw), int(dh)))
        if fade and fogt > 0.06:
            sp.set_alpha(int(255 * (1 - fogt * 0.92)))
        if clip < H:
            self.screen.set_clip((0, 0, W, max(0, int(clip))))
        self.screen.blit(sp, (int(x), int(y)))
        if clip < H:
            self.screen.set_clip(None)

    def draw_birds(self, t):
        for i in range(6):
            x = (t * (24 + i * 3) + i * 170) % (W + 120) - 60
            y = 118 + i * 16 + math.sin(t * 1.3 + i) * 8
            flap = math.sin(t * 9 + i * 1.7) * 6
            pygame.draw.lines(self.screen, (40, 46, 60), False, [(x - 9, y - flap), (x, y), (x + 9, y - flap)], 2)

    # ---- the world ------------------------------------------------------------
    def draw_world(self, tr, pos, px, bg_off, camd=CAMD, cam_h=CAMH, ox=0.0, oy=0.0, cars=True, t=0.0, elev_z=None, dn=DRAW):
        scr = self.screen
        th, segs = tr.theme, tr.segs
        N, L = len(segs), tr.length
        fogc, bgk, key = th["fog"], th["bg"], tr.spec["theme"]
        wet = th["weather"] == "rain"
        night = th["night"]
        sky, layers = self.assets.background(key)
        scr.blit(sky, (0, 0))
        for img, y, fac in layers:
            w2 = img.get_width()
            x = -int((bg_off * fac) % w2)
            scr.blit(img, (x, y))
            if x + w2 < W:
                scr.blit(img, (x + w2, y))
        if bgk == "coast":
            self.draw_birds(t)
        scr.fill(fogc, (0, HALF_H + 10 + int(oy), W, H))
        base = segs[int(pos // SEGL) % N]
        base_pct = (pos % SEGL) / SEGL
        ez = (pos + PLAYERZ) if elev_z is None else elev_z
        pseg = segs[int(ez // SEGL) % N]
        ppct = (ez % SEGL) / SEGL
        cam_y = lerp(pseg.y1, pseg.y2, ppct) + cam_h
        camx = px * ROADW
        hx, hy = HALF_W + ox, HALF_H + oy
        x = 0.0
        dx = -(base.curve * base_pct)
        maxy = H
        poly = pygame.draw.polygon
        line = pygame.draw.line
        road_c, grass_c, rum_c = th["road"], th["grass"], th["rumble"]
        tun_fog = (6, 6, 10)
        sheen_c = mix(th["sky"][1], (255, 255, 255), 0.2)
        for n in range(dn):
            seg = segs[(base.idx + n) % N]
            looped = seg.idx < base.idx
            camz = pos - (L if looped else 0.0)
            z1 = seg.idx * SEGL - camz
            z2 = z1 + SEGL
            seg.clip = maxy
            seg.v = False
            tf = 1.0 - 1.0 / math.exp((n / dn) ** 2 * FOGD)
            seg.fog = tf
            cx1, cx2 = x - camx, x + dx - camx
            cy1, cy2 = seg.y1 - cam_y, seg.y2 - cam_y
            seg.ok = z1 > camd
            if seg.ok:
                s1 = camd / z1
                seg.ss1 = s1
                seg.sx1 = hx + s1 * cx1 * HALF_W
                seg.sy1 = hy - s1 * cy1 * HALF_H
                seg.sw1 = s1 * ROADW * HALF_W
            x += dx
            dx += seg.curve
            if z1 <= camd or z2 <= camd:
                continue
            s2 = camd / z2
            seg.ss2 = s2
            seg.sx2 = hx + s2 * cx2 * HALF_W
            seg.sy2 = hy - s2 * cy2 * HALF_H
            seg.sw2 = s2 * ROADW * HALF_W
            seg.v = True
            y1, y2 = seg.sy1, seg.sy2
            if y2 >= y1 or y2 >= maxy:
                continue
            x1, x2, w1, w2 = seg.sx1, seg.sx2, seg.sw1, seg.sw2
            f, tun, hue = seg.flag, seg.tunnel, seg.hue
            if f < 2:
                road, grass, rum = road_c[f], grass_c[f], rum_c[f]
                lane = th["lane"] if f == 0 else None
            elif f == 2:
                road, grass, rum, lane = (236, 236, 236), grass_c[0], rum_c[0], None
            else:
                road, grass, rum, lane = (22, 22, 26), grass_c[1], rum_c[1], None
            if f < 2:
                road, grass = shade(road, hue), shade(grass, hue)
            if wet:
                road = shade(road, 0.8)
            fc, t_ = fogc, tf
            if tun:
                road, grass, rum = shade(road, 0.62), (14, 14, 18), shade(rum, 0.6)
                fc, t_ = tun_fog, clamp(n / 70.0, 0.0, 1.0) ** 1.3
            if t_ > 0.002:
                road, grass, rum = mix(road, fc, t_), mix(grass, fc, t_), mix(rum, fc, t_)
                if lane:
                    lane = mix(lane, fc, t_)
            scr.fill(grass, (0, int(y2), W, int(y1 - y2) + 1))
            r1, r2 = w1 / max(6, 2 * LANES), w2 / max(6, 2 * LANES)
            poly(scr, rum, [(x1 - w1 - r1, y1), (x1 - w1, y1), (x2 - w2, y2), (x2 - w2 - r2, y2)])
            poly(scr, rum, [(x1 + w1 + r1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 + w2 + r2, y2)])
            poly(scr, road, [(x1 - w1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 - w2, y2)])
            if (wet or night) and not tun and n < 150:
                sc_ = mix(road, mix(sheen_c, fc, t_), 0.16 if wet else 0.08)
                poly(scr, sc_, [(x1 - w1 * 0.2, y1), (x1 + w1 * 0.2, y1), (x2 + w2 * 0.2, y2), (x2 - w2 * 0.2, y2)])
            if lane:
                l1, l2 = w1 / max(32, 8 * LANES), w2 / max(32, 8 * LANES)
                lw1, lw2 = w1 * 2 / LANES, w2 * 2 / LANES
                lx1, lx2 = x1 - w1 + lw1, x2 - w2 + lw2
                for _ in range(1, LANES):
                    poly(scr, lane, [(lx1 - l1 / 2, y1), (lx1 + l1 / 2, y1), (lx2 + l2 / 2, y2), (lx2 - l2 / 2, y2)])
                    lx1 += lw1
                    lx2 += lw2
            if f < 2 and n < 170:                                   # solid edge lines
                ec = mix(th["lane"], fc, t_) if t_ > 0.002 else th["lane"]
                for sgn in (-1, 1):
                    poly(scr, ec, [(x1 + sgn * w1 * 0.94, y1), (x1 + sgn * w1 * 0.975, y1),
                                   (x2 + sgn * w2 * 0.975, y2), (x2 + sgn * w2 * 0.94, y2)])
            if seg.decals and n < 120:
                dark = mix(shade(road, 0.55), fc, t_)
                for dc in seg.decals:
                    k = dc[0]
                    if k == "seam":
                        fr = dc[1]
                        xm, ym, wm = x1 + (x2 - x1) * fr, y1 + (y2 - y1) * fr, w1 + (w2 - w1) * fr
                        line(scr, dark, (xm - wm, ym), (xm + wm, ym), 1)
                    elif k == "patch":
                        fr = dc[2]
                        xm, ym, wm = x1 + (x2 - x1) * fr, y1 + (y2 - y1) * fr, w1 + (w2 - w1) * fr
                        cxp = xm + wm * dc[1]
                        poly(scr, dark, [(cxp - wm * 0.18, ym), (cxp + wm * 0.18, ym), (cxp + wm * 0.14, ym - wm * 0.05), (cxp - wm * 0.14, ym - wm * 0.05)])
                    else:
                        fr0, fr1 = dc[2], min(1.0, dc[2] + 0.55)
                        a = (x1 + (x2 - x1) * fr0 + (w1 + (w2 - w1) * fr0) * dc[1], y1 + (y2 - y1) * fr0)
                        b = (x1 + (x2 - x1) * fr1 + (w1 + (w2 - w1) * fr1) * dc[1], y1 + (y2 - y1) * fr1)
                        line(scr, dark, a, b, max(1, int(w1 * 0.012)))
            maxy = y1
        # ---- far-to-near pass: tunnels, rails, cars, scenery
        sprites = self.assets.sprites(key)
        emissive = ("lamp", "neon")
        tun_wall = (60, 62, 72)
        for n in range(dn - 1, 0, -1):
            seg = segs[(base.idx + n) % N]
            clip = seg.clip
            vis = seg.v and seg.sy2 < seg.sy1 and seg.sy2 < clip
            if vis and (seg.tunnel or seg.rail):
                if clip < H:
                    scr.set_clip((0, 0, W, max(0, int(clip))))
                x1, x2, y1, y2 = seg.sx1, seg.sx2, seg.sy1, seg.sy2
                if seg.tunnel:
                    tt = clamp(n / 70.0, 0.0, 1.0) ** 1.3
                    wl, wr = mix(tun_wall, tun_fog, tt), mix(shade(tun_wall, 0.82), tun_fog, tt)
                    cl = mix((40, 42, 50), tun_fog, tt)
                    w1_, w2_ = seg.ss1 * TUN_W * HALF_W, seg.ss2 * TUN_W * HALF_W
                    h1_, h2_ = seg.ss1 * TUN_H * HALF_H, seg.ss2 * TUN_H * HALF_H
                    col = wl if seg.idx % 2 == 0 else wr
                    poly(scr, col, [(x1 - w1_, y1), (x1 - w1_, y1 - h1_), (x2 - w2_, y2 - h2_), (x2 - w2_, y2)])
                    poly(scr, col, [(x1 + w1_, y1), (x1 + w1_, y1 - h1_), (x2 + w2_, y2 - h2_), (x2 + w2_, y2)])
                    poly(scr, cl, [(x1 - w1_, y1 - h1_), (x1 + w1_, y1 - h1_), (x2 + w2_, y2 - h2_), (x2 - w2_, y2 - h2_)])
                    if seg.idx % 4 == 0:                                   # ceiling light strips
                        lc = mix((255, 236, 190), tun_fog, tt * 0.7)
                        poly(scr, lc, [(x1 - w1_ * 0.12, y1 - h1_), (x1 + w1_ * 0.12, y1 - h1_), (x2 + w2_ * 0.12, y2 - h2_), (x2 - w2_ * 0.12, y2 - h2_)])
                    if seg.idx % 6 == 0:                                   # wall stripe
                        sc2 = mix((230, 170, 40), tun_fog, tt)
                        poly(scr, sc2, [(x1 - w1_, y1 - h1_ * 0.18), (x1 - w1_, y1 - h1_ * 0.24), (x2 - w2_, y2 - h2_ * 0.24), (x2 - w2_, y2 - h2_ * 0.18)])
                        poly(scr, sc2, [(x1 + w1_, y1 - h1_ * 0.18), (x1 + w1_, y1 - h1_ * 0.24), (x2 + w2_, y2 - h2_ * 0.24), (x2 + w2_, y2 - h2_ * 0.18)])
                if seg.rail:
                    steel = mix((176, 182, 192), fogc, seg.fog)
                    steel_hi = mix((226, 230, 238), fogc, seg.fog)
                    post = mix((90, 94, 104), fogc, seg.fog)
                    hh1, hh2 = seg.ss1 * RAIL_H * HALF_H, seg.ss2 * RAIL_H * HALF_H
                    for sgn, bit in ((-1, 1), (1, 2)):
                        if seg.rail & bit:
                            xa, xb = x1 + sgn * seg.sw1 * 1.17, x2 + sgn * seg.sw2 * 1.17
                            poly(scr, steel, [(xa, y1), (xa, y1 - hh1), (xb, y2 - hh2), (xb, y2)])
                            poly(scr, steel_hi, [(xa, y1 - hh1 * 0.55), (xa, y1 - hh1), (xb, y2 - hh2), (xb, y2 - hh2 * 0.55)])
                            if seg.idx % 2 == 0:
                                pw = max(1.0, seg.sw1 * 0.014)
                                poly(scr, post, [(xa - pw, y1), (xa - pw, y1 - hh1 * 1.05), (xa + pw, y1 - hh1 * 1.05), (xa + pw, y1)])
                if clip < H:
                    scr.set_clip(None)
            if not seg.ok:
                continue
            if cars:
                for car in seg.cars:
                    if seg.v:
                        sc = lerp(seg.ss1, seg.ss2, car.percent)
                        cxp = lerp(seg.sx1, seg.sx2, car.percent) + sc * car.offset * ROADW * HALF_W
                        cyp = lerp(seg.sy1, seg.sy2, car.percent)
                    else:
                        sc = seg.ss1
                        cxp = seg.sx1 + sc * car.offset * ROADW * HALF_W
                        cyp = seg.sy1
                    yq = int(clamp(round(car.yaw / 0.1), -3, 3))
                    sg = car.sig if int(t * 3) % 2 == 0 else 0
                    img, anc, refw = self.assets.car_sprite(car.kind, car.color, yq, car.brake, sg, key)
                    dw = car.w * ROADW * sc * HALF_W
                    fct = dw / refw
                    self.blit_scaled(img, img.get_width() * fct, img.get_height() * fct, cxp - anc[0] * fct, cyp - anc[1] * fct, clip, seg.fog)
            for sk, off, anchor in seg.sprites:
                if n > 175 and sk not in ("building", "bridge", "portal", "stand", "neon"):
                    continue
                img = sprites[sk]
                if isinstance(img, list):
                    if sk in ("palm", "pine", "bush"):
                        img = img[int((math.sin(t * 1.6 + seg.idx * 0.7) * 0.5 + 0.5) * 4.99)]
                    elif sk == "turbine":
                        img = img[int(t * 3.5 + seg.idx) % 8]
                    else:
                        img = img[1 if math.sin(t * 9 + seg.idx * 1.3) > 0.93 else 0]
                sc = seg.ss1
                dw = SPRITE_W[sk] * ROADW * sc * HALF_W
                dh = dw * img.get_height() / img.get_width()
                self.blit_scaled(img, dw, dh, seg.sx1 + sc * off * ROADW * HALF_W + dw * anchor, seg.sy1 - dh, clip, seg.fog,
                                 fade=sk not in emissive)

    # ---- player car and cockpit views ---------------------------------------------
    def draw_player_car(self, race):
        th = race.track.theme
        st = dict(steer=race.steer * 0.5, wphase=race.wphase, brake=race.brake_on, boost=race.boosting, lights=th["night"])
        view = dict(yaw=race.yaw_v, pitch=race.pitch, roll=race.roll, bob=race.bounce, cam_d=8.4, cam_h=2.1, cam_pitch=0.14)
        surf, anc, refw = self.assets.car3d.render("sports", CAR_COLORS[self.save["color"]], st, view, th)
        f = PLAYER_W * ROADW * (CAMD / PLAYERZ) * HALF_W / refw
        lat = (race.px - race.cam_px) * ROADW * (CAMD / PLAYERZ) * HALF_W
        img = pygame.transform.smoothscale(surf, (max(1, int(surf.get_width() * f)), max(1, int(surf.get_height() * f))))
        self.screen.blit(img, (HALF_W + lat - anc[0] * f, H - 22 - anc[1] * f))

    def gauge(self, cx, cy, r, frac, red_from=0.8, label=""):
        scr = self.screen
        pygame.draw.circle(scr, (8, 8, 12), (cx, cy), r + 6)
        pygame.draw.circle(scr, (80, 84, 104), (cx, cy), r + 6, 2)
        for k in range(11):
            a = math.radians(135 + 270 * k / 10)
            col = (255, 90, 80) if k / 10 >= red_from else (205, 208, 220)
            ln = 14 if k % 2 == 0 else 8
            pygame.draw.line(scr, col, (cx + (r - 3) * math.cos(a), cy + (r - 3) * math.sin(a)),
                             (cx + (r - ln) * math.cos(a), cy + (r - ln) * math.sin(a)), 2)
        a = math.radians(135 + 270 * clamp(frac, 0, 1))
        pygame.draw.line(scr, (255, 70, 50), (cx - 8 * math.cos(a), cy - 8 * math.sin(a)),
                         (cx + (r - 10) * math.cos(a), cy + (r - 10) * math.sin(a)), 3)
        pygame.draw.circle(scr, (30, 30, 36), (cx, cy), 6)
        if label:
            self.text(label, cx, cy + r * 0.38, (170, 175, 195), self.assets.f_small, "c", False)

    def draw_cockpit(self, race, mode):
        scr, t = self.screen, race.t
        col = CAR_COLORS[self.save["color"]]
        vib = math.sin(t * 60) * min(1.0, race.speed / MAXSPEED) * 1.2
        rain = race.track.theme["weather"] == "rain"
        if mode == 1:                                                    # hood camera: bonnet with highlights
            base = shade(col, 0.55 if race.track.theme["night"] else 0.9)
            y0 = H - 150 + vib
            pts = [(HALF_W - 420, H), (HALF_W - 250, y0 + 20), (HALF_W - 90, y0 - 4), (HALF_W + 90, y0 - 4), (HALF_W + 250, y0 + 20), (HALF_W + 420, H)]
            pygame.draw.polygon(scr, base, pts)
            for i in range(14):
                tt = i / 13
                c2 = mix(shade(base, 1.25), shade(base, 0.6), tt)
                yy = y0 + (H - y0) * tt
                half = 90 + 330 * tt - (1 - tt) * 0
                pygame.draw.line(scr, c2, (HALF_W - half * 0.98, yy), (HALF_W + half * 0.98, yy), int((H - y0) / 13) + 2)
            pygame.draw.line(scr, shade(base, 1.5), (HALF_W - 130, y0 + 4), (HALF_W + 130, y0 + 4), 3)
            pygame.draw.polygon(scr, shade(base, 0.4), [(HALF_W - 70, H), (HALF_W - 40, y0 + 30), (HALF_W + 40, y0 + 30), (HALF_W + 70, H)], 2)
            pygame.draw.polygon(scr, (12, 12, 16), [(HALF_W - 90, y0 - 4), (HALF_W - 250, y0 + 20), (HALF_W - 270, y0 + 28), (HALF_W + 270, y0 + 28), (HALF_W + 250, y0 + 20), (HALF_W + 90, y0 - 4)], 3)
        else:                                                            # cockpit: dashboard, pillars, wheel, gauges
            dash = [(0, H), (0, H - 118), (HALF_W - 330, H - 152), (HALF_W - 120, H - 172), (HALF_W + 120, H - 172), (HALF_W + 330, H - 152), (W, H - 118), (W, H)]
            pygame.draw.polygon(scr, (20, 20, 26), dash)
            pygame.draw.lines(scr, (70, 72, 90), False, dash[1:7], 3)
            pygame.draw.rect(scr, (10, 10, 14), (HALF_W - 250, H - 176, 500, 118), border_radius=26)
            pygame.draw.rect(scr, (60, 62, 80), (HALF_W - 250, H - 176, 500, 118), 2, border_radius=26)
            self.gauge(HALF_W - 120, H - 112, 46, clamp(race.rpm / 8000, 0, 1), 0.82, "RPM")
            self.gauge(HALF_W + 120, H - 112, 46, clamp(race.speed / (MAXSPEED * 1.35), 0, 1), 0.9, "")
            self.text(f"{int(race.kph)}", HALF_W + 120, H - 118, (255, 255, 255), self.assets.f_mid, "c")
            self.text(f"G{race.gear}", HALF_W, H - 150, (255, 210, 60) if race.shift_t > 0 else (235, 235, 240), self.assets.f_mid, "c")
            pygame.draw.rect(scr, (60, 200, 255), (HALF_W - 60, H - 100, int(120 * race.turbo), 7))
            pygame.draw.rect(scr, (70, 74, 96), (HALF_W - 60, H - 100, 120, 7), 1)
            for sgn in (-1, 1):                                          # A-pillars
                pygame.draw.polygon(scr, (14, 14, 18), [(HALF_W + sgn * 512, 0), (HALF_W + sgn * 440, 0), (HALF_W + sgn * 360, H - 150), (HALF_W + sgn * 512, H - 118)])
            pygame.draw.rect(scr, (12, 12, 16), (0, 0, W, 16))
            pygame.draw.rect(scr, (18, 20, 26), (HALF_W - 78, 14, 156, 42), border_radius=8)           # rear-view mirror
            for yy in range(40):
                pygame.draw.line(scr, mix(race.track.theme["sky"][0], race.track.theme["sky"][1], yy / 40), (HALF_W - 72, 18 + yy), (HALF_W + 72, 18 + yy))
            pygame.draw.rect(scr, (70, 74, 96), (HALF_W - 78, 14, 156, 42), 2, border_radius=8)
            for rv in race.rivals:                                       # rivals that are close behind appear in the mirror
                dz = ((race.pos + PLAYERZ) - rv.z) % race.track.length
                if 100 < dz < 7000:
                    s = clamp(1.0 - dz / 7000, 0.15, 1.0)
                    pygame.draw.rect(scr, rv.color, (HALF_W + rv.offset * 52 - 7 * s, 40 - 6 * s, 14 * s, 8 * s))
            ang = -race.steer * 1.4 + vib * 0.01                           # steering wheel
            cx, cy, R = HALF_W, H + 50, 205
            pygame.draw.circle(scr, (16, 16, 20), (cx, cy), R, 22)
            pygame.draw.circle(scr, (44, 46, 58), (cx, cy), R - 9, 2)
            for k in (0, 2.0944, 4.18879):
                a = ang + k - math.pi / 2
                pygame.draw.line(scr, (22, 22, 28), (cx, cy), (cx + (R - 12) * math.cos(a), cy + (R - 12) * math.sin(a)), 16)
            pygame.draw.line(scr, (255, 70, 50), (cx + (R - 24) * math.sin(ang), cy - (R - 24) * math.cos(ang)),
                             (cx + (R + 10) * math.sin(ang), cy - (R + 10) * math.cos(ang)), 6)
        if rain:
            ph = (math.sin(t * 2.3) * 0.5 + 0.5)
            a = math.radians(200 + 150 * ph)
            px0, py0 = HALF_W + 140, H - 120
            pygame.draw.line(scr, (8, 8, 10), (px0, py0), (px0 + 330 * math.cos(a), py0 + 330 * math.sin(a)), 6)

    def update_particles(self, race, dt):
        keep = []
        for p in race.particles:
            p[5] -= dt
            if p[5] <= 0:
                continue
            p[1] += p[3] * dt
            p[2] += p[4] * dt
            if p[0] == "spark":
                p[4] += 900 * dt
            keep.append(p)
        race.particles = keep[-260:]

    def draw_particles(self, race):
        for kind, x, y, vx, vy, life, col, size in race.particles:
            if kind == "spark":
                pygame.draw.line(self.screen, col, (x, y), (x - vx * 0.03, y - vy * 0.03), 2)
            else:
                a = int(clamp(life * (4.0 if kind == "flame" else 1.6), 0, 1) * (200 if kind == "flame" else 110))
                s = int(size * (1.3 - life)) if kind != "flame" else int(size)
                if s < 2:
                    continue
                surf = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*col, a), (s, s), s)
                self.screen.blit(surf, (x - s, y - s))

    def draw_weather(self, race, dt):
        wth = race.track.theme["weather"]
        if not wth:
            return
        sp = 0.6 + clamp(race.speed / MAXSPEED, 0, 1.3)
        if wth == "rain":
            for d in race.weather[:110]:
                d[1] += 900 * d[2] * dt
                d[0] -= 120 * dt * sp
                if d[1] > H:
                    d[1], d[0] = -20, random.uniform(0, W + 150)
                if d[0] < 0:
                    d[0] += W
                pygame.draw.line(self.screen, (150, 165, 198), (d[0], d[1]), (d[0] - 5, d[1] - 18 * d[2]), 1)
            for d in race.drops:                                        # droplets crawling down the lens / windscreen
                d[1] += dt * (14 + 60 * sp * d[3])
                if d[1] > H * 0.8:
                    d[0], d[1], d[2], d[3] = random.uniform(0, W), -6, random.uniform(2, 6), random.uniform(0, 1)
                pygame.draw.circle(self.screen, (150, 170, 205), (int(d[0]), int(d[1])), int(d[2]), 1)
                pygame.draw.circle(self.screen, (235, 240, 255), (int(d[0] - d[2] * 0.3), int(d[1] - d[2] * 0.3)), 1)
        else:
            for d in race.weather:
                d[1] += 150 * d[2] * dt * sp
                d[0] += math.sin(race.t * 1.3 + d[1] * 0.01) * 30 * dt
                if d[1] > H:
                    d[1], d[0] = -6, random.uniform(0, W)
                pygame.draw.circle(self.screen, (245, 248, 255), (int(d[0]), int(d[1])), 2 if d[2] > 1 else 1)

    # ---- HUD ------------------------------------------------------------------------
    def draw_hud(self, race):
        scr = self.screen
        a = self.assets
        if race.cam_mode != 2:
            cx, cy, r = W - 120, H - 112, 92
            pygame.draw.circle(scr, (8, 8, 14), (cx, cy), r + 14)
            pygame.draw.circle(scr, (60, 62, 80), (cx, cy), r + 14, 2)
            self.arc(cx, cy, r, 135, 405, (50, 52, 66), 10)
            n = int(clamp(race.rpm / 8000, 0, 1) * 54)
            for i in range(n):
                ang = 135 + 270 * i / 54
                col = (70, 220, 120) if i < 38 else ((255, 210, 60) if i < 46 else (255, 60, 50))
                self.arc(cx, cy, r, ang, ang + 4.2, col, 10)
            if race.turbo > 0.02:
                self.arc(cx, cy, r - 18, 135, 135 + 270 * race.turbo, (90, 200, 255), 4)
            for k in range(9):
                ang = math.radians(135 + 270 * k / 8)
                pygame.draw.line(scr, (180, 180, 195) if k < 7 else (255, 90, 80),
                                 (cx + (r - 26) * math.cos(ang), cy + (r - 26) * math.sin(ang)),
                                 (cx + (r - 34) * math.cos(ang), cy + (r - 34) * math.sin(ang)), 2)
            self.text(f"{int(race.kph)}", cx, cy - 30, (255, 255, 255), a.f_big, "c")
            self.text("km/h", cx, cy + 14, (160, 165, 185), a.f_small, "c")
            self.text(f"G{race.gear}", cx, cy + 34, (255, 210, 60) if race.shift_t > 0 else (255, 255, 255), a.f_mid, "c")
        bx, by, bw, bh = 24, H - 44, 260, 18
        pygame.draw.rect(scr, (10, 10, 18), (bx - 3, by - 3, bw + 6, bh + 6), border_radius=6)
        col = (80, 200, 255) if not race.boosting else (255, 190, 80)
        pygame.draw.rect(scr, col, (bx, by, int(bw * race.nitro / race.cap), bh), border_radius=4)
        self.text("NITRO  [Shift]", bx, by - 22, (160, 200, 230), a.f_small)
        if race.damage > 1:
            pygame.draw.rect(scr, (10, 10, 18), (bx - 3, by - 40, 126, 12))
            pygame.draw.rect(scr, (230, 70, 60), (bx, by - 38, int(120 * race.damage / 100), 8))
            self.text("DAMAGE", bx + 132, by - 44, (230, 140, 130), a.f_small)
        if race.drifting:
            self.text(f"DRIFT {race.drift_t:.1f}s", bx, by - 72, (255, 210, 80), a.f_mid)
        elif race.boost_t > 0:
            self.text("BOOST!", bx, by - 72, (255, 150, 60), a.f_mid)
        elif race.draft > 0.3:
            self.text("SLIPSTREAM", bx, by - 72, (150, 230, 255), a.f_mid)
        order = race.standings()
        me = [i for i, r in enumerate(order) if r[2]][0]
        rk = me + 1
        self.text(f"{rk}", 24, 10, (255, 220, 90), a.f_big)
        self.text(f"/ 6  {ordinal(rk)}", 64, 24, (230, 230, 240), a.f_mid)
        lap_show = min(race.lap + 1, race.laps)
        self.text(f"LAP {lap_show}/{race.laps}", 24, 60, (255, 255, 255))
        cur = race.t - race.lap_t0 if race.state == "racing" and not race.finished else (race.lap_times[-1] if race.lap_times else 0)
        self.text(f"TIME {fmt_time(max(0, cur))}", 24, 88, (220, 225, 240), a.f_small)
        self.text(f"BEST {fmt_time(race.best_lap or self.save['best'].get(str(race.ti)))}", 24, 106, (170, 220, 170), a.f_small)
        mp = order[me][1]
        for i, (name, prog, you) in enumerate(order):               # leaderboard tower with time gaps
            gap = (prog - mp) / MAXSPEED
            tag = "" if you else (f"+{gap:.1f}" if gap > 0 else f"{gap:.1f}")
            yy = 134 + i * 17
            pygame.draw.rect(scr, (255, 220, 90) if you else (14, 14, 24), (24, yy, 140, 16))
            self.text(f"{i + 1} {name}", 28, yy, (20, 20, 26) if you else (230, 232, 244), a.f_small, "l", False)
            self.text(tag, 160, yy, (20, 20, 26) if you else (170, 175, 200), a.f_small, "r", False)
        self.draw_minimap(race)
        txt, tm = race.banner
        if tm > 0:
            self.text(txt, HALF_W, 90, (255, 235, 120), a.f_big, "c")
        if race.state == "countdown":
            n = int(math.ceil(race.cd - 0.6))
            for i in range(3):                                      # starting lights
                lit = n <= 3 - i if n > 0 else True
                col = (60, 255, 100) if n <= 0 else ((255, 50, 40) if lit else (50, 14, 14))
                pygame.draw.circle(scr, (10, 10, 14), (HALF_W - 70 + i * 70, 82), 28)
                pygame.draw.circle(scr, col, (HALF_W - 70 + i * 70, 82), 22)
            self.text("Hold UP to rev.  Shift = nitro, Space = drift, C = camera", HALF_W, 270, (235, 235, 245), a.f_small, "c")
        if abs(race.px) > 1.0 and race.speed > MAXSPEED * 0.3:
            self.text("OFF ROAD", HALF_W, 200, (255, 120, 90), a.f_mid, "c")
        if race.cam_mode and race.t - race.lap_t0 < 0:
            pass

    def draw_minimap(self, race):
        tr = race.track
        x0, y0, sz = W - 178, 12, 160
        panel = pygame.Surface((sz + 12, sz + 12), pygame.SRCALPHA)
        panel.fill((6, 6, 14, 170))
        self.screen.blit(panel, (x0 - 6, y0 - 6))
        pts = [(x0 + 6 + p[0] * (sz - 12), y0 + 6 + p[1] * (sz - 12)) for p in tr.map_pts[::5]]
        pygame.draw.lines(self.screen, (90, 96, 130), True, pts, 5)
        pygame.draw.lines(self.screen, (150, 156, 190), True, pts, 2)

        def at(z):
            p = tr.map_pts[int(z // SEGL) % len(tr.map_pts)]
            return int(x0 + 6 + p[0] * (sz - 12)), int(y0 + 6 + p[1] * (sz - 12))

        pygame.draw.circle(self.screen, (255, 255, 255), at(0), 4, 1)
        for rv in race.rivals:
            pygame.draw.circle(self.screen, rv.color, at(rv.z), 3)
        pygame.draw.circle(self.screen, (255, 230, 70), at(race.pos + PLAYERZ), 5)
        pygame.draw.circle(self.screen, (0, 0, 0), at(race.pos + PLAYERZ), 5, 1)

    # ---- race scene ---------------------------------------------------------------------
    def draw_race(self, race, dt):
        tr = race.track
        th = tr.theme
        L = tr.length
        mode = race.cam_mode
        j = race.shake * 10 + (1.2 if race.rumble else 0)
        ox, oy = random.uniform(-j, j), random.uniform(-j, j) * 0.6 + race.bounce * 70
        camd = 1.0 / math.tan(math.radians(FOV * (1 + race.fov_k) / 2))
        if mode == 0:
            pos, cam_h, cpx = race.pos, CAMH, race.cam_px
        elif mode == 1:
            pos, cam_h, cpx = (race.pos + PLAYERZ - 420) % L, 640, race.px
        else:
            pos, cam_h, cpx = (race.pos + PLAYERZ - 160) % L, 520, race.px
        self.draw_world(tr, pos, cpx, race.bg_off, camd, cam_h, ox, oy, True, race.t, race.pos + PLAYERZ, 150 if self.lowq else DRAW)
        if th["night"]:
            self.screen.blit(self.cone, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        sp = clamp(race.speed / MAXSPEED, 0, 1.4)
        amt = clamp((sp - 0.8) / 0.5, 0, 1) * 0.5 + (0.35 if race.boosting else 0.0)
        if amt > 0.05 and dt > 0 and not self.lowq:                                       # radial / motion blur
            small = pygame.transform.smoothscale(self.screen, (W // 5, H // 5))
            big = pygame.transform.scale(small, (int(W * 1.07), int(H * 1.07)))
            big.set_alpha(int(amt * 120))
            self.screen.blit(big, (-(big.get_width() - W) // 2, -(big.get_height() - H) // 2))
        if th["bg"] in ("coast", "alpine", "mesa") and not self.lowq:   # lens flare
            sx, sy = (420, 300) if th["bg"] == "mesa" else (760, 120)
            ang = math.atan2(HALF_H - sy, HALF_W - sx)
            for k, (name, sz) in enumerate((("white", 90), ("amber", 60), ("white", 130))):
                d = (k + 1) * 190
                g = pygame.transform.scale(self.assets.car3d.glow[name], (sz, sz))
                g.fill((60, 60, 60), special_flags=pygame.BLEND_RGB_MULT)
                self.screen.blit(g, (sx + math.cos(ang) * d - sz / 2, sy + math.sin(ang) * d - sz / 2), special_flags=pygame.BLEND_RGB_ADD)
        if race.boosting:
            for _ in range(16):
                a = random.uniform(0, math.tau)
                r0, r1 = random.uniform(160, 300), random.uniform(330, 560)
                pygame.draw.line(self.screen, (230, 240, 255), (HALF_W + math.cos(a) * r0, HALF_H + 40 + math.sin(a) * r0 * 0.6),
                                 (HALF_W + math.cos(a) * r1, HALF_H + 40 + math.sin(a) * r1 * 0.6), 1)
        self.update_particles(race, dt)
        if mode == 0:
            self.draw_player_car(race)
        else:
            self.draw_cockpit(race, mode)
        self.draw_particles(race)
        if not race.seg_at(race.pos + PLAYERZ).tunnel:
            self.draw_weather(race, dt)
        self.screen.blit(self.vig, (0, 0))
        if race.flash > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((235, 240, 255, int(150 * race.flash)))
            self.screen.blit(ov, (0, 0))
        if race.damage > 55:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.rect(ov, (200, 0, 0, int(40 * (race.damage - 55) / 45)), (0, 0, W, H), 22)
            self.screen.blit(ov, (0, 0))
        self.draw_hud(race)
        if race.cam_banner[1] > 0:
            self.text(race.cam_banner[0], HALF_W, H - 60, (255, 255, 255), self.assets.f_mid, "c")
            race.cam_banner = (race.cam_banner[0], race.cam_banner[1] - dt)

    # ---- menus ---------------------------------------------------------------------------------
    def menu_backdrop(self, ti, dt, dim=140):
        tr = self.tracks[ti]
        self.demo_t += dt
        self.demo_pos = (self.demo_pos + dt * MAXSPEED * 0.55) % tr.length
        self.draw_world(tr, self.demo_pos, math.sin(self.demo_t * 0.5) * 0.35, self.demo_t * 40, cars=False, t=self.demo_t)
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 10, dim))
        self.screen.blit(ov, (0, 0))

    def draw_turntable(self, cx, cy, width, yaw, color, theme_key="coast"):
        th = THEMES[theme_key]
        st = dict(brake=False, steer=0.0, wphase=yaw * 3, lights=True)
        surf, anc, refw = self.assets.car3d.render("sports", color, st, dict(yaw=yaw, cam_d=9.4, cam_h=2.7, cam_pitch=0.21), th)
        f = width / (refw * 1.2)
        img = pygame.transform.smoothscale(surf, (max(1, int(surf.get_width() * f)), max(1, int(surf.get_height() * f))))
        self.screen.blit(img, (cx - anc[0] * f, cy - anc[1] * f))

    def draw_title(self, dt):
        self.menu_backdrop(0, dt, 80)
        self.text("REDLINE", 60, 50, (255, 80, 60), self.assets.f_title)
        self.text("HORIZON", 60, 124, (255, 230, 120), self.assets.f_title)
        items = ["Race", "Garage", "How to play", "Sound: " + ("OFF" if self.audio.muted else "ON"), "Quit"]
        for i, it in enumerate(items):
            sel = i == self.menu_i
            self.text(("> " if sel else "  ") + it, 70, 270 + i * 50, (255, 230, 120) if sel else (220, 225, 240),
                      self.assets.f_big if sel else self.assets.f_mid)
        self.draw_turntable(850, 530, 340, self.turn * 0.7, CAR_COLORS[self.save["color"]])
        self.text(f"Cash ${self.save['money']}   Races {self.save['races']}   Wins {self.save['wins']}", 70, H - 44,
                  (180, 190, 210), self.assets.f_small)

    def draw_tracks(self, dt):
        ti = self.track_i
        self.menu_backdrop(ti, dt, 70)
        tr, spec = self.tracks[ti], TRACKS[ti]
        locked = ti >= self.save["unlocked"]
        panel = pygame.Surface((560, 250), pygame.SRCALPHA)
        panel.fill((8, 8, 20, 190))
        self.screen.blit(panel, (HALF_W - 280, 90))
        self.text(f"< {spec['name']} >", HALF_W, 104, (255, 230, 120), self.assets.f_big, "c")
        self.text(spec["blurb"], HALF_W, 162, (220, 225, 240), self.assets.f_small, "c")
        stars = "*" * (ti + 1) + "-" * (3 - ti)
        tun = sum(1 for s in tr.segs if s.tunnel) // 70
        self.text(f"Difficulty {stars}   Laps {spec['laps']}   Length {tr.length / 1000:.0f}k   Tunnels {tun}", HALF_W, 196,
                  (200, 205, 225), self.assets.f_small, "c")
        best = self.save["best"].get(str(ti))
        self.text(f"Best lap: {fmt_time(best)}", HALF_W, 224, (170, 225, 170), self.assets.f_mid, "c")
        if locked:
            self.text("LOCKED - finish top 3 on the previous track", HALF_W, 272, (255, 120, 100), self.assets.f_mid, "c")
        else:
            self.text("Enter: start race", HALF_W, 272, (255, 255, 255), self.assets.f_mid, "c")
        self.text("Left/Right: choose    Esc: back", HALF_W, H - 40, (180, 190, 210), self.assets.f_small, "c")

    def draw_garage(self, dt):
        self.menu_backdrop(0, dt, 190)
        self.text("GARAGE", HALF_W, 24, (255, 230, 120), self.assets.f_big, "c")
        self.text(f"Cash: ${self.save['money']}", HALF_W, 76, (170, 235, 170), self.assets.f_mid, "c")
        self.draw_turntable(235, 400, 400, self.turn * 0.8, CAR_COLORS[self.save["color"]])
        for i, (label, key, desc) in enumerate(UPGRADES + [("Paint", "color", "Left / Right to change")]):
            y = 130 + i * 78
            sel = i == self.garage_i
            pygame.draw.rect(self.screen, (24, 26, 46) if not sel else (44, 40, 74), (480, y, 500, 66), border_radius=8)
            if sel:
                pygame.draw.rect(self.screen, (255, 230, 120), (480, y, 500, 66), 2, border_radius=8)
            self.text(label, 496, y + 6, (255, 255, 255), self.assets.f_mid)
            self.text(desc, 496, y + 38, (170, 175, 200), self.assets.f_small)
            if key == "color":
                for c, col in enumerate(CAR_COLORS):
                    r = pygame.Rect(790 + (c % 4) * 44, y + 8 + (c // 4) * 26, 38, 22)
                    pygame.draw.rect(self.screen, col, r, border_radius=4)
                    if c == self.save["color"]:
                        pygame.draw.rect(self.screen, (255, 255, 255), r, 2, border_radius=4)
            else:
                lvl = self.save["up"][key]
                for p in range(5):
                    pygame.draw.rect(self.screen, (255, 200, 60) if p < lvl else (50, 52, 70), (800 + p * 34, y + 10, 28, 14), border_radius=3)
                cost = "MAX" if lvl >= 5 else f"${upgrade_cost(lvl)}"
                self.text(cost, 970, y + 36, (255, 230, 120) if lvl < 5 else (140, 200, 140), self.assets.f_small, "r")
        self.text("Up/Down select   Enter buy   Left/Right paint   Esc back", HALF_W, H - 36, (180, 190, 210), self.assets.f_small, "c")
        m, tm = self.msg
        if tm > 0:
            self.text(m, HALF_W, 108, (255, 150, 120), self.assets.f_small, "c")

    def draw_controls(self, dt):
        self.menu_backdrop(0, dt, 200)
        self.text("HOW TO PLAY", HALF_W, 36, (255, 230, 120), self.assets.f_big, "c")
        lines = ["UP / W ........ accelerate        DOWN / S ....... brake",
                 "LEFT / RIGHT ... steer (A / D)     LEFT SHIFT ..... nitro",
                 "SPACE .......... drift (hold while steering at speed)",
                 "C .............. camera: chase / hood / cockpit",
                 "P / ESC ........ pause    M ... mute    F2 ... performance mode", "",
                 "Drifting fills your nitro tank, and a long drift gives a free boost",
                 "when you let go. Tuck in behind a car for a slipstream. Leaving the",
                 "road, clipping scenery or ramming traffic costs speed AND damages the car.",
                 "Finish top 3 to unlock the next track. Prize money buys upgrades."]
        for i, l in enumerate(lines):
            self.text(l, HALF_W, 120 + i * 38, (225, 228, 240), self.assets.f_small, "c")
        self.text("Esc: back", HALF_W, H - 40, (180, 190, 210), self.assets.f_small, "c")

    def draw_pause(self):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 10, 160))
        self.screen.blit(ov, (0, 0))
        self.text("PAUSED", HALF_W, 220, (255, 230, 120), self.assets.f_title, "c")
        self.text("Enter / P: resume        Q: quit to menu", HALF_W, 330, (230, 235, 245), self.assets.f_mid, "c")

    def draw_results(self, dt):
        self.menu_backdrop(self.results["ti"], dt, 190)
        r = self.results
        self.text("FINISH!" if r["rank"] <= 3 else "RACE OVER", HALF_W, 24, (255, 230, 120), self.assets.f_big, "c")
        self.text(f"You placed {ordinal(r['rank'])}", HALF_W, 80, (255, 255, 255), self.assets.f_mid, "c")
        y = 130
        for i, (name, tm, you) in enumerate(r["table"]):
            col = (255, 230, 120) if you else (215, 220, 235)
            self.text(f"{i + 1}. {name:<6}", 330, y, col, self.assets.f_mid)
            self.text(tm, 700, y, col, self.assets.f_mid, "r")
            y += 36
        self.text(f"Prize ${r['prize']}   {'NEW BEST LAP +$200   ' if r['record'] else ''}Best lap {fmt_time(r['best'])}",
                  HALF_W, 360, (170, 235, 170), self.assets.f_mid, "c")
        if r["unlocked"]:
            self.text(f"Unlocked: {TRACKS[r['unlocked']]['name']}!", HALF_W, 400, (255, 200, 90), self.assets.f_mid, "c")
        self.text(f"Top speed {int(r['top'])} km/h   Crashes {r['crashes']}", HALF_W, 440, (190, 196, 220), self.assets.f_small, "c")
        self.text("Enter: next   R: retry   G: garage   Esc: menu", HALF_W, H - 50, (200, 205, 225), self.assets.f_small, "c")

    # ---- flow ----------------------------------------------------------------------------------------
    def start_race(self, ti):
        self.race = Race(self, ti)
        self.race.cam_banner = ("", 0.0)
        self.state = "race"

    def finish_race(self):
        race = self.race
        L = race.track.length
        rk = race.rank_final or race.rank()
        prize = PRIZES[rk - 1]
        key = str(race.ti)
        record = False
        if race.best_lap is not None and (key not in self.save["best"] or race.best_lap < self.save["best"][key]):
            if key in self.save["best"]:
                prize += 200
                record = True
            self.save["best"][key] = race.best_lap
        unlocked = None
        if rk <= 3 and race.ti + 1 < len(TRACKS) and self.save["unlocked"] < race.ti + 2:
            self.save["unlocked"] = race.ti + 2
            unlocked = race.ti + 1
        self.save["money"] += prize
        self.save["races"] += 1
        self.save["wins"] += 1 if rk == 1 else 0
        self.write_save()
        entries = [("YOU", race.finish_t, True)]
        for rv in race.rivals:
            entries.append((rv.name, rv.finish_t if rv.finished else None, False))
        done = sorted([e for e in entries if e[1] is not None], key=lambda e: e[1])
        rest = sorted([e for e in entries if e[1] is None],
                      key=lambda e: -next(r.lap * L + r.z for r in race.rivals if r.name == e[0]))
        table = [(name, fmt_time(tm), you) for name, tm, you in done]
        for name, _, you in rest:
            gap = race.laps * L - next(r.lap * L + r.z for r in race.rivals if r.name == name)
            table.append((name, f"+{gap / MAXSPEED:.1f}s", you))
        self.results = dict(rank=rk, prize=prize, record=record, best=race.best_lap, ti=race.ti, table=table,
                            unlocked=unlocked, top=race.top_speed_seen, crashes=race.crashes)
        self.audio.silence()
        self.state = "results"

    def read_input(self):
        k = pygame.key.get_pressed()
        return dict(thr=k[pygame.K_UP] or k[pygame.K_w], brk=k[pygame.K_DOWN] or k[pygame.K_s],
                    left=k[pygame.K_LEFT] or k[pygame.K_a], right=k[pygame.K_RIGHT] or k[pygame.K_d],
                    nitro=k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT], hand=k[pygame.K_SPACE])

    def on_key(self, key):
        st = self.state
        if key == pygame.K_m:
            self.audio.muted = not self.audio.muted
            if self.audio.muted:
                self.audio.silence()
            return
        if st == "title":
            n = 5
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_i = (self.menu_i - 1) % n
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.menu_i = (self.menu_i + 1) % n
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.menu_i == 0:
                    self.state = "tracks"
                elif self.menu_i == 1:
                    self.state, self.garage_i = "garage", 0
                elif self.menu_i == 2:
                    self.state = "controls"
                elif self.menu_i == 3:
                    self.audio.muted = not self.audio.muted
                    if self.audio.muted:
                        self.audio.silence()
                else:
                    return "quit"
            elif key == pygame.K_ESCAPE:
                return "quit"
        elif st == "tracks":
            if key in (pygame.K_LEFT, pygame.K_a):
                self.track_i = (self.track_i - 1) % len(TRACKS)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.track_i = (self.track_i + 1) % len(TRACKS)
            elif key == pygame.K_RETURN and self.track_i < self.save["unlocked"]:
                self.start_race(self.track_i)
            elif key == pygame.K_g:
                self.state, self.garage_i = "garage", 0
            elif key == pygame.K_ESCAPE:
                self.state = "title"
        elif st == "garage":
            if key in (pygame.K_UP, pygame.K_w):
                self.garage_i = (self.garage_i - 1) % 5
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.garage_i = (self.garage_i + 1) % 5
            elif self.garage_i == 4 and key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                step = -1 if key in (pygame.K_LEFT, pygame.K_a) else 1
                self.save["color"] = (self.save["color"] + step) % len(CAR_COLORS)
                self.write_save()
            elif key == pygame.K_RETURN and self.garage_i < 4:
                k = UPGRADES[self.garage_i][1]
                lvl = self.save["up"][k]
                if lvl >= 5:
                    self.msg = ("Already maxed out.", 1.5)
                elif self.save["money"] < upgrade_cost(lvl):
                    self.msg = ("Not enough cash - go win some races!", 1.8)
                else:
                    self.save["money"] -= upgrade_cost(lvl)
                    self.save["up"][k] += 1
                    self.write_save()
                    self.msg = ("", 0.0)
            elif key == pygame.K_ESCAPE:
                self.state = "title"
        elif st == "controls":
            if key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.state = "title"
        elif st == "race":
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.state = "paused"
                self.audio.silence()
            elif key == pygame.K_F2:
                self.lowq = not self.lowq
                self.race.cam_banner = ("Performance mode " + ("ON" if self.lowq else "OFF"), 1.5)
            elif key == pygame.K_c:
                self.race.cam_mode = (self.race.cam_mode + 1) % 3
                self.race.cam_banner = (CAM_NAMES[self.race.cam_mode], 1.5)
        elif st == "paused":
            if key in (pygame.K_p, pygame.K_RETURN, pygame.K_ESCAPE):
                self.state = "race"
            elif key == pygame.K_q:
                self.audio.stop()
                self.state = "title"
        elif st == "results":
            if key == pygame.K_RETURN:
                self.state = "tracks"
                self.track_i = min(self.results["ti"] + (1 if self.results["rank"] <= 3 else 0), self.save["unlocked"] - 1, len(TRACKS) - 1)
            elif key == pygame.K_r:
                self.start_race(self.results["ti"])
            elif key == pygame.K_g:
                self.state, self.garage_i = "garage", 0
            elif key == pygame.K_ESCAPE:
                self.state = "title"
        return None

    def frame(self, dt):
        st = self.state
        self.turn += dt
        self.msg = (self.msg[0], max(0.0, self.msg[1] - dt))
        if st == "race":
            race = self.race
            inp = self.read_input()
            steps = max(1, int(math.ceil(dt / (1 / 50))))
            for _ in range(steps):
                race.update(dt / steps, inp)
            self.draw_race(race, dt)
            self.dt_avg += (dt - self.dt_avg) * 0.05                       # adaptive quality
            self.slow_t = self.slow_t + dt if self.dt_avg > 0.026 else 0.0
            if self.slow_t > 1.5 and not self.lowq:
                self.lowq = True
                race.cam_banner = ("Performance mode ON (F2 toggles)", 2.5)
            if race.finished and race.t - race.finish_t > 4.5:
                self.finish_race()
        elif st == "paused":
            self.draw_race(self.race, 0.0)
            self.draw_pause()
        elif st == "title":
            self.draw_title(dt)
        elif st == "tracks":
            self.draw_tracks(dt)
        elif st == "garage":
            self.draw_garage(dt)
        elif st == "controls":
            self.draw_controls(dt)
        elif st == "results":
            self.draw_results(dt)
        pygame.display.flip()

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.1)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.KEYDOWN and self.on_key(e.key) == "quit":
                    return
            self.frame(dt)


if __name__ == "__main__":
    try:
        Game().run()
    finally:
        pygame.quit()
        sys.exit()