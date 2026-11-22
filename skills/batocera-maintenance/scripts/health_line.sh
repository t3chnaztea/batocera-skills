#!/bin/bash
# Print ONE line of key=value pairs that describes the cabinet's health.
# Read-only. Meant to be run over SSH by another machine once a month; that
# machine compares the values with its limits and sends a message only when a
# value is out of range.
#
#   disk_used_pct       how full /userdata is
#   backup_age_days     days since the backup stamp file changed (na: no stamp)
#   throttle_pkg        CPU package thermal throttle count since boot
#   uptime_days         so the throttle count can be read as a rate
#   watchdog_kills_30d  lines of the last 30 days in the frontend watchdog log
#   es_api              HTTP code of the ES API (200 or 302: the frontend is up)
#
# BACKUP_STAMP  the file your backup job touches or rewrites when it succeeds.
# WATCHDOG_LOG  a log with one line per frontend kill; each line must start
#               with "YYYY-MM-DD HH:MM:SS". Without such a log the count is 0.
BACKUP_STAMP="${BACKUP_STAMP:-/userdata/system/.last-monthly-backup}"
WATCHDOG_LOG="${WATCHDOG_LOG:-/userdata/system/logs/es-watchdog.log}"

disk=$(df -P /userdata 2>/dev/null | awk 'NR==2 {gsub("%","",$5); print $5}')

bts=$(stat -c %Y "$BACKUP_STAMP" 2>/dev/null)
if [ -n "$bts" ]; then
  backup=$(( ($(date +%s) - bts) / 86400 ))
else
  backup=na
fi

pkg=$(cat /sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_count 2>/dev/null || echo na)
updays=$(awk '{printf "%.1f", $1 / 86400}' /proc/uptime)

cut=$(date -d '30 days ago' '+%Y-%m-%d %H:%M:%S')
kills=0
if [ -s "$WATCHDOG_LOG" ]; then
  kills=$(awk -v cut="$cut" '/^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] / { if (($1 " " $2) >= cut) n++ } END { print n + 0 }' "$WATCHDOG_LOG")
fi

es=$(curl -s -o /dev/null --max-time 10 -w '%{http_code}' http://127.0.0.1:1234/systems)
[ -n "$es" ] || es=000

echo "disk_used_pct=${disk:-na} backup_age_days=$backup throttle_pkg=$pkg uptime_days=$updays watchdog_kills_30d=$kills es_api=$es"
