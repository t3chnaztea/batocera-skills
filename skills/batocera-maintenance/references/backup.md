# Backups

A safe, agent-runnable backup architecture for a Batocera cabinet: **push-only,
dry-run-first, rsync over SSH**, parameterized so nothing is hardcoded.

## Principles

- **Push, don't pull, from the cabinet's side of the schedule.** The cabinet
  pushes to a backup host on its own boot-loop schedule (see the maintenance
  skill). A complementary pull from the backup host on a different day gives you
  two independent mechanisms — if one silently stops, the other still runs.
- **Dry-run before any run that can delete.** Any rsync with `--delete` gets a
  `--dry-run` pass first, reviewed, before the real run. `--delete` on the wrong
  source path mirrors an empty dir over your backup.
- **Separate ROMs from userdata.** ROMs are large and change rarely; saves,
  system config, and BIOS are small and change constantly. Back them to separate
  destinations on separate cadences so a routine userdata sync never has to walk
  hundreds of GB of ROMs.

## What to back up

Under `/userdata`, in priority order:

- `saves/` — save states and SRAM. **Highest value, smallest size, most
  volatile.** If you back up nothing else, back this up.
- `system/` — `batocera.conf`, `configs/`, `services/`, scrapers, your tools.
  This is your whole setup.
- `bios/` — BIOS files (tedious to re-source).
- `decorations/`, `shaders/`, `themes/` — large but reconstructable; back up on a
  slower cadence or once after big changes.
- `roms/` — separate destination, infrequent cadence.

Exclude caches and logs (`system/logs/`, scraper image caches) to keep the sync
lean.

## Parameterized push script

```bash
#!/bin/sh
# backup-to-remote.sh -- push /userdata essentials to a backup host over SSH.
# Configure these (env or edit):
BACKUP_HOST="${BACKUP_HOST:?set BACKUP_HOST}"     # user@host or host
BACKUP_PORT="${BACKUP_PORT:-22}"
BACKUP_DEST="${BACKUP_DEST:?set BACKUP_DEST}"     # remote path, e.g. /pool/batocera/userdata
DRY="${DRY:-1}"                                    # 1 = dry-run (default), 0 = apply

RSYNC_OPTS="-avh --delete --exclude=system/logs/ --exclude='**/media/**cache**'"
[ "$DRY" = "1" ] && RSYNC_OPTS="$RSYNC_OPTS --dry-run"

for d in saves system bios; do
  echo "=== $d (DRY=$DRY) ==="
  rsync $RSYNC_OPTS -e "ssh -p $BACKUP_PORT -o StrictHostKeyChecking=no" \
    "/userdata/$d/" "$BACKUP_HOST:$BACKUP_DEST/$d/"
done
```

Run it dry first (`DRY=1 ./backup-to-remote.sh`), read the file list, then
`DRY=0`. Set up SSH key auth from the cabinet to the backup host so the scheduled
run is non-interactive (Batocera can hold a key under `/userdata/system/.ssh/`).

## Scheduling (catch-up semantics)

The maintenance skill's boot-loop pattern gates the monthly push on a stamp file
so it runs on the **first boot of the month the cabinet is powered on**, not at a
fixed clock time it might sleep through. Log each run (`>> backup.log`) so you can
confirm it fired. A backup that "should have run at 3 AM" on a machine that's off
at 3 AM never runs — catch-up gating is why this matters on a cabinet that isn't
always on.

## Verifying a backup

`mail.send`-style "job completed" or an rsync exit 0 means the *transfer* ran, not
that the data is recoverable. Periodically spot-check: list the destination, diff
a known file's size/mtime, and once in a while actually restore a save to a scratch
path and confirm it loads. Trust restores, not exit codes.
