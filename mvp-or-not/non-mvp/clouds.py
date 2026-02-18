#!/usr/bin/env python3
"""
Volumetric ASCII Cloud Visualization

Generative cloud system with multiple parallax layers, procedural
simplex noise, fractal Brownian motion, sky gradient, and a sun.
"""

import curses
import math
import time
import random
import locale

# ---------------------------------------------------------------------------
# Simplex noise (2-D)
# ---------------------------------------------------------------------------

_F2 = 0.5 * (math.sqrt(3.0) - 1.0)
_G2 = (3.0 - math.sqrt(3.0)) / 6.0

_GRAD2 = ((1, 1), (-1, 1), (1, -1), (-1, -1),
           (1, 0), (-1, 0), (0, 1), (0, -1))


def _build_perm(seed: int):
    rng = random.Random(seed)
    p = list(range(256))
    rng.shuffle(p)
    return (p + p)


def simplex2(x: float, y: float, perm) -> float:
    s = (x + y) * _F2
    i = math.floor(x + s)
    j = math.floor(y + s)

    t = (i + j) * _G2
    x0 = x - (i - t)
    y0 = y - (j - t)

    i1, j1 = (1, 0) if x0 > y0 else (0, 1)

    x1 = x0 - i1 + _G2
    y1 = y0 - j1 + _G2
    x2 = x0 - 1.0 + 2.0 * _G2
    y2 = y0 - 1.0 + 2.0 * _G2

    ii = int(i) & 255
    jj = int(j) & 255

    def _contrib(gx, gy, dx, dy):
        ct = 0.5 - dx * dx - dy * dy
        if ct <= 0:
            return 0.0
        ct *= ct
        return ct * ct * (gx * dx + gy * dy)

    gi0 = _GRAD2[perm[ii + perm[jj]] & 7]
    gi1 = _GRAD2[perm[ii + i1 + perm[jj + j1]] & 7]
    gi2 = _GRAD2[perm[ii + 1 + perm[jj + 1]] & 7]

    n = (_contrib(*gi0, x0, y0) +
         _contrib(*gi1, x1, y1) +
         _contrib(*gi2, x2, y2))
    return 70.0 * n


def fbm(x, y, perm, *, octaves=5, lacunarity=2.0, gain=0.5):
    value = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        value += amp * simplex2(x * freq, y * freq, perm)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return value / norm

# ---------------------------------------------------------------------------
# Cloud layer
# ---------------------------------------------------------------------------

class CloudLayer:
    __slots__ = ("speed", "scale", "threshold", "y_off", "octaves",
                 "density_bias", "perm")

    def __init__(self, speed, scale, threshold, y_off, seed,
                 density_bias=0.0, octaves=5):
        self.speed = speed
        self.scale = scale
        self.threshold = threshold
        self.y_off = y_off
        self.octaves = octaves
        self.density_bias = density_bias
        self.perm = _build_perm(seed)

    def sample(self, x, y, t):
        nx = (x + t * self.speed) * self.scale
        ny = (y + self.y_off) * self.scale
        v = fbm(nx, ny, self.perm, octaves=self.octaves)
        v = (v + 1.0) * 0.5 + self.density_bias
        if v < self.threshold:
            return 0.0
        return min(1.0, (v - self.threshold) / (1.0 - self.threshold))

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

DENSITY_UNI = " .·:;░▒▓█"
DENSITY_ASC = " .:-=+*#%@"


def _detect_unicode():
    try:
        "░▒▓█".encode("utf-8")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _setup_colors():
    curses.start_color()
    curses.use_default_colors()
    rich = curses.can_change_color() and curses.COLORS >= 256
    if rich:
        curses.init_pair(1, 255, -1)    # bright white
        curses.init_pair(2, 252, -1)    # light grey
        curses.init_pair(3, 249, -1)    # mid grey
        curses.init_pair(4, 243, -1)    # dark grey
        curses.init_pair(5, 117, -1)    # sky blue
        curses.init_pair(6, 153, -1)    # pale blue
        curses.init_pair(7, 229, -1)    # sun glow
        curses.init_pair(8, 223, -1)    # sun rays
        curses.init_pair(9, 22,  -1)    # ground green
        curses.init_pair(10, 240, -1)   # status dim
    else:
        curses.init_pair(1, curses.COLOR_WHITE, -1)
        curses.init_pair(2, curses.COLOR_WHITE, -1)
        curses.init_pair(3, curses.COLOR_CYAN, -1)
        curses.init_pair(4, curses.COLOR_BLUE, -1)
        curses.init_pair(5, curses.COLOR_CYAN, -1)
        curses.init_pair(6, curses.COLOR_BLUE, -1)
        curses.init_pair(7, curses.COLOR_YELLOW, -1)
        curses.init_pair(8, curses.COLOR_YELLOW, -1)
        curses.init_pair(9, curses.COLOR_GREEN, -1)
        curses.init_pair(10, curses.COLOR_WHITE, -1)
    return rich


def _cloud_attr(density, layer, rich):
    if rich:
        if layer == 0:
            if density > 0.7:
                return curses.color_pair(4)
            return curses.color_pair(3)
        if layer == 1:
            if density > 0.6:
                return curses.color_pair(3)
            if density > 0.3:
                return curses.color_pair(2)
            return curses.color_pair(1)
        if density > 0.65:
            return curses.color_pair(1) | curses.A_BOLD
        if density > 0.35:
            return curses.color_pair(2) | curses.A_BOLD
        return curses.color_pair(1)
    # fallback
    if layer == 2:
        return curses.color_pair(1) | curses.A_BOLD
    if layer == 1:
        return curses.color_pair(2)
    return curses.color_pair(3)

