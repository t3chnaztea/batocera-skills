#!/bin/bash
# Launch one ROM with batocera-launch (not the ES HTTP API), take screenshots,
# optionally record the screen, then stop the emulator.
# Use it where the ES API /launch does nothing (group systems) or stops on an
# ES dialog (a file format the core does not support).
# Run it ON the Batocera box, inside the hours when a lit screen is acceptable.
#
# usage: direct_launch.sh <system> <rom> <out prefix> "<shot times s>" [record_start_s record_len_s]
#   example: direct_launch.sh nes "/userdata/roms/nes/Some Game (USA).zip" /userdata/system/test/some "20 45" 25 40
#
# Output: <out prefix>-<time>.png per shot, <out prefix>.launch.log, and with
# the two record arguments <out prefix>.rec.mp4 (x11grab, video only).
# The last line is a one-line result: was an emulator running at each shot
# time, which process, the volume after the run, and the error lines in the log.
#
# The system volume goes to 0 for the run and back at the end, also when the
# script is interrupted. It will not start while a game or an emulator runs.
#
# EMUS      process names that count as "an emulator" and get stopped at the end.
#           Add the standalone emulators your systems use.
# REC_SIZE  capture size, default the current resolution.
# REC_FPS   capture frame rate, default 30.
SYS="$1"; ROM="$2"; OUT="$3"; TIMES="$4"; RS="$5"; RL="$6"
if [ -z "$SYS" ] || [ ! -e "$ROM" ] || [ -z "$OUT" ] || [ -z "$TIMES" ]; then
  echo "usage: $0 <system> <rom> <out prefix> \"<shot times s>\" [record_start_s record_len_s]"; exit 2
fi
EMUS="${EMUS:-retroarch}"
API=http://127.0.0.1:1234
export XAUTHORITY="${XAUTHORITY:-/var/lib/.Xauthority}" DISPLAY="${DISPLAY:-:0}"

running() { for e in $EMUS; do pgrep -x "$e" >/dev/null && return 0; done; return 1; }
curl -s -m 5 $API/runningGame | grep -q '"path"' && { echo "game running, abort"; exit 1; }
running && { echo "emulator already running, abort"; exit 1; }

VOL=$(batocera-audio getSystemVolume)
stop() {
  for e in $EMUS; do pkill -x "$e" 2>/dev/null; done
  for i in $(seq 1 15); do running || break; sleep 1; done
  running && for e in $EMUS; do pkill -9 -x "$e" 2>/dev/null; done
}
cleanup() { stop; [ "$VOL" -gt 0 ] 2>/dev/null && batocera-audio setSystemVolume "$VOL"; }
trap cleanup EXIT
[ "$VOL" -gt 0 ] 2>/dev/null && batocera-audio setSystemVolume 0

# The emulator needs the audio and session sockets of the desktop session.
# Take XDG_RUNTIME_DIR from the ES process. Match the ES binary by its exact
# command name: its arguments are not the same after every start.
ESPID=$(ps aux | awk '$11 == "emulationstation" {print $2}' | head -1)
if [ -n "$ESPID" ]; then
  X=$(tr '\0' '\n' < "/proc/$ESPID/environ" | grep '^XDG_RUNTIME_DIR=') && export "$X"
fi

mkdir -p "$(dirname "$OUT")"
T0=$(date +%s)
setsid nohup batocera-launch -system "$SYS" -rom "$ROM" > "$OUT.launch.log" 2>&1 &

RECPID=""
if [ -n "$RS" ] && [ -n "$RL" ]; then
  SIZE="${REC_SIZE:-$(batocera-resolution currentResolution 2>/dev/null | grep -E '^[0-9]+x[0-9]+$')}"
  SIZE="${SIZE:-1920x1080}"
  ( while [ $(( $(date +%s) - T0 )) -lt "$RS" ]; do sleep 1; done
    ffmpeg -v error -y -f x11grab -framerate "${REC_FPS:-30}" -video_size "$SIZE" -i "$DISPLAY" \
      -t "$RL" -c:v libx264 -preset ultrafast -crf 20 -pix_fmt yuv420p "$OUT.rec.mp4" ) &
  RECPID=$!
fi

R=""
for T in $TIMES; do
  while [ $(( $(date +%s) - T0 )) -lt "$T" ]; do sleep 1; done
  if running; then R="$R $T:1"; else R="$R $T:0"; fi
  # batocera-screenshot does not overwrite a file: use a new prefix for each run
  timeout 25 batocera-screenshot "$OUT-$T.png" >/dev/null 2>&1
done
[ -n "$RECPID" ] && wait "$RECPID"
PROC=$(for e in $EMUS; do pgrep -x "$e" >/dev/null && echo "$e"; done | tr '\n' ' ')
cleanup; trap - EXIT
echo "$SYS | $(basename "$ROM") | running=$R | proc=$PROC | vol=$(batocera-audio getSystemVolume) | errs=$(grep -ciE 'error|traceback' "$OUT.launch.log")"
