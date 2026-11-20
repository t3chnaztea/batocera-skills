# Bezels

Detail behind the bezel section: how `.info` sidecars really work, generating
missing ones, filtering unusable ones, the large-library fallback strategy, and
the Mega-Bezel per-game-art postmortem.

## Anatomy

A bezel is a full-screen PNG with a transparent cutout where the game shows.
Packs live at `/userdata/decorations/<pack>/`; per-game art at
`.../games/<system>/<rom>.png` with a `.png.info` (or `<rom>.info`) sidecar. The
`.info` is JSON describing the viewport:

```json
{ "width": 1920, "height": 1080,
  "top": 33, "left": 250, "bottom": 40, "right": 250,
  "opacity": 1.0, "messagex": 0.22, "messagey": 0.12 }
```

`top/left/bottom/right` are insets (pixels from each edge) defining where the
game viewport sits.

## `.info` values are artistic intent, not alpha coordinates

**The trap that costs the most iterations.** When a game is misaligned inside the
cutout, you fix `top` (usually) — but `top` is **not** the y-offset of the first
transparent pixel. It is where the artist intends the game's top edge to sit,
which is frequently *above* the fully-transparent region because the top of the
bezel art is semi-transparent and the game is designed to extend behind it.

Concretely: a bezel whose alpha-transparent area starts at y=128 may want
`top=33` — i.e. the game extends ~95px *up behind* the artwork. Autodetecting the
alpha bbox and setting `top=128` moves the game the **wrong way** (down).

Method that works:
1. Back up the `.info`:
   `cp x.png.info x.png.info.bak-$(date +%Y%m%d-%H%M%S)`.
2. Launch the game, screenshot (the `batocera-ops` verify loop).
3. Nudge `top` in ~20px steps: **smaller = game moves up, larger = down.**
4. Repeat until the viewport top aligns. `left`/`right`/`bottom` usually ship
   correct; horizontal is rarely off.

After a launch, the applied viewport shows up as
`custom_viewport_x/y/width/height` in
`/userdata/system/configs/retroarch/retroarchcustom.cfg`, and the bezel file used
is logged in `es_launch_stdout.log` (`getBezelInfos Original bezel file used:`).

## Generating missing `.info` sidecars

Some packs ship PNGs without `.info` files (thebezelproject ships thousands
missing sidecars across dozens of systems). With no sidecar, configgen guesses a
viewport heuristically and often renders the game undersized/top-anchored.

`generate_tbp_info.py` fixes this correctly: it **alpha-detects the transparent
cutout** and writes a proportionally-scaled `.info`. This is the *right* use of
alpha detection — sizing an otherwise-missing sidecar — distinct from the
misalignment fix above (which is artistic and eyeballed). The script:

- Never overwrites an existing `.info` (safe to re-run, safe on packs where some
  sidecars exist).
- Skips PNGs with no real cutout (< 2% transparent, or a viewport under 10% of
  either dimension) — e.g. full-overlay art with no screen hole. Those correctly
  get no sidecar.
- Scales the detected viewport to the target 1920×1080 if the PNG differs.

Run per-system or `--all`. Sanity-check a couple of results with the verify loop.

## Filtering unusable bezels

`filter_small_bezels.py` moves bezels whose cutout's **shorter dimension** is
below a pixel threshold into a `filtered_too_small/` subdir, so Batocera's
per-ROM lookup misses them and falls back to the pack default. Shorter-dimension
is the right metric: it binds on height for horizontal cabinets and on width for
vertical ones. `--dry-run` first; reverse any time with
`mv filtered_too_small/* .`.

## Large-library fallback strategy

When a pack only has real art for a fraction of a big system, the un-arted
majority falls back to a generic system bezel that often looks worse than no
bezel. Invert the default:

- **System default:** a clean shader frame (e.g. a Koko-AIO ambilight preset)
  with `<system>.bezel=none`.
- **Per-game overrides:** only the ROMs that *have* real art get
  `<system>["<rom>"].bezel=<pack>` plus their period-appropriate shader.

`snes-bezel-fallback.py` implements this for SNES: it reads which ROMs have art,
writes a marker-delimited generated block of per-game overrides, sets the system
shader to the Koko fallback, and backs up `batocera.conf` first. It's idempotent
(regenerates its own block) and shows how to handle a special sub-group (SuperFX
titles pinned to a different shader) with exact-filename keys. Adapt the paths
and the "which ROMs have art" source to your pack.

## Building a fallback bezel from a green-screen picture

The pack-level `default.png` renders for every game that has no art of its own.
Replacing it is a small change with a wide effect, and it needs no `.info`
edit if the new image is cut to the viewport the old one used.

