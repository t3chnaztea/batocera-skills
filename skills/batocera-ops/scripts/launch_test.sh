#!/bin/sh
# Launch a list of ROMs one by one through the ES HTTP API, screenshot each, stop it, log the result.
# Run it ON the Batocera box, detached (setsid nohup ... &), because SSH drops idle sessions.
#
# usage: launch_test.sh <outdir> <list file>
# list line:  <shot times in seconds, comma separated>|<full ROM path>
#   example:  20,35|/userdata/roms/snes/Some Game (USA).sfc
#
# Output: <outdir>/<system>-<rom>-<time>.png, the launch stdout and stderr logs per game,
# and one line per game in <outdir>/results.tsv. The last line is ALLDONE.
#
# Every step has a time limit. A game that does not stop after emukill gets SIGKILL
# and hung=1 in the results, and the run goes on to the next game.
# Set QUIET_FROM and QUIET_TO (hours, 24 h clock) to stop the run outside the hours
# when a screen that turns on and makes noise is acceptable.
OUT="$1"; LIST="$2"
[ -n "$OUT" ] && [ -f "$LIST" ] || { echo "usage: $0 <outdir> <list file>"; exit 2; }
EMUS="${EMUS:-retroarch}"   # process names to SIGKILL if a game hangs; add your standalone emulators
export XAUTHORITY="${XAUTHORITY:-/var/lib/.Xauthority}"
API=http://127.0.0.1:1234
mkdir -p "$OUT"
running() { curl -s -m 5 $API/runningGame | grep -c '"path"'; }
while IFS='|' read -r TIMES ROM <&3; do
  [ -z "$ROM" ] && continue
  if [ -n "$QUIET_FROM" ] && [ -n "$QUIET_TO" ]; then
    H=$(date +%H | sed 's/^0//')
    if [ "$H" -ge "$QUIET_FROM" ] || [ "$H" -lt "$QUIET_TO" ]; then echo "QUIET HOURS, stop" >> "$OUT/results.tsv"; exit 3; fi
  fi
  K="$(basename "$(dirname "$ROM")")-$(basename "$ROM" | sed 's/\.[^.]*$//')"
  # Do not start a test while someone plays.
  if [ "$(running)" != 0 ]; then echo "$K	SKIP	game already running" >> "$OUT/results.tsv"; exit 4; fi
  : > /userdata/system/logs/es_launch_stderr.log
  : > /userdata/system/logs/es_launch_stdout.log
  T0=$(date +%s)
  curl -s -m 10 -X POST $API/launch -d "$ROM" > "$OUT/$K.launch.txt" 2>&1
  RUN=""
  for T in $(echo "$TIMES" | tr ',' ' '); do
    while [ $(( $(date +%s) - T0 )) -lt "$T" ]; do sleep 1; done
    timeout 25 batocera-screenshot "$OUT/$K-$T.png" >/dev/null 2>&1
    RUN="$RUN $T:$(running)"
  done
  cp /userdata/system/logs/es_launch_stderr.log "$OUT/$K.stderr.log" 2>/dev/null
  cp /userdata/system/logs/es_launch_stdout.log "$OUT/$K.stdout.log" 2>/dev/null
  curl -s -m 10 $API/emukill >/dev/null 2>&1
  i=0; HUNG=0
  while [ "$(running)" != 0 ]; do
    i=$((i+1)); sleep 2
    if [ $i -eq 10 ]; then HUNG=1; for e in $EMUS; do pkill -9 -x "$e"; done; fi
    [ $i -gt 20 ] && break
  done
  echo "$K	running=$RUN	secs=$(( $(date +%s) - T0 ))	hung=$HUNG	errlines=$(wc -l < "$OUT/$K.stderr.log")" >> "$OUT/results.tsv"
  sleep 5
done 3< "$LIST"
echo ALLDONE >> "$OUT/results.tsv"
