#!/usr/bin/env python3
"""Render effect layers for a seasonal boot splash.

Writes into <outdir>:
  snow.mp4    white flakes on pure black (three sizes, slow sideways drift)
  bells.wav   quiet sleigh bells
  rumble.wav  low thunder, one strike per --strike time

Every layer is bright art on pure black, so make_season_splash.sh can put it on
the normal splash with the screen blend. No alpha channel is needed.

Usage:
  python3 make_splash_layers.py <outdir> [--seconds 9] [--size 1920x1080]
      [--fps 30] [--flakes 520] [--strike 1.9 --strike 5.5] [--seed 1]

Set --seconds to the length of your splash clip (ffprobe prints it).
Needs: pillow, numpy, and ffmpeg in PATH.
"""
import argparse
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("outdir")
ap.add_argument("--seconds", type=float, default=9.0)
ap.add_argument("--size", default="1920x1080")
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--flakes", type=int, default=520)
ap.add_argument("--strike", type=float, action="append", help="thunder time in seconds, repeatable")
ap.add_argument("--seed", type=int, default=1)
args = ap.parse_args()

W, H = map(int, args.size.split("x"))
SECS, FPS, SR = args.seconds, args.fps, 48000
strikes = args.strike or [SECS * 0.2, SECS * 0.6]
rng = np.random.default_rng(args.seed)
os.makedirs(args.outdir, exist_ok=True)


def out(name):
    return os.path.join(args.outdir, name)


def save_wav(name, samples):
    pcm = (np.clip(samples / np.max(np.abs(samples)), -1, 1) * 0.8 * 32767).astype(np.int16)
    with wave.open(out(name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# Snow. Bigger flakes fall faster and are brighter, which reads as depth.
n = args.flakes
x0, y0 = rng.uniform(0, W, n), rng.uniform(0, H, n)
size = rng.choice([1.2, 2.0, 3.2], n, p=[0.5, 0.33, 0.17]) * (H / 1080)
fall = size * rng.uniform(28, 44, n)
sway, phase = rng.uniform(8, 26, n), rng.uniform(0, 6.28, n)
ff = subprocess.Popen(
    ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
     "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", out("snow.mp4")],
    stdin=subprocess.PIPE,
)
for frame in range(int(SECS * FPS)):
    t = frame / FPS
    im = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(im)
    xs = (x0 + sway * np.sin(t * 0.9 + phase) + 12 * t) % W
    ys = (y0 + fall * t) % H
    for x, y, s in zip(xs, ys, size):
        draw.ellipse((x - s, y - s, x + s, y + s), fill=min(255, int(150 + 32 * s)))
    ff.stdin.write(im.filter(ImageFilter.GaussianBlur(0.8)).tobytes())
ff.stdin.close()
if ff.wait() != 0:
    raise SystemExit("ffmpeg failed to write snow.mp4")

t = np.arange(int(SECS * SR)) / SR

# Sleigh bells: a cluster of inharmonic partials, struck 8 times a second.
bells = np.zeros_like(t)
for k in range(int(SECS * 8)):
    start = k / 8 + rng.uniform(-0.012, 0.012)
    env = np.where(t >= start, np.exp(-(t - start) * 26), 0) * (1.0 if k % 2 == 0 else 0.6)
    for freq in rng.uniform(2600, 7200, 7):
        bells += env * np.sin(2 * np.pi * freq * t + rng.uniform(0, 6.28)) * rng.uniform(0.4, 1)
bells *= np.minimum(1, t / 0.6) * np.minimum(1, (SECS - t) / 1.2)
save_wav("bells.wav", bells)

# Thunder: low-passed noise with a slow decay. The first strike is the loudest
# and gets a short crack on top.
noise = rng.standard_normal(len(t))
low = np.convolve(noise, np.ones(400) / 400, mode="same") * 6 + np.convolve(noise, np.ones(60) / 60, mode="same")
rumble = np.zeros_like(t)
for i, start in enumerate(strikes):
    amp, decay = (1.0, 1.1) if i == 0 else (0.45, 0.8)
    rumble += np.where(t >= start, np.exp(-(t - start) * decay) * amp, 0) * low * (1 + 0.5 * np.sin(2 * np.pi * 3.1 * t))
first = strikes[0]
crack = np.where((t >= first) & (t < first + 0.15), noise * np.exp(-(t - first) * 30), 0)
save_wav("rumble.wav", rumble + crack * 0.35 * np.max(np.abs(rumble)))

print(f"wrote snow.mp4, bells.wav, rumble.wav to {args.outdir} ({SECS:g} s, {W}x{H}, {FPS} fps)")
