# EmulationStation: restart, logs, and event hooks

Operational reference for the Batocera frontend. Load when a change needs ES
restarted, when diagnosing a launch/crash, or when ES behaves oddly after an
edit.

## Restarting ES without losing your edits

ES rewrites `gamelist.xml` and `es_settings.cfg` **on clean exit**. If you edited
those files on disk and then let ES exit gracefully, it overwrites your edits
with its in-memory copy. To make external edits stick, either stop ES before
editing or kill it uncatchably after.

**The swissknife `--restart` is unreliable on some builds.**
`batocera-es-swissknife --restart` matches the process with `pgrep
emulationstation`, but the Linux process comm name is truncated to 15
characters, so the running binary shows as `emulationstatio` and the match can
fail (no-op restart). Don't rely on it for anything that matters.

**Reliable pattern — SIGKILL the binary, let the supervisor respawn it:**

```bash
# Find the ES BINARY pid (not the wrapper): the process whose command is
# exactly "emulationstation". The wrapper is emulationstation-standalone.
ps aux | awk '$11 == "emulationstation" {print $2}'

kill -9 <es-pid>     # SIGKILL is uncatchable — the save-on-exit handler never
                     # runs, so your on-disk gamelist/es_settings edits survive.
```

**Match the binary, never its arguments.** ES does not get the same argument
list at every start: a start at boot and a restart by the wrapper can differ
(for example `--no-startup-game` is present after one and not after the
other). A kill pattern that includes an argument works in the session where
you wrote it and matches nothing after the next reboot. The command then exits
without an error, ES keeps its old in-memory settings, and its next clean exit
writes them over your edit.

**How to tell that a kill did nothing:** read the pid before and after.

```bash
es_pid() { ps aux | awk '$11 == "emulationstation" {print $2}'; }
OLD=$(es_pid); for p in $OLD; do kill -9 "$p"; done
i=0; until curl -s -m 3 -o /dev/null http://127.0.0.1:1234/systems; do i=$((i+1)); [ $i -gt 60 ] && break; sleep 2; done
echo "old=$OLD new=$(es_pid) back after $((i*2)) s"
```

An empty `old`, the same pid twice, or "back after 0 s" means nothing was
killed. A real restart takes several seconds and gives a new pid. Check
`/runningGame` first: the kill also ends a game in progress.

A supervisor wrapper (`emulationstation-standalone`, a
`while [ -e /var/run/emulationstation-standalone ]` loop) auto-respawns ES,
which reloads your edited files. Verify the new PID is up and the change is
reflected (e.g. hidden counts match what you wrote).

**If you accidentally kill the wrapper** (it matches
`pgrep -x emulationstatio` because of the 15-char truncation — always use `-f`,
never `-x`), relaunch it:

```bash
DISPLAY=:0 HOME=/userdata/system setsid nohup \
  /usr/bin/emulationstation-standalone > /tmp/es-relaunch.log 2>&1 &
```

**To stop ES entirely** for a batch of gamelist edits (then start after):

```bash
/etc/init.d/S31emulationstation stop
# ... edit gamelists ...
/etc/init.d/S31emulationstation start
```

## Log inventory

Verbosity is high by default. The commonly-cited path
`/userdata/system/configs/emulationstation/es_log.txt` exists but is often
**0 bytes** on recent builds — superseded by per-launch logs. Look here instead:

**Frontend / system logs — `/userdata/system/logs/`:**
- `es_launch_stdout.log` — **the real ES log.** DEBUG-level per-launch trace:
  every config key written, the controller GUID, the full env dump, and the
  **exact emulator command line + shader path**. First stop for "why did the
  launch do X."
- `es_launch_stderr.log` — launch errors only.
- `batocera.log` — system startup (mostly locale init).
- `batocera-upgrade.log` — last version upgrade trace.
- `backup.log` — rsync backup output.
- `display.log` — resolution/EDID negotiation.
- `scraper*.log`, `thebezelproject.log`, `mpv.log` — per-subsystem.

**RetroArch per-launch logs — `/userdata/system/configs/retroarch/logs/`:**
- One file per session (not appended): `retroarch__YYYY_MM_DD__HH_MM_SS.log`.
- Enabled by `log_verbosity/log_to_file/log_to_file_timestamp = "true"` in
  `retroarchcustom.cfg`.

**Kernel / X / syslog — `/var/log/`:** `Xorg.0.log`, `messages`, `dmesg`
(command), plus per-component crash logs. Start here for driver/display/boot
issues that predate ES.

**Diagnosis order:** `es_launch_stdout.log` (get the exact command line + shader
path) → the matching timestamped RetroArch log → `/var/log/Xorg.0.log` + `dmesg`
for anything below the emulator layer.

## ES executes scripts as event hooks

ES auto-runs **anything executable** in `/userdata/system/scripts/` as a game
event hook, calling it with positional args:
`<script> gameStart|gameStop <system> <emulator> <core> <rom>`. Consequences:

