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
# Find the ES BINARY pid (not the wrapper). Match the leading space so you get
# the real process, not the emulationstation-standalone wrapper script.
pgrep -f "^emulationstation "

kill -9 <es-pid>     # SIGKILL is uncatchable — the save-on-exit handler never
                     # runs, so your on-disk gamelist/es_settings edits survive.
```

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

This endpoint is a documented control surface, not synthetic input — but it
takes over the screen, so don't use it while someone is playing.
