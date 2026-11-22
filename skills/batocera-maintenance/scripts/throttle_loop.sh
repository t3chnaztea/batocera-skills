#!/bin/bash
# Daily throttle log loop: one line at start, then one every 24 h.
# Batocera has no cron. Start this from the boot service with a guard, so a
# second "start" does not add a second loop:
#
#   pgrep -f throttle_loop.sh >/dev/null 2>&1 || /bin/bash /userdata/system/health/throttle_loop.sh >/dev/null 2>&1 &
#
# Keep both scripts outside /userdata/system/scripts/: every executable in that
# folder runs at each game start and stop.
DIR="$(dirname "$0")"
while true; do
  /bin/bash "$DIR/throttle_log.sh"
  sleep 86400
done
