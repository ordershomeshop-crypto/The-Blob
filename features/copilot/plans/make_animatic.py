# make_animatic.py
# Generates 96 PNG frames (1080x1920) and a 4s SFX WAV for the "Diet Starts Tomorrow" animatic loop.
# Requires: Pillow, numpy
# Run: python make_animatic.py

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np
import math
import os
import wave
import struct

# ---- Settings ----
W, H = 1080, 1920
FPS = 24
DURATION = 4.0
FRAMES = int(FPS * DURATION)  # 96
OUT_DIR = "frames"
SFX_FILE = "sfx_mix.wav"
SR = 44100

os.makedirs(OUT_DIR, exist_ok=True)

# ---- Easing helpers ----
def lerp(a, b, t): return a + (b - a) * t
def ease_in_out(t): return (1 - math.cos(math.pi * t)) / 2
def ease_out(t): return 1 - (1 - t) * (1 - t)
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))

# ---- Animation key timings in frames ----
# Matches spec earlier: door thud ~frame16, victory walk frames 24-47, door creak ~frame54, blink hold frames ~82-88, final door shut at ~frame94
# We will follow approximate timings described in the plan.
# Utility: convert frame index to normalized t in [0,1]
def tf(f): return f / (FRAMES - 1)

# ---- Blob & scene parameters ----
blob_radius = 180
start_center = (W//2, H//2 - 120)  # initial center
left_center = (W//2 - 220, H//2 - 120)  # where it walks toward left
fridge_x = W - 240  # fridge left edge when closed
fridge_width = 240
fridge_height = 700
floor_y = H//2 + 360

# Precompute per-frame parameters
frames = []
for i in range(FRAMES):
    # default pose values
    center_x = start_center[0]
    center_y = start_center[1]
    scale_y = 1.0
    chest_tilt = 0.0
    eyebrow_raise = 0.0
    eye_widen = 0.0
    blink = 0.0
    fridge_open = 0.0  # 0 closed, 1 wide
    light_alpha = 0.0

    # Stage 1: frames 0-23 vow (frames 0..23)
    if 0 <= i <= 23:
        # small nod: 7-12 frames nod down then up
        if 7 <= i <= 12:
            nod_t = (i - 7) / (12 - 7)
            chest_tilt = -0.06 * math.sin(nod_t * math.pi)  # subtle rotation
        # door push at 12..16: close door hard at 16
        if 12 <= i <= 16:
            # fridge was slightly ajar at t=12 and closes by 16
            fridge_open = 0.6 * (1 - clamp((i - 12)/4))
    # Stage 2: 24-47 victory walk
    if 24 <= i <= 47:
        walk_t = (i - 24) / (47 - 24)
        # move center_x left with a tiny bounce
        center_x = lerp(start_center[0], left_center[0], ease_out(walk_t))
        # small bounce on steps: three contacts at approx frames 28,36,44
        for contact in (28, 36, 44):
            d = abs(i - contact)
            if d < 3:
                scale_y = 1.0 - 0.08 * (1 - d/3)
        if i >= 40:
            eyebrow_raise = 1.0 if i < 44 else 0.0
    # Stage 3: 48-71 temptation
    if 48 <= i <= 71:
        # fridge creaks open at ~54 (i ~= 54)
        if i >= 52:
            fridge_open = clamp((i - 52) / (8))  # open gradually 52..60
        # light spill alpha ramps with fridge_open
        light_alpha = fridge_open * 0.9
        # blob slows and leans back
        slow_t = clamp((i - 48) / (71 - 48))
        # move back slightly toward start
        center_x = lerp(left_center[0], left_center[0] + 60, slow_t * 0.6)
        # eye widen at ~60
        if 58 <= i <= 64:
            eye_widen = 1.0 - abs(i - 61)/3.0
    # Stage 4: 72-95 surrender & loop
    if 72 <= i <= 95:
        # stop at 76, blink hold 76..88, then slide back 86..94
        if 72 <= i <= 76:
            # decelerate
            pass
        # blink long: closed most between 82..88
        if 76 <= i <= 90:
            # blink progress: 76->82 close, 82->88 hold, 88->90 open
            if 76 <= i <= 82:
                blink = clamp((i - 76) / 6)
            elif 82 <= i <= 88:
                blink = 1.0
            else:
                blink = clamp(1.0 - (i - 88) / 2)
        # sigh happens around 82
        # slide back toward fridge 86..92
        if 86 <= i <= 92:
            slide_t = clamp((i - 86) / 6)
            center_x = lerp(left_center[0] + 60, start_center[0], ease_in_out(slide_t))
        # final door shutting at 94..95
        if i >= 92:
            fridge_open = clamp(1.0 - (i - 92) / 3.0)

    # Ensure frame 0 and frame 95 identical later by overriding final frame to start pose
    frames.append({
        'center': (int(center_x), int(center_y)),
        'scale_y': scale_y,
        'chest_tilt': chest_tilt,
        'eyebrow': eyebrow_raise,
        'eye_widen': eye_widen,
        'blink': blink,
        'fridge_open': clamp(fridge_open),
        'light_alpha': clamp(light_alpha),
    })

# Force frame 95 identical to frame 0 for invisible loop
frames[-1] = frames[0].copy()

# ---- Drawing function ----
def draw_frame(i, data):
    img = Image.new('RGB', (W, H), (245, 245, 245))  # plain kitchen wall
    draw = ImageDraw.Draw(img)

    # floor line (subtle)
    floor_color = (230, 230, 230)
    draw.rectangle([0, floor_y, W, H], fill=(240,240,240))

    # fridge body (right)
    fx = fridge_x
    fy = floor_y - fridge_height
    # fridge base
    fridge_color = (220, 230, 235)
    draw.rectangle([fx, fy, fx + fridge_width, fy + fridge_height], fill=fridge_color)
    # fridge door (we represent opening as left edge sliding right when open)
    door_open = data['fridge_open']  # 0 closed, 1 open
    door_shift = int(door_open * 120)  # how far door slides open
    door_color = (235, 245, 250)
    draw.rectangle([fx + door_shift, fy + 10, fx + fridge_width, fy + fridge_height - 10], fill=door_color)
    # fridge handle
    handle_x = fx + fridge_width - 40
    draw.rounded_rectangle([handle_x, fy + fridge_height//2 - 40, handle_x + 16, fy + fridge_height//2 + 40], radius=8, fill=(160,160,160))

    # light spill when open: draw a soft vertical gradient rectangle from fridge door to floor
    if data['light_alpha'] > 0.02:
        alpha = int(160 * data['light_alpha'])
        # create gradient overlay
        grad = Image.new('RGBA', (W, H), (0,0,0,0))
        gdraw = ImageDraw.Draw(grad)
        gx0 = fx - 220
        gx1 = fx + 40
        for y in range(fy + fridge_height//4, floor_y + 60):
            rel = (y - (fy + fridge_height//4)) / (floor_y + 60 - (fy + fridge_height//4) + 1)
            line_alpha = int(alpha * (1 - rel)**1.6 * 0.9)
            gdraw.line([(gx0, y), (gx1, y)], fill=(255, 230, 80, line_alpha))
        img = Image.alpha_composite(img.convert('RGBA'), grad).convert('RGB')

    # Blob (simple round character)
    cx, cy = data['center']
    r = blob_radius
    sy = data['scale_y']
    # simulate squash: scale y of ellipse
    blob_w = int(r * 2)
    blob_h = int(r * 2 * sy)
    blob_box = [cx - blob_w//2, cy - blob_h//2, cx + blob_w//2, cy + blob_h//2]
    draw.ellipse(blob_box, fill=(190, 80, 120))  # pink blob

    # chest highlight (subtle)
    draw.ellipse([cx - 40, cy - 10, cx + 40, cy + 30], fill=(220,120,150))

    # eyes and brows
    eye_w = 36
    eye_h = 20
    # left eye position relative to blob center
    ex = cx - 46
    ey = cy - 34
    pupil_r = 10
    # blink: 0..1 means closed
    blink = data['blink']
    # eye widen factor -> pupil smaller when widened
    ew = 1.0 + 0.2 * data['eye_widen']
    # left eye
    # eyelid: draw an ellipse clipped by blink
    lid_h = int(eye_h * (1 - blink))
    if lid_h > 2:
        draw.ellipse([ex - eye_w, ey - lid_h//2, ex + eye_w, ey + lid_h//2], fill=(255,255,255))
        draw.ellipse([ex - pupil_r, ey - pupil_r, ex + pupil_r, ey + pupil_r], fill=(30,30,30))
    else:
        # closed: small line
        draw.line([ex - 18, ey, ex + 18, ey], fill=(40,40,40), width=4)
    # right eye
    ex2 = cx + 46
    if lid_h > 2:
        draw.ellipse([ex2 - eye_w, ey - lid_h//2, ex2 + eye_w, ey + lid_h//2], fill=(255,255,255))
        draw.ellipse([ex2 - pupil_r, ey - pupil_r, ex2 + pupil_r, ey + pupil_r], fill=(30,30,30))
    else:
        draw.line([ex2 - 18, ey, ex2 + 18, ey], fill=(40,40,40), width=4)

    # eyebrow (one raised during victory walk)
    if data['eyebrow'] > 0.1:
        draw.line([ex2 - 24, ey - 36, ex2 + 18, ey - 48], fill=(50,50,50), width=8)
    else:
        draw.line([ex - 28, ey - 46, ex - 6, ey - 40], fill=(50,50,50), width=6)
        draw.line([ex2 - 6, ey - 40, ex2 + 28, ey - 46], fill=(50,50,50), width=6)

    # small smile when open
    if data['blink'] > 0.4:
        draw.arc([cx - 48, cy - 10, cx + 48, cy + 60], start=200, end=340, fill=(80,30,60), width=6)

    # fridge shadow / ground contact
    draw.rectangle([fx - 8, floor_y - 6, fx + fridge_width + 8, floor_y + 20], fill=(210,210,210))

    # subtle vignette / contrast
    img = img.filter(ImageFilter.GaussianBlur(radius=0.0))

    return img

# ---- Render frames ----
print("Rendering frames...")
for i, data in enumerate(frames):
    img = draw_frame(i, data)
    fname = os.path.join(OUT_DIR, f"frame_{i:03d}.png")
    img.save(fname, optimize=True)
    if i % 12 == 0:
        print(f"  wrote {fname}")

print("Frames written to", OUT_DIR)

# ---- Generate SFX WAV ----
print("Generating SFX WAV...")
t = np.linspace(0, DURATION, int(SR * DURATION), endpoint=False)
sfx = np.zeros_like(t)

# Helper: add a decaying sine burst at time center (seconds)
def add_burst(arr, center_s, freq, duration_s, amp=0.8, decay=6.0):
    idx0 = int(max(0, (center_s - duration_s/2) * SR))
    idx1 = int(min(len(arr), (center_s + duration_s/2) * SR))
    times = np.arange(idx0, idx1) / SR
    env = np.exp(-decay * (times - center_s + duration_s/2) / duration_s)
    env = np.clip(env, 0, 1)
    wave = np.sin(2 * math.pi * freq * (times - (center_s - duration_s/2))) * env
    arr[idx0:idx1] += amp * wave

# Helper: add a soft noise-based sigh
def add_sigh(arr, start_s, length_s, amp=0.4):
    idx0 = int(start_s * SR)
    idx1 = int(min(len(arr), idx0 + int(length_s * SR)))
    n = idx1 - idx0
    noise = np.random.normal(0, 1, n) * np.linspace(1.0, 0.1, n)
    arr[idx0:idx1] += amp * 0.15 * noise

# Compute important times (seconds) from frame numbers in the plan:
sec = lambda frame: frame / FPS
# door thud at frame ~16 and ~94 -> sec(16), sec(94)
add_burst(sfx, sec(16), freq=90, duration_s=0.22, amp=1.0, decay=8.0)
add_burst(sfx, sec(94), freq=95, duration_s=0.22, amp=1.0, decay=8.0)
# ding at frame ~54
add_burst(sfx, sec(54), freq=1200, duration_s=0.18, amp=0.6, decay=12.0)
# tiny footsteps at frames 28,36,44 (soft high-frequency clicks)
for f in (28,36,44):
    add_burst(sfx, sec(f), freq=450, duration_s=0.08, amp=0.18, decay=18.0)
# sigh at frame ~82
add_sigh(sfx, sec(82), length_s=0.45, amp=0.8)
# gentle low ambient to glue things
sfx += 0.02 * np.sin(2 * math.pi * 55 * t) * np.exp(-0.6 * t)

# Normalize to int16
max_val = np.max(np.abs(sfx)) + 1e-9
sfx = sfx / max_val * 0.9
sfx_int16 = np.int16(sfx * 32767)

# Write WAV (mono)
with wave.open(SFX_FILE, 'w') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(sfx_int16.tobytes())

print("WAV written:", SFX_FILE)
print("Done. Render MP4 with the ffmpeg command:")
print("ffmpeg -framerate 24 -i frames/frame_%03d.png -i sfx_mix.wav -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest -movflags +faststart animatic_1080x1920_24fps_4s.mp4")
