# ROM formats and quirks

The file-format and system-quirk landmines that make a game refuse to appear or
refuse to launch, and how to get past each. All were learned the hard way on a
real cabinet.

## es_systems_custom.cfg REPLACES the stock system list

The single most destructive one. Batocera reads system definitions from
`/usr/share/emulationstation/es_systems.cfg` (the stock list, read-only). To
customize, people drop a file in `/userdata/system/configs/emulationstation/`.

**`es_systems_custom.cfg` does NOT merge with the stock list — it replaces it.**
Boot with that filename present and ES shows *only* the systems you defined in
it; every stock system (all your consoles) vanishes from the menu. This reads as
catastrophic ("the whole library is gone") but nothing was deleted — ES just
loaded a one-system definition.

- **To ADD a system or a custom collection**, use a **differently-named** merge
  file — e.g. `es_systems_<something>.cfg` — which ES *merges* with the stock
  list. Reserve the exact name `es_systems_custom.cfg` for the rare case where
  you truly intend to define the entire system list yourself.
- If systems disappeared after you added a custom cfg: check for a stray
  `es_systems_custom.cfg`, remove it (or rename it to a merge name), restart ES.
- Corollary: before "restoring" a config file you believe is missing, confirm it
  should exist. A file being *correctly absent* is common; re-creating it under
  a forbidden name causes exactly this failure. Read the subsystem's own notes
  before recreating anything.

## Extensionless ROM inside a zip → silent load failure

ES lists a `.zip` fine, but the emulator won't load it, and the failure is
nearly invisible: RetroArch exits in ~1 second, status 1, with only
`Could not read content file` in the log and nothing on screen.

Cause: the file *inside* the zip has no extension the core recognizes (e.g. a
SNES rom zipped as bare `donkeykongcountry` with no `.sfc`). The core opens the
zip, finds no loadable member, and bails.

Detect and fix:

```bash
# inspect inner names across a system's zips
for z in /userdata/roms/snes/*.zip; do echo "$z:"; unzip -Z1 "$z"; done
# any inner file with no .sfc/.smc (or the system's real extension) is the culprit
```

Rezip the inner file with the correct extension (unzip, rename to add `.sfc`,
rezip). Only a handful of files in a library are usually affected, but each one
looks like a broken emulator until you spot the missing extension.

## 3DO / Opera has no .m3u support

Multi-disc management on most CD systems uses `.m3u` playlists (list the discs,
the core swaps between them). **The Opera core (3DO) does not support `.m3u`** —
it reports `supported_extensions "iso|bin|chd|cue"` and `disk_control false`
(upstream Opera issue #14). Handing it an `.m3u` fails with "failure opening
image."

So for 3DO multi-disc, don't use playlists. Instead (see
`fix-3do-multidisc.py`):

- Give **disc 1** a clean gamelist entry (drop the "(Disc 1)" suffix), unhidden.
- Mark **discs 2+** `<hidden>true</hidden>` — still on disk, still launchable.
- When a game asks for the next disc, toggle ES "show hidden games" and launch
  that disc directly. Opera defaults `opera_nvram_storage=shared` for
  disc-named ROMs, so the save carries across discs.

## Bare .bin disc images are invisible

For a system whose ES extension list wants `.cue`/`.chd`, a lone `.bin` with no
`.cue` is invisible to the menu entirely. Generate a minimal `.cue` pointing at
it. Pick the track mode by sniffing the raw-CD sync pattern
(`00 FF*10 00` at offset 0 ⇒ `MODE1/2352`, else `MODE1/2048`):

```
FILE "game.bin" BINARY
  TRACK 01 MODE1/2352
    INDEX 01 00:00:00
```

`fix-3do-multidisc.py` does this sniff-and-generate automatically.

## Multi-track CHD / disc verification notes

- A `.chd` can wrap a single-track or multi-track disc. When hashing tracks out
  of an extracted CHD to compare against Redump per-track SHA1s, split the
  combined `.bin` by the CUE's INDEX/PREGAP offsets — see `dat-verify.py` and the
  dat-verification reference for the exact Redump pregap convention.
- `.bin`/`.cue` pairs are handled by the emulator automatically; you don't need
  an `.m3u` for a single multi-track disc.

## Cave CV1000 lives in `cave3rd`

The Cave CV1000 shmup system's directory is **`cave3rd`**, not `cv1000` (which
doesn't exist). The display name is "Cave CV1000" but the internal name is
`cave3rd` — verify with
`grep cave3rd /usr/share/emulationstation/es_systems.cfg`. Prefer the standalone
**MAME** emulator over Demul (`cave3rd.emulator=mame` / `cave3rd.core=mame`):
MAME runs natively, Demul needs WINE + Vulkan. CV1000 titles are self-contained
parents — no BIOS. Note that some Cave games people expect here are *not* CV1000
hardware (DoDonPachi Dai-Ou-Jou is PGM; Deathsmiles II X is Taito Type X2) and
belong on other systems.

## Some add-ons need a keyboard the cabinet lacks

Not a ROM format, but a recurring "why won't this work on the cabinet" trap:
add-on frameworks (e.g. Batocera Unofficial Add-ons) can install Electron/desktop
apps whose account login and menus **require a keyboard**. On a controller-only
arcade cabinet these are unusable regardless of whether they launch. Vet an
add-on's input needs before installing; a weak arcade-cabinet iGPU also rules out
local-render/streaming apps. When an add-on doesn't fit, remove it cleanly and
SIGKILL-restart ES so the cleaned gamelist isn't clobbered on exit.
