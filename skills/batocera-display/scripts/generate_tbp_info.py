#!/usr/bin/env python3
"""Generate .info sidecar files for bezel-pack PNGs by autodetecting the alpha
cutout in each PNG.

Some decoration packs (thebezelproject in particular) ship per-game bezel PNGs
without the .info sidecar that tells configgen where the game viewport goes.
Without it, configgen guesses a viewport heuristically and the game often renders
undersized or top-anchored inside the cutout. This detects the transparent cutout
and writes a correct .info.

Safety: NEVER overwrites an existing .info file. Skips PNGs whose cutout is too
small (<2% transparent, or a viewport under 10% of either dimension) to be a real
screen hole -- e.g. full-overlay art -- which correctly get no sidecar.

Point BASE at your pack. Usage:
  python3 generate_tbp_info.py <system> [<system> ...]
  python3 generate_tbp_info.py --all
"""
import json
import sys
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError as e:
    print("Missing dep: %s" % e)
    sys.exit(1)

BASE = Path("/userdata/decorations/thebezelproject/games")
TARGET_W, TARGET_H = 1920, 1080


def detect_viewport(img):
    """Return {top,left,bottom,right} in pixels of the transparent area, or None."""
    alpha = np.array(img)[:, :, 3]
    mask = alpha < 10
    if mask.sum() / mask.size < 0.02:
        return None
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return None
    top = int(rows[0])
    left = int(cols[0])
    bottom = int(img.height - rows[-1] - 1)
    right = int(img.width - cols[-1] - 1)
    vp_w = img.width - left - right
    vp_h = img.height - top - bottom
    if vp_w < img.width * 0.10 or vp_h < img.height * 0.10:
        return None
    return {"top": top, "left": left, "bottom": bottom, "right": right}


def make_info(vp, w=TARGET_W, h=TARGET_H):
    return {
        "width": w,
        "height": h,
        "top": vp["top"],
        "left": vp["left"],
        "bottom": vp["bottom"],
        "right": vp["right"],
        "opacity": 1.0,
        "messagex": 0.22,
        "messagey": 0.12,
    }


def process_system(system):
    sys_dir = BASE / system
    if not sys_dir.exists():
        print("  %s: directory missing" % system)
        return 0, 0, 0
    written, skipped_existing, skipped_no_viewport = 0, 0, 0
    for png in sorted(sys_dir.glob("*.png")):
        info_path = png.with_suffix(".info")
        if info_path.exists():
            skipped_existing += 1
            continue
        try:
            img = Image.open(png).convert("RGBA")
            img.load()
        except Exception:
            skipped_no_viewport += 1
            continue
        vp = detect_viewport(img)
        if vp is None:
            skipped_no_viewport += 1
            continue
        # If PNG isn't 1920x1080, scale the viewport proportionally
        sx = TARGET_W / img.width
        sy = TARGET_H / img.height
        vp_scaled = {
            "top": int(round(vp["top"] * sy)),
            "left": int(round(vp["left"] * sx)),
            "bottom": int(round(vp["bottom"] * sy)),
            "right": int(round(vp["right"] * sx)),
        }
        info = make_info(vp_scaled)
        with open(info_path, "w") as f:
            json.dump(info, f, indent=3)
        written += 1
    print("  %s: wrote %d, skipped existing %d, skipped no-viewport %d" % (
        system, written, skipped_existing, skipped_no_viewport))
    return written, skipped_existing, skipped_no_viewport


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args == ["--all"]:
        systems = [d.name for d in BASE.iterdir() if d.is_dir()]
    else:
        systems = args
    print("Generating .info files for systems: %s" % ", ".join(systems))
    print()
    total_w, total_se, total_sn = 0, 0, 0
    for s in systems:
        w, se, sn = process_system(s)
        total_w += w
        total_se += se
        total_sn += sn
    print()
    print("TOTAL: wrote %d, skipped existing %d, skipped no-viewport %d" % (
        total_w, total_se, total_sn))


if __name__ == "__main__":
    main()
