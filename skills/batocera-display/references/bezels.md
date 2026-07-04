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
