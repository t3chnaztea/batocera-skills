#!/bin/bash
# Append one line to a thermal throttle log: uptime, the CPU throttle counters,
# the hottest core temperature and the load.
# The throttle counters reset at boot, so uptime_s makes two lines comparable:
# a count that grows while uptime also grows is new throttling.
# Run it from throttle_loop.sh (started by the boot service). Read-only apart
# from the log line.
T=/sys/devices/system/cpu/cpu0/thermal_throttle
LOG="${THROTTLE_LOG:-/userdata/system/logs/throttle.log}"

up=$(cut -d. -f1 /proc/uptime)
core=$(cat "$T/core_throttle_count" 2>/dev/null || echo na)
pkg=$(cat "$T/package_throttle_count" 2>/dev/null || echo na)

max=
for h in /sys/class/hwmon/hwmon*; do
  # Intel: coretemp. AMD: set HWMON_NAME=k10temp.
  [ "$(cat "$h/name" 2>/dev/null)" = "${HWMON_NAME:-coretemp}" ] || continue
  for f in "$h"/temp*_input; do
    v=$(cat "$f" 2>/dev/null) || continue
    case "$v" in ''|*[!0-9]*) continue ;; esac
    if [ -z "$max" ] || [ "$v" -gt "$max" ]; then max=$v; fi
  done
done
if [ -n "$max" ]; then temp=$((max / 1000)); else temp=na; fi

load=$(cut -d' ' -f1-3 /proc/loadavg | tr ' ' '/')

echo "$(date '+%Y-%m-%d %H:%M:%S') uptime_s=$up core_throttle_count=$core package_throttle_count=$pkg temp_max_c=$temp load=$load" >> "$LOG"
