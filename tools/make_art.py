#!/usr/bin/env python3
"""
Generates every piece of pixel art for Gerald:

  gfx/sprites.png   512x512 atlas  (frog frames, objects, icons, lily pad, font)
  gfx/bg.png        256x512 atlas  (top-day, top-night, bottom-screen wallpaper)
  gfx/*.t3s         tex3ds descriptors
  banner/icon.png   48x48 HOME-menu icon
  banner/banner.png 256x128 HOME-menu banner
  source/atlas.h    cell coordinates shared with the C code

Re-run after tweaking:   python3 tools/make_art.py [--preview out.png]
Needs: Pillow, numpy
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def hexc(s, a=255):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


OUT = hexc('26203a')
WHITE = hexc('ffffff')
DARK = hexc('1c1830')
PINK = hexc('ff8fa3')


# ----------------------------------------------------------------------------
# tiny pixel canvas
# ----------------------------------------------------------------------------
def _c(c):
    return tuple(c) if len(c) == 4 else tuple(c) + (255,)


class Cv:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = _c(c)

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.w, int(x + w)), min(self.h, int(y + h))
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1] = _c(c)

    def ell(self, cx, cy, rx, ry, c):
        rx, ry = max(rx, 0.5), max(ry, 0.5)
        ys, xs = np.mgrid[0:self.h, 0:self.w]
        m = ((xs + .5 - cx) / rx) ** 2 + ((ys + .5 - cy) / ry) ** 2 <= 1.0
        self.a[m] = _c(c)

    def line(self, x0, y0, x1, y1, c, t=1):
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.rect(x0, y0, t, t, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def outline(self, c):
        al = self.a[:, :, 3] > 0
        p = np.pad(al, 1)
        n = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
        self.a[n & ~al] = c

    def over(self, other, x, y):
        over(self.a, other.a if isinstance(other, Cv) else other, x, y)


def over(dst, src, x, y):
    sh, sw = src.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dst.shape[1], x + sw), min(dst.shape[0], y + sh)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    d = dst[y0:y1, x0:x1].astype(np.float32)
    sa, da = s[..., 3:4] / 255.0, d[..., 3:4] / 255.0
    oa = sa + da * (1 - sa)
    rgb = (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    dst[y0:y1, x0:x1] = np.concatenate([rgb, oa * 255], axis=2).round().astype(np.uint8)


def scaled(arr, k):
    return np.repeat(np.repeat(arr, k, axis=0), k, axis=1)


# ----------------------------------------------------------------------------
# 5x7 pixel font (uppercase, digits, a little punctuation)
# ----------------------------------------------------------------------------
FONT = {
    'A': ".###.|#...#|#...#|#####|#...#|#...#|#...#",
    'B': "####.|#...#|#...#|####.|#...#|#...#|####.",
    'C': ".###.|#...#|#....|#....|#....|#...#|.###.",
    'D': "####.|#...#|#...#|#...#|#...#|#...#|####.",
    'E': "#####|#....|#....|####.|#....|#....|#####",
    'F': "#####|#....|#....|####.|#....|#....|#....",
    'G': ".###.|#...#|#....|#.###|#...#|#...#|.###.",
    'H': "#...#|#...#|#...#|#####|#...#|#...#|#...#",
    'I': ".###.|..#..|..#..|..#..|..#..|..#..|.###.",
    'J': "..###|...#.|...#.|...#.|...#.|#..#.|.##..",
    'K': "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#",
    'L': "#....|#....|#....|#....|#....|#....|#####",
    'M': "#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#",
    'N': "#...#|##..#|#.#.#|#..##|#...#|#...#|#...#",
    'O': ".###.|#...#|#...#|#...#|#...#|#...#|.###.",
    'P': "####.|#...#|#...#|####.|#....|#....|#....",
    'Q': ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#",
    'R': "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
    'S': ".####|#....|#....|.###.|....#|....#|####.",
    'T': "#####|..#..|..#..|..#..|..#..|..#..|..#..",
    'U': "#...#|#...#|#...#|#...#|#...#|#...#|.###.",
    'V': "#...#|#...#|#...#|#...#|#...#|.#.#.|..#..",
    'W': "#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#",
    'X': "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
    'Y': "#...#|#...#|.#.#.|..#..|..#..|..#..|..#..",
    'Z': "#####|....#|...#.|..#..|.#...|#....|#####",
    '0': ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.",
    '1': "..#..|.##..|..#..|..#..|..#..|..#..|.###.",
    '2': ".###.|#...#|....#|...#.|..#..|.#...|#####",
    '3': ".###.|#...#|....#|..##.|....#|#...#|.###.",
    '4': "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.",
    '5': "#####|#....|####.|....#|....#|#...#|.###.",
    '6': ".###.|#....|#....|####.|#...#|#...#|.###.",
    '7': "#####|....#|...#.|..#..|.#...|.#...|.#...",
    '8': ".###.|#...#|#...#|.###.|#...#|#...#|.###.",
    '9': ".###.|#...#|#...#|.####|....#|....#|.###.",
    '!': "..#..|..#..|..#..|..#..|..#..|.....|..#..",
    '"': ".#.#.|.#.#.|.....|.....|.....|.....|.....",
    "'": "..#..|..#..|.#...|.....|.....|.....|.....",
    '(': "...#.|..#..|.#...|.#...|.#...|..#..|...#.",
    ')': ".#...|..#..|...#.|...#.|...#.|..#..|.#...",
    '*': ".....|#.#.#|.###.|#####|.###.|#.#.#|.....",
    '+': ".....|..#..|..#..|#####|..#..|..#..|.....",
    ',': ".....|.....|.....|.....|.##..|..#..|.#...",
    '-': ".....|.....|.....|.###.|.....|.....|.....",
    '.': ".....|.....|.....|.....|.....|.##..|.##..",
    '/': "....#|...#.|...#.|..#..|.#...|.#...|#....",
    ':': ".....|.##..|.##..|.....|.##..|.##..|.....",
    '<': "...#.|..#..|.#...|#....|.#...|..#..|...#.",
    '=': ".....|.....|#####|.....|#####|.....|.....",
    '>': ".#...|..#..|...#.|....#|...#.|..#..|.#...",
    '?': ".###.|#...#|....#|...#.|..#..|.....|..#..",
    '%': "##..#|##..#|...#.|..#..|.#...|#..##|#..##",
    '@': ".....|.#.#.|#####|#####|.###.|..#..|.....",   # heart
    '$': "..#..|..#..|#####|.###.|.#.#.|#...#|.....",   # star-ish
    '_': ".....|.....|.....|.....|.....|.....|#####",
}
FONT_FIRST, FONT_COUNT = 32, 64      # ascii 32..95, uppercase only


def glyph_cell(ch):
    rows = FONT.get(ch)
    cell = np.zeros((8, 8, 4), np.uint8)
    if rows:
        for y, r in enumerate(rows.split('|')):
            for x, c in enumerate(r):
                if c == '#':
                    cell[y, x] = WHITE
    return cell


def draw_text(arr, text, x, y, scale, color, outline=None):
    """draw onto an RGBA numpy array (compositing)"""
    def put(ox, oy, col):
        cx = x + ox
        for ch in text.upper():
            g = glyph_cell(ch)[:7, :5].copy()
            g[g[..., 3] > 0] = col
            over(arr, scaled(g, scale), cx, y + oy)
            cx += 6 * scale
    if outline is not None:
        st = max(1, scale // 2)
        for dx in (-st, 0, st):
            for dy in (-st, 0, st):
                if dx or dy:
                    put(dx, dy, outline)
    put(0, 0, color)


# ----------------------------------------------------------------------------
# Gerald
# ----------------------------------------------------------------------------
class Pal:
    def __init__(s, body, dark, light, belly):
        s.body, s.dark, s.light, s.belly = [hexc(v) for v in (body, dark, light, belly)]


PALS = {
    1: Pal('4a7856', '325846', '6ea07a', '96be82'),     # tadpole
    2: Pal('7ad660', '54aa54', 'b0f08c', 'e8f8b0'),     # froglet
    3: Pal('5cbe56', '3a8c46', '96e278', 'e0f4a8'),     # frog
    4: Pal('84aa5c', '60824c', 'b0ce84', 'e2e6b4'),     # elder
}
SICK_PAL = Pal('a6c456', '7e9646', 'c6dc7a', 'ebebaa')
MOUTH = hexc('8a2c42')
TONGUE = hexc('ff6f8a')
BLUSH = hexc('ff9fb4')
SHELL = hexc('f2fbff')
TEAR = hexc('8fd8ff')


def eyes(cv, expr, cx, cy, ro, rw, lean=0):
    """one eye centred on pixel (cx,cy)"""
    cx, cy = int(cx), int(cy)
    if expr in ('blink', 'eat'):
        if expr == 'eat':  # happy chomping eyes
            for dx, dy in ((-2, 1), (-1, 0), (0, 0), (1, 0), (2, 1)):
                cv.px(cx + dx, cy + dy, OUT)
        else:
            cv.rect(cx - 2, cy, 5, 1, OUT)
        return
    if expr == 'happy':
        for dx, dy in ((-2, 1), (-1, 0), (0, -1), (1, 0), (2, 1)):
            cv.px(cx + dx, cy + dy, OUT)
        return
    if expr == 'sleep':
        for dx, dy in ((-2, 0), (-1, 1), (0, 1), (1, 1), (2, 0)):
            cv.px(cx + dx, cy + dy, OUT)
        return
    cv.ell(cx + .5, cy + .5, ro, ro, OUT)
    cv.ell(cx + .5, cy + .5, rw, rw, WHITE)
    if expr == 'sick':
        for d in range(-2, 3):
            cv.px(cx + d, cy + d, OUT)
            cv.px(cx + d, cy - d, OUT)
        return
    py = cy + (1 if expr == 'sad' else 0)
    cv.rect(cx - 1, py - 1, 2, 3, DARK)
    cv.px(cx, py - 1, hexc('6b6a9a'))
    if expr == 'sad':
        # heavy droopy lid
        side = -1 if lean < 0 else 1
        for i in range(-int(rw), int(rw) + 1):
            top = int(cy - rw + 0.5)
            slope = (i * side) // 2
            cv.rect(cx + i, top - 1, 1, 3 + slope + 1, hexc('3a8c46'))
            cv.px(cx + i, top + 2 + slope, OUT)


def draw_frog(stage, expr, br=0):
    cv = Cv(32, 32)
    pal = SICK_PAL if expr == 'sick' else PALS[stage]
    k = {2: 0.66, 3: 0.92, 4: 0.92}[stage]

    def X(x): return 16 + (x - 16) * k
    def Y(y): return 29.5 + (y - 29.5) * k
    def R(r): return r * k

    # legs behind
    cv.ell(X(6), Y(22.5), R(5.5), R(6.5), pal.dark)
    cv.ell(X(26), Y(22.5), R(5.5), R(6.5), pal.dark)
    cv.ell(X(4.5), Y(28), R(4.6), R(2.1), pal.body)
    cv.ell(X(27.5), Y(28), R(4.6), R(2.1), pal.body)
    # body
    cv.ell(X(16), Y(20.2 + br * .6), R(10.6), R(9.6 - br * .6), pal.body)
    # eye bumps
    re = R(5.2) * (1 + (1 - k) * .6)
    ey = Y(9.6 + br * .8)
    ex1, ex2 = X(9.5), X(22.5)
    cv.ell(ex1, ey, re, re, pal.body)
    cv.ell(ex2, ey, re, re, pal.body)
    # belly + arms
    cv.ell(X(16), Y(24.6), R(6.6), R(4.9), pal.belly)
    cv.ell(X(10.8), Y(27.6), R(3.2), R(2.3), pal.light)
    cv.ell(X(21.2), Y(27.6), R(3.2), R(2.3), pal.light)
    cv.outline(OUT)
    # highlights & spots
    cv.px(ex1 - re * .5, ey - re * .6, pal.light)
    cv.px(ex2 - re * .5, ey - re * .6, pal.light)
    for sx, sy in ((13, 15), (19, 15), (16, 13), (11, 19), (21, 19)):
        cv.px(X(sx), Y(sy), pal.dark)
    # eyes
    ro, rw = re * .86, re * .64
    eyes(cv, expr, ex1, ey, ro, rw, -1)
    eyes(cv, expr, ex2, ey, ro, rw, 1)
    # mouth
    my = Y(17.2 + br * .6)
    half = R(8.0)
    if expr in ('eat', 'tongue'):
        cv.ell(X(16), my + R(1.5), R(6.3), R(4.2), OUT)
        cv.ell(X(16), my + R(1.7), R(5.3), R(3.2), MOUTH)
        cv.ell(X(16), my + R(3.4), R(3.0), R(1.6), TONGUE)
        if expr == 'tongue':
            ty = my - R(7)
            cv.rect(X(16) - 2, ty - 1, 4, my - ty + 2, OUT)
            cv.rect(X(16) - 1, ty, 2, my - ty + 1, TONGUE)
            cv.rect(X(16) - 2, ty - 2, 4, 3, OUT)
            cv.rect(X(16) - 1, ty - 1, 2, 2, TONGUE)
    else:
        for xi in range(int(X(16) - half), int(X(16) + half) + 1):
            t = (xi + .5 - X(16)) / half
            if expr == 'sad':
                yy = my + 1.8 * (1 - 0) - 2.4 * (1 - t * t)   # frown
            elif expr == 'sick':
                yy = my + 1 + round(math.sin(xi * 1.1)) * 0.8   # wobbly
            elif expr == 'sleep':
                yy = my + 1.2 - 0.6 * (1 - t * t)
            else:
                yy = my + 0.1 + 2.2 * (1 - t * t)               # smile
            cv.px(xi, round(yy), OUT)
    # blush
    if expr not in ('sick', 'sad'):
        cv.rect(X(6.2), Y(17.6), max(2, R(3)), max(1, R(2)), BLUSH)
        cv.rect(X(22.8), Y(17.6), max(2, R(3)), max(1, R(2)), BLUSH)
    if expr == 'sad':
        cv.px(ex1 - 2, ey + re + 1, TEAR)
        cv.px(ex1 - 2, ey + re + 2, TEAR)
        cv.px(ex2 + 2, ey + re + 1, TEAR)
        cv.px(ex2 + 2, ey + re + 2, TEAR)
    if stage == 4:  # elder: bushy white brows, little glasses, tuft of beard
        for ex in (ex1, ex2):
            cv.rect(ex - 3, ey - re - 1, 6, 2, hexc('f4f4f4'))
            cv.px(ex - 4, ey - re, hexc('f4f4f4'))
            cv.px(ex + 3, ey - re, hexc('f4f4f4'))
            cv.ell(ex + .5, ey + .5, re + .2, re + .2, (0, 0, 0, 0)) if False else None
        g = hexc('8a6a3a')
        for ex in (ex1, ex2):
            for a in range(0, 360, 20):
                cv.px(ex + math.cos(math.radians(a)) * (re - .2),
                      ey + math.sin(math.radians(a)) * (re - .2), g)
        cv.line(ex1 + re - 1, ey, ex2 - re + 1, ey, g)
        cv.rect(X(14), Y(21.6), 4, 2, hexc('f4f4f4'))
        cv.px(X(15), Y(23.4), hexc('f4f4f4'))
        cv.px(X(16), Y(23.4), hexc('f4f4f4'))
    return cv


def draw_tadpole(expr, phase=0):
    cv = Cv(32, 32)
    pal = SICK_PAL if expr == 'sick' else PALS[1]
    # tail first (behind)
    pts = []
    for i in range(0, 15):
        t = i / 14.0
        x = 18 + 12.5 * t
        y = 20 + 3.2 * math.sin(t * 5.2 + phase * math.pi) * (0.4 + t)
        pts.append((x, y, 3.2 - 2.4 * t))
    for x, y, r in pts:
        cv.ell(x, y, r, r, pal.dark)
    # head/body
    cv.ell(13, 19.5, 9.2, 7.6, pal.body)
    cv.ell(13, 22.2, 6.2, 4.0, pal.belly)
    cv.outline(OUT)
    cv.px(8, 14, pal.light)
    cv.px(9, 14, pal.light)
    for sx, sy in ((12, 15), (16, 16), (10, 18)):
        cv.px(sx, sy, pal.dark)
    ex1, ex2, ey = 8.5, 17.5, 14.5
    # eyes slightly taller than head
    for ex in (ex1, ex2):
        cv.ell(ex, ey, 3.7, 3.7, pal.body)
    cv.outline(OUT)
    for ex in (ex1, ex2):
        eyes(cv, expr, ex, ey, 3.4, 2.5, -1 if ex == ex1 else 1)
    # mouth
    my = 21
    if expr in ('eat', 'tongue'):
        cv.ell(13, my + 1, 3.4, 2.4, OUT)
        cv.ell(13, my + 1, 2.4, 1.5, MOUTH)
    else:
        for i, dy in enumerate((0, 1, 1, 1, 0)) if expr not in ('sad',) else enumerate((1, 0, 0, 0, 1)):
            cv.px(11 + i, my + dy, OUT)
    if expr not in ('sick', 'sad'):
        cv.rect(5, 19, 2, 1, BLUSH)
        cv.rect(19, 19, 2, 1, BLUSH)
    return cv


def draw_egg(frame):
    cv = Cv(32, 32)
    jelly, rim, dot = hexc('cdeef2'), hexc('f4feff'), hexc('243238')
    cv.ell(16, 19, 11, 12.2, jelly)
    cv.ell(16, 20, 8.5, 9.5, hexc('b6e2ea'))
    cv.outline(hexc('4a8a9a'))
    # highlight
    cv.rect(9, 11, 2, 4, rim)
    cv.rect(10, 9, 3, 2, rim)
    # yolk
    cv.ell(16, 20, 4.2, 4.2, dot)
    cv.px(14, 18, hexc('6c8088'))
    cv.px(15, 18, hexc('6c8088'))
    # little tadpole tail curled in the jelly
    if frame == 3:   # cracking
        c = hexc('3b6070')
        for x, y in ((14, 8), (15, 9), (16, 10), (15, 11), (16, 12), (17, 13), (18, 14), (19, 14), (20, 15)):
            cv.px(x, y, c)
        cv.px(16, 9, hexc('ffffff'))
    arr = cv.a
    if frame in (1, 2):   # wobble: shear rows
        sign = -1 if frame == 1 else 1
        out = np.zeros_like(arr)
        for y in range(32):
            sh = int(round(sign * (31 - y) / 8.0))
            out[y] = np.roll(arr[y], sh, axis=0)
        cv.a = out
    return cv


FROG_EXPR = ['idle', 'idle2', 'blink', 'happy', 'eat', 'sad', 'sick', 'sleep', 'tongue']


def frog_sheet_cell(stage, expr_index):
    expr = FROG_EXPR[expr_index]
    if stage == 0:
        return draw_egg(expr_index if expr_index < 4 else 0)
    base = 'idle' if expr == 'idle2' else expr
    if stage == 1:
        return draw_tadpole(base, phase=1 if expr == 'idle2' or expr_index % 2 else 0)
    return draw_frog(stage, base, br=1 if expr == 'idle2' else 0)


# ----------------------------------------------------------------------------
# little objects (16x16) and icons
# ----------------------------------------------------------------------------
def obj_poop(frame):
    cv = Cv(16, 16)
    b, d, l = hexc('9a6234'), hexc('73451f'), hexc('c88a52')
    cv.ell(8, 12.2, 6.2, 3.2, b)
    cv.ell(8, 8.6, 4.6, 2.9, b)
    cv.ell(8.5, 5.4, 2.6, 2.4, b)
    cv.px(8, 2, b)
    cv.px(9, 3, b)
    cv.outline(OUT)
    cv.rect(5, 11, 2, 1, l)
    cv.rect(6, 7, 2, 1, l)
    cv.px(5, 13, d)
    cv.px(11, 13, d)
    cv.px(10, 9, d)
    # eyes
    cv.px(6, 12, DARK)
    cv.px(10, 12, DARK)
    if frame == 1:
        g = hexc('8ed05a')
        for x, y in ((2, 4), (3, 3), (2, 2), (13, 5), (12, 4), (13, 3)):
            cv.px(x, y, g)
    return cv


def obj_fly(frame):
    cv = Cv(16, 16)
    wing = hexc('e4f6ff')
    if frame == 0:
        cv.ell(4.6, 6.2, 3.4, 2.2, wing)
        cv.ell(11.4, 6.2, 3.4, 2.2, wing)
    else:
        cv.ell(4.2, 4.6, 2.2, 3.6, wing)
        cv.ell(11.8, 4.6, 2.2, 3.6, wing)
    cv.ell(8, 9, 2.7, 3.7, hexc('4a3f7a'))
    cv.ell(8, 5.6, 2.2, 1.9, hexc('5c5094'))
    cv.outline(OUT)
    cv.px(6, 5, hexc('ff6a6a'))
    cv.px(10, 5, hexc('ff6a6a'))
    cv.rect(7, 8, 2, 1, hexc('8a80c8'))
    cv.rect(7, 10, 2, 1, hexc('8a80c8'))
    return cv


def obj_cricket():
    cv = Cv(16, 16)
    body, dk, lt = hexc('b98c3c'), hexc('7e5a24'), hexc('dcb460')
    cv.ell(7.5, 9, 5.6, 3.2, body)
    cv.ell(12.6, 8, 2.4, 2.3, body)
    cv.line(11, 5, 14, 2, dk)
    cv.line(13, 5, 15, 3, dk)
    cv.line(4, 11, 3, 14, dk)
    cv.line(7, 12, 7, 14, dk)
    cv.line(10, 12, 12, 14, dk)
    cv.outline(OUT)
    cv.rect(4, 7, 6, 1, lt)
    cv.px(13, 8, DARK)
    cv.px(6, 9, dk)
    cv.px(8, 9, dk)
    return cv


def obj_candy():
    cv = Cv(16, 16)
    cv.ell(8, 8, 4.2, 4.2, hexc('ff7aa8'))
    cv.rect(3, 6, 2, 4, hexc('ffd1e0'))
    cv.rect(11, 6, 2, 4, hexc('ffd1e0'))
    cv.line(2, 4, 3, 6, hexc('ffd1e0'))
    cv.line(2, 11, 3, 9, hexc('ffd1e0'))
    cv.line(13, 6, 14, 4, hexc('ffd1e0'))
    cv.line(13, 9, 14, 11, hexc('ffd1e0'))
    cv.outline(OUT)
    cv.rect(6, 5, 2, 1, WHITE)
    cv.px(5, 6, WHITE)
    cv.line(6, 10, 10, 6, hexc('ffffff'))
    return cv


def obj_sparkle():
    cv = Cv(16, 16)
    y = hexc('fff6a0')
    w = WHITE
    cv.rect(7, 2, 2, 12, y)
    cv.rect(2, 7, 12, 2, y)
    cv.rect(6, 6, 4, 4, y)
    cv.rect(7, 4, 2, 8, w)
    cv.rect(4, 7, 8, 2, w)
    cv.px(4, 4, y)
    cv.px(11, 4, y)
    cv.px(4, 11, y)
    cv.px(11, 11, y)
    return cv


def obj_heart():
    cv = Cv(16, 16)
    r = hexc('ff5577')
    cv.ell(5.2, 6, 3.4, 3.2, r)
    cv.ell(10.8, 6, 3.4, 3.2, r)
    for i in range(0, 6):
        cv.rect(2 + i, 7 + i, 12 - 2 * i, 1, r)
    cv.outline(OUT)
    cv.rect(3, 4, 2, 1, hexc('ffb0c0'))
    cv.px(3, 5, hexc('ffb0c0'))
    return cv


def obj_zzz():
    cv = Cv(16, 16)
    c = hexc('7a8cff')
    def z(x, y, s):
        cv.rect(x, y, s, 1, c)
        for i in range(s):
            cv.px(x + s - 1 - i, y + i, c)
        cv.rect(x, y + s - 1, s, 1, c)
    z(2, 8, 5)
    z(8, 2, 6)
    return cv


def obj_excl():
    cv = Cv(16, 16)
    c = hexc('ff4a5a')
    cv.rect(6, 2, 4, 8, c)
    cv.rect(7, 10, 2, 1, c)
    cv.rect(6, 12, 4, 3, c)
    cv.outline(OUT)
    cv.rect(7, 3, 1, 5, hexc('ff9aa6'))
    return cv


def obj_note():
    cv = Cv(16, 16)
    c = hexc('7a8cff')
    cv.ell(5, 12, 3, 2.4, c)
    cv.rect(7, 3, 2, 10, c)
    cv.rect(9, 3, 4, 2, c)
    cv.rect(12, 4, 1, 4, c)
    cv.outline(OUT)
    return cv


def obj_drop():
    cv = Cv(16, 16)
    c = hexc('5ac8ff')
    cv.ell(8, 10, 4, 4, c)
    for i in range(5):
        cv.rect(8 - i // 2, 2 + i, 1 + i // 2 * 2 if i else 1, 1, c)
    cv.outline(OUT)
    cv.rect(6, 9, 1, 2, WHITE)
    return cv


def obj_bubble():
    cv = Cv(16, 16)
    cv.ell(8, 8, 5.5, 5.5, hexc('b8ecff', 200))
    cv.ell(8, 8, 4.3, 4.3, hexc('dff8ff', 120))
    cv.outline(hexc('4aa8d8'))
    cv.rect(5, 5, 2, 1, WHITE)
    cv.px(5, 6, WHITE)
    return cv


def obj_cross():
    cv = Cv(16, 16)
    cv.rect(6, 2, 4, 12, hexc('ff4a5a'))
    cv.rect(2, 6, 12, 4, hexc('ff4a5a'))
    cv.outline(OUT)
    cv.rect(7, 3, 1, 4, hexc('ff9aa6'))
    return cv


def obj_skull():
    cv = Cv(16, 16)
    cv.ell(8, 7, 5.5, 5, hexc('f0f0f8'))
    cv.rect(5, 10, 6, 4, hexc('f0f0f8'))
    cv.outline(OUT)
    cv.rect(5, 6, 2, 2, DARK)
    cv.rect(9, 6, 2, 2, DARK)
    cv.px(8, 9, DARK)
    cv.px(6, 12, OUT)
    cv.px(8, 12, OUT)
    cv.px(10, 12, OUT)
    return cv


def icon_play():
    cv = Cv(16, 16)
    cols = [hexc('ff5a5a'), hexc('fff6e0'), hexc('4aa8ff'), hexc('ffd94a')]
    ys, xs = np.mgrid[0:16, 0:16]
    inside = ((xs + .5 - 8) / 6.2) ** 2 + ((ys + .5 - 8) / 6.2) ** 2 <= 1
    ang = (np.degrees(np.arctan2(ys + .5 - 8, xs + .5 - 8)) + 360) % 360
    idx = (ang // 90).astype(int) % 4
    for i in range(4):
        cv.a[inside & (idx == i)] = cols[i]
    cv.outline(OUT)
    cv.rect(4, 4, 2, 1, WHITE)
    return cv


def icon_clean():
    cv = Cv(16, 16)
    cv.ell(5.5, 10.5, 4.2, 4.2, hexc('b8ecff'))
    cv.ell(11, 6, 3.2, 3.2, hexc('b8ecff'))
    cv.ell(11.5, 12.5, 2.2, 2.2, hexc('b8ecff'))
    cv.outline(hexc('3a98cf'))
    cv.px(3, 8, WHITE)
    cv.px(4, 8, WHITE)
    cv.px(3, 9, WHITE)
    cv.px(10, 4, WHITE)
    cv.px(11, 4, WHITE)
    return cv


def icon_moon():
    cv = Cv(16, 16)
    cv.ell(8, 8, 6, 6, hexc('ffe27a'))
    cv.ell(11, 6.5, 5, 5, (0, 0, 0, 0))
    cv.a[np.all(cv.a == (0, 0, 0, 0), axis=2)] = 0
    # carve crescent: clear pixels inside second circle
    ys, xs = np.mgrid[0:16, 0:16]
    carve = ((xs + .5 - 11) / 5) ** 2 + ((ys + .5 - 6.5) / 5) ** 2 <= 1
    cv.a[carve] = 0
    cv.outline(OUT)
    cv.px(12, 11, hexc('fff6a0'))
    cv.px(13, 11, hexc('fff6a0'))
    cv.px(12, 10, hexc('fff6a0'))
    cv.px(12, 12, hexc('fff6a0'))
    return cv


def icon_meds():
    cv = Cv(16, 16)
    # capsule drawn diagonally
    for i in range(-4, 5):
        cx, cy = 8 + i, 8 - i
        col = hexc('ff5a6a') if i < 0 else hexc('f4f4ff')
        cv.ell(cx + .5, cy + .5, 2.6, 2.6, col)
    cv.ell(4.4, 11.6, 2.6, 2.6, hexc('ff5a6a'))
    cv.ell(11.6, 4.4, 2.6, 2.6, hexc('f4f4ff'))
    cv.outline(OUT)
    cv.px(5, 10, hexc('ffb0b8'))
    cv.px(11, 3, WHITE)
    return cv


def icon_info():
    cv = Cv(16, 16)
    cv.ell(8, 8, 6.2, 6.2, hexc('6ab4ff'))
    cv.outline(OUT)
    cv.rect(7, 3, 2, 2, WHITE)
    cv.rect(7, 6, 2, 6, WHITE)
    cv.rect(6, 6, 3, 1, WHITE)
    cv.rect(6, 11, 4, 1, WHITE)
    return cv


def icon_back():
    cv = Cv(16, 16)
    c = hexc('f4f4ff')
    for i in range(6):
        cv.rect(2 + i, 8 - i, 1, 1 + 2 * i, c)
    cv.rect(7, 6, 7, 5, c)
    cv.outline(OUT)
    return cv


def icon_sun():
    cv = Cv(16, 16)
    y = hexc('ffe27a')
    for a in range(0, 360, 45):
        cv.line(8 + math.cos(math.radians(a)) * 4, 8 + math.sin(math.radians(a)) * 4,
                8 + math.cos(math.radians(a)) * 7, 8 + math.sin(math.radians(a)) * 7, y)
    cv.ell(8, 8, 4, 4, y)
    cv.outline(OUT)
    return cv


def icon_sound(on):
    cv = Cv(16, 16)
    c = hexc('f4f4ff')
    cv.rect(2, 6, 3, 4, c)
    for i in range(4):
        cv.rect(5 + i, 6 - i, 1, 4 + 2 * i, c)
    cv.outline(OUT)
    if on:
        cv.px(11, 6, hexc('ffe27a'))
        cv.px(12, 7, hexc('ffe27a'))
        cv.px(12, 8, hexc('ffe27a'))
        cv.px(11, 9, hexc('ffe27a'))
        cv.px(13, 4, hexc('ffe27a'))
        cv.px(14, 5, hexc('ffe27a'))
        cv.px(14, 10, hexc('ffe27a'))
        cv.px(13, 11, hexc('ffe27a'))
    else:
        cv.line(10, 5, 14, 11, hexc('ff4a5a'), 1)
        cv.line(14, 5, 10, 11, hexc('ff4a5a'), 1)
    return cv


def lily_pad():
    cv = Cv(48, 16)
    dk, md, lt = hexc('2f8a4a'), hexc('46b05a'), hexc('72d47a')
    cv.ell(24, 9.5, 23.5, 6.4, dk)
    cv.ell(24, 8.2, 23, 5.8, md)
    cv.ell(22, 7.4, 17, 3.6, lt)
    # notch
    for i in range(0, 12):
        cv.rect(36 + i, 8 + (i // 4), 1, 1, (0, 0, 0, 0))
    cv.outline(OUT)
    for x, y in ((10, 6), (14, 7), (20, 5), (28, 6), (32, 7)):
        cv.px(x, y, hexc('a8ec9a'))
    return cv


def ripple(frame):
    cv = Cv(32, 8)
    c = hexc('e8f8ff', 200)
    r = 5 + frame * 5
    cv.ell(16, 4, r, r * 0.26 + 0.5, c)
    cv.ell(16, 4, r - 1.6, max(0.4, (r - 1.6) * 0.26), (0, 0, 0, 0))
    return cv


# ----------------------------------------------------------------------------
# backgrounds
# ----------------------------------------------------------------------------
def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def banded_gradient(cv, y0, y1, colors):
    nb = len(colors)
    bayer = [[0.0, 0.5], [0.75, 0.25]]
    for y in range(y0, y1):
        t = (y - y0) / max(1, (y1 - y0 - 1))
        v = t * (nb - 1)
        base = min(nb - 2, int(v))
        frac = v - base
        for x in range(cv.w):
            idx = base + (1 if frac > bayer[y % 2][x % 2] else 0)
            cv.px(x, y, colors[idx] + (255,))


def cloud(cv, cx, cy, s, col, shade):
    for dx, dy, rx, ry in ((0, 0, 8, 4), (-7, 2, 6, 3), (8, 2, 7, 3), (3, -3, 6, 4), (-3, -2, 5, 3)):
        cv.ell(cx + dx * s, cy + dy * s, rx * s, ry * s, col)
    cv.rect(cx - 14 * s, cy + 3 * s, 30 * s, 1, shade)


def scene(w, h, night, seed=3):
    rnd = random.Random(seed)
    cv = Cv(w, h)
    wh = int(h * 0.55)  # water line
    if night:
        sky = [(8, 10, 36), (16, 20, 58), (26, 32, 80), (40, 48, 102), (58, 68, 122)]
        far, near = (24, 46, 78), (14, 34, 56)
        grass, water_a, water_b = (18, 52, 54), (34, 70, 126), (14, 32, 84)
        ripple_c = (84, 118, 178)
        stem, cat = (22, 70, 56), (70, 46, 40)
    else:
        sky = [(104, 188, 240), (128, 204, 244), (152, 218, 246), (178, 230, 248), (204, 240, 250)]
        far, near = (108, 178, 160), (70, 150, 104)
        grass, water_a, water_b = (104, 184, 90), (92, 178, 216), (52, 122, 178)
        ripple_c = (150, 214, 238)
        stem, cat = (62, 134, 70), (126, 80, 52)
    banded_gradient(cv, 0, wh - 6, sky)
    # sun / moon
    sx, sy = int(w * 0.80), int(h * 0.2)
    if night:
        for _ in range(int(w * h / 260)):
            x, y = rnd.randrange(w), rnd.randrange(int(wh * .8))
            cv.px(x, y, (255, 255, 230) if rnd.random() < .6 else (170, 190, 255))
        cv.ell(sx, sy, 10, 10, (252, 246, 214))
        cv.ell(sx, sy, 8, 8, (240, 238, 200))
        for cx, cy, r in ((-3, -2, 2), (3, 3, 1.5), (2, -4, 1)):
            cv.ell(sx + cx, sy + cy, r, r, (214, 212, 178))
    else:
        cv.ell(sx, sy, 12, 12, (255, 244, 190))
        cv.ell(sx, sy, 9, 9, (255, 236, 130))
        cloud(cv, int(w * .22), int(h * .2), 1, (255, 255, 255), (214, 230, 246))
        cloud(cv, int(w * .56), int(h * .31), 1, (255, 255, 255), (214, 230, 246))
        cloud(cv, int(w * .92), int(h * .45), 1, (246, 252, 255), (206, 224, 244))
    # hills + trees
    ph1, ph2 = rnd.random() * 6, rnd.random() * 6
    for x in range(w):
        top = wh - 12 - int(5 * math.sin(x * .07 + ph1) + 3 * math.sin(x * .21 + ph2))
        cv.rect(x, top, 1, wh - top, far + (255,))
    for x in range(w):
        bump = abs(((x + 5) % 13) - 6)
        top = wh - 7 - int(4 * math.sin(x * .13 + ph2) + (6 - bump) * .7 + 1.5 * math.sin(x * .5))
        cv.rect(x, top, 1, wh - top, near + (255,))
    # shore
    cv.rect(0, wh - 4, w, 4, grass + (255,))
    cv.rect(0, wh - 4, w, 1, lerp(grass, (255, 255, 255), .2 if not night else .1) + (255,))
    cv.rect(0, wh, w, 1, lerp(grass, (0, 0, 0), .35) + (255,))
    # water
    for y in range(wh + 1, h):
        t = (y - wh) / max(1, h - wh - 1)
        col = lerp(water_a, water_b, t)
        cv.rect(0, y, w, 1, col + (255,))
    for _ in range(int(w * (h - wh) / 95)):
        x, y = rnd.randrange(w - 12), rnd.randrange(wh + 3, h - 1)
        ln = rnd.randint(4, 10)
        cv.rect(x, y, ln, 1, ripple_c + (255,))
    # sun/moon reflection
    for i, y in enumerate(range(wh + 3, h - 6, 3)):
        ln = max(2, 14 - i * 2)
        cv.rect(sx - ln // 2, y, ln, 1, (252, 246, 214, 255) if night else (255, 244, 190, 255))
    # reeds
    def reeds(x0, x1):
        for _ in range(5):
            x = rnd.randint(x0, x1)
            top = wh - rnd.randint(14, 30)
            cv.rect(x, top, 1, wh + 4 - top, stem + (255,))
            cv.rect(x + 1, top + 4, 1, wh + 4 - top - 4, lerp(stem, (0, 0, 0), .2) + (255,))
            cv.line(x, wh - 2, x + rnd.choice((-5, 5)), wh - 14, stem + (255,))
            cv.ell(x + .5, top + 3, 1.7, 4.2, cat + (255,))
            cv.rect(x, top - 3, 1, 3, stem + (255,))
    reeds(2, int(w * .12))
    reeds(int(w * .88), w - 3)
    # decorative lily pads in the corners
    def pad(cx, cy, flower):
        cv.ell(cx, cy + 1, 10, 3.2, lerp(water_b, (0, 0, 0), .3) + (255,))
        pc = (36, 110, 76) if night else (62, 160, 82)
        cv.ell(cx, cy, 10, 3.2, pc + (255,))
        cv.ell(cx - 1, cy - .5, 7, 1.8, lerp(pc, (255, 255, 255), .22) + (255,))
        if flower:
            cv.ell(cx + 2, cy - 2, 2.6, 1.8, (255, 150, 190, 255) if not night else (190, 110, 160, 255))
            cv.px(cx + 2, cy - 3, (255, 236, 130, 255))
    pad(int(w * .13), h - 10, True)
    pad(int(w * .87), h - 8, False)
    return cv


def wallpaper(w, h, seed=11):
    rnd = random.Random(seed)
    cv = Cv(w, h)
    top, bot = (66, 150, 176), (40, 112, 148)
    for y in range(h):
        cv.rect(0, y, w, 1, lerp(top, bot, y / h) + (255,))
    for _ in range(90):
        x, y = rnd.randrange(w - 10), rnd.randrange(h)
        cv.rect(x, y, rnd.randint(3, 8), 1, lerp(top, (210, 240, 255), .35) + (255,))
    for i in range(9):
        cx, cy = rnd.randrange(w), rnd.randrange(h)
        pc = (54, 150, 86)
        cv.ell(cx, cy + 1, 10, 3.6, (28, 96, 80, 255))
        cv.ell(cx, cy, 10, 3.6, pc + (255,))
        cv.ell(cx - 1, cy - .6, 7, 1.9, (92, 190, 104, 255))
        for k in range(0, 12):
            cv.px(cx + 2 + k % 8, cy + k // 6, (66, 158, 90, 255)) if False else None
        if i % 3 == 0:
            cv.ell(cx + 3, cy - 2, 2.6, 1.8, (255, 150, 190, 255))
            cv.px(cx + 3, cy - 3, (255, 236, 130, 255))
    # dim it: it sits behind a wooden UI
    cv.a[..., :3] = (cv.a[..., :3].astype(np.float32) * 0.62).astype(np.uint8)
    return cv


# ----------------------------------------------------------------------------
# atlas assembly
# ----------------------------------------------------------------------------
OBJ_NAMES = ['poop0', 'poop1', 'fly0', 'fly1', 'cricket', 'candy', 'sparkle', 'heart',
             'zzz', 'excl', 'note', 'drop', 'bubble', 'cross', 'skull']
ICON_NAMES = ['feed', 'play', 'clean', 'sleep', 'meds', 'info', 'back', 'meal', 'snack',
              'sun', 'sound_on', 'sound_off']
FROG_STAGES = 5   # egg, tadpole, froglet, frog, elder
OBJ_Y, ICON_Y, MISC_Y, FONT_Y = 160, 176, 192, 448


def build_sprites():
    sheet = Cv(512, 512)
    for st in range(FROG_STAGES):
        for e in range(len(FROG_EXPR)):
            sheet.a[st * 32:(st + 1) * 32, e * 32:(e + 1) * 32] = frog_sheet_cell(st, e).a
    objs = [obj_poop(0), obj_poop(1), obj_fly(0), obj_fly(1), obj_cricket(), obj_candy(),
            obj_sparkle(), obj_heart(), obj_zzz(), obj_excl(), obj_note(), obj_drop(),
            obj_bubble(), obj_cross(), obj_skull()]
    for i, o in enumerate(objs):
        sheet.a[OBJ_Y:OBJ_Y + 16, i * 16:(i + 1) * 16] = o.a
    icons = [obj_cricket(), icon_play(), icon_clean(), icon_moon(), icon_meds(), icon_info(),
             icon_back(), obj_cricket(), obj_candy(), icon_sun(), icon_sound(True), icon_sound(False)]
    for i, o in enumerate(icons):
        sheet.a[ICON_Y:ICON_Y + 16, i * 16:(i + 1) * 16] = o.a
    sheet.a[MISC_Y:MISC_Y + 16, 0:48] = lily_pad().a
    for i in range(3):
        sheet.a[MISC_Y:MISC_Y + 8, 64 + i * 32:96 + i * 32] = ripple(i).a
    for i in range(FONT_COUNT):
        sheet.a[FONT_Y:FONT_Y + 8, i * 8:(i + 1) * 8] = glyph_cell(chr(FONT_FIRST + i))
    return sheet


def build_bg():
    sheet = Cv(256, 512)
    sheet.a[0:120, 0:200] = scene(200, 120, False, 3).a
    sheet.a[128:248, 0:200] = scene(200, 120, True, 5).a
    sheet.a[256:376, 0:160] = wallpaper(160, 120).a
    return sheet


def build_icon():
    cv = Cv(48, 48)
    banded_gradient(Cv(1, 1), 0, 1, [(0, 0, 0), (0, 0, 0)])
    sky = [(110, 190, 240), (150, 216, 246), (196, 238, 250)]
    nb = Cv(48, 30)
    banded_gradient(nb, 0, 30, sky)
    cv.a[0:30] = nb.a
    for y in range(30, 48):
        cv.rect(0, y, 48, 1, lerp((92, 178, 216), (52, 122, 178), (y - 30) / 17) + (255,))
    for x, y, l in ((4, 36, 7), (30, 33, 8), (14, 43, 9), (34, 44, 6), (22, 38, 5)):
        cv.rect(x, y, l, 1, (150, 214, 238, 255))
    cv.ell(38, 9, 6, 6, (255, 244, 190, 255))
    cv.ell(38, 9, 4.5, 4.5, (255, 236, 130, 255))
    cloud(cv, 12, 9, 0.5, (255, 255, 255, 255), (214, 230, 246, 255))
    # pad + gerald
    pad = lily_pad().a
    over(cv.a, pad, 0, 30)
    over(cv.a, scaled(pad, 1), 0, 30)
    cv.ell(24, 40, 21, 5, (0, 0, 0, 0))
    cv.a[34:46, :] = cv.a[34:46, :]
    cv2 = Cv(48, 48)
    cv2.a = cv.a.copy()
    over(cv2.a, pad, 0, 32)
    g = draw_frog(3, 'happy').a
    over(cv2.a, g, 8, 8)
    # rounded edge
    out = cv2.a
    for (x, y) in ((0, 0), (1, 0), (0, 1), (47, 0), (46, 0), (47, 1), (0, 47), (1, 47), (0, 46), (47, 47), (46, 47), (47, 46)):
        out[y, x] = hexc('26203a')
    out[0, 2:46] = hexc('26203a')
    out[47, 2:46] = hexc('26203a')
    out[2:46, 0] = hexc('26203a')
    out[2:46, 47] = hexc('26203a')
    return out


def build_banner():
    cv = scene(256, 128, False, 7)
    pad = lily_pad().a
    over(cv.a, scaled(pad, 2), 150, 86)
    over(cv.a, scaled(draw_frog(3, 'happy').a, 2), 172, 36)
    arr = cv.a
    draw_text(arr, "GERALD", 12, 18, 4, hexc('ffe66d'), outline=hexc('2a5a2a'))
    draw_text(arr, "VIRTUAL PET", 14, 62, 2, hexc('ffffff'), outline=hexc('26203a'))
    # banner is drawn on an opaque background -> keep alpha
    return arr



# ----------------------------------------------------------------------------
# wooden UI kit (bottom screen) -- drawn at 1x, shown at 2x
# ----------------------------------------------------------------------------
WOOD_OUT = hexc('2e1a0e')


def _tone(c, t):
    return tuple(min(255, int(v * t)) for v in c[:3]) + (255,)


def wood_fill(cv, x, y, w, h, tone=1.0, seed=1):
    rnd = random.Random(seed)
    A, B = (154, 100, 54), (140, 90, 48)
    seam, gl, gh = (96, 58, 28), (122, 76, 38), (174, 120, 70)
    for i, py in enumerate(range(y, y + h, 8)):
        ph = min(8, y + h - py)
        cv.rect(x, py, w, ph, _tone(A if i % 2 == 0 else B, tone))
        if ph == 8:
            cv.rect(x, py + 7, w, 1, _tone(seam, tone))
        for _ in range(max(2, w // 12)):
            gx, gy = rnd.randrange(x, x + w), py + rnd.randrange(1, max(2, ph - 1))
            cv.rect(gx, gy, min(rnd.randint(3, 9), x + w - gx), 1, _tone(gl, tone))
        for _ in range(max(1, w // 28)):
            gx, gy = rnd.randrange(x, x + w), py + rnd.randrange(1, max(2, ph - 1))
            cv.rect(gx, gy, min(rnd.randint(2, 5), x + w - gx), 1, _tone(gh, tone))
        sx = x + rnd.randrange(6, max(7, w - 6))
        cv.rect(sx, py, 1, max(1, ph - 1), _tone(seam, tone))
        if rnd.random() < 0.35 and w > 40:          # knot
            kx, ky = x + rnd.randrange(8, w - 8), py + 4
            cv.ell(kx, ky, 2.2, 1.6, _tone(gl, tone))
            cv.px(kx, ky, _tone(seam, tone))


def nail(cv, x, y):
    cv.rect(x, y, 3, 3, (150, 156, 170, 255))
    cv.px(x, y, (226, 230, 240, 255))
    cv.px(x + 2, y + 2, (74, 78, 94, 255))


def round_corners(cv, col=WOOD_OUT):
    w, h = cv.w, cv.h
    for (cx, cy, dx, dy) in ((0, 0, 1, 1), (w - 1, 0, -1, 1), (0, h - 1, 1, -1), (w - 1, h - 1, -1, -1)):
        cv.px(cx, cy, (0, 0, 0, 0))
        cv.px(cx + dx, cy, col)
        cv.px(cx, cy + dy, col)


def panel_wood(w, h, tone=1.0, gold=False, seed=1, nails=True):
    cv = Cv(w, h)
    wood_fill(cv, 0, 0, w, h, tone, seed)
    if gold:
        bl, bd, bm = (255, 226, 130), (190, 130, 36), (244, 190, 70)
    else:
        bl, bd, bm = (150, 100, 56), (74, 44, 22), (112, 70, 36)
    t = 4
    cv.rect(0, 0, w, t, bm)
    cv.rect(0, h - t, w, t, bm)
    cv.rect(0, 0, t, h, bm)
    cv.rect(w - t, 0, t, h, bm)
    cv.rect(1, 1, w - 2, 1, bl)                 # bevel highlight (top/left)
    cv.rect(1, 1, 1, h - 2, bl)
    cv.rect(1, h - 2, w - 2, 1, bd)             # bevel shadow (bottom/right)
    cv.rect(w - 2, 1, 1, h - 2, bd)
    cv.rect(t, t, w - 2 * t, 1, bd)             # inner groove
    cv.rect(t, t, 1, h - 2 * t, bd)
    cv.rect(t, h - t - 1, w - 2 * t, 1, _tone(bl, 0.9))
    cv.rect(w - t - 1, t, 1, h - 2 * t, _tone(bl, 0.9))
    cv.rect(0, 0, w, 1, WOOD_OUT)
    cv.rect(0, h - 1, w, 1, WOOD_OUT)
    cv.rect(0, 0, 1, h, WOOD_OUT)
    cv.rect(w - 1, 0, 1, h, WOOD_OUT)
    if nails:
        for nx, ny in ((2, 2), (w - 5, 2), (2, h - 5), (w - 5, h - 5)):
            nail(cv, nx, ny)
    round_corners(cv)
    return cv


def panel_parchment(w, h):
    cv = Cv(w, h)
    rnd = random.Random(5)
    cv.rect(0, 0, w, h, (240, 222, 170, 255))
    for _ in range(w * h // 18):
        cv.px(rnd.randrange(w), rnd.randrange(h), (228, 205, 150, 255))
    for _ in range(w * h // 60):
        cv.px(rnd.randrange(w), rnd.randrange(h), (250, 236, 192, 255))
    band = (208, 168, 104, 255)
    cv.rect(1, 1, w - 2, 2, band)
    cv.rect(1, h - 3, w - 2, 2, band)
    cv.rect(1, 1, 2, h - 2, band)
    cv.rect(w - 3, 1, 2, h - 2, band)
    cv.rect(3, 3, w - 6, 1, (226, 196, 134, 255))
    cv.rect(3, h - 4, w - 6, 1, (226, 196, 134, 255))
    pc = (86, 56, 28, 255)
    cv.rect(0, 0, w, 1, pc)
    cv.rect(0, h - 1, w, 1, pc)
    cv.rect(0, 0, 1, h, pc)
    cv.rect(w - 1, 0, 1, h, pc)
    round_corners(cv, pc)
    for nx, ny in ((2, 2), (w - 5, 2)):
        nail(cv, nx, ny)
    return cv


def button_round(sel):
    cv = Cv(22, 22)
    if sel:
        rim, hi, lo, face = (255, 206, 84), (255, 240, 160), (176, 116, 30), (92, 76, 110)
    else:
        rim, hi, lo, face = (150, 156, 172), (214, 220, 232), (84, 88, 106), (60, 52, 74)
    cv.ell(11, 11, 11, 11, WOOD_OUT)
    cv.ell(11, 11, 10, 10, rim + (255,))
    ys, xs = np.mgrid[0:22, 0:22]
    ring = (((xs + .5 - 11) ** 2 + (ys + .5 - 11) ** 2) <= 100)
    d2 = (xs + .5 - 11) ** 2 + (ys + .5 - 11) ** 2
    cv.a[ring & ((xs + ys) < 18) & (d2 > 70)] = hi + (255,)
    cv.a[ring & ((xs + ys) > 26) & (d2 > 70)] = lo + (255,)
    cv.ell(11, 11, 8, 8, WOOD_OUT)
    cv.ell(11, 11, 7.5, 7.5, face + (255,))
    cv.px(4, 8, hi + (255,))
    return cv


def frame_box(w, h):
    cv = panel_wood(w, h, 0.9, seed=9, nails=True)
    x0, y0, x1, y1 = 5, 5, w - 5, h - 5
    cv.rect(x0 - 1, y0 - 1, x1 - x0 + 2, y1 - y0 + 2, WOOD_OUT)
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        cv.rect(x0, y, x1 - x0, 1, lerp((120, 196, 206), (70, 146, 168), t) + (255,))
    for i in range(0, (x1 - x0) + (y1 - y0), 7):    # soft glints
        for k in range(3):
            px_, py_ = x0 + i - k, y0 + k
            if x0 <= px_ < x1 and y0 <= py_ < y1:
                cv.px(px_, py_, (170, 224, 230, 255))
    return cv


UI_SPRITES = {          # name: (x, y, w, h)
    'panel_stats': (0, 0, 156, 52),
    'panel_msg': (160, 0, 156, 24),
    'panel_info': (0, 56, 156, 116),
    'panel_title': (160, 28, 140, 60),
    'sign_bar': (160, 92, 156, 15),
    'sign_title': (160, 110, 110, 14),
    'btn_round': (0, 176, 22, 22),
    'btn_round_sel': (24, 176, 22, 22),
    'btn_sign': (48, 176, 50, 35),
    'btn_sign_sel': (100, 176, 50, 35),
    'frame': (0, 212, 42, 44),
}


def build_ui():
    sheet = Cv(512, 256)

    def put(name, cv):
        x, y, w, h = UI_SPRITES[name]
        assert (cv.w, cv.h) == (w, h), name
        sheet.a[y:y + h, x:x + w] = cv.a
    put('panel_stats', panel_wood(156, 52, 0.78, seed=2))
    put('panel_msg', panel_parchment(156, 24))
    put('panel_info', panel_wood(156, 116, 0.78, seed=3))
    put('panel_title', panel_wood(140, 60, 0.85, seed=4))
    put('sign_bar', panel_wood(156, 15, 0.9, seed=6))
    put('sign_title', panel_wood(110, 14, 1.0, seed=7))
    put('btn_round', button_round(False))
    put('btn_round_sel', button_round(True))
    put('btn_sign', panel_wood(50, 35, 0.95, seed=8))
    put('btn_sign_sel', panel_wood(50, 35, 1.05, gold=True, seed=8))
    put('frame', frame_box(42, 44))
    return sheet


def write_png(arr, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(arr, 'RGBA').save(path)


def write_header(path):
    L = []
    L.append('// generated by tools/make_art.py -- do not edit by hand')
    L.append('#pragma once')
    L.append('#define SPR_W 512')
    L.append('#define SPR_H 512')
    L.append('#define BG_W 256')
    L.append('#define BG_H 512')
    L.append('#define FROG_CELL 32')
    L.append('#define OBJ_CELL 16')
    L.append('#define FROG_COLS %d' % len(FROG_EXPR))
    L.append('#define OBJ_Y %d' % OBJ_Y)
    L.append('#define ICON_Y %d' % ICON_Y)
    L.append('#define MISC_Y %d' % MISC_Y)
    L.append('#define FONT_Y %d' % FONT_Y)
    L.append('#define FONT_FIRST %d' % FONT_FIRST)
    L.append('#define FONT_COUNT %d' % FONT_COUNT)
    L.append('#define PAD_X 0')
    L.append('#define PAD_W 48')
    L.append('#define PAD_H 16')
    L.append('#define RIPPLE_X 64')
    L.append('#define RIPPLE_W 32')
    L.append('#define RIPPLE_H 8')
    L.append('')
    L.append('#define UI_W 512')
    L.append('#define UI_H 256')
    for n, (x, y, w, h) in UI_SPRITES.items():
        N = n.upper()
        L.append('#define UI_%s_X %d' % (N, x))
        L.append('#define UI_%s_Y %d' % (N, y))
        L.append('#define UI_%s_W %d' % (N, w))
        L.append('#define UI_%s_H %d' % (N, h))
    L.append('')
    L.append('enum { ST_EGG = 0, ST_TADPOLE, ST_FROGLET, ST_FROG, ST_ELDER };')
    L.append('enum { EX_IDLE = 0, EX_IDLE2, EX_BLINK, EX_HAPPY, EX_EAT, EX_SAD, EX_SICK, EX_SLEEP, EX_TONGUE };')
    L.append('enum {')
    for i, n in enumerate(OBJ_NAMES):
        L.append('    OBJ_%s = %d,' % (n.upper(), i))
    L.append('    OBJ_COUNT')
    L.append('};')
    L.append('enum {')
    for i, n in enumerate(ICON_NAMES):
        L.append('    ICO_%s = %d,' % (n.upper(), i))
    L.append('    ICO_COUNT')
    L.append('};')
    with open(path, 'w') as f:
        f.write('\n'.join(L) + '\n')


def main():
    preview = None
    if '--preview' in sys.argv:
        preview = sys.argv[sys.argv.index('--preview') + 1]
    spr = build_sprites()
    bg = build_bg()
    write_png(spr.a, os.path.join(ROOT, 'gfx', 'sprites.png'))
    write_png(bg.a, os.path.join(ROOT, 'gfx', 'bg.png'))
    ui = build_ui()
    write_png(ui.a, os.path.join(ROOT, 'gfx', 'ui.png'))
    for name in ('sprites', 'bg', 'ui'):
        with open(os.path.join(ROOT, 'gfx', name + '.t3s'), 'w') as f:
            f.write('-f rgba8888\n%s.png\n' % name)
    icon = build_icon()
    banner = build_banner()
    write_png(icon, os.path.join(ROOT, 'banner', 'icon.png'))
    write_png(banner, os.path.join(ROOT, 'banner', 'banner.png'))
    write_header(os.path.join(ROOT, 'source', 'atlas.h'))
    if preview:
        # magnified contact sheets for eyeballing
        top = spr.a[0:160]
        Image.fromarray(scaled(top, 4), 'RGBA').save(preview + '_frogs.png')
        mid = spr.a[160:208, 0:512]
        Image.fromarray(scaled(mid, 3), 'RGBA').save(preview + '_objs.png')
        font = spr.a[FONT_Y:FONT_Y + 8, 0:512]
        Image.fromarray(scaled(font, 3), 'RGBA').save(preview + '_font.png')
        Image.fromarray(scaled(bg.a[0:376, 0:200], 2), 'RGBA').save(preview + '_bg.png')
        Image.fromarray(scaled(banner, 3), 'RGBA').save(preview + '_banner.png')
        Image.fromarray(scaled(icon, 6), 'RGBA').save(preview + '_icon.png')
        Image.fromarray(scaled(ui.a, 3), 'RGBA').save(preview + '_ui.png')
    print('art written')


if __name__ == '__main__':
    main()
