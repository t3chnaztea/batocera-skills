#!/usr/bin/env python3
"""Mock a bezel over a game screenshot and measure how much picture its corners hide.

Usage:
  python3 bezel_preview.py <game.png> <left> <top> <right> <bottom> <bezel.png> [<bezel.png> ...]

Writes <bezel>-prev.jpg next to each bezel. Prints, per corner, the number of
pixels along the 45 degree diagonal that the bezel covers. A CRT-style rounded
opening can hide 40 px of picture in each corner; score and credit text often
sits there.

Needs: pillow, numpy.
"""
import sys

import numpy as np
from PIL import Image

game_path = sys.argv[1]
L, T, R, B = map(int, sys.argv[2:6])
for p in sys.argv[6:]:
    b = Image.open(p).convert("RGBA")
    W, H = b.size
    game = Image.open(game_path).convert("RGB").resize((W - L - R, H - T - B), Image.LANCZOS)
    c = Image.new("RGB", (W, H), (0, 0, 0))
    c.paste(game, (L, T))
    c.paste(b, (0, 0), b)
    c.save(p.rsplit(".", 1)[0] + "-prev.jpg", quality=88)
    a = np.asarray(b)[..., 3]
    cuts = []
    for x, y, dx, dy in ((L, T, 1, 1), (W - R - 1, T, -1, 1), (L, H - B - 1, 1, -1), (W - R - 1, H - B - 1, -1, -1)):
        n = 0
        while a[y + dy * n, x + dx * n] > 128:
            n += 1
        cuts.append(n)
    print(p, "corner cover px (TL TR BL BR):", cuts)
