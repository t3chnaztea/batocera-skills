---
name: batocera-display
description: >-
  Use when working on how games look on a Batocera cabinet: CRT and other
  shaders, shaderset resolution and per-game shader overrides, bezel/overlay
  artwork and alignment, generating missing .info sidecars, filtering
  unusable bezels, pinning the display resolution, or diagnosing moire and
  cropped/misaligned game viewports inside bezels. Covers why a shaderset seems
  invalid, why .info top values are not alpha coordinates, and why Mega-Bezel
  per-game art fails. Not for performance/framerate tuning (batocera-tuning).
compatibility: Requires SSH access to a Batocera host (tested on v41-v44).
---

# Batocera Display

Shaders, bezels, and display mode — everything about how the picture looks.
Assumes the connection pattern, `batocera.conf`/configgen model, and verify loop
from `batocera-ops`. Because display changes are visual, the
`batocera-ops` **remote verify loop** (ES HTTP API launch + `batocera-screenshot`)
is your primary tool here: never declare a shader or bezel "working" from the
config alone — launch it and look.

## Shaders

Shaders are assigned per-system (or per-game) in `batocera.conf`. Two key
mechanisms and the traps around each.

### `shaderset` resolves against TWO search paths

`<system>.shaderset=<name>` is a **folder-name lookup** resolved against both:

1. `/userdata/shaders/configs/<name>/` (user-installed)
2. `/usr/share/batocera/shaders/configs/<name>/` (system-bundled)

Checking only one path is enough to wrongly declare a preset invalid. Some
built-in names are aliases that resolve to a preset deep under
`/usr/share/batocera/shaders/`. Before concluding a `shaderset` value is dead:

```bash
SSHB "find /userdata/shaders /usr/share/batocera/shaders -maxdepth 3 -iname '<name>*'"
```

And read the launch log for the shader actually used on the last launch — it is
authoritative:

```bash
SSHB "grep -i 'set-shader\|shader' /userdata/system/logs/es_launch_stdout.log | tail"
```

### Two shader keys: `shaderset` vs `-renderer.shader`

- `<system>.shaderset=<name>` — a Batocera shaderset folder (may bundle bezel
  art, e.g. Koko-AIO/Duimon presets).
- `<system>-renderer.shader=<path>` — a direct RetroArch `.slangp` path (relative
  to the shaders dir, or absolute). This is how you assign a plain CRT preset
  like `crt/crt-super-xbr` or a custom `.slangp`.

Per-game overrides use the exact-filename key from `batocera-ops` →
batocera-conf: `snes["Super Mario World (USA).sfc"]-renderer.shader=...`. A glob
(`snes["Star Fox*"]...`) **never matches**.

### Anti-moiré: integer scaling is impossible inside a custom-viewport bezel

A CRT mask shader (crt-royale and friends) can produce rainbow moiré when the
game isn't integer-scaled. The usual cure — `video_scale_integer` — **is ignored
for a custom viewport**, and bezels that force a custom RetroArch viewport (with
fractional coordinates) put you exactly there. So you cannot integer-scale inside
those bezels.

The workaround is to tame the mask instead of the scale: a wrapper `.slangp` that
`#reference`s the CRT preset and sets `mask_sample_mode_desired=1` (a
scale-tolerant mask sampling mode). Point the arcade systems' `-renderer.shader`
at the wrapper. Verify with before/after screenshots — this is precisely the kind
of change that must be seen, not assumed. Full detail in
[references/shaders.md](references/shaders.md).

### Pin the display mode in batocera.conf, not the boot conf

If a CEC-controlled TV renegotiates EDID on each wake and sometimes lands on
59.94Hz/1080i, pin it: `es.resolution=1920x1080.60.00`. This **must** go in
`/userdata/system/batocera.conf`, not `/boot/batocera-boot.conf` (the boot
conf's lower section is auto-synced from batocera.conf on boot and a direct edit
gets blanked). Confirm in `display.log` after a reboot.

## Bezels

Bezels/overlays are PNGs with a transparent "cutout" where the game shows,
plus a `.info` sidecar describing the viewport. Packs live under
`/userdata/decorations/<pack>/`, with per-game art at
`.../games/<system>/<rom>.png` (+ `.png.info`).

### `.info` coordinates are artistic intent, NOT the alpha cutout

The single biggest bezel trap. When a game renders misaligned inside the cutout,
the fix is the `.info` sidecar's `top`/`left`/`bottom`/`right` — but **`top` is
not the PNG's transparent-pixel offset.** It's where the artist intends the
game's viewport edge to sit, often *above* the alpha cutout because the top
bezel artwork is semi-transparent and the game is meant to extend behind it.

