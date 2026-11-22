#!/bin/sh
# Build a seasonal boot splash: the normal splash clip plus effect layers.
#
# Usage:
#   make_season_splash.sh <base.mp4> <out.mp4> <layer> [<layer> ...]
#
# <base.mp4>  the normal splash clip. It is not changed.
# <layer>     a video (.mp4, .mov, .mkv, .webm) or a still picture (.png, .jpg)
#             of bright art on PURE BLACK. Layers go on with the screen blend,
#             where black adds nothing, so no alpha channel is needed. A layer
#             is stretched to the output size: make it in the same aspect ratio.
#
# Options are environment variables:
#   SOUND=file.wav   a sound mixed under the original audio (default: none)
#   SOUND_VOL=0.16   its volume; the original audio keeps its level
#   FADE_IN=2.0      second at which the layers fade in. Set it to the moment
#                    the logo lands, so the decoration does not cover the intro.
#   FADE_LEN=0.8     length of each fade in seconds
#   FADE_OUT=        second at which the layers fade out (default: 1 s before the end)
#   SIZE=1920x1080   output size
#   FPS=30           output frame rate
#
# Do not brighten a layer with the eq filter. eq=brightness lifts black to grey,
# and the screen blend then puts a grey haze on the whole picture. Make the art
# brighter in the source file instead.
#
# Run it on a workstation with ffmpeg, then copy the result to the cabinet.
# Needs: ffmpeg, ffprobe, awk.
[ $# -ge 3 ] || { sed -n '2,25p' "$0"; exit 1; }
BASE=$1; OUT=$2; shift 2
SIZE=${SIZE:-1920x1080}; FPS=${FPS:-30}
FADE_IN=${FADE_IN:-2.0}; FADE_LEN=${FADE_LEN:-0.8}; SOUND_VOL=${SOUND_VOL:-0.16}
W=${SIZE%x*}; H=${SIZE#*x}
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$BASE") || exit 1
FADE_OUT=${FADE_OUT:-$(awk "BEGIN{print $D-1}")}
FADE="fade=t=in:st=$FADE_IN:d=$FADE_LEN,fade=t=out:st=$FADE_OUT:d=$FADE_LEN"

# One input and one filter chain per layer. Each layer is screened onto the
# result of the one before it.
LAYERS=$#
set -- "$@" -i "$BASE"
FG="[0:v]fps=$FPS,scale=$W:$H,format=gbrp[v0]"
N=0
while [ "$N" -lt "$LAYERS" ]; do
  layer=$1; shift
  N=$((N + 1))
  case "$layer" in
    *.png|*.PNG|*.jpg|*.JPG|*.jpeg|*.JPEG) set -- "$@" -loop 1 -t "$D" -i "$layer" ;;
    *) set -- "$@" -i "$layer" ;;
  esac
  FG="$FG;[$N:v]fps=$FPS,scale=$W:$H,$FADE,format=gbrp[l$N];[v$((N - 1))][l$N]blend=all_mode=screen[v$N]"
done
FG="$FG;[v$N]format=yuv420p[v]"

# Audio. normalize=0 keeps the original track at its level; the default halves
# both inputs. A clip without an audio track gets the sound alone.
HAS_AUDIO=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$BASE" | head -1)
if [ -n "$SOUND" ]; then
  set -- "$@" -i "$SOUND"
  S=$((N + 1))
  if [ -n "$HAS_AUDIO" ]; then
    FG="$FG;[$S:a]volume=$SOUND_VOL,afade=t=in:st=0.3:d=1.5[s];[0:a][s]amix=inputs=2:duration=first:normalize=0[a]"
  else
    FG="$FG;[$S:a]volume=$SOUND_VOL,afade=t=in:st=0.3:d=1.5[a]"
  fi
  set -- "$@" -filter_complex "$FG" -map "[v]" -map "[a]" -c:a aac -b:a 160k
elif [ -n "$HAS_AUDIO" ]; then
  set -- "$@" -filter_complex "$FG" -map "[v]" -map 0:a -c:a copy
else
  set -- "$@" -filter_complex "$FG" -map "[v]"
fi

ffmpeg -v error -y "$@" -t "$D" -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -r "$FPS" \
  -movflags +faststart "$OUT" || exit 1
echo "base: $D s"
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height -of csv=p=0 "$OUT" | tr '\n' ' '
echo
