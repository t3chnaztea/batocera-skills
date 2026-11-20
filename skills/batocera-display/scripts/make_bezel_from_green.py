#!/usr/bin/env python3
"""Turn a bezel picture with a flat green screen into a Batocera bezel PNG.

Input: any frontal picture of a monitor surround (photo, render, generated image)
whose screen area is one flat chroma green (#00FF00). The script finds the green
area, scales the picture so that area lands exactly on the viewport you give,
cuts it to transparency, and removes green spill on the edge.

Usage:
  python3 make_bezel_from_green.py <in.png> <out.png> <left> <top> <right> <bottom> [--size 1920x1080]

<left> <top> <right> <bottom> are the four margins of the viewport, the same
numbers that go in the bezel's .info file. Write that .info yourself; this
script does not create it.

Needs: pillow, numpy.
"""
import argparse

import numpy as np
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("margins", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
ap.add_argument("--size", default="1920x1080")
args = ap.parse_args()
W, H = map(int, args.size.split("x"))
L, T, R, B = args.margins

im = Image.open(args.src).convert("RGB")
a = np.asarray(im).astype(int)
# green = bright G, dark R and B, and G well above both
mask = (a[..., 1] > 140) & (a[..., 0] < 130) & (a[..., 2] < 130) & (a[..., 1] - np.maximum(a[..., 0], a[..., 2]) > 60)
if not mask.any():
    raise SystemExit("no green screen area found")
ys, xs = np.where(mask)
x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
sx, sy = (W - L - R) / (x1 - x0), (H - T - B) / (y1 - y0)
nw, nh = round(im.width * sx), round(im.height * sy)
big = im.resize((nw, nh), Image.LANCZOS)
m = Image.fromarray((mask * 255).astype("uint8")).resize((nw, nh), Image.LANCZOS)
ox, oy = L - round(x0 * sx), T - round(y0 * sy)
canvas = Image.new("RGB", (W, H), (6, 6, 6))
canvas.paste(big, (ox, oy))
mk = Image.new("L", (W, H), 0)
mk.paste(m, (ox, oy))
# grow the hole a little and soften its edge so no green line is left
mk = mk.point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(1.2))
c = np.asarray(canvas).astype(int)
spill = c[..., 1] - np.maximum(c[..., 0], c[..., 2])
c[..., 1] = np.where(spill > 8, np.maximum(c[..., 0], c[..., 2]), c[..., 1])
out = np.dstack([c, 255 - np.asarray(mk).astype(int)]).astype("uint8")
Image.fromarray(out, "RGBA").save(args.dst, optimize=True)
print(f"green box {x0},{y0}-{x1},{y1}  scale {sx:.3f} x {sy:.3f}")
print(f"source picture covers x {ox}..{ox + nw}, y {oy}..{oy + nh} of the {W}x{H} canvas (gaps are filled near-black)")
