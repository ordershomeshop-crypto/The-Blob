# Diet Starts Tomorrow — Animatic package

This folder contains a ready-to-run animatic generator for the "Diet Starts Tomorrow" 4s loop (1080×1920, 24fps).

What is included
- make_animatic.py — generates 96 PNG frames in frames/ and a synchronized sfx_mix.wav
- render.sh — convenience script to run the generator and render an MP4 with ffmpeg
- README.md — this file

How to render (Linux / macOS / WSL)

1) Install Python dependencies
   pip install pillow numpy

2) Run the generator (this writes frames/frame_000.png -> frame_095.png and sfx_mix.wav):
   python features/copilot/plans/make_animatic.py

3) Render MP4 with ffmpeg (example):
   ffmpeg -framerate 24 -i features/copilot/plans/frames/frame_%03d.png -i features/copilot/plans/sfx_mix.wav -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest -movflags +faststart features/copilot/plans/animatic_1080x1920_24fps_4s.mp4

Notes
- The script keeps frame_000 and frame_095 identical so the loop is seamless. Do not enable frame blending or per-frame motion blur when rendering, unless you verify the seam.
- If your default branch is not "main" (e.g. "master"), adjust accordingly when pulling or merging.
