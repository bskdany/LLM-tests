#!/usr/bin/env python3
import os, sys, time, math, random

cols, rows = os.get_terminal_size()
rows -= 1

DENSITY = " .,:;+=xX#%@"

random.seed(time.time())
clouds = []
for _ in range(5):
    cx, cy = random.uniform(0, cols), random.uniform(2, rows * 0.55)
    blobs = []
    for _ in range(random.randint(5, 10)):
        bx = cx + random.gauss(0, 9)
        by = cy + random.gauss(0, 1.8)
        rx = random.uniform(4, 10)
        ry = random.uniform(2, 4.5)
        blobs.append((bx, by, rx, ry))
    clouds.append((blobs, random.uniform(0.4, 1.8)))

sys.stdout.write("\033[?25l\033[2J")
t = 0.0
try:
    while True:
        buf = []
        for y in range(rows):
            row = []
            for x in range(cols):
                d = 0.0
                for blobs, speed in clouds:
                    for bx, by, rx, ry in blobs:
                        wx = (bx + t * speed) % cols
                        dx = x - wx
                        if dx > cols / 2: dx -= cols
                        if dx < -cols / 2: dx += cols
                        dy = y - by
                        v = (dx / rx) ** 2 + (dy / ry) ** 2
                        if v < 1:
                            d += (1 - v) ** 1.5
                idx = min(int(d * (len(DENSITY) - 1) / 1.3), len(DENSITY) - 1)
                row.append(DENSITY[idx])
            buf.append("".join(row))
        sys.stdout.write("\033[H" + "\n".join(buf))
        sys.stdout.flush()
        t += 0.3
        time.sleep(0.05)
except KeyboardInterrupt:
    sys.stdout.write("\033[?25h\033[2J\033[H")
