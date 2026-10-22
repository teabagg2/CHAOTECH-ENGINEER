#!/usr/bin/env python3
"""
DEPTHS OF EMBER - a roguelike in Pygame
=======================================
Descend eight procedurally generated floors, slay the Ember Dragon and claim
the Amulet of Ember.

Run:      pip install pygame
          python ember_depths.py

Features: random dungeon generation, recursive shadowcasting field of view,
A* pathfinding AI (melee, erratic, ranged, regenerating, life-draining and
boss monsters), inventory, equipment, consumables, XP / leveling,
fog-of-war memory, and save / load.

Two views: a first-person 3D raycast view (default) and a top-down map (V).

Controls (3D view)
  Forward / back .. W S  (or Up / Down)
  Strafe .......... A D
  Turn ............ Q E  (or Left / Right),  Z = about-face
  Walk into a monster to attack it.
Controls (top-down view)
  Move ............ Arrow keys / WASD / Numpad, diagonals Q E Z C
Both
  View toggle ..... V
  Wait ............ Space or .
  Pick up ......... G or ,
  Stairs .......... > or Enter
  Inventory ....... I   (letter = use/equip, Tab = toggle drop mode)
  Save / Load ..... F5 / F9
  Quit ............ Esc
"""
import heapq
import math
import os
import pickle
import random
import sys

import pygame

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
MAP_W, MAP_H = 72, 48
TILE = 20
VIEW_W, VIEW_H = 44, 30
LOG_H = 110
SIDE_W = 290
SCREEN_W = VIEW_W * TILE + SIDE_W
SCREEN_H = VIEW_H * TILE + LOG_H
FOV_RADIUS = 9
MAX_DEPTH = 8
PACK_SIZE = 15
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ember_save.pkl")

WALL, FLOOR, STAIRS = 0, 1, 2

# Colors
BG = (10, 10, 14)
WALL_LIT, WALL_DIM = (84, 90, 112), (36, 38, 50)
FLOOR_LIT, FLOOR_DIM = (62, 56, 52), (26, 25, 30)
DOT_LIT, DOT_DIM = (90, 82, 70), (40, 38, 38)
WHITE = (235, 235, 235)
GREY = (150, 150, 160)
RED = (220, 70, 60)
GREEN = (90, 210, 110)
BLUE = (90, 150, 240)
YELLOW = (240, 210, 90)
ORANGE = (240, 140, 50)
PURPLE = (180, 110, 230)
CYAN = (90, 220, 230)

# --------------------------------------------------------------------------
# Data tables
# --------------------------------------------------------------------------
# name: glyph, color, hp, atk, def, xp, first depth, actions/turn, ai
MONSTERS = {
    "rat":      dict(glyph="r", color=(176, 130, 90),  hp=6,  atk=3,  df=0, xp=4,  depth=1, speed=1, ai="melee"),
    "bat":      dict(glyph="b", color=(170, 110, 210), hp=5,  atk=3,  df=0, xp=5,  depth=1, speed=2, ai="erratic"),
    "goblin":   dict(glyph="g", color=(90, 190, 90),   hp=12, atk=5,  df=1, xp=9,  depth=2, speed=1, ai="melee"),
    "archer":   dict(glyph="a", color=(220, 190, 110), hp=10, atk=6,  df=0, xp=12, depth=3, speed=1, ai="ranged"),
    "orc":      dict(glyph="o", color=(70, 150, 70),   hp=22, atk=8,  df=2, xp=18, depth=4, speed=1, ai="melee"),
    "skeleton": dict(glyph="s", color=(220, 220, 210), hp=18, atk=9,  df=3, xp=20, depth=5, speed=1, ai="melee"),
    "troll":    dict(glyph="T", color=(120, 170, 80),  hp=36, atk=11, df=3, xp=32, depth=6, speed=1, ai="regen"),
    "wraith":   dict(glyph="W", color=(130, 150, 240), hp=28, atk=12, df=2, xp=40, depth=7, speed=1, ai="drain"),
}
DRAGON = dict(glyph="D", color=(240, 70, 40), hp=100, atk=17, df=5, xp=500, depth=MAX_DEPTH, speed=1, ai="boss")

# name, attack bonus, first depth
WEAPONS = [("Dagger", 2, 1), ("Short Sword", 4, 2), ("Battle Axe", 6, 3),
           ("Warhammer", 8, 5), ("Runeblade", 11, 7)]
# name, defense bonus, first depth
ARMORS = [("Leather Armor", 1, 1), ("Chainmail", 3, 3),
          ("Plate Armor", 5, 5), ("Dragonscale Mail", 7, 7)]

ITEM_STYLE = {
    "heal": ("!", RED), "might": ("!", ORANGE), "vigor": ("!", GREEN),
    "fireball": ("?", ORANGE), "teleport": ("?", PURPLE), "mapping": ("?", CYAN),
    "weapon": ("/", GREY), "armor": ("[", BLUE), "amulet": ("*", YELLOW),
}

OCTANTS = [(1, 0, 0, 1), (0, 1, 1, 0), (0, -1, 1, 0), (-1, 0, 0, 1),
           (-1, 0, 0, -1), (0, -1, -1, 0), (0, 1, -1, 0), (1, 0, 0, -1)]
FACE = [(0, -1), (1, 0), (0, 1), (-1, 0)]   # N E S W
DIRS8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


# --------------------------------------------------------------------------
# Field of view: recursive shadowcasting
# --------------------------------------------------------------------------
def compute_fov(tiles, ox, oy, radius):
    visible = {(ox, oy)}

    def blocks(x, y):
        return not (0 <= x < MAP_W and 0 <= y < MAP_H) or tiles[y][x] == WALL

    def cast(row, start, end, xx, xy, yx, yy):
        if start < end:
            return
        new_start = start
        r2 = radius * radius
        for j in range(row, radius + 1):
            dx, dy = -j - 1, -j
            blocked = False
            while dx <= 0:
                dx += 1
                X = ox + dx * xx + dy * xy
                Y = oy + dx * yx + dy * yy
                l_slope = (dx - 0.5) / (dy + 0.5)
                r_slope = (dx + 0.5) / (dy - 0.5)
                if start < r_slope:
                    continue
                elif end > l_slope:
                    break
                if dx * dx + dy * dy < r2 and 0 <= X < MAP_W and 0 <= Y < MAP_H:
                    visible.add((X, Y))
                if blocked:
                    if blocks(X, Y):
                        new_start = r_slope
                        continue
                    blocked = False
                    start = new_start
                elif blocks(X, Y) and j < radius:
                    blocked = True
                    cast(j + 1, start, l_slope, xx, xy, yx, yy)
                    new_start = r_slope
            if blocked:
                break

    for xx, xy, yx, yy in OCTANTS:
        cast(1, 1.0, 0.0, xx, xy, yx, yy)
    return visible


# --------------------------------------------------------------------------
# Entities
# --------------------------------------------------------------------------
class Actor:
    def __init__(self, x, y, name, glyph, color, hp, atk, df):
        self.x, self.y = x, y
        self.name, self.glyph, self.color = name, glyph, color
        self.hp = self.max_hp = hp
        self.atk, self.df = atk, df

    @property
    def power(self):
        return self.atk

    @property
    def guard(self):
        return self.df


