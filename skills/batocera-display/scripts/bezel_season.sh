#!/bin/sh
# Season dressing: swap the fallback bezel and the boot splash to match the
# season, and show one custom collection during one season only.
#
# Layout (all under /userdata, so it survives upgrades):
#   $SEASON_DIR/state                 one word, the current season name
#   $SEASON_DIR/bezels/default/       the normal files
#   $SEASON_DIR/bezels/<season>/      the files for one season
#   $SEASON_DIR/splash/default/splash.mp4    the normal boot clip
#   $SEASON_DIR/splash/<season>/splash.mp4   the boot clip for one season
# Each bezel folder holds default.png and, if you use them, per-system files
# such as systems/<system>.png. A season without a folder gets the default
# folder, so the normal bezel and splash come back when the season ends.
# Put every file that any season replaces into the default folder too, or that
# file keeps its seasonal copy.
#
# Collection (optional): set COLLECTION to the name of a custom collection and
# COLLECTION_SEASON to the season that shows it. The script adds the name to
# CollectionSystemsCustom in es_settings.cfg in that season and removes it in
# every other one. ES writes es_settings.cfg when it exits cleanly, so the
# script edits the file and then sends SIGKILL to ES; the wrapper starts ES
# again. It does nothing while a game runs. The next pass does the work.
#
# The script only writes when something differs, so it is safe to run at boot
# and on a timer. Batocera has no cron: call it from your boot service loop.
SEASON_DIR="${SEASON_DIR:-/userdata/system/season-bezel}"
PACK="${PACK:-/userdata/decorations/thebezelproject}"
SPLASH="${SPLASH:-/userdata/splash/splash.mp4}"
ES_CFG="${ES_CFG:-/userdata/system/configs/emulationstation/es_settings.cfg}"
COLLECTION="${COLLECTION:-}"
COLLECTION_SEASON="${COLLECTION_SEASON:-}"
LOG="$SEASON_DIR/season.log"
STATE=$(cat "$SEASON_DIR/state" 2>/dev/null)
log() { echo "$(date '+%F %T') season ${STATE:-default}: $1" >> "$LOG"; }
put() {                                  # copy $1 over $2 when they differ
  cmp -s "$1" "$2" && return 0
  cp "$1" "$2" && chmod 644 "$2" && log "$1 -> $2"
}

S=$STATE
[ -n "$S" ] && [ -d "$SEASON_DIR/bezels/$S" ] || S=default
SRC="$SEASON_DIR/bezels/$S"
if [ -d "$SRC" ]; then
  ( cd "$SRC" && find . -name '*.png' ) | while read -r f; do
    f=${f#./}
    [ -f "$PACK/$f" ] || continue        # replace existing bezels only, never add new ones
    put "$SRC/$f" "$PACK/$f"
  done
fi

S=$STATE
[ -n "$S" ] && [ -d "$SEASON_DIR/splash/$S" ] || S=default
[ -f "$SEASON_DIR/splash/$S/splash.mp4" ] && put "$SEASON_DIR/splash/$S/splash.mp4" "$SPLASH"

[ -n "$COLLECTION" ] && [ -n "$COLLECTION_SEASON" ] || exit 0
grep -q 'name="CollectionSystemsCustom"' "$ES_CFG" 2>/dev/null || exit 0
CUR=$(sed -n 's/.*name="CollectionSystemsCustom" value="\([^"]*\)".*/\1/p' "$ES_CFG")
WANT=0; [ "$STATE" = "$COLLECTION_SEASON" ] && WANT=1
HAS=0; case ",$CUR," in *,"$COLLECTION",*) HAS=1;; esac
[ "$WANT" = "$HAS" ] && exit 0
curl -s -m 5 http://127.0.0.1:1234/runningGame | grep -q '"path"' && exit 0
if [ "$WANT" = 1 ]; then NEW="${CUR:+$CUR,}$COLLECTION"
else NEW=$(echo "$CUR" | tr ',' '\n' | grep -vx "$COLLECTION" | paste -sd, -); fi
sed -i "s|name=\"CollectionSystemsCustom\" value=\"[^\"]*\"|name=\"CollectionSystemsCustom\" value=\"$NEW\"|" "$ES_CFG"
for p in $(pgrep -f '^emulationstation '); do kill -9 "$p"; done
log "CollectionSystemsCustom=$NEW (ES restarted)"
exit 0