- **Don't park a one-shot manual script there** — it will be invoked with hook
  args on the next launch and crash (or worse). Put utilities elsewhere
  (`/userdata/system/` root, or a `tools/` dir), or make the script no-op when
  called with hook positional arguments.
- **Event hooks are global and fire often.** A `scripts/system-selected/` hook
  runs on **every carousel tile change** in the ES menu. A slow or leaky hook
  there degrades the whole frontend, and because hooks are global (not
  theme-scoped) the symptom masquerades as a "theme-independent ES bug." If ES
  feels progressively laggy, audit `/userdata/system/scripts/` and
  `/userdata/system/configs/emulationstation/scripts/` for installed hooks
  before blaming themes or gamelists. See `batocera-tuning` for the full
  diagnostic order.

## ES HTTP API (port 1234)

Runs on the box; useful for launching and inspecting without a controller.

- Launch a file: `curl -s -X POST http://127.0.0.1:1234/launch -d '<abs path>'`
  (works for files not in the ES menu too).
- List a system's games (name/path/hidden):
  `curl -s http://127.0.0.1:1234/systems/<system>/games`.
- Quit the running emulator: `batocera-es-swissknife --emukill`.

**Two limits of `/launch`:**

- **Group systems.** Where ES groups several systems under one tile, `/launch`
  with a path from a grouped system returns and nothing starts. List them:
  `curl -s http://127.0.0.1:1234/systems | python3 -c "import sys,json; print([s['name'] for s in json.load(sys.stdin) if s.get('groupsystem') == 'true'])"`.
- **Unsupported formats.** If the core does not accept the file (a `.zip` on a
  core that wants the bare ROM, for example), ES shows a warning dialog and
  waits for a button. No game starts, and later `/launch` calls do nothing
  until ES is restarted. The tell is `/runningGame` staying empty with no new
  lines in `es_launch_stdout.log`; a screenshot shows the dialog.

For both, start the game with `batocera-launch -system <system> -rom <path>`
instead. `batocera-ops` → `scripts/direct_launch.sh` does that with
screenshots, and the main skill file has the details.

This endpoint is a documented control surface, not synthetic input — but it
takes over the screen, so don't use it while someone is playing.

## Custom collections need theme art

A custom collection is a text file,
`/userdata/system/configs/emulationstation/collections/custom-<name>.cfg`, with
one ROM path per line. ES shows it when `<name>` is in the comma-separated
`CollectionSystemsCustom` value in `es_settings.cfg`. That is enough for the
games to appear, but the tile has no background and no logo until the theme
has art for `<name>`.

A theme reads these files for a collection named `<name>`:

- `<theme>/<name>/theme.xml`, a small file that includes the main theme. Copy
  it from another collection's folder.
- The theme's per-system art and logo files, named `<name>.<ext>`. The folders
  and the number of sizes differ per theme.

Find the exact paths in two ways. Use both, because a theme can read one name
from several folders:

```bash
cd /userdata/themes/<theme>
grep -rn 'system.theme' --include='*.xml' . | head -30   # every path built from the name
find . -iname '<existing-collection>*'                    # the full set one collection has
```

Copy the set of an existing collection, rename each file to `<name>`, and then
replace the pictures. Keep the pixel size and the file type of each one.

**Check the tile without sending input.** Set `StartupSystem` in
`es_settings.cfg` to `<name>` for one ES start. ES opens on that tile.

```bash
CFG=/userdata/system/configs/emulationstation/es_settings.cfg
cp $CFG $CFG.pre-tile-check
grep StartupSystem $CFG                  # note the old value
# set value="<name>" on that line, then:
kill -9 $(ps aux | awk '$11 == "emulationstation" {print $2}')
sleep 25; batocera-screenshot
cp $CFG.pre-tile-check $CFG              # put the old value back
kill -9 $(ps aux | awk '$11 == "emulationstation" {print $2}')
```

Both restarts use SIGKILL for the reason at the top of this file. Check that
no game runs first. Look at the screenshot for the background, the logo and
the game count. If the count is lower than the number of lines in the `.cfg`,
a line is hidden or does not resolve. `batocera-ops` →
`scripts/collection_status.py <cfg>` prints the state of every line.

### Symlinked and renamed system folders

A collection line must name the game by the path ES itself uses. That matters
when one ROM folder is a symlink to another, which upgrades and manual
renames leave behind (an old folder name that points at the new one, or the
reverse). Both paths open the same file, but ES indexes the games under one
system name only, the one in `es_systems.cfg`. A line that goes through the
other folder name exists on disk and still never shows in the tile.

```bash
find /userdata/roms -maxdepth 1 -type l -exec ls -ld {} +      # symlinked system folders
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:1234/systems/<folder name>/games
```

`200` means ES indexes that name; `404` means it does not, so use the other
name in the collection. `collection_status.py` reports such lines as
`NO-SYSTEM`, and lines with a wrong file name as `NOT-INDEXED`. It exits 1
when any line fails, so it also works as a check after a library change.
