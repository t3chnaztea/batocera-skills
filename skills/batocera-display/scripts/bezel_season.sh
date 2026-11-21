#!/bin/sh
# Swap the fallback bezel to match the season.
#
# Layout (all under /userdata, so it survives upgrades):
#   $SEASON_DIR/state                 one word, the current season name
#   $SEASON_DIR/bezels/default/       the normal files
#   $SEASON_DIR/bezels/<season>/      the files for one season
# Each folder holds default.png and, if you use them, per-system files such as
# systems/<system>.png. A season without a folder gets bezels/default/, so the
# normal bezel comes back when the season ends.
# Put every file that any season replaces into bezels/default/ too, or that file
# keeps its seasonal copy.
#
# The script only copies when the file differs, so it is safe to run at boot and
# on a timer. Batocera has no cron: call it from your boot service loop.
SEASON_DIR="${SEASON_DIR:-/userdata/system/season-bezel}"
PACK="${PACK:-/userdata/decorations/thebezelproject}"
S=$(cat "$SEASON_DIR/state" 2>/dev/null)
[ -n "$S" ] && [ -d "$SEASON_DIR/bezels/$S" ] || S=default
SRC="$SEASON_DIR/bezels/$S"
[ -d "$SRC" ] || exit 0
( cd "$SRC" && find . -name '*.png' ) | while read -r f; do
  f=${f#./}
  [ -f "$PACK/$f" ] || continue        # replace existing bezels only, never add new ones
  cmp -s "$SRC/$f" "$PACK/$f" && continue
  cp "$SRC/$f" "$PACK/$f" && chmod 644 "$PACK/$f" && echo "$(date '+%F %T') bezel $S -> $PACK/$f" >> "$SEASON_DIR/season.log"
done
exit 0