class Item:
    def __init__(self, kind, name, value=0):
        self.kind, self.name, self.value = kind, name, value

    @property
    def glyph(self):
        return ITEM_STYLE[self.kind][0]

    @property
    def color(self):
        return ITEM_STYLE[self.kind][1]

    def label(self):
        if self.kind == "weapon":
            return f"{self.name} (+{self.value} atk)"
        if self.kind == "armor":
            return f"{self.name} (+{self.value} def)"
        return self.name


class Player(Actor):
    def __init__(self, x, y):
        super().__init__(x, y, "you", "@", (255, 240, 200), 34, 3, 0)
        self.level, self.xp = 1, 0
        self.weapon = self.armor = None
        self.inventory = []
        self.kills = 0
        self.might = 0

    @property
    def xp_next(self):
        return 20 * self.level

    @property
    def power(self):
        return self.atk + self.level + self.might + (self.weapon.value if self.weapon else 0)

    @property
    def guard(self):
        return self.df + self.level // 3 + (self.armor.value if self.armor else 0)


class Monster(Actor):
    def __init__(self, x, y, name, t):
        super().__init__(x, y, name, t["glyph"], t["color"], t["hp"], t["atk"], t["df"])
        self.xp, self.speed, self.ai = t["xp"], t["speed"], t["ai"]
        self.last_seen = None


