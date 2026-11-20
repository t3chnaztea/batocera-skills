#!/usr/bin/env python3
"""Move a finished bezel onto a different opening without stretching the whole image.

Nine-slice resize: the side panels, the top and bottom lip, and the centre are
each resized on their own. Art on the side panels keeps its shape much better
than with one global stretch. Use it to make a per-system variant of a bezel,
for example a 1440x1080 opening for a standalone emulator that draws a 4:3
picture at full height.

Usage:
  python3 reslice_bezel.py <in.png> <out.png> <left> <top> <right> <bottom>

The opening of <in.png> is read from its alpha channel. The four numbers are the
margins of the new opening. Write the matching .info yourself.

Needs: pillow, numpy.
"""
import sys

import numpy as np
from PIL import Image

im = Image.open(sys.argv[1]).convert("RGBA")
W, H = im.size
L, T, R, B = map(int, sys.argv[3:7])
ys, xs = np.where(np.asarray(im)[..., 3] < 128)
sx = [0, int(xs.min()), int(xs.max()) + 1, W]
sy = [0, int(ys.min()), int(ys.max()) + 1, H]
dx, dy = [0, L, W - R, W], [0, T, H - B, H]
out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
for i in range(3):
    for j in range(3):
        if dx[i + 1] > dx[i] and dy[j + 1] > dy[j] and sx[i + 1] > sx[i] and sy[j + 1] > sy[j]:
            part = im.crop((sx[i], sy[j], sx[i + 1], sy[j + 1])).resize((dx[i + 1] - dx[i], dy[j + 1] - dy[j]), Image.LANCZOS)
            out.paste(part, (dx[i], dy[j]))
out.save(sys.argv[2], optimize=True)
print(f"opening {sx[1]},{sy[1]}-{sx[2]},{sy[2]} -> {L},{T}-{W - R},{H - B}")
