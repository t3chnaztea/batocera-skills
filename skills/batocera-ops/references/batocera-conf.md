# batocera.conf and the configgen model

The single most important thing to understand before editing any Batocera
setting: **most per-emulator config files are regenerated on every launch.**
Hand-editing them looks like it works, then silently reverts. This reference
explains where a setting must live to survive.

## The two layers

1. **`/userdata/system/batocera.conf`** — the source of truth. One flat file,
   `key=value`, comments with `#`. You edit this. It persists.
2. **Generated per-emulator configs** — at launch, Batocera's *configgen*
   (Python under `/usr/share/batocera/configgen/`) reads `batocera.conf`, then
   **writes fresh** RetroArch/standalone config files under
   `/userdata/system/configs/`. Your hand-edits to those generated files are
   overwritten by the next launch.

Rule of thumb: **write to `batocera.conf`, read the generated files to verify.**
The generated `retroarchcustom.cfg` and `retroarch-core-options.cfg` show what
the *last* launch actually used — that's your assertion target, not your edit
target.

## Key syntax and precedence

Batocera keys are dotted and increasingly specific. More specific wins:

```
global.<key>          # applies to everything
<system>.<key>        # applies to one system, e.g. snes.videomode
<system>["<rom>"].<key>   # applies to ONE rom
```

Example — a system default plus a per-game override:

```
snes.bezel=none
snes["Super Mario World (USA).sfc"].bezel=thebezelproject
```

### The per-game key trap: exact filename match

A per-game key (`<system>["<name>"].<key>`) matches configgen's *game short
name*, which is the **exact rom filename including extension**, with `=` and `#`
stripped. It is **not** a glob and **not** the display name.

- `snes["Star Fox*"]...` — **never matches.** There is no wildcard expansion;
  `*` is a literal character in the lookup key.
- `snes["Star Fox (USA).sfc"]...` — matches the file
  `Star Fox (USA).sfc`.

If a per-game override "isn't taking," this is almost always why: the key uses a
glob, the display name, or the name without the extension. Pull the real
filename (`ls /userdata/roms/<system>/`) and use it verbatim.

### The scope trap: emulator name vs rom-dir name

Some config keys are scoped to the **emulator/core name**, others to the **rom
directory name**, and they are not always the same. A key like
`fbneo.<something>` applies to launches from the `fbneo` core context — which is
**not** the same as launches out of a different rom directory that happens to
use the same core. If an override appears to do nothing for a system, confirm
which name the key is actually keyed on (check `es_launch_stdout.log` for the
launch's system/emulator/core) rather than assuming the rom-dir name is the
scope. See `batocera-tuning` for a worked overclock-scope example.

## es_features.cfg: the catalog of valid setting keys

Don't guess emulator setting keys. `batocera.conf` accepts any `key=value`
line, so a misspelled or invented key fails **silently** — no error, no effect.
The OS ships the authoritative catalog at
`/usr/share/emulationstation/es_features.cfg` (read-only rootfs, ~12k lines):
every tunable feature per emulator/core, with the exact conf-key suffix and the
values it accepts.

Structure: `<emulator name="…">` blocks containing
`<feature name="HUMAN LABEL" value="<conf-key-suffix>">` with `<choice>`
children enumerating valid values. The `value` attribute is exactly the string
configgen reads — prefix it with the system name and you have your conf key:

```bash
# what graphics-API values does standalone PCSX2 accept?
grep -A6 'value="pcsx2_gfxbackend"' /usr/share/emulationstation/es_features.cfg
#   <choice name="OpenGL"   value="12" />
#   <choice name="Software" value="13" />
#   <choice name="Vulkan"   value="14" />
```

So "switch PS2 to OpenGL" is `ps2.pcsx2_gfxbackend=12`. Two lessons in one
lookup: the file gives the real key name (`pcsx2_gfxbackend`, not
`gfxbackend`), and the accepted values — which are often opaque enums like
`12`, not the human-readable choice name. Check this file before proposing any
emulator-specific key; verify after a launch by reading the generated config as
usual.

## Worked example: a setting that won't stick

Symptom: you pick a palette / shader / option in the in-game RetroArch quick
menu, it looks right, but it resets to a washed-out default on the next launch.

Cause: **configgen is forcing the value every launch.** The quick-menu change
writes to a core-options file that the next configgen run overwrites from
`batocera.conf` (or from a configgen default when `batocera.conf` is silent).
The quick menu is not authoritative across launches; configgen is.

Fix: pin the value in `batocera.conf` so configgen writes *your* choice. Some
core options have a managed Batocera key; others are pass-through. Two forms:

```
# managed key (Batocera translates it to the core option)
gb.gb_colorization=PixelShift - Pack 1

# raw pass-through to a specific libretro core option
gb.retroarchcore.gambatte_gb_palette_pixelshift_1=PixelShift 28 - GB Washed Yellow Backlight
```

Then verify by launching and reading the generated
`cores/retroarch-core-options.cfg` — the option should show your value, not the
default.

### The `.opt` exception

A per-game `.opt` file (e.g. `<rom>.opt` alongside the ROM) **replaces**, not
overlays, the global core options for that game. If a game has an `.opt`, values
inside it are authoritative for that launch — a conflicting `batocera.conf` key
will *not* win. When a single game behaves differently from its system, check
for an `.opt`.

## Boot config vs batocera.conf

A few display/boot settings live in `/boot/batocera-boot.conf`, but the lower
section of that file is **auto-synced from `batocera.conf` on every boot** — a
direct edit there gets blanked. For example, pin the resolution with
`es.resolution=1920x1080.60.00` in **`batocera.conf`**, not in the boot conf.
Confirm in `display.log` after a reboot.

## Always back up first

```bash
cp /userdata/system/batocera.conf \
   /userdata/system/batocera.conf.bak-$(date +%Y%m%d-%H%M%S)
```

Cheap insurance; do it before every edit. When a change misbehaves, `diff`
against the backup to see exactly what you changed.