**Source picture.** Any straight-on picture of a monitor surround works. The
screen must be one flat `#00FF00` area with no reflections or gradients, and
nothing else in the picture may be green. With an image model, say exactly
that, and ask for a 16:9 frame.

**Convert.** Read the four margins from the current `default.info`, then:

```bash
python3 make_bezel_from_green.py source.png default.png <left> <top> <right> <bottom>
python3 bezel_preview.py some-game-screenshot.png <left> <top> <right> <bottom> default.png
```

The first script scales the picture so the green box lands exactly on the
viewport, turns it transparent, and removes the green fringe. The second writes
a mock and prints the corner cover.

**Corner trap.** A realistic CRT opening has round corners. On a 1387x1062
viewport a "natural" generated bezel hid 41 px along each corner diagonal, which
cut the first letter off a credit counter. Asking for "nearly square corners,
radius about 2 percent of the screen width" brought that down to 8 px. Check
the number before you install; do not judge it by eye on a dark frame.

**Side art trap.** The source picture is usually wider than what ends up on
screen, because the side panels get cropped when the opening is scaled to the
viewport. Stickers or text placed on the panels get cut off. To add side art,
first make the plain bezel, composite it over flat green at the final
resolution, and give that composite to the image model as the reference with
the instruction to keep framing and positions exactly. The output then maps
almost 1:1 and nothing is cropped.

**Install and verify.** Back up the old `default.png`, copy the new one in with
mode 644, launch a game that uses the fallback, and take a screenshot. Check
that text in the picture corners is complete.

## Standalone emulators: the bezel is an overlay, not a viewport

For libretro cores the launcher writes a custom viewport from the `.info`, so
the picture always sits inside the opening. For most standalone emulators the
`.info` only decides whether the bezel is accepted. The bezel is then drawn as
a full-screen overlay, and the launcher assumes the game fills a 4:3 box at
full height (or 16:9 when the emulator is set to widescreen). Consequences:

- A bezel with a 1387 px wide opening covers about 26 px on each side of a
  1440 px wide picture.
- An emulator "auto" aspect that picks 3:2 for progressive output draws 1620 px
  wide, and the bezel covers much more.

Fix per system:

1. Set the emulator's aspect option to 4:3 for that system in `batocera.conf`.
2. Make a system bezel (`<pack>/systems/<system>.png` + `.info`) whose opening
   is the 4:3 box. `reslice_bezel.py` nine-slices an existing bezel onto the
   new opening, so the side panels and any art on them are not stretched:

```bash
python3 reslice_bezel.py default.png systems/<system>.png 240 0 240 0
```

**Small picture in a screen corner.** If a standalone emulator shows the game
as a 640x480 box in the bottom-left corner of a black screen on some launches
and full screen on others, the bezel is not the cause. The window is full
screen but the OpenGL renderer kept its start-up surface size. It happens with
and without a bezel. On a PCSX2-based arcade emulator this hit 5 of 6 launches
with the automatic (OpenGL) renderer and 0 of 6 with Vulkan, so set that
system's graphics API to Vulkan. Test with several launches in a row and one
screenshot each; a single good launch proves nothing.

## Mega-Bezel per-game cabinet art: a documented dead end

Combining Mega-Bezel's photoreal CRT rendering with **per-game** cabinet-art
bezels does not work on Batocera. Don't spend a day on it. The failure modes,
verified across multiple attempts:

1. **Stale bezel symlink.** Batocera's `writeBezelConfig` returns `bezel: None`
   for these launches even with `<system>.bezel=<pack>` set and the per-game PNG
   present. The runtime symlink (`/var/run/shader_bezels/bezel.png`) is never
   updated, so every game renders with whatever bezel the *previous* launch left
   symlinked — wrong art on almost every game.
2. **Rotation not propagated.** Mega-Bezel renders the framebuffer as-given and
   doesn't see Batocera's `video_rotation` transform, so vertical arcade games
   render sideways inside the cutout.
3. **Cutout variance can't be bracketed.** Per-game bezel cutouts vary wildly in
   size (from ~15% to 100% of screen area). A single global scale offset can't
   fit both a tiny cutout and a full-screen one; roughly half render wrong.

**The false positive that fools you:** testing one horizontal game right after
pushing the config "works" because (a) horizontal games don't expose the rotation
bug, (b) that game happens to be the one that populated the symlink so it's not
stale for that test, and (c) its cutout happens to match your global offset.
**Never declare a Batocera shader/bezel setup working from a single ROM.** Verify
across at least: one vertical game, one game launched *after a different game*
(so a stale symlink would show), and one game from a different bezel family.

The only known working "shader + bezel art" combo on Batocera is the Koko-AIO /
Duimon shaderset, which uses **one generic cabinet frame for all arcade games** —
fine if you want a uniform look, not a per-game cabinet-art solution.
