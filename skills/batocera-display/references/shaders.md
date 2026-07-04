# Shaders

Detail behind the shader section of the skill. Shaders are GPU-cost-heavy — a
weak arcade-cabinet iGPU can run a plain CRT preset at 1080p but chokes on a
full beam-simulation multi-pass stack. Match the shader to the hardware, and
verify framerate as well as appearance (see `batocera-tuning` for the framerate
side).

## Assigning shaders

- `<system>.shaderset=<name>` — a shaderset folder. Resolves against **both**
  `/userdata/shaders/configs/<name>/` and
  `/usr/share/batocera/shaders/configs/<name>/`. Built-in short names can be
  aliases to a deep preset path — don't declare one invalid by grepping only the
  user dir.
- `<system>-renderer.shader=<path>` — a direct `.slangp` (relative to the
  shaders dir or absolute). Use for plain CRT presets and custom wrappers.
- Per-game override: `<system>["<exact rom filename>"]-renderer.shader=<path>`.
  Exact filename with extension; no globs (see `batocera-ops` → batocera-conf).

The launch log is the source of truth for what actually ran:
`grep -i 'set-shader' /userdata/system/logs/es_launch_stdout.log`.

## Signal-accurate assignment

A defensible way to pick CRT presets is by the console's real output signal:

- **RGB / arcade** (Neo Geo, most arcade boards) — sharpest mask preset.
- **S-Video** (SNES, PlayStation on many setups) — an S-Video CRT preset.
- **Composite** (most 8/16-bit home consoles) — a composite preset with dot
  crawl / bleed.

The point is consistency and period feel, not a single "best" shader. Pick a
scheme and apply it per system.

## Anti-moiré inside custom-viewport bezels

The problem, precisely: a CRT mask shader interferes with the game's pixel grid
when the game is scaled by a non-integer factor, producing rainbow moiré banding.
The normal fix is integer scaling (`video_scale_integer = true`), **but RetroArch
ignores `video_scale_integer` when a custom viewport is set** — and a bezel that
forces a custom viewport (fractional `custom_viewport_x/y/width/height`) does
exactly that. So integer scaling is off the table inside those bezels.

Workaround — change how the mask is sampled instead of how the game is scaled:

```
# /userdata/shaders/custom/crt-royale-nomoire.slangp
#reference "shaders/crt/crt-royale.slangp"
mask_sample_mode_desired = "1"
```

Then point the affected systems at it:

```
fbneo-renderer.shader=custom/crt-royale-nomoire
mame-renderer.shader=custom/crt-royale-nomoire
neogeo-renderer.shader=custom/crt-royale-nomoire
```

`mask_sample_mode_desired=1` selects a scale-tolerant mask sampling that survives
the fractional scale a bezel viewport imposes. **Verify with before/after
framebuffer screenshots** — moiré is a visual artifact; a config diff proves
nothing. Capture the same game at the same viewport before and after.

## Display mode pinning

If the display renegotiates EDID (common when a TV is CEC power-cycled by home
automation) it may land on an off mode (59.94Hz, interlaced) that hurts shader
timing. Pin it:

```
es.resolution=1920x1080.60.00
```

**In `/userdata/system/batocera.conf`, not `/boot/batocera-boot.conf`** — the
boot conf's lower section is auto-synced from batocera.conf on each boot, so a
direct boot-conf edit is blanked. Confirm after reboot:
`grep -i resolution /userdata/system/logs/display.log`.

## Cost note

A 19-pass beam-sim + upscaler + CRT-royale stack can drop a weak iGPU to ~1 fps
at 1080p while plain CRT-royale runs full speed. When a shader "doesn't work,"
check framerate before assuming the config is wrong — it may be running fine and
just too slow to be usable. That diagnostic lives in `batocera-tuning`.
