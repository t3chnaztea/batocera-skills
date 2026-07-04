#!/usr/bin/env python3
"""Filter out bezels whose screen cutout is too small to be practical.

Moves filtered .png + .info pairs to a sidecar `filtered_too_small/` subdirectory
inside each system's bezel folder. Batocera's per-ROM bezel lookup then misses
them and falls back to the pack default (e.g.
/userdata/decorations/<pack>/default.png).

Fully reversible: `mv filtered_too_small/* .` restores any individual bezel.

Threshold metric: the SHORTER of cutout width / cutout height. This handles both
horizontal cabinets (where height is the binding constraint) and vertical
cabinets (where width is the binding constraint).

Point BASE at your pack. Usage:
  python3 filter_small_bezels.py --dry-run                 # default systems, threshold 600
  python3 filter_small_bezels.py --threshold 550           # change threshold
  python3 filter_small_bezels.py --systems fbneo mame      # specific systems
  python3 filter_small_bezels.py --all                     # every system in the pack
  python3 filter_small_bezels.py                           # APPLY (no --dry-run)
"""
import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError as e:
    print("Missing dep: %s" % e)
    sys.exit(1)

BASE = Path("/userdata/decorations/authentic_arcade/games")
DEFAULT_THRESHOLD = 600
DEFAULT_SYSTEMS = ["fbneo", "mame"]


def measure_cutout(png_path):
    """Return (cut_w, cut_h) of the transparent area, or None if no cutout."""
    try:
        img = Image.open(png_path).convert("RGBA")
        img.load()
    except Exception:
        return None
    alpha = np.array(img)[:, :, 3]
    mask = alpha < 10
    if not mask.any():
        return None
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    cut_w = int(cols[-1] - cols[0] + 1)
    cut_h = int(rows[-1] - rows[0] + 1)
    return cut_w, cut_h


def process_system(system, threshold, dry_run):
    sys_dir = BASE / system
    if not sys_dir.exists():
        print("  %s: directory missing" % system)
        return [], []
    filtered_dir = sys_dir / "filtered_too_small"
    if not dry_run:
        filtered_dir.mkdir(exist_ok=True)

    to_filter = []
    keep = []
    for png in sorted(sys_dir.glob("*.png")):
        if png.parent.name == "filtered_too_small":
            continue
        dims = measure_cutout(png)
        if dims is None:
            continue
        cut_w, cut_h = dims
        short = min(cut_w, cut_h)
        rom = png.stem
        if short < threshold:
            to_filter.append((rom, cut_w, cut_h, short))
        else:
            keep.append((rom, cut_w, cut_h, short))

    print("  %s: %d total, would filter %d (short<%d), keep %d" % (
        system, len(to_filter) + len(keep), len(to_filter), threshold, len(keep)))

    if not dry_run:
        for rom, _, _, _ in to_filter:
            for suffix in (".png", ".info"):
                src = sys_dir / (rom + suffix)
                if src.exists():
                    src.rename(filtered_dir / src.name)

    return to_filter, keep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                    help="Min cutout shorter-dimension in pixels (default %d)" % DEFAULT_THRESHOLD)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--systems", nargs="+", help="Specific systems (default: %s)" % " ".join(DEFAULT_SYSTEMS))
    g.add_argument("--all", action="store_true", help="All systems under the pack's games/ dir")
    ap.add_argument("--dry-run", action="store_true", help="Print what would be filtered without moving files")
    ap.add_argument("--show-list", action="store_true", help="Print every filtered ROM (not just count)")
    args = ap.parse_args()

    if args.all:
        systems = sorted([d.name for d in BASE.iterdir() if d.is_dir() and d.name != "filtered_too_small"])
    elif args.systems:
        systems = args.systems
    else:
        systems = DEFAULT_SYSTEMS

    print("=" * 60)
    print("Filter bezels with cutout shorter dim < %d px" % args.threshold)
    print("Mode: %s" % ("DRY RUN" if args.dry_run else "APPLY"))
    print("Systems: %s" % ", ".join(systems))
    print("=" * 60)
    print()

    total_filter, total_keep = [], []
    for system in systems:
        to_filter, keep = process_system(system, args.threshold, args.dry_run)
        total_filter.extend([(system, *r) for r in to_filter])
        total_keep.extend([(system, *r) for r in keep])

    print()
    print("SUMMARY: would filter %d, would keep %d (total %d)" % (
        len(total_filter), len(total_keep), len(total_filter) + len(total_keep)))

    if args.show_list and total_filter:
        print()
        print("ROMs that would be filtered (smallest first):")
        for system, rom, cw, ch, short in sorted(total_filter, key=lambda x: x[4]):
            print("  %-10s %-25s cut=%dx%d short=%d" % (system, rom, cw, ch, short))


if __name__ == "__main__":
    main()
