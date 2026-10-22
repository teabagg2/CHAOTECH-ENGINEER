#!/usr/bin/env python3
"""
REDLINE HORIZON - a pseudo-3D arcade racer in Pygame
====================================================
Race rivals and traffic across four hand-tuned, procedurally built tracks.
Hills, curves, a 6-speed gearbox with a tachometer, drifting, nitro, lap
timing, race positions, prize money, a garage with upgrades, rain / snow,
night driving, synthesized engine sound and a track minimap.

Run:      pip install pygame
          python redline_horizon.py

Controls
  Accelerate ..... Up / W            Brake ........... Down / S
  Steer .......... Left / Right or A / D
  Nitro .......... Left Shift         Drift ........... Space (while steering)
  Pause .......... P or Esc           Mute ............ M
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
SPRITE_W = {"palm": 0.85, "pine": 0.75, "cactus": 0.45, "rock": 0.65, "bush": 0.55,
            "lamp": 0.14, "building": 2.0, "neon": 1.2, "ad": 1.1,
            "chev_l": 0.35, "chev_r": 0.35, "gantry": 2.6}
NON_SOLID = {"gantry"}
CAR_W = {"sports": 0.28, "sedan": 0.28, "van": 0.30, "truck": 0.36}


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
    __slots__ = ("idx", "y1", "y2", "curve", "flag", "sprites", "cars",
                 "sx1", "sy1", "sw1", "ss1", "sx2", "sy2", "sw2", "ss2", "clip", "fog", "ok")

    def __init__(self, idx, y1, y2, curve):
        self.idx, self.y1, self.y2, self.curve = idx, y1, y2, curve
        self.flag = (idx // RUMBLE) % 2
        self.sprites, self.cars = [], []
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

        self.spr_cache[key] = out
        return out

    # ---- cars (rear view) ---------------------------------------------------
    def car(self, kind, color, brake=False, boost=False):
        k = (kind, color, brake, boost)
        if k in self.car_cache:
            return self.car_cache[k]
        d = pygame.draw
        w = 160
        h = {"sports": 84, "sedan": 94, "van": 124, "truck": 142}[kind]
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        dark, light = shade(color, 0.55), shade(color, 1.25)
        d.ellipse(s, (0, 0, 0, 120), (4, h - 18, w - 8, 16))
        for wx in (8, w - 34):
            d.rect(s, (18, 18, 22), (wx, h - 40, 26, 34), border_radius=6)
            d.rect(s, (48, 48, 56), (wx + 4, h - 38, 18, 6), border_radius=3)
        tail_on = (255, 70, 70) if brake else (170, 24, 24)
        if kind in ("sports", "sedan"):
            d.polygon(s, color, [(10, h - 20), (w - 10, h - 20), (w - 3, h - 44), (w - 14, h - 56), (14, h - 56), (3, h - 44)])
            d.polygon(s, dark, [(10, h - 20), (w - 10, h - 20), (w - 6, h - 30), (6, h - 30)])
            ch = 24 if kind == "sports" else 32
            d.polygon(s, dark, [(34, h - 56), (w - 34, h - 56), (w - 46, h - 56 - ch), (46, h - 56 - ch)])
            d.polygon(s, (36, 56, 88), [(42, h - 58), (w - 42, h - 58), (w - 52, h - 54 - ch), (52, h - 54 - ch)])
            d.line(s, light, (14, h - 56), (w - 14, h - 56), 2)
            if kind == "sports":
                d.rect(s, dark, (12, h - 70, w - 24, 8), border_radius=3)
                d.rect(s, shade(color, 0.4), (30, h - 62, 8, 10))
                d.rect(s, shade(color, 0.4), (w - 38, h - 62, 8, 10))
        elif kind == "van":
            d.rect(s, color, (12, 6, w - 24, h - 28), border_radius=10)
            d.rect(s, dark, (12, h - 40, w - 24, 18))
            d.rect(s, (36, 56, 88), (28, 16, w - 56, 26), border_radius=4)
            d.line(s, dark, (w // 2, 46), (w // 2, h - 40), 2)
        else:
            d.rect(s, (210, 212, 220), (8, 4, w - 16, h - 34), border_radius=6)
            d.rect(s, (160, 162, 172), (8, 4, w - 16, h - 34), 3, border_radius=6)
            d.line(s, (150, 152, 164), (w // 2, 8), (w // 2, h - 34), 2)
            d.rect(s, color, (8, h - 36, w - 16, 14))
        ty = h - 46 if kind in ("sports", "sedan") else h - 36
        for tx in (12, w - 46):
            d.rect(s, tail_on, (tx, ty, 34, 10), border_radius=3)
            if brake:
                d.rect(s, (255, 170, 170), (tx + 4, ty + 2, 26, 3))
        d.rect(s, (236, 236, 236), (w // 2 - 18, ty + 6, 36, 13))
        d.rect(s, (30, 30, 80), (w // 2 - 14, ty + 10, 28, 3))
        for ex in (w // 2 - 36, w // 2 + 24):
            d.circle(s, (60, 60, 68), (ex + 6, h - 12), 6)
            d.circle(s, (20, 20, 24), (ex + 6, h - 12), 3)
        if boost:
            for ex in (w // 2 - 30, w // 2 + 30):
                fl = random.randint(14, 24)
                d.polygon(s, (255, 150, 40), [(ex - 7, h - 14), (ex + 7, h - 14), (ex, h - 14 + fl)])
                d.polygon(s, (120, 190, 255), [(ex - 3, h - 14), (ex + 3, h - 14), (ex, h - 14 + fl * 0.6)])
        self.car_cache[k] = s
        if boost:
            self.car_cache.pop(k, None)
        return s


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
            pygame.mixer.set_num_channels(10)
            self.eng = [self._tone_loop(f) for f in (48, 80, 130, 200)]
            self.skid = self._noise_loop(0.22, 6500)
            self.wind = self._noise_loop(0.06, 9000)
            self.sfx = {"crash": self._crash(), "boost": self._sweep(), "beep": self._beep(660, 0.18),
                        "go": self._beep(1040, 0.45), "lap": self._beep(880, 0.3)}
            self.ch = [pygame.mixer.Channel(i) for i in range(10)]
            self.started = False
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
        for i, snd in enumerate(self.eng):
            self.ch[i].play(snd, loops=-1)
            self.ch[i].set_volume(0)
        self.ch[4].play(self.skid, loops=-1)
        self.ch[4].set_volume(0)
        self.ch[5].play(self.wind, loops=-1)
        self.ch[5].set_volume(0)
        self.started = True

    def silence(self):
        if self.ok and self.started:
            for i in range(6):
                self.ch[i].set_volume(0)

    def stop(self):
        if self.ok:
            pygame.mixer.stop()
            self.started = False

    def update(self, rpm_frac, throttle, speed_pct, skid, boosting):
        if not self.ok or not self.started:
            return
        m = 0.0 if self.muted else 1.0
        load = 0.35 + 0.65 * throttle
        for i in range(4):
            v = max(0.0, 1.0 - abs(rpm_frac - i / 3.0) * 2.6)
            self.ch[i].set_volume(min(1.0, v * load * 0.42 * m))
        self.ch[4].set_volume(min(1.0, skid * 0.35 * m))
        self.ch[5].set_volume(min(1.0, (speed_pct ** 2) * (0.5 + 0.4 * boosting) * m))

    def play(self, name):
        if self.ok and not self.muted:
            self.ch[6 + (hash(name) % 4)].play(self.sfx[name])


# --------------------------------------------------------------------------
# Race simulation
# --------------------------------------------------------------------------
class Car:
    __slots__ = ("z", "offset", "speed", "w", "kind", "color", "rival", "top", "name", "lap",
                 "seg", "percent", "finished", "finish_t", "brake", "progress")

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
            c = Car(z, (-0.45 if col == 0 else 0.45), 0.0, "sports", palette[i % len(palette)],
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
        # weather particles
        wth = tr.theme["weather"]
        if wth:
            n = 140 if wth == "rain" else 90
            self.weather = [[rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.7, 1.3)] for _ in range(n)]
        g = self.g
        g.audio.start()

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

    def all_racers(self):
        return [("YOU", self.progress, True)] + [(r.name, r.lap * self.track.length + r.z, False) for r in self.rivals]

    def rank(self):
        order = sorted(self.all_racers(), key=lambda r: -r[1])
        return [i for i, r in enumerate(order) if r[2]][0] + 1

    # ---- player -----------------------------------------------------------
    def step_player(self, dt, inp):
        up, L = self.up, self.track.length
        seg = self.seg_at(self.pos + PLAYERZ)
        racing = self.state == "racing"
        top0 = self.top0
        sp = self.speed / top0
        self.brake_on = bool(inp["brk"])
        self.throttle = 1.0 if (inp["thr"] and racing) else 0.0

        wants_boost = inp["nitro"] and self.nitro > 0 and self.speed > top0 * 0.2 and racing
        if wants_boost:
            self.nitro = max(0.0, self.nitro - dt * 30)
        if self.boost_t > 0:
            self.boost_t -= dt
        self.boosting = bool(wants_boost or self.boost_t > 0)
        top = top0 * (1.28 if self.boosting else 1.0)

        # steering + drift
        target = (1 if inp["right"] else 0) - (1 if inp["left"] else 0)
        self.steer += (target - self.steer) * min(1.0, dt * (9 if target else 12))
        was_drift = self.drifting
        self.drifting = bool(inp["hand"] and sp > 0.35 and abs(self.steer) > 0.2 and racing)
        dx = dt * 2 * clamp(self.speed / MAXSPEED, 0, 1.3) * (1 + 0.07 * up["tires"])
        self.px += self.steer * dx * (1.3 if self.drifting else 1.0)
        cf = CENTRIF * (1 - 0.06 * up["tires"]) * (1.35 if self.drifting else 1.0)
        self.px -= dx * (self.speed / MAXSPEED) * seg.curve * cf
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
            self.gear = gear
        self.shift_t = max(0.0, self.shift_t - dt)
        lo, hi = GEAR_LO[gear - 1], GEAR_HI[gear - 1]
        r = clamp((sp - lo) / (hi - lo), 0, 1)
        target_rpm = 1300 + r * 6200 + (400 if self.throttle else 0)
        if self.shift_t > 0:
            target_rpm -= 1800
        self.rpm += (target_rpm - self.rpm) * min(1.0, dt * 11)
        tq = 1.0 - 0.4 * abs(r - 0.7)
        acc = (MAXSPEED / 3.0) * GEAR_MUL[gear - 1] * tq * max(0.0, 1 - sp ** 2) * (1 + 0.08 * up["engine"])
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
            self.dust(dt, (120, 100, 80) if self.track.theme["bg"] != "alpine" else (240, 240, 250))
        if self.speed > top:
            self.speed = max(top, self.speed - MAXSPEED * 0.5 * dt)
        self.speed = clamp(self.speed, 0.0, MAXSPEED * 1.5)

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
        if self.drifting and self.speed > 0:
            self.smoke(dt)
        self.g.audio.update(clamp((self.rpm - 1000) / 6800, 0, 1), self.throttle, clamp(sp, 0, 1.3),
                            1.0 if self.drifting else (0.5 if abs(self.px) > 1 and self.speed > MAXSPEED * 0.2 else 0.0),
                            1.0 if self.boosting else 0.0)

    def crash(self, impact, severity):
        if self.crash_cd > 0:
            return
        self.crash_cd = 0.5
        self.crashes += 1
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
            self.px += ((0.0) - self.px) * 0
            return
        if self.finished:
            inp = self.autopilot(brake_after=True)
        self.step_player(dt, inp)
        self.update_cars(dt)
        # lap tracking (handles wrapping forwards and being pushed backwards over the line)
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
                    self.banner = (f"LAP {self.lap + 1}/{self.laps}   {fmt_time(lt)}", 2.4)
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
        # look for slow traffic ahead in our lane
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
        self.sb = pygame.Surface((W, H), pygame.SRCALPHA)

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
            sh = font.render(str(s), True, (0, 0, 0))
            self.screen.blit(sh, r.move(2, 2))
        self.screen.blit(img, r)
        return r

    def arc(self, cx, cy, r, a0, a1, color, width):
        n = max(2, int(abs(a1 - a0) / 4))
        pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        pygame.draw.lines(self.screen, color, False, pts, width)

    # ---- the world ------------------------------------------------------------
    def blit_sprite(self, img, wfrac, x, y, scale, anchor, clip, fogt, fade=True):
        dw = wfrac * ROADW * scale * HALF_W
        if dw < 2 or dw > W * 2.2:
            return
        dh = dw * img.get_height() / img.get_width()
        dx, dy = x + dw * anchor, y - dh
        if dx > W or dx + dw < 0:
            return
        if dy + dh - clip >= dh:
            return
        sp = pygame.transform.scale(img, (max(1, int(dw)), max(1, int(dh))))
        if fade and fogt > 0.06:
            sp.set_alpha(int(255 * (1 - fogt * 0.92)))
        if clip < H:
            self.screen.set_clip((0, 0, W, max(0, int(clip))))
        self.screen.blit(sp, (int(dx), int(dy)))
        if clip < H:
            self.screen.set_clip(None)

    def draw_world(self, tr, pos, px, bg_off, ox=0, oy=0, cars=True):
        scr = self.screen
        th, segs = tr.theme, tr.segs
        N, L = len(segs), tr.length
        fogc = th["fog"]
        sky, layers = self.assets.background(tr.spec["theme"])
        scr.blit(sky, (0, 0))
        for img, y, fac in layers:
            w2 = img.get_width()
            x = -int((bg_off * fac) % w2)
            scr.blit(img, (x, y))
            if x + w2 < W:
                scr.blit(img, (x + w2, y))
        scr.fill(fogc, (0, HALF_H + 10 + oy, W, H))
        base = segs[int(pos // SEGL) % N]
        base_pct = (pos % SEGL) / SEGL
        pseg = segs[int((pos + PLAYERZ) // SEGL) % N]
        ppct = ((pos + PLAYERZ) % SEGL) / SEGL
        cam_y = lerp(pseg.y1, pseg.y2, ppct) + CAMH
        camx = px * ROADW
        hx, hy = HALF_W + ox, HALF_H + oy
        x = 0.0
        dx = -(base.curve * base_pct)
        maxy = H
        poly = pygame.draw.polygon
        lanes_w = ROADW * 2 / LANES
        for n in range(DRAW):
            seg = segs[(base.idx + n) % N]
            looped = seg.idx < base.idx
            camz = pos - (L if looped else 0.0)
            z1 = seg.idx * SEGL - camz
            z2 = z1 + SEGL
            seg.clip = maxy
            t = 1.0 - 1.0 / math.exp((n / DRAW) ** 2 * FOGD)
            seg.fog = t
            cx1, cx2 = x - camx, x + dx - camx
            cy1, cy2 = seg.y1 - cam_y, seg.y2 - cam_y
            seg.ok = z1 > CAMD
            if z1 > CAMD:
                s1 = CAMD / z1
                seg.ss1 = s1
                seg.sx1 = hx + s1 * cx1 * HALF_W
                seg.sy1 = hy - s1 * cy1 * HALF_H
                seg.sw1 = s1 * ROADW * HALF_W
            x += dx
            dx += seg.curve
            if z1 <= CAMD or z2 <= CAMD:
                continue
            s2 = CAMD / z2
            seg.ss2 = s2
            seg.sx2 = hx + s2 * cx2 * HALF_W
            seg.sy2 = hy - s2 * cy2 * HALF_H
            seg.sw2 = s2 * ROADW * HALF_W
            y1, y2 = seg.sy1, seg.sy2
            if y2 >= y1 or y2 >= maxy:
                continue
            x1, x2, w1, w2 = seg.sx1, seg.sx2, seg.sw1, seg.sw2
            f = seg.flag
            if f < 2:
                road, grass, rum = th["road"][f], th["grass"][f], th["rumble"][f]
                lane = th["lane"] if f == 0 else None
            elif f == 2:
                road, grass, rum, lane = (236, 236, 236), th["grass"][0], th["rumble"][0], None
            else:
                road, grass, rum, lane = (22, 22, 26), th["grass"][1], th["rumble"][1], None
            if t > 0.002:
                road, grass, rum = mix(road, fogc, t), mix(grass, fogc, t), mix(rum, fogc, t)
                if lane:
                    lane = mix(lane, fogc, t)
            scr.fill(grass, (0, int(y2), W, int(y1 - y2) + 1))
            r1, r2 = w1 / max(6, 2 * LANES), w2 / max(6, 2 * LANES)
            poly(scr, rum, [(x1 - w1 - r1, y1), (x1 - w1, y1), (x2 - w2, y2), (x2 - w2 - r2, y2)])
            poly(scr, rum, [(x1 + w1 + r1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 + w2 + r2, y2)])
            poly(scr, road, [(x1 - w1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 - w2, y2)])
            if lane:
                l1, l2 = w1 / max(32, 8 * LANES), w2 / max(32, 8 * LANES)
                lw1, lw2 = w1 * 2 / LANES, w2 * 2 / LANES
                lx1, lx2 = x1 - w1 + lw1, x2 - w2 + lw2
                for _ in range(1, LANES):
                    poly(scr, lane, [(lx1 - l1 / 2, y1), (lx1 + l1 / 2, y1), (lx2 + l2 / 2, y2), (lx2 - l2 / 2, y2)])
                    lx1 += lw1
                    lx2 += lw2
            maxy = y1
        # sprites + cars, far to near
        sprites = self.assets.sprites(tr.spec["theme"])
        emissive = ("lamp", "neon")
        for n in range(DRAW - 1, 0, -1):
            seg = segs[(base.idx + n) % N]
            if not seg.ok:
                continue
            clip = seg.clip
            if cars:
                for car in seg.cars:
                    sc = lerp(seg.ss1, seg.ss2, car.percent) if seg.ss2 else seg.ss1
                    cxp = lerp(seg.sx1, seg.sx2, car.percent) + sc * car.offset * ROADW * HALF_W
                    cyp = lerp(seg.sy1, seg.sy2, car.percent)
                    img = self.assets.car(car.kind, car.color, car.brake)
                    self.blit_sprite(img, car.w, cxp, cyp, sc, -0.5, clip, seg.fog)
            for key, off, anchor in seg.sprites:
                sc = seg.ss1
                self.blit_sprite(sprites[key], SPRITE_W[key], seg.sx1 + sc * off * ROADW * HALF_W, seg.sy1, sc,
                                 anchor, clip, seg.fog, fade=key not in emissive)

    def draw_player_car(self, race, t):
        sp = clamp(race.speed / MAXSPEED, 0, 1.3)
        img = self.assets.car("sports", CAR_COLORS[self.save["color"]], race.brake_on, race.boosting)
        dw = int(PLAYER_W * ROADW * (CAMD / PLAYERZ) * HALF_W)
        dh = int(dw * img.get_height() / img.get_width())
        sc = pygame.transform.scale(img, (dw, dh))
        ang = -race.steer * 4.0 * (0.4 + sp) - (race.steer * 7 if race.drifting else 0)
        if abs(ang) > 0.3:
            sc = pygame.transform.rotate(sc, ang)
        bob = math.sin(t * 38) * sp * 1.6 + (race.shake * math.sin(t * 90) * 6)
        r = sc.get_rect(midbottom=(HALF_W + (race.steer * 8 if race.drifting else 0), H - 14 + bob))
        self.screen.blit(sc, r)

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
                a = int(clamp(life * 1.6, 0, 1) * 110)
                s = int(size * (1.3 - life))
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
        sb = self.sb
        if wth == "rain":
            sb.fill((0, 0, 0, 0))
            for d in race.weather:
                d[1] += 900 * d[2] * dt
                d[0] -= 120 * dt * sp
                if d[1] > H:
                    d[1], d[0] = -20, random.uniform(0, W + 150)
                if d[0] < 0:
                    d[0] += W
                pygame.draw.line(sb, (190, 205, 235, 120), (d[0], d[1]), (d[0] - 5, d[1] - 18 * d[2]), 1)
            self.screen.blit(sb, (0, 0))
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
        # tachometer / speedo
        cx, cy, r = W - 120, H - 112, 92
        pygame.draw.circle(scr, (8, 8, 14), (cx, cy), r + 14)
        pygame.draw.circle(scr, (60, 62, 80), (cx, cy), r + 14, 2)
        self.arc(cx, cy, r, 135, 405, (50, 52, 66), 10)
        frac = clamp(race.rpm / 8000, 0, 1)
        n = int(frac * 54)
        for i in range(n):
            a = 135 + 270 * i / 54
            col = (70, 220, 120) if i < 38 else ((255, 210, 60) if i < 46 else (255, 60, 50))
            self.arc(cx, cy, r, a, a + 4.2, col, 10)
        for k in range(9):
            a = math.radians(135 + 270 * k / 8)
            p1 = (cx + (r - 18) * math.cos(a), cy + (r - 18) * math.sin(a))
            p2 = (cx + (r - 28) * math.cos(a), cy + (r - 28) * math.sin(a))
            pygame.draw.line(scr, (180, 180, 195) if k < 7 else (255, 90, 80), p1, p2, 2)
        self.text(f"{int(race.kph)}", cx, cy - 30, (255, 255, 255), self.assets.f_big, "c")
        self.text("km/h", cx, cy + 14, (160, 165, 185), self.assets.f_small, "c")
        gcol = (255, 210, 60) if race.shift_t > 0 else (255, 255, 255)
        self.text(f"G{race.gear}", cx, cy + 34, gcol, self.assets.f_mid, "c")
        # nitro bar
        bx, by, bw, bh = 24, H - 44, 260, 18
        pygame.draw.rect(scr, (10, 10, 18), (bx - 3, by - 3, bw + 6, bh + 6), border_radius=6)
        fill = race.nitro / race.cap
        col = (80, 200, 255) if not race.boosting else (255, 190, 80)
        pygame.draw.rect(scr, col, (bx, by, int(bw * fill), bh), border_radius=4)
        self.text("NITRO  [Shift]", bx, by - 24, (160, 200, 230), self.assets.f_small)
        if race.drifting:
            self.text(f"DRIFT {race.drift_t:.1f}s", bx, by - 50, (255, 210, 80), self.assets.f_mid)
        elif race.boost_t > 0:
            self.text("BOOST!", bx, by - 50, (255, 150, 60), self.assets.f_mid)
        # race info
        rk = race.rank()
        self.text(f"{rk}", 24, 14, (255, 220, 90), self.assets.f_huge if False else self.assets.f_big)
        self.text(f"/ 6  {ordinal(rk)}", 64, 28, (230, 230, 240), self.assets.f_mid)
        lap_show = min(race.lap + 1, race.laps)
        self.text(f"LAP {lap_show}/{race.laps}", 24, 66, (255, 255, 255))
        cur = race.t - race.lap_t0 if race.state == "racing" and not race.finished else (race.lap_times[-1] if race.lap_times else 0)
        self.text(f"TIME {fmt_time(max(0, cur))}", 24, 94, (220, 225, 240), self.assets.f_small)
        self.text(f"BEST {fmt_time(race.best_lap or self.save['best'].get(str(race.ti)))}", 24, 114, (170, 220, 170), self.assets.f_small)
        self.draw_minimap(race)
        txt, tm = race.banner
        if tm > 0:
            self.text(txt, HALF_W, 90, (255, 235, 120), self.assets.f_big, "c")
        if race.state == "countdown":
            n = int(math.ceil(race.cd - 0.6))
            self.text("GO!" if n <= 0 else str(n), HALF_W, 130, (255, 80, 70) if n > 0 else (90, 255, 120), self.assets.f_huge, "c")
            self.text("Hold UP to rev. Shift = nitro, Space = drift", HALF_W, 270, (235, 235, 245), self.assets.f_small, "c")
        if abs(race.px) > 1.0 and race.speed > MAXSPEED * 0.3:
            self.text("OFF ROAD", HALF_W, 200, (255, 120, 90), self.assets.f_mid, "c")

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
        jitter = race.shake * 10
        ox = random.uniform(-jitter, jitter)
        oy = random.uniform(-jitter, jitter) * 0.6
        self.draw_world(tr, race.pos, race.px, race.bg_off, ox, oy)
        if tr.theme["night"]:
            self.screen.blit(self.cone, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self.update_particles(race, dt)
        if race.boosting:
            for _ in range(14):
                a = random.uniform(0, math.tau)
                r0, r1 = random.uniform(160, 300), random.uniform(330, 560)
                pygame.draw.line(self.screen, (230, 240, 255), (HALF_W + math.cos(a) * r0, HALF_H + 40 + math.sin(a) * r0 * 0.6),
                                 (HALF_W + math.cos(a) * r1, HALF_H + 40 + math.sin(a) * r1 * 0.6), 1)
        self.draw_player_car(race, race.t)
        self.draw_particles(race)
        self.draw_weather(race, dt)
        self.draw_hud(race)

    # ---- menus ---------------------------------------------------------------------------------
    def menu_backdrop(self, ti, dt, dim=140):
        tr = self.tracks[ti]
        self.demo_t += dt
        self.demo_pos = (self.demo_pos + dt * MAXSPEED * 0.55) % tr.length
        self.draw_world(tr, self.demo_pos, math.sin(self.demo_t * 0.5) * 0.35,
                        self.demo_t * 40, cars=False)
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 10, dim))
        self.screen.blit(ov, (0, 0))

    def draw_title(self, dt):
        self.menu_backdrop(0, dt, 90)
        self.text("REDLINE", HALF_W, 70, (255, 80, 60), self.assets.f_title, "c")
        self.text("HORIZON", HALF_W, 140, (255, 230, 120), self.assets.f_title, "c")
        items = ["Race", "Garage", "How to play", "Sound: " + ("OFF" if self.audio.muted else "ON"), "Quit"]
        for i, it in enumerate(items):
            sel = i == self.menu_i
            self.text(("> " if sel else "  ") + it, HALF_W, 280 + i * 46, (255, 230, 120) if sel else (220, 225, 240),
                      self.assets.f_big if sel else self.assets.f_mid, "c")
        self.text(f"Cash ${self.save['money']}   Races {self.save['races']}   Wins {self.save['wins']}", HALF_W, H - 44,
                  (180, 190, 210), self.assets.f_small, "c")

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
        self.text(f"Difficulty {stars}   Laps {spec['laps']}   Length {tr.length / 1000:.0f}k", HALF_W, 196, (200, 205, 225), self.assets.f_small, "c")
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
        img = self.assets.car("sports", CAR_COLORS[self.save["color"]], False, False)
        big = pygame.transform.scale(img, (330, int(330 * img.get_height() / img.get_width())))
        self.screen.blit(big, big.get_rect(midtop=(250, 150)))
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
                 "SPACE .......... drift (hold while steering at speed)", "P / ESC ........ pause           M ... mute", "",
                 "Drifting fills your nitro tank, and a long drift gives a free boost",
                 "when you release it. Leaving the road or clipping scenery and traffic",
                 "costs you speed. Climb through six gears; shifts cost a moment of power.",
                 "Finish top 3 to unlock the next track. Prize money buys upgrades."]
        for i, l in enumerate(lines):
            self.text(l, HALF_W, 130 + i * 38, (225, 228, 240), self.assets.f_small, "c")
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
        table = []
        for name, tm, you in done:
            table.append((name, fmt_time(tm), you))
        for name, _, you in rest:
            gap = (race.finish_t is not None) and (race.laps * L - next(r.lap * L + r.z for r in race.rivals if r.name == name))
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
        self.msg = (self.msg[0], max(0.0, self.msg[1] - dt))
        if st == "race":
            race = self.race
            inp = self.read_input()
            steps = max(1, int(math.ceil(dt / (1 / 50))))
            for _ in range(steps):
                race.update(dt / steps, inp)
            self.draw_race(race, dt)
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