Do **not** derive `.info top` from the alpha bounding box (autodetecting the
transparent region and using that as `top` moves the game the wrong way).
Instead: launch, screenshot, and nudge `top` in ~20px steps (smaller = game
moves up, larger = down). Back up the `.info` before each iteration. See
[references/bezels.md](references/bezels.md).

### Generating missing `.info` sidecars

Some packs (notably thebezelproject) ship thousands of PNGs **without** `.info`
files. Without a sidecar, configgen guesses a viewport heuristically and often
gets it wrong (undersized, top-anchored game). [scripts/generate_tbp_info.py](scripts/generate_tbp_info.py)
alpha-detects each PNG's cutout and writes a correct `.info`, never overwriting
an existing one. This is the correct use of alpha detection — sizing a *missing*
sidecar — as opposed to the misalignment fix above, which is artistic and
eyeballed.

### Filtering unusable bezels

Some bezels have a cutout so small the game is postage-stamped. [scripts/filter_small_bezels.py](scripts/filter_small_bezels.py)
moves any bezel whose cutout's shorter dimension is below a threshold into a
`filtered_too_small/` sidecar dir, so Batocera falls back to the pack default.
Fully reversible (`mv filtered_too_small/* .`).

### SNES (and similar) fallback strategy

When a pack has per-game art for only a fraction of a large library (e.g. ~50 of
~760 SNES ROMs) and everything else falls back to an ugly generic system bezel,
invert the default: set the system to a clean shader-frame look (a Koko-AIO
ambilight preset, `<system>.bezel=none`) and write **per-game overrides** only
for the ROMs that *do* have real art. [scripts/snes-bezel-fallback.py](scripts/snes-bezel-fallback.py)
is a ready-to-adapt implementation (idempotent, generates a marker block,
backs up `batocera.conf`).

### Make your own fallback bezel

`<pack>/default.png` + `default.info` is the bezel every game without its own
art gets, so one good file improves a lot of games. You can build one from any
frontal picture of a monitor surround (a photo, a render, an image-model
output) as long as the screen area is one flat chroma green.
[scripts/make_bezel_from_green.py](scripts/make_bezel_from_green.py) scales the
green area onto the viewport from the existing `.info` and cuts it to alpha, so
the `.info` stays unchanged. [scripts/bezel_preview.py](scripts/bezel_preview.py)
mocks the result over a game screenshot and prints how many pixels each corner
hides. Keep the old `default.png` as a backup, then launch a game and
screenshot it. The prompt rules and the corner trap are in
[references/bezels.md](references/bezels.md).

### Seasonal fallback bezel

Because the fallback is one file, it is also the cheapest place for a seasonal
look: string lights in December, and the normal bezel back in January.
[scripts/bezel_season.sh](scripts/bezel_season.sh) reads a season name from a
state file and copies that season's files over the live ones. A season with no
folder gets the default folder, so the normal bezel returns without a second
script. Call it at boot and from a boot-service timer loop (see
`batocera-maintenance`; there is no cron).

Build the seasonal variant from the finished normal bezel: draw the decoration
on top, then reuse the normal bezel's alpha channel, so the opening and the
`.info` do not change. Do not send art that contains green (holly, green
bulbs) through the chroma-key script. It cuts those pixels out with the screen.

Two rules for image-model prompts came from a cobweb and blood-spatter variant:

- Name each thing you do not want. "Dry cobwebs" still gave thick wet strands
  until the prompt also said no drips, no runs and no hanging clumps.
- Attach a reference picture for a texture that words describe badly. One
  photo of spatter fixed in one pass what three prompt rewrites did not.

Change one element per pass and tell the model to keep the rest unchanged.
To preview a season that is months away, copy its files over the live ones,
launch a game, take a screenshot, then run the season script to put the
current season back. Compare a checksum of the live file with the season file
to confirm the restore.

### Standalone emulators ignore the `.info` viewport

Libretro cores place the picture from the `.info`. Most standalone emulators do
not: the launcher draws the bezel as an overlay and assumes a 4:3 picture at
full screen height (1440x1080 on a 1080p display). A bezel with a smaller
opening then covers the picture edges, and a non-4:3 emulator ratio makes it
worse. Fix it per system: set the emulator's own aspect option to 4:3 and give
that system a bezel whose opening is the 4:3 box.
[scripts/reslice_bezel.py](scripts/reslice_bezel.py) converts an existing bezel
to the new opening without stretching the side art.

### Don't attempt per-game Mega-Bezel cabinet art

Combining Mega-Bezel's photoreal CRT with per-game cabinet-art bezels is a known
dead end on Batocera (stale bezel symlink returns `bezel: None`, rotation isn't
propagated to the shader, and per-game cutout variance can't be bracketed by one
global scale offset). The full postmortem — including the false-positive that
fools you into thinking it works after one ROM — is in
[references/bezels.md](references/bezels.md). Read it before spending a day on
this; the short version is *don't*.