# ---------------------------------------------------------------------------
# Decorative elements
# ---------------------------------------------------------------------------

_SUN = [
    r"    .  ",
    r" \  |  / ",
    r"-- (bg) --",
    r" /  |  \ ",
    r"    '  ",
]

_SUN_CORE = [
    r"   ",
    r"   ",
    r"(@)",
    r"   ",
    r"   ",
]


def _draw_sun(scr, h, w, rich):
    cx, cy = int(w * 0.82), max(3, int(h * 0.12))
    attr_ray = curses.color_pair(8) if rich else curses.color_pair(7)
    attr_core = (curses.color_pair(7) | curses.A_BOLD) if rich else (curses.color_pair(7) | curses.A_BOLD)
    for dy, line in enumerate(_SUN):
        for dx, ch in enumerate(line):
            px = cx + dx - len(line) // 2
            py = cy + dy - 2
            if 0 <= px < w and 0 <= py < h and ch != ' ':
                try:
                    scr.addch(py, px, ch, attr_ray)
                except curses.error:
                    pass
    for dy, line in enumerate(_SUN_CORE):
        for dx, ch in enumerate(line):
            px = cx + dx - len(line) // 2
            py = cy + dy - 2
            if 0 <= px < w and 0 <= py < h and ch != ' ':
                try:
                    scr.addch(py, px, ch, attr_core)
                except curses.error:
                    pass


def _draw_ground(scr, h, w, perm, rich):
    y = h - 2
    attr = curses.color_pair(9) if rich else curses.color_pair(9)
    for x in range(w):
        v = simplex2(x * 0.08, 77.7, perm)
        ch = '▁' if v > 0.1 else '▂' if v > -0.2 else '▃'
        try:
            scr.addch(y, x, ch, attr)
        except curses.error:
            pass

# ---------------------------------------------------------------------------
# Vertical envelope — shapes the cloud band
# ---------------------------------------------------------------------------

def _vert_weight(ratio):
    """Bell-ish curve: clouds live in the upper-mid portion of the screen."""
    center = 0.30
    width = 0.28
    d = abs(ratio - center) / width
    if d >= 1.0:
        return 0.0
    return math.cos(d * math.pi * 0.5) ** 2

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(40)

    rich = _setup_colors()
    uni = _detect_unicode()
    density_ramp = DENSITY_UNI if uni else DENSITY_ASC
    ramp_len = len(density_ramp)

    master_seed = random.randint(0, 100_000)
    ground_perm = _build_perm(master_seed + 999)

    layers = [
        CloudLayer(speed=0.8,  scale=0.025, threshold=0.52,
                   y_off=300, seed=master_seed + 200, density_bias=0.04, octaves=3),
        CloudLayer(speed=1.5,  scale=0.035, threshold=0.46,
                   y_off=150, seed=master_seed + 100, density_bias=0.07, octaves=4),
        CloudLayer(speed=2.8,  scale=0.05,  threshold=0.42,
                   y_off=0,   seed=master_seed,       density_bias=0.10, octaves=5),
    ]

    t = 0.0
    start = time.monotonic()
    frames = 0

    while True:
        key = stdscr.getch()
        if key in (ord('q'), ord('Q'), 27):
            break

        height, width = stdscr.getmaxyx()
        cloud_h = height - 2
        if cloud_h < 4 or width < 10:
            stdscr.erase()
            stdscr.addstr(0, 0, "Terminal too small")
            stdscr.refresh()
            time.sleep(0.1)
            continue

        stdscr.erase()

        _draw_sun(stdscr, cloud_h, width, rich)

        # --- composit cloud layers (back → front) ---
        step = 2 if width > 200 else 1
        for y in range(cloud_h):
            vr = y / cloud_h
            vw = _vert_weight(vr)
            if vw < 0.01:
                continue
            x = 0
            while x < width:
                best_d = 0.0
                best_l = 0
                for li, layer in enumerate(layers):
                    d = layer.sample(x, y, t) * vw
                    if d > best_d:
                        best_d = d
                        best_l = li
                if best_d > 0.02:
                    idx = int(best_d * (ramp_len - 1))
                    idx = max(0, min(ramp_len - 1, idx))
                    ch = density_ramp[idx]
                    if ch != ' ':
                        attr = _cloud_attr(best_d, best_l, rich)
                        try:
                            stdscr.addch(y, x, ch, attr)
                        except curses.error:
                            pass
                x += step

        _draw_ground(stdscr, height, width, ground_perm, rich)

        frames += 1
        elapsed = time.monotonic() - start
        fps = frames / max(0.001, elapsed)
        status = f" Volumetric ASCII Clouds │ {width}×{height} │ {fps:.0f} FPS │ Press [q] to quit "
        try:
            attr_s = curses.color_pair(10) | curses.A_DIM if rich else curses.A_REVERSE
            stdscr.addnstr(height - 1, 0, status, width - 1, attr_s)
        except curses.error:
            pass

        stdscr.refresh()
        t += 0.35


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(main)