# --------------------------------------------------------------------------
# The world / game logic (no pygame objects, so it pickles cleanly)
# --------------------------------------------------------------------------
class World:
    def __init__(self):
        self.messages = []
        self.depth = 0
        self.turn = 0
        self.state = "play"          # play | dead | won
        self.player = Player(0, 0)
        self.log("You descend into the Depths of Ember. Find the Amulet on floor 8.", YELLOW)
        self.player.weapon = Item("weapon", "Rusty Dagger", 1)
        self.player.inventory.append(Item("heal", "Healing Potion", 18))
        self.new_level(1)

    # ---- utilities -------------------------------------------------------
    def log(self, text, color=WHITE):
        self.messages.append((text, color))
        del self.messages[:-120]

    def in_bounds(self, x, y):
        return 0 <= x < MAP_W and 0 <= y < MAP_H

    def walkable(self, x, y):
        return self.in_bounds(x, y) and self.tiles[y][x] != WALL

    def monster_at(self, x, y):
        for m in self.monsters:
            if m.x == x and m.y == y:
                return m
        return None

    def items_at(self, x, y):
        return [i for i in self.floor_items if (i[0], i[1]) == (x, y)]

    # ---- level generation ------------------------------------------------
    def new_level(self, depth):
        self.depth = depth
        tiles = [[WALL] * MAP_W for _ in range(MAP_H)]
        rooms = []
        for _ in range(300):
            w, h = random.randint(5, 11), random.randint(4, 8)
            x, y = random.randint(1, MAP_W - w - 2), random.randint(1, MAP_H - h - 2)
            if any(x - 1 < rx + rw and x + w + 1 > rx and y - 1 < ry + rh and y + h + 1 > ry
                   for rx, ry, rw, rh in rooms):
                continue
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    tiles[yy][xx] = FLOOR
            if rooms:
                self._tunnel(tiles, self._center(rooms[-1]), (x + w // 2, y + h // 2))
            rooms.append((x, y, w, h))
            if len(rooms) >= 13:
                break
        for _ in range(3):  # extra loops so the level is not a single chain
            a, b = random.sample(rooms, 2)
            self._tunnel(tiles, self._center(a), self._center(b))

        self.tiles, self.rooms = tiles, rooms
        self.explored = [[False] * MAP_W for _ in range(MAP_H)]
        self.monsters, self.floor_items = [], []

        p = self.player
        p.x, p.y = self._center(rooms[0])
        sx, sy = self._center(rooms[-1])
        if depth < MAX_DEPTH:
            tiles[sy][sx] = STAIRS
        else:
            self.monsters.append(Monster(sx, sy, "Ember Dragon", DRAGON))
        self._populate()
        self.update_fov()

    @staticmethod
    def _center(room):
        x, y, w, h = room
        return x + w // 2, y + h // 2

    @staticmethod
    def _tunnel(tiles, a, b):
        (x1, y1), (x2, y2) = a, b
        if random.random() < 0.5:
            corners = [(x2, y1)]
        else:
            corners = [(x1, y2)]
        pts = [(x1, y1), corners[0], (x2, y2)]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            step_x = (bx > ax) - (bx < ax)
            step_y = (by > ay) - (by < ay)
            x, y = ax, ay
            while (x, y) != (bx, by):
                tiles[y][x] = tiles[y][x] or FLOOR
                x, y = x + step_x, y + step_y
            tiles[by][bx] = tiles[by][bx] or FLOOR

    def _free_spot(self, room, avoid=None, min_dist=0):
        for _ in range(40):
            x = random.randint(room[0], room[0] + room[2] - 1)
            y = random.randint(room[1], room[1] + room[3] - 1)
            if self.tiles[y][x] != FLOOR or self.monster_at(x, y):
                continue
            if (x, y) == (self.player.x, self.player.y):
                continue
            if avoid and max(abs(x - avoid[0]), abs(y - avoid[1])) < min_dist:
                continue
            return x, y
        return None

    def _populate(self):
        d = self.depth
        pool = [(n, t) for n, t in MONSTERS.items() if t["depth"] <= d]
        weights = [max(1, 4 - (d - t["depth"])) for _, t in pool]
        count = 4 + d + random.randint(0, 3)
        for _ in range(count):
            room = random.choice(self.rooms[1:])
            spot = self._free_spot(room, (self.player.x, self.player.y), 7)
            if spot:
                name, t = random.choices(pool, weights)[0]
                self.monsters.append(Monster(spot[0], spot[1], name, t))

        def drop(item):
            spot = self._free_spot(random.choice(self.rooms))
            if spot:
                self.floor_items.append((spot[0], spot[1], item))

        drop(Item("heal", "Healing Potion", 18 + 2 * d))   # guaranteed each floor
        for _ in range(random.randint(3, 5)):
            drop(self._random_item())

    def _random_item(self):
        d = self.depth
        kind = random.choices(
            ["heal", "might", "vigor", "fireball", "teleport", "mapping", "weapon", "armor"],
            [22, 5, 6, 14, 9, 9, 10, 10])[0]
        if kind == "heal":
            return Item("heal", "Healing Potion", 16 + 2 * d)
        if kind == "might":
            return Item("might", "Potion of Might", 1)
        if kind == "vigor":
            return Item("vigor", "Potion of Vigor", 6)
        if kind == "fireball":
            return Item("fireball", "Scroll of Fireball", 12 + 3 * d)
        if kind == "teleport":
            return Item("teleport", "Scroll of Teleport")
        if kind == "mapping":
            return Item("mapping", "Scroll of Mapping")
        table = WEAPONS if kind == "weapon" else ARMORS
        opts = [t for t in table if t[2] <= d + 1]
        name, val, _ = random.choice(opts[-3:])
        return Item(kind, name, val)

    # ---- field of view ---------------------------------------------------
    def update_fov(self):
        self.visible = compute_fov(self.tiles, self.player.x, self.player.y, FOV_RADIUS)
        for x, y in self.visible:
            self.explored[y][x] = True

    # ---- player actions --------------------------------------------------
    def player_move(self, dx, dy):
        """Returns True if a turn was consumed."""
        if self.state != "play":
            return False
        p = self.player
        nx, ny = p.x + dx, p.y + dy
        target = self.monster_at(nx, ny)
        if target:
            self.attack(p, target)
        elif self.walkable(nx, ny):
            p.x, p.y = nx, ny
            self.update_fov()
            self.pickup()
        else:
            return False
        self.end_turn()
        return True

    def wait(self):
        if self.state == "play":
            self.end_turn()

    def pickup(self):
        p = self.player
        for entry in self.items_at(p.x, p.y):
            item = entry[2]
            if item.kind == "amulet":
                self.floor_items.remove(entry)
                self.state = "won"
                self.log("You seize the Amulet of Ember. YOU WIN!", YELLOW)
            elif len(p.inventory) >= PACK_SIZE:
                self.log(f"Your pack is full - can't take {item.name}.", GREY)
            else:
                self.floor_items.remove(entry)
                p.inventory.append(item)
                self.log(f"You pick up the {item.label()}.", CYAN)

    def descend(self):
        p = self.player
        if self.state == "play" and self.tiles[p.y][p.x] == STAIRS:
            self.log(f"You descend to floor {self.depth + 1}.", YELLOW)
            self.new_level(self.depth + 1)
            return True
        self.log("There are no stairs here.", GREY)
        return False

    def use_item(self, idx):
        p = self.player
        if not (0 <= idx < len(p.inventory)) or self.state != "play":
            return False
        item = p.inventory[idx]
        used = True
        if item.kind == "heal":
            healed = min(item.value, p.max_hp - p.hp)
            if healed <= 0:
                self.log("You are already at full health.", GREY)
                return False
            p.hp += healed
            self.log(f"You drink the potion and recover {healed} HP.", GREEN)
        elif item.kind == "might":
            p.might += item.value
            self.log("Power surges through your arms! (+1 attack)", ORANGE)
        elif item.kind == "vigor":
            p.max_hp += item.value
            p.hp += item.value
            self.log(f"You feel hardier. (+{item.value} max HP)", GREEN)
        elif item.kind == "fireball":
            used = self._fireball(item)
        elif item.kind == "teleport":
            used = self._teleport()
        elif item.kind == "mapping":
            for y in range(MAP_H):
                for x in range(MAP_W):
                    if self.tiles[y][x] != WALL or any(
                            self.walkable(x + dx, y + dy) for dx, dy in DIRS8):
                        self.explored[y][x] = True
            self.log("The layout of the floor burns into your mind.", CYAN)
        elif item.kind in ("weapon", "armor"):
            slot = "weapon" if item.kind == "weapon" else "armor"
            old = getattr(p, slot)
            setattr(p, slot, item)
            p.inventory.pop(idx)
            if old and old.name != "Rusty Dagger":
                p.inventory.append(old)
            self.log(f"You equip the {item.label()}.", BLUE)
            self.end_turn()
            return True
        if used:
            p.inventory.pop(idx)
            self.end_turn()
        return used

    def drop_item(self, idx):
        p = self.player
        if 0 <= idx < len(p.inventory):
            item = p.inventory.pop(idx)
            self.floor_items.append((p.x, p.y, item))
            self.log(f"You drop the {item.label()}.", GREY)
            self.end_turn()
            return True
        return False

    def _fireball(self, item):
        p = self.player
        seen = [m for m in self.monsters if (m.x, m.y) in self.visible]
        if not seen:
            self.log("There is nothing to target.", GREY)
            return False
        tgt = min(seen, key=lambda m: max(abs(m.x - p.x), abs(m.y - p.y)))
        self.log(f"A fireball explodes around the {tgt.name}!", ORANGE)
        for m in list(self.monsters):
            if max(abs(m.x - tgt.x), abs(m.y - tgt.y)) <= 2:
                m.hp -= item.value
                self.log(f"The {m.name} burns for {item.value}.", ORANGE)
                if m.hp <= 0:
                    self.kill(m)
        return True

    def _teleport(self):
        for _ in range(100):
            room = random.choice(self.rooms)
            spot = self._free_spot(room)
            if spot:
                self.player.x, self.player.y = spot
                self.update_fov()
                self.log("The world lurches - you are elsewhere.", PURPLE)
                return True
        return False

    # ---- combat ----------------------------------------------------------
    def attack(self, a, d, ranged=False):
        is_player = a is self.player
        who = "You" if is_player else f"The {a.name}"
        target = "you" if d is self.player else f"the {d.name}"
        if random.random() > (0.75 if ranged else 0.9):
            self.log(f"{who} miss{'' if is_player else 'es'} {target}.", GREY)
            return
        guard = d.guard // 2 if ranged else d.guard
        dmg = max(1, random.randint(a.power - 1, a.power + 2) - guard)
        crit = random.random() < 0.08
        if crit:
            dmg *= 2
        d.hp -= dmg
        verb = "shoots" if ranged else "hits"
        if is_player:
            verb = "hit"
        color = YELLOW if (is_player and crit) else (RED if d is self.player else WHITE)
        self.log(f"{who} {verb} {target} for {dmg}{' (CRITICAL!)' if crit else ''}.", color)
        if getattr(a, "ai", "") == "drain":
            a.hp = min(a.max_hp, a.hp + dmg // 2)
        if d.hp <= 0:
            if d is self.player:
                self.state = "dead"
                self.log(f"You were slain by the {a.name}. Press R to try again.", RED)
            else:
                self.kill(d)

    def kill(self, m):
        if m not in self.monsters:
            return
        self.monsters.remove(m)
        p = self.player
        p.kills += 1
        self.log(f"The {m.name} dies. (+{m.xp} XP)", GREEN)
        p.xp += m.xp
        while p.xp >= p.xp_next:
            p.xp -= p.xp_next
            p.level += 1
            p.max_hp += 7
            p.hp = min(p.max_hp, p.hp + 7 + p.max_hp // 4)
            self.log(f"*** You reach level {p.level}! ***", YELLOW)
        if m.ai == "boss":
            self.floor_items.append((m.x, m.y, Item("amulet", "Amulet of Ember")))
            self.log("The dragon collapses. The Amulet of Ember glints where it fell!", YELLOW)
        elif random.random() < 0.12:
            self.floor_items.append((m.x, m.y, self._random_item()))

    # ---- turn processing -------------------------------------------------
    def end_turn(self):
        if self.state != "play":
            return
        self.turn += 1
        p = self.player
        if self.turn % 8 == 0 and p.hp < p.max_hp:
            p.hp += 1
        for m in list(self.monsters):
            if m not in self.monsters:
                continue
            if m.ai == "regen" and m.hp < m.max_hp:
                m.hp += 1
            for _ in range(m.speed):
                if self.state != "play" or m.hp <= 0:
                    break
                self._monster_act(m)

    def _monster_act(self, m):
        p = self.player
        dx, dy = p.x - m.x, p.y - m.y
        dist = max(abs(dx), abs(dy))
        sees = (m.x, m.y) in self.visible and dist <= FOV_RADIUS
        if sees:
            m.last_seen = (p.x, p.y)

        if sees and m.ai == "boss" and 2 <= dist <= 7 and random.random() < 0.3:
            dmg = max(3, random.randint(9, 14) - p.guard // 2)
            p.hp -= dmg
            self.log(f"The Ember Dragon breathes fire! You take {dmg}.", ORANGE)
            if p.hp <= 0:
                self.state = "dead"
                self.log("You were burned to ash. Press R to try again.", RED)
            return
        if sees and m.ai == "ranged" and 2 <= dist <= 7:
            self.attack(m, p, ranged=True)
            return
        if dist == 1:
            self.attack(m, p)
            return
        if m.ai == "erratic" and random.random() < 0.4:
            self._step_random(m)
            return
        if m.last_seen:
            step = self._astar((m.x, m.y), m.last_seen, m)
            if step:
                m.x, m.y = step
            if (m.x, m.y) == m.last_seen and not sees:
                m.last_seen = None
            elif not step:
                m.last_seen = None
        elif random.random() < 0.3:
            self._step_random(m)

    def _step_random(self, m):
        dx, dy = random.choice(DIRS8)
        nx, ny = m.x + dx, m.y + dy
        if self.walkable(nx, ny) and not self.monster_at(nx, ny) \
                and (nx, ny) != (self.player.x, self.player.y):
            m.x, m.y = nx, ny

    def _astar(self, start, goal, mover, limit=700):
        occupied = {(o.x, o.y) for o in self.monsters if o is not mover}
        occupied.add((self.player.x, self.player.y))
        occupied.discard(goal)
        h = lambda a: max(abs(a[0] - goal[0]), abs(a[1] - goal[1]))
        openq = [(h(start), 0, start)]
        came, cost = {start: None}, {start: 0}
        while openq and limit > 0:
            limit -= 1
            _, g, cur = heapq.heappop(openq)
            if cur == goal:
                while came[cur] is not None and came[cur] != start:
                    cur = came[cur]
                return cur if cur != start else None
            for dx, dy in DIRS8:
                nxt = (cur[0] + dx, cur[1] + dy)
                if not self.walkable(*nxt) or nxt in occupied:
                    continue
                ng = g + 1
                if ng < cost.get(nxt, 1 << 30):
                    cost[nxt] = ng
                    came[nxt] = cur
                    heapq.heappush(openq, (ng + h(nxt), ng, nxt))
        return None


# --------------------------------------------------------------------------
# Rendering and input
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Depths of Ember")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        names = "dejavusansmono,consolas,menlo,couriernew,monospace"
        self.font = pygame.font.SysFont(names, TILE - 2, bold=True)
        self.small = pygame.font.SysFont(names, 14)
        self.mid = pygame.font.SysFont(names, 17, bold=True)
        self.big = pygame.font.SysFont(names, 44, bold=True)
        self.glyph_cache = {}
        self.world = World()
        self.show_inv = False
        self.drop_mode = False
        pygame.key.set_repeat(220, 70)
        self.init3d()

    # -- helpers
    def glyph(self, ch, color):
        key = (ch, color)
        if key not in self.glyph_cache:
            self.glyph_cache[key] = self.font.render(ch, True, color)
        return self.glyph_cache[key]

    def text(self, s, x, y, color=WHITE, font=None):
        surf = (font or self.small).render(s, True, color)
        self.screen.blit(surf, (x, y))
        return surf.get_height()

    def bar(self, x, y, w, h, frac, color, label=""):
        pygame.draw.rect(self.screen, (40, 40, 48), (x, y, w, h))
        pygame.draw.rect(self.screen, color, (x, y, int(w * max(0, min(1, frac))), h))
        if label:
            self.text(label, x + 4, y, WHITE)

    def save(self):
        with open(SAVE_FILE, "wb") as f:
            pickle.dump(self.world, f)
        self.world.log("Game saved.", GREY)

    def load(self):
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, "rb") as f:
                self.world = pickle.load(f)
            self.world.log("Game loaded.", GREY)
        else:
            self.world.log("No save file found.", GREY)

    # -- drawing
    def draw(self):
        w = self.world
        self.screen.fill(BG)
        if self.view3d:
            self.draw3d()
        else:
            self.draw_topdown()
        self.draw_sidebar()
        self.draw_log()
        if self.show_inv:
            self.draw_inventory()
        if w.state != "play":
            self.draw_end()
        pygame.display.flip()

    def draw_topdown(self):
        w = self.world
        p = w.player
        cx = max(0, min(MAP_W - VIEW_W, p.x - VIEW_W // 2))
        cy = max(0, min(MAP_H - VIEW_H, p.y - VIEW_H // 2))

        for vy in range(VIEW_H):
            for vx in range(VIEW_W):
                mx, my = cx + vx, cy + vy
                if not w.explored[my][mx]:
                    continue
                lit = (mx, my) in w.visible
                rect = (vx * TILE, vy * TILE, TILE, TILE)
                t = w.tiles[my][mx]
                if t == WALL:
                    pygame.draw.rect(self.screen, WALL_LIT if lit else WALL_DIM, rect)
                    pygame.draw.rect(self.screen, BG, rect, 1)
                else:
                    pygame.draw.rect(self.screen, FLOOR_LIT if lit else FLOOR_DIM, rect)
                    if t == STAIRS:
                        g = self.glyph(">", YELLOW if lit else (110, 100, 50))
                        self.screen.blit(g, g.get_rect(center=(rect[0] + TILE // 2, rect[1] + TILE // 2)))
                    else:
                        pygame.draw.circle(self.screen, DOT_LIT if lit else DOT_DIM,
                                           (rect[0] + TILE // 2, rect[1] + TILE // 2), 1)

        def put(x, y, ch, color):
            if cx <= x < cx + VIEW_W and cy <= y < cy + VIEW_H:
                g = self.glyph(ch, color)
                self.screen.blit(g, g.get_rect(center=((x - cx) * TILE + TILE // 2,
                                                       (y - cy) * TILE + TILE // 2)))

        for x, y, item in w.floor_items:
            if (x, y) in w.visible:
                put(x, y, item.glyph, item.color)
        for m in w.monsters:
            if (m.x, m.y) in w.visible:
                put(m.x, m.y, m.glyph, m.color)
                if m.hp < m.max_hp:
                    bx, by = (m.x - cx) * TILE, (m.y - cy) * TILE + TILE - 3
                    pygame.draw.rect(self.screen, (60, 0, 0), (bx + 1, by, TILE - 2, 2))
                    pygame.draw.rect(self.screen, RED, (bx + 1, by, int((TILE - 2) * m.hp / m.max_hp), 2))
        put(p.x, p.y, "@", p.color if w.state == "play" else RED)

    def draw_sidebar(self):
        w, p = self.world, self.world.player
        x0 = VIEW_W * TILE
        pygame.draw.rect(self.screen, (18, 18, 26), (x0, 0, SIDE_W, SCREEN_H))
        pygame.draw.line(self.screen, (60, 60, 80), (x0, 0), (x0, SCREEN_H))
        x, y = x0 + 12, 10
        y += self.text("DEPTHS OF EMBER", x, y, ORANGE, self.mid) + 4
        y += self.text(f"Floor {w.depth} / {MAX_DEPTH}     Turn {w.turn}", x, y, GREY) + 8
        self.bar(x, y, SIDE_W - 24, 16, p.hp / p.max_hp, (170, 40, 40), f"HP {p.hp}/{p.max_hp}")
        y += 22
        self.bar(x, y, SIDE_W - 24, 16, p.xp / p.xp_next, (60, 90, 190), f"LV {p.level}  XP {p.xp}/{p.xp_next}")
        y += 28
        y += self.text(f"Attack {p.power}    Defense {p.guard}    Kills {p.kills}", x, y) + 6
        y += self.text(f"Weapon: {p.weapon.label() if p.weapon else '-'}", x, y, GREY) + 2
        y += self.text(f"Armor:  {p.armor.label() if p.armor else '-'}", x, y, GREY) + 10
        y += self.text("IN SIGHT", x, y, ORANGE) + 2
        seen = sorted((m for m in w.monsters if (m.x, m.y) in w.visible),
                      key=lambda m: max(abs(m.x - p.x), abs(m.y - p.y)))
        for m in seen[:7]:
            y += self.text(f" {m.glyph} {m.name} {m.hp}/{m.max_hp}", x, y, m.color) + 1
        if not seen:
            y += self.text(" nothing", x, y, (90, 90, 100))
        y = SCREEN_H - 150
        if self.view3d:
            lines = ["Move W/S   Strafe A/D", "Turn Q/E or Left/Right",
                     "Z about-face   V: 2D map", "Wait Space    Pickup G",
                     "Stairs > / Enter  Pack I", "Save F5  Load F9  Quit Esc"]
        else:
            lines = ["Move WASD/arrows  diag QEZC", "Wait Space    Pickup G",
                     "Stairs > / Enter  Pack I", "V: first-person 3D view",
                     "Save F5  Load F9  Quit Esc"]
        for line in lines:
            y += self.text(line, x, y, (110, 110, 130)) + 3

    def draw_log(self):
        y0 = VIEW_H * TILE
        pygame.draw.rect(self.screen, (14, 14, 20), (0, y0, VIEW_W * TILE, LOG_H))
        pygame.draw.line(self.screen, (60, 60, 80), (0, y0), (VIEW_W * TILE, y0))
        for i, (msg, color) in enumerate(self.world.messages[-6:]):
            fade = 0.45 + 0.55 * (i + 1) / min(6, len(self.world.messages))
            c = tuple(int(v * fade) for v in color)
            self.text(msg, 10, y0 + 6 + i * 17, c)

    def draw_inventory(self):
        p = self.world.player
        w, h = 520, 60 + PACK_SIZE * 22
        x, y = (VIEW_W * TILE - w) // 2, 30
        pygame.draw.rect(self.screen, (20, 20, 30), (x, y, w, h))
        pygame.draw.rect(self.screen, ORANGE if self.drop_mode else (110, 110, 150), (x, y, w, h), 2)
        title = "DROP which item?  (Tab: back to use)" if self.drop_mode else "INVENTORY - letter to use/equip (Tab: drop mode, I/Esc: close)"
        self.text(title, x + 14, y + 10, ORANGE if self.drop_mode else WHITE)
        for i in range(PACK_SIZE):
            yy = y + 42 + i * 22
            letter = chr(ord("a") + i)
            if i < len(p.inventory):
                it = p.inventory[i]
                self.text(f"{letter})", x + 16, yy, YELLOW, self.mid)
                self.text(f"{it.glyph} {it.label()}", x + 54, yy + 1, it.color, self.mid)
            else:
                self.text(f"{letter})", x + 16, yy, (60, 60, 70), self.mid)

    def draw_end(self):
        w = self.world
        overlay = pygame.Surface((VIEW_W * TILE, VIEW_H * TILE), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        won = w.state == "won"
        title = "VICTORY" if won else "YOU DIED"
        surf = self.big.render(title, True, YELLOW if won else RED)
        cx = VIEW_W * TILE // 2
        self.screen.blit(surf, surf.get_rect(center=(cx, 220)))
        p = w.player
        score = w.depth * 100 + p.kills * 10 + p.level * 50 + (1000 if won else 0)
        for i, s in enumerate([f"Floor {w.depth}   Level {p.level}   Kills {p.kills}",
                               f"Score: {score}", "Press R for a new run, Esc to quit"]):
            r = self.mid.render(s, True, WHITE)
            self.screen.blit(r, r.get_rect(center=(cx, 290 + i * 30)))

    # ------------------------------------------------------------------
    # First-person 3D view (raycasting)
    # ------------------------------------------------------------------
    COLW = 2

    def init3d(self):
        self.VW, self.VH = VIEW_W * TILE, VIEW_H * TILE
        self.cols = self.VW // self.COLW
        self.vp = pygame.Surface((self.VW, self.VH))
        self.tex = self.make_texture()
        self.bg = self.make_background()
        self.vignette = self.make_vignette()
        self.sprites = {}
        self.view3d = True
        self.facing = 1
        self.cam_x = self.cam_y = 0.5
        self.cam_a = 0.0
        self.t = self.walk = self.swing = self.flash = 0.0
        self.prev_hp = self.world.player.hp
        self.level_key = None
        self.stairs = []

    def make_texture(self):
        rnd = random.Random(7)
        t = pygame.Surface((64, 64))
        t.fill((34, 34, 42))
        tone = {(r, k): rnd.randint(92, 134) for r in range(8) for k in range(4)}
        for row in range(8):
            y0, off = row * 8, (0 if row % 2 == 0 else 8)
            for bx in range(-1, 4):
                if off == 0 and bx < 0:
                    continue
                b = tone[(row, bx % 4)]
                x0 = bx * 16 + off
                pygame.draw.rect(t, (b, b - 4, b + 12), (x0 + 1, y0 + 1, 14, 6))
                pygame.draw.line(t, (min(255, b + 28), min(255, b + 24), min(255, b + 44)),
                                 (x0 + 1, y0 + 1), (x0 + 14, y0 + 1))
                pygame.draw.line(t, (b - 30, b - 32, b - 14), (x0 + 1, y0 + 6), (x0 + 14, y0 + 6))
        for _ in range(420):
            x, y = rnd.randrange(64), rnd.randrange(64)
            r, g, b, _a = t.get_at((x, y))
            d = rnd.randint(-14, 14)
            t.set_at((x, y), (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d))))
        return t

    def make_background(self):
        s = pygame.Surface((self.VW, self.VH))
        h = self.VH // 2
        for y in range(self.VH):
            if y < h:
                t = y / h
                col = (int(4 + 26 * t), int(4 + 20 * t), int(8 + 26 * t))
            else:
                t = (y - h) / (self.VH - h)
                col = (int(12 + 60 * t), int(10 + 48 * t), int(10 + 40 * t))
            pygame.draw.line(s, col, (0, y), (self.VW, y))
        return s

    def make_vignette(self):
        sm = pygame.Surface((48, 32), pygame.SRCALPHA)
        for y in range(32):
            for x in range(48):
                d = min(1.0, math.hypot((x - 23.5) / 24, (y - 15.5) / 16) / 1.15)
                sm.set_at((x, y), (0, 0, 0, min(255, int(215 * max(0.0, d - 0.38) / 0.62))))
        return pygame.transform.smoothscale(sm, (self.VW, self.VH))

    # ---- per-frame state --------------------------------------------------
    def sync_level(self, key):
        w, p = self.world, self.world.player
        self.level_key = key
        best, bf = -1, 1
        for f, (dx, dy) in enumerate(FACE):
            x, y, d = p.x, p.y, 0
            while w.walkable(x + dx, y + dy) and d < 40:
                x, y, d = x + dx, y + dy, d + 1
            if d > best:
                best, bf = d, f
        self.facing = bf
        self.cam_x, self.cam_y = p.x + 0.5, p.y + 0.5
        self.cam_a = (bf - 1) * math.pi / 2
        self.prev_hp = p.hp
        self.stairs = [(x, y) for y in range(MAP_H) for x in range(MAP_W)
                       if w.tiles[y][x] == STAIRS]

    def update(self, dt):
        dt = min(dt, 0.1)
        w, p = self.world, self.world.player
        key = (id(w), w.depth)
        if key != self.level_key:
            self.sync_level(key)
        self.t += dt
        tx, ty = p.x + 0.5, p.y + 0.5
        if max(abs(tx - self.cam_x), abs(ty - self.cam_y)) > 2.5:      # teleport / new level
            self.cam_x, self.cam_y = tx, ty
        k = min(1.0, dt * 14)
        if math.hypot(tx - self.cam_x, ty - self.cam_y) > 0.03:
            self.walk += dt * 11
        self.cam_x += (tx - self.cam_x) * k
        self.cam_y += (ty - self.cam_y) * k
        ta = (self.facing - 1) * math.pi / 2
        diff = (ta - self.cam_a + math.pi) % (2 * math.pi) - math.pi
        self.cam_a += diff * k
        self.swing = max(0.0, self.swing - dt * 3.5)
        if p.hp < self.prev_hp:
            self.flash = 1.0
        self.prev_hp = p.hp
        self.flash = max(0.0, self.flash - dt * 2.5)

    # ---- sprites ----------------------------------------------------------
    @staticmethod
    def glow(s, pos, r, color):
        for i in range(6):
            pygame.draw.circle(s, (*color, 14 + i * 9), pos, max(2, r - i * 4))

    def sprite_surface(self, key, ent):
        if key not in self.sprites:
            s = pygame.Surface((64, 64), pygame.SRCALPHA)
            if key[0] == "m":
                self.paint_monster(s, ent)
            elif key[0] == "i":
                self.paint_item(s, ent)
            else:
                self.paint_stairs(s)
            self.sprites[key] = s
        return self.sprites[key]

    def paint_monster(self, s, m):
        d, c, n = pygame.draw, m.color, m.name
        dk = tuple(int(v * 0.5) for v in c)
        lt = tuple(min(255, int(v * 1.3) + 25) for v in c)
        eye = (255, 70, 40)
        if n == "bat":
            d.polygon(s, dk, [(32, 26), (1, 6), (9, 34), (21, 30)])
            d.polygon(s, dk, [(32, 26), (63, 6), (55, 34), (43, 30)])
            d.ellipse(s, c, (22, 18, 20, 28))
            d.polygon(s, c, [(24, 22), (22, 8), (30, 20)])
            d.polygon(s, c, [(40, 22), (42, 8), (34, 20)])
            for ex in (28, 36):
                d.circle(s, (255, 230, 80), (ex, 30), 3)
            d.polygon(s, (240, 240, 240), [(29, 40), (31, 46), (32, 40)])
        elif n == "rat":
            d.line(s, dk, (10, 52), (0, 40), 3)
            d.ellipse(s, c, (6, 34, 40, 24))
            d.polygon(s, lt, [(40, 38), (62, 50), (40, 58)])
            d.circle(s, lt, (22, 36), 6)
            d.circle(s, (255, 150, 150), (54, 51), 3)
            d.circle(s, eye, (46, 44), 3)
            for lx in (14, 34):
                d.rect(s, dk, (lx, 54, 5, 8))
        elif n == "wraith":
            d.polygon(s, (*dk, 230), [(32, 2), (12, 22), (4, 62), (18, 52), (32, 62), (46, 52), (60, 62), (52, 22)])
            d.circle(s, (10, 10, 20), (32, 20), 11)
            for ex in (27, 37):
                d.circle(s, (160, 220, 255), (ex, 20), 3)
            d.polygon(s, c, [(14, 34), (2, 52), (14, 46)])
            d.polygon(s, c, [(50, 34), (62, 52), (50, 46)])
        elif n == "Ember Dragon":
            d.polygon(s, dk, [(30, 24), (0, 4), (6, 40), (24, 40)])
            d.polygon(s, dk, [(34, 24), (64, 4), (58, 40), (40, 40)])
            d.ellipse(s, c, (14, 22, 36, 38))
            d.ellipse(s, lt, (22, 36, 20, 22))
            d.rect(s, dk, (16, 54, 10, 10))
            d.rect(s, dk, (38, 54, 10, 10))
            d.ellipse(s, c, (18, 4, 28, 24))
            d.polygon(s, (230, 220, 180), [(20, 8), (12, 0), (26, 6)])
            d.polygon(s, (230, 220, 180), [(44, 8), (52, 0), (38, 6)])
            for ex in (25, 39):
                d.circle(s, (255, 220, 40), (ex, 14), 3)
            d.polygon(s, (255, 150, 40), [(26, 24), (32, 32), (38, 24)])
        else:                                   # humanoid family
            wide = 4 if n in ("troll", "orc") else 0
            d.rect(s, dk, (22 - wide // 2, 44, 8, 19))
            d.rect(s, dk, (34 + wide // 2, 44, 8, 19))
            d.rect(s, c, (17 - wide, 22, 30 + 2 * wide, 26))
            d.rect(s, dk, (17 - wide, 22, 30 + 2 * wide, 26), 2)
            d.rect(s, c, (9 - wide, 24, 8, 22))
            d.rect(s, c, (47 + wide, 24, 8, 22))
            d.circle(s, lt, (32, 14), 11)
            d.circle(s, dk, (32, 14), 11, 2)
            for ex in (27, 37):
                d.circle(s, eye, (ex, 13), 2)
            if n == "goblin":
                d.polygon(s, lt, [(21, 12), (9, 6), (22, 18)])
                d.polygon(s, lt, [(43, 12), (55, 6), (42, 18)])
            elif n == "orc":
                d.polygon(s, (240, 240, 220), [(28, 21), (26, 28), (31, 22)])
                d.polygon(s, (240, 240, 220), [(36, 21), (38, 28), (33, 22)])
            elif n == "troll":
                d.rect(s, dk, (24, 5, 16, 4))
                d.ellipse(s, lt, (26, 18, 12, 6))
            elif n == "skeleton":
                for ry in (26, 32, 38):
                    d.line(s, dk, (20, ry), (44, ry), 2)
                d.circle(s, (30, 30, 30), (27, 13), 3)
                d.circle(s, (30, 30, 30), (37, 13), 3)
                d.circle(s, eye, (27, 13), 1)
                d.circle(s, eye, (37, 13), 1)
            elif n == "archer":
                d.arc(s, (150, 100, 50), (46, 8, 16, 48), -1.4, 1.4, 3)
                d.line(s, (220, 220, 200), (56, 10), (56, 54), 1)

    def paint_item(self, s, it):
        d, c, k = pygame.draw, it.color, it.kind
        self.glow(s, (32, 46), 26, c)
        if k in ("heal", "might", "vigor"):
            d.rect(s, (110, 80, 50), (28, 26, 8, 8))
            d.rect(s, (200, 220, 230), (27, 32, 10, 6))
            d.ellipse(s, c, (18, 36, 28, 26))
            d.ellipse(s, (255, 255, 255), (24, 40, 7, 9))
        elif k in ("fireball", "teleport", "mapping"):
            d.rect(s, (225, 205, 160), (16, 38, 32, 20))
            d.ellipse(s, (190, 165, 115), (11, 36, 10, 24))
            d.ellipse(s, (190, 165, 115), (43, 36, 10, 24))
            d.circle(s, c, (32, 48), 6)
        elif k == "weapon":
            d.polygon(s, (205, 210, 225), [(50, 8), (54, 12), (24, 48), (18, 42)])
            d.line(s, (255, 255, 255), (50, 10), (20, 44), 1)
            d.line(s, (200, 160, 60), (12, 38), (28, 54), 4)
            d.line(s, (110, 70, 40), (16, 50), (8, 58), 4)
        elif k == "armor":
            d.polygon(s, c, [(18, 26), (46, 26), (54, 36), (45, 42), (45, 60), (19, 60), (19, 42), (10, 36)])
            d.polygon(s, tuple(min(255, v + 50) for v in c), [(26, 28), (38, 28), (38, 44), (26, 44)])
            d.rect(s, (30, 40, 70), (18, 26, 28, 34), 2)
        else:                                   # amulet
            d.arc(s, (210, 180, 70), (12, 10, 40, 40), 3.3, 6.1, 2)
            d.polygon(s, (255, 220, 60), [(32, 36), (42, 48), (32, 62), (22, 48)])
            d.polygon(s, (255, 255, 200), [(32, 40), (37, 48), (32, 56)])

    def paint_stairs(self, s):
        d = pygame.draw
        self.glow(s, (32, 36), 30, (255, 200, 80))
        d.rect(s, (30, 22, 8), (8, 4, 48, 60), border_radius=14)
        d.rect(s, (255, 205, 90), (8, 4, 48, 60), 4, border_radius=14)
        for i in range(3):
            y = 18 + i * 12
            d.polygon(s, (255, 225, 120), [(18, y), (32, y + 8), (46, y), (46, y + 4), (32, y + 12), (18, y + 4)])

    # ---- the frame ---------------------------------------------------------
    def draw3d(self):
        w, p, vp = self.world, self.world.player, self.vp
        W, H = self.VW, self.VH
        cols, colw = self.cols, self.COLW
        vp.blit(self.bg, (0, 0))
        a = self.cam_a
        dirx, diry = math.cos(a), math.sin(a)
        plx, ply = -diry * 0.66, dirx * 0.66
        px, py = self.cam_x, self.cam_y
        flick = 1.0 + 0.05 * math.sin(self.t * 9) + 0.03 * math.sin(self.t * 23.7)
        lg = max(0.5, 0.86 - 0.045 * w.depth)
        lb = max(0.3, 0.68 - 0.05 * w.depth)
        reach = FOV_RADIUS + 1.5
        tiles, tex = w.tiles, self.tex
        zbuf = [99.0] * cols
        BM = pygame.BLEND_RGB_MULT

        # --- walls
        for c in range(cols):
            camx = 2.0 * c / cols - 1.0
            rdx, rdy = dirx + plx * camx, diry + ply * camx
            mx, my = int(px), int(py)
            ddx = abs(1.0 / rdx) if rdx else 1e30
            ddy = abs(1.0 / rdy) if rdy else 1e30
            if rdx < 0:
                stx, sdx = -1, (px - mx) * ddx
            else:
                stx, sdx = 1, (mx + 1.0 - px) * ddx
            if rdy < 0:
                sty, sdy = -1, (py - my) * ddy
            else:
                sty, sdy = 1, (my + 1.0 - py) * ddy
            side, hit = 0, False
            for _ in range(16):
                if sdx < sdy:
                    sdx += ddx
                    mx += stx
                    side = 0
                else:
                    sdy += ddy
                    my += sty
                    side = 1
                if not (0 <= mx < MAP_W and 0 <= my < MAP_H) or tiles[my][mx] == WALL:
                    hit = True
                    break
            if not hit:
                continue
            dist = max(0.05, (sdx - ddx) if side == 0 else (sdy - ddy))
            zbuf[c] = dist
            sh = 1.0 - dist / reach
            if sh <= 0:
                continue
            wallx = (py + dist * rdy) if side == 0 else (px + dist * rdx)
            wallx -= math.floor(wallx)
            tx = int(wallx * 64)
            if (side == 0 and rdx > 0) or (side == 1 and rdy < 0):
                tx = 63 - tx
            lineh = int(H / dist)
            if lineh > H:
                crop = max(1, int(64 * H / lineh))
                strip = tex.subsurface((tx, (64 - crop) // 2, 1, crop))
                h, y0 = H, 0
            else:
                strip = tex.subsurface((tx, 0, 1, 64))
                h, y0 = max(1, lineh), (H - lineh) // 2
            x0 = c * colw
            vp.blit(pygame.transform.scale(strip, (colw, h)), (x0, y0))
            var = 0.86 + 0.14 * (((mx * 73856093) ^ (my * 19349663)) % 100) / 100.0
            sh = min(1.0, (sh ** 1.3) * flick * var * 1.15) * (0.72 if side else 1.0)
            vp.fill((int(255 * sh), int(255 * sh * lg), int(255 * sh * lb)), (x0, y0, colw, h), BM)

        # --- sprites (monsters, items, stairs), far to near
        invdet = 1.0 / (plx * diry - dirx * ply)
        todo = []

        def add(x, y, surf, hfac, lift, ent):
            sx, sy = x + 0.5 - px, y + 0.5 - py
            tx = invdet * (diry * sx - dirx * sy)
            ty = invdet * (-ply * sx + plx * sy)
            if ty > 0.25:
                todo.append((ty, tx, surf, hfac, lift, ent))

        for x, y in self.stairs:
            if w.explored[y][x]:
                add(x, y, self.sprite_surface(("s",), None), 1.0, 0.0, None)
        for x, y, it in w.floor_items:
            if (x, y) in w.visible:
                add(x, y, self.sprite_surface(("i", it.kind), it), 0.38, 0.0, None)
        for m in w.monsters:
            if (m.x, m.y) in w.visible:
                big = 1.35 if m.ai == "boss" else (0.95 if m.name == "troll" else 0.8)
                lift = 0.28 if m.name == "bat" else 0.0
                add(m.x, m.y, self.sprite_surface(("m", m.name), m), big, lift, m)
        todo.sort(key=lambda e: -e[0])
        for ty, tx, surf, hfac, lift, ent in todo:
            size = int(H / ty * hfac)
            if size < 3 or size > 1500:
                continue
            bottom = H / 2 + H / (2 * ty) - lift * size
            top = int(bottom - size)
            x0 = int(W / 2 * (1 + tx / ty)) - size // 2
            if x0 + size < 0 or x0 > W:
                continue
            sp = pygame.transform.scale(surf, (size, size))
            sh = min(1.0, max(0.25, max(0.0, 1.0 - ty / reach) ** 1.1 * flick * 1.15))
            sp.fill((int(255 * sh), int(255 * sh * lg), int(255 * sh * lb), 255), special_flags=BM)
            for sx in range(max(0, x0), min(W, x0 + size), colw):
                if ty < zbuf[sx // colw] + 0.02:
                    vp.blit(sp, (sx, top), area=(sx - x0, 0, colw, size))
            if isinstance(ent, Monster) and ent.hp < ent.max_hp:
                cxm = x0 + size // 2
                if 0 <= cxm < W and ty < zbuf[cxm // colw] + 0.02:
                    bw = max(16, int(size * 0.6))
                    pygame.draw.rect(vp, (70, 0, 0), (cxm - bw // 2, top - 8, bw, 5))
                    pygame.draw.rect(vp, RED, (cxm - bw // 2, top - 8, int(bw * ent.hp / ent.max_hp), 5))

        vp.blit(self.vignette, (0, 0))
        self.draw_weapon(vp)
        self.draw_minimap(vp)
        name = ["North", "East", "South", "West"][self.facing]
        label = self.small.render(f"Facing {name}", True, GREY)
        vp.blit(label, (10, 8))
        if self.flash > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((200, 0, 0, int(140 * self.flash)))
            vp.blit(ov, (0, 0))
        shx = int(random.uniform(-1, 1) * 7 * self.flash)
        shy = int(random.uniform(-1, 1) * 7 * self.flash)
        self.screen.blit(vp, (shx, shy))

    def draw_weapon(self, vp):
        w = self.world
        W, H = self.VW, self.VH
        wp = w.player.weapon.value if w.player.weapon else 0
        steel = [(150, 150, 160), (150, 150, 160), (165, 185, 225), (165, 185, 225), (190, 205, 245),
                 (190, 205, 245), (210, 190, 120), (210, 190, 120), (225, 150, 100), (225, 150, 100),
                 (110, 230, 255), (110, 230, 255), (110, 230, 255)][min(wp, 12)]
        bob = math.sin(self.walk) * 5
        bobx = math.cos(self.walk * 0.5) * 7
        sw = math.sin(self.swing * math.pi) if self.swing > 0 else 0.0
        bx = W * 0.76 + bobx - sw * 150
        by = H + 40 + abs(bob) - sw * 110
        ang = math.radians(-64 - sw * 50)
        dx, dy = math.cos(ang), math.sin(ang)
        nx, ny = -dy, dx
        L = 330
        tip = (bx + dx * L, by + dy * L)
        bw = 20
        d = pygame.draw
        d.polygon(vp, tuple(int(v * 0.55) for v in steel),
                  [(bx + nx * bw, by + ny * bw), (bx - nx * bw, by - ny * bw), tip])
        d.polygon(vp, steel, [(bx + nx * bw * 0.2, by + ny * bw * 0.2),
                              (bx - nx * bw, by - ny * bw), tip])
        d.line(vp, (255, 255, 255), (bx, by), tip, 2)
        gx, gy = bx - dx * 4, by - dy * 4
        d.line(vp, (200, 160, 60), (gx + nx * 46, gy + ny * 46), (gx - nx * 46, gy - ny * 46), 12)
        d.line(vp, (96, 60, 36), (gx, gy), (gx - dx * 110, gy - dy * 110), 16)

    def draw_minimap(self, vp):
        w, p = self.world, self.world.player
        R, ts = 15, 4
        size = (2 * R + 1) * ts
        ox, oy = self.VW - size - 10, 10
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        surf.fill((8, 8, 14, 175))
        for ty in range(-R, R + 1):
            y = p.y + ty
            if not 0 <= y < MAP_H:
                continue
            for tx in range(-R, R + 1):
                x = p.x + tx
                if 0 <= x < MAP_W and w.explored[y][x]:
                    t = w.tiles[y][x]
                    col = (66, 72, 96) if t == WALL else ((255, 210, 80) if t == STAIRS else (56, 52, 50))
                    pygame.draw.rect(surf, col, ((tx + R) * ts, (ty + R) * ts, ts, ts))
        for m in w.monsters:
            if (m.x, m.y) in w.visible and abs(m.x - p.x) <= R and abs(m.y - p.y) <= R:
                pygame.draw.rect(surf, RED, ((m.x - p.x + R) * ts, (m.y - p.y + R) * ts, ts, ts))
        c = R * ts + ts // 2
        fx, fy = FACE[self.facing]
        pts = [(c + fx * 7, c + fy * 7), (c - fy * 4 - fx * 3, c + fx * 4 - fy * 3),
               (c + fy * 4 - fx * 3, c - fx * 4 - fy * 3)]
        pygame.draw.polygon(surf, YELLOW, pts)
        vp.blit(surf, (ox, oy))
        pygame.draw.rect(vp, (90, 90, 120), (ox, oy, size, size), 1)

    # -- input
    MOVES = {
        pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_KP8: (0, -1),
        pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1), pygame.K_KP2: (0, 1),
        pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_KP4: (-1, 0),
        pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0), pygame.K_KP6: (1, 0),
        pygame.K_q: (-1, -1), pygame.K_KP7: (-1, -1),
        pygame.K_e: (1, -1), pygame.K_KP9: (1, -1),
        pygame.K_z: (-1, 1), pygame.K_KP1: (-1, 1),
        pygame.K_c: (1, 1), pygame.K_KP3: (1, 1),
    }

    def handle_key(self, event):
        w = self.world
        k = event.key
        if k == pygame.K_F5:
            self.save()
            return
        if k == pygame.K_F9:
            self.load()
            return
        if w.state != "play":
            if k == pygame.K_r:
                self.world = World()
                self.show_inv = False
            elif k == pygame.K_ESCAPE:
                return "quit"
            return
        if self.show_inv:
            if k in (pygame.K_ESCAPE, pygame.K_i):
                self.show_inv = False
            elif k == pygame.K_TAB:
                self.drop_mode = not self.drop_mode
            elif pygame.K_a <= k <= pygame.K_z:
                idx = k - pygame.K_a
                done = w.drop_item(idx) if self.drop_mode else w.use_item(idx)
                if done:
                    self.show_inv = False
                    self.drop_mode = False
            return
        if k == pygame.K_ESCAPE:
            return "quit"
        if k == pygame.K_i:
            self.show_inv, self.drop_mode = True, False
        elif k == pygame.K_v:
            self.view3d = not self.view3d
        elif self.view3d and k in (pygame.K_q, pygame.K_LEFT):
            self.facing = (self.facing - 1) % 4
        elif self.view3d and k in (pygame.K_e, pygame.K_RIGHT):
            self.facing = (self.facing + 1) % 4
        elif self.view3d and k == pygame.K_z:
            self.facing = (self.facing + 2) % 4
        elif self.view3d and k in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN,
                                   pygame.K_a, pygame.K_d):
            fx, fy = FACE[self.facing]
            rx, ry = -fy, fx
            vec = {pygame.K_w: (fx, fy), pygame.K_UP: (fx, fy),
                   pygame.K_s: (-fx, -fy), pygame.K_DOWN: (-fx, -fy),
                   pygame.K_a: (-rx, -ry), pygame.K_d: (rx, ry)}[k]
            if w.monster_at(w.player.x + vec[0], w.player.y + vec[1]):
                self.swing = 1.0
            w.player_move(*vec)
        elif not self.view3d and k in self.MOVES:
            w.player_move(*self.MOVES[k])
        elif k in (pygame.K_SPACE, pygame.K_PERIOD, pygame.K_KP5):
            w.wait()
        elif k in (pygame.K_g, pygame.K_COMMA):
            w.pickup()
        elif k == pygame.K_RETURN or getattr(event, "unicode", "") == ">":
            w.descend()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and self.handle_key(event) == "quit":
                    return
            self.update(self.clock.tick(30) / 1000.0)
            self.draw()


if __name__ == "__main__":
    try:
        Game().run()
    finally:
        pygame.quit()
        sys.exit()
        