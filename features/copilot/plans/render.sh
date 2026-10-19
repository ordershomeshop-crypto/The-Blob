#!/usr/bin/env bash
set -euo pipefail

# Convenience script: generate frames and render MP4
ROOT_DIR="$(dirname "$0")"
python "$ROOT_DIR/make_animatic.py"
ffmpeg -framerate 24 -i "$ROOT_DIR/frames/frame_%03d.png" -i "$ROOT_DIR/sfx_mix.wav" -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest -movflags +faststart "$ROOT_DIR/animatic_1080x1920_24fps_4s.mp4"

echo "Rendered: $ROOT_DIR/animatic_1080x1920_24fps_4s.mp4"
