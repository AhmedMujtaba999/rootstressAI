"""
make_demo_video.py
------------------
Renders a short demo video of the Root Stress Detection System for the
GitHub README: title card -> architecture flow -> request -> model reply -> end card.

Run from the repo root:

    pip install -r demo/requirements.txt

    python demo/make_demo_video.py                                   # sample field image + sample reply
    python demo/make_demo_video.py --image mapImage.jpeg             # your own field image
    python demo/make_demo_video.py --image mapImage.jpeg --call-api  # real reply from your deployed API
    python demo/make_demo_video.py --zones 6                         # change the zone count in the prompt

Outputs (written to demo/):
    demo.mp4    1280x720 H.264  -> drag into the README on github.com for a video player
    demo.gif    800px wide      -> commit to the repo, plays inline in the README
    poster.png  title frame     -> optional thumbnail
"""

import argparse
import base64
import io
import os
import random
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# imageio-ffmpeg ships its own ffmpeg binary, so nothing else needs installing.
try:
    import imageio_ffmpeg

    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG = "ffmpeg"  # fall back to a system-wide ffmpeg

# ---------------------------------------------------------------- settings
W, H = 1280, 720
FPS = 24
FADE = 0.35  # seconds of fade in/out on each scene

PROJECT_NAME = "Root Stress Detection System"
REPO_URL = "github.com/AhmedMujtaba999/rootstressAI"
ENDPOINT = "POST /backendLogicForZones"

BG = (14, 21, 18)
PANEL = (22, 33, 28)
PANEL_EDGE = (44, 62, 54)
TEXT = (232, 240, 236)
MUTED = (143, 163, 154)
GREEN = (74, 222, 128)
ORANGE = (255, 153, 0)
TEAL = (45, 212, 191)

PROMPT_TEMPLATE = (
    "You will receive an image showing a green-coloured dotted boundary. "
    "Please divide the highlighted area into {zones} zones of roughly equal size. "
    "These zones are for agricultural use, so make them practical and regular in shape. "
    "Do not use any external maps or resources. Only analyze the provided image."
)

SAMPLE_REPLY = (
    "The selected area can be divided into 4 practical zones using two horizontal "
    "and two vertical divisions. This creates four regular sections that are easier "
    "for crop planning, irrigation, and field access."
)

# Font file names are tried in order. Pillow searches the system font folders
# (C:\Windows\Fonts, /Library/Fonts, /usr/share/fonts) for bare names.
FONT_CANDIDATES = {
    "regular": ["Inter-Regular.otf", "segoeui.ttf", "Arial.ttf", "arial.ttf", "DejaVuSans.ttf"],
    "semibold": ["Inter-SemiBold.otf", "seguisb.ttf", "Arial Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "bold": ["Inter-Bold.otf", "segoeuib.ttf", "Arial Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "mono": ["DejaVuSansMono.ttf", "consola.ttf", "Menlo.ttc", "Courier New.ttf", "cour.ttf"],
}


@lru_cache(maxsize=None)
def font(kind, size):
    for name in FONT_CANDIDATES[kind]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


# ---------------------------------------------------------------- helpers
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ease(t):
    """Smoothstep: 0..1 -> 0..1 with soft start and stop."""
    t = clamp(t)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    """Blend two RGB colours; t=0 gives c1, t=1 gives c2."""
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def appear(t, start, length=0.6):
    """0 before `start`, rising to 1 over `length` seconds."""
    return ease((t - start) / length)


def wrap(draw, text, fnt, max_w):
    """Split text into lines that fit max_w pixels. Keeps explicit newlines."""
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            test = (line + " " + word).strip()
            if draw.textlength(test, font=fnt) <= max_w:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_typed(draw, x, y, lines, fnt, fill, n_chars, line_h, t, cursor_color=GREEN):
    """Typewriter effect over pre-wrapped lines, so text never reflows while typing."""
    total = sum(len(l) for l in lines) + max(len(lines) - 1, 0)
    left = n_chars
    end = (x, y)
    for line in lines:
        if left <= 0:
            break
        part = line[:left]
        draw.text((x, y), part, font=fnt, fill=fill)
        end = (x + draw.textlength(part, font=fnt) + 3, y)
        left -= len(line) + 1
        y += line_h
    typing = n_chars < total
    if typing or int(t * 2) % 2 == 0:  # solid while typing, blinking after
        cx, cy = end
        draw.rectangle([cx, cy + 4, cx + 2, cy + line_h - 8], fill=cursor_color)


def fit_text(draw, text, kind, max_w, max_h, sizes=(24, 22, 20, 18, 16, 15, 14)):
    """Largest font size whose wrapped text fits the box; trims if even the smallest is too big."""
    for size in sizes:
        fnt = font(kind, size)
        line_h = int(size * 1.5)
        lines = wrap(draw, text, fnt, max_w)
        if len(lines) * line_h <= max_h:
            return fnt, lines, line_h
    max_lines = max_h // line_h
    lines = lines[:max_lines]
    lines[-1] = lines[-1].rstrip(" .,") + " …"
    return fnt, lines, line_h


def clean_reply(text):
    """Strip markdown the model may return (**bold**, # headings) so it reads well on screen."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def background():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for gx in range(40, W, 40):  # faint dot grid
        for gy in range(40, H, 40):
            d.point((gx, gy), fill=(28, 40, 34))
    return img


def header(d, eyebrow, title, a=1.0):
    d.text((60, 42), eyebrow.upper(), font=font("semibold", 16), fill=mix(BG, GREEN, a))
    d.text((60, 66), title, font=font("bold", 34), fill=mix(BG, TEXT, a))


def chip(d, x, y, label, color, a=1.0):
    fnt = font("semibold", 18)
    w = d.textlength(label, font=fnt) + 32
    d.rounded_rectangle([x, y, x + w, y + 40], radius=20, fill=mix(BG, PANEL, a), outline=mix(BG, color, a), width=2)
    d.text((x + 16, y + 9), label, font=fnt, fill=mix(BG, TEXT, a))
    return x + w + 12


def rounded(img, radius=18):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], radius=radius, fill=255)
    return mask


# ---------------------------------------------------------------- sample field image
def make_sample_field(path, size=900, seed=7):
    """Synthetic aerial view of farm parcels with a green dotted boundary, like the real input."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (size, size), (120, 98, 66))
    d = ImageDraw.Draw(img)

    # patchwork of parcels, each with crop rows at its own angle
    palette = [(98, 130, 64), (132, 152, 76), (152, 126, 84), (86, 112, 58), (166, 148, 96), (110, 140, 70)]
    cuts_x = [0, 290 + rnd.randint(-30, 30), 610 + rnd.randint(-30, 30), size]
    cuts_y = [0, 260 + rnd.randint(-30, 30), 640 + rnd.randint(-30, 30), size]
    for i in range(3):
        for j in range(3):
            box = [cuts_x[i] + 6, cuts_y[j] + 6, cuts_x[i + 1] - 6, cuts_y[j + 1] - 6]
            base = rnd.choice(palette)
            d.rectangle(box, fill=base)
            rows = Image.new("RGB", (size * 2, size * 2), base)
            rd = ImageDraw.Draw(rows)
            darker = tuple(max(c - 22, 0) for c in base)
            for k in range(0, size * 2, 14):
                rd.line([(k, 0), (k, size * 2)], fill=darker, width=5)
            rows = rows.rotate(rnd.choice([0, 15, 30, 60, 90, 120]), center=(size, size))
            rows = rows.crop((size // 2, size // 2, size // 2 + size, size // 2 + size))
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).rectangle(box, fill=255)
            img.paste(rows, (0, 0), mask)

    # dirt tracks between parcels
    for x in cuts_x[1:-1]:
        d.line([(x, 0), (x, size)], fill=(176, 156, 120), width=10)
    for y in cuts_y[1:-1]:
        d.line([(0, y), (size, y)], fill=(176, 156, 120), width=10)

    # texture
    noise = Image.effect_noise((size, size), 28).convert("RGB")
    img = Image.blend(img, noise, 0.08).filter(ImageFilter.GaussianBlur(0.8))

    # green dotted boundary around the area to divide
    d = ImageDraw.Draw(img)
    poly = [(230, 190), (680, 160), (720, 650), (250, 700)]
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        steps = int(length // 22)
        for s in range(steps):
            if s % 2 == 0:
                a, b = s / steps, (s + 1) / steps
                d.line([(lerp(x1, x2, a), lerp(y1, y2, a)), (lerp(x1, x2, b), lerp(y1, y2, b))],
                       fill=(40, 255, 90), width=7)

    img.save(path, "JPEG", quality=90)
    return path


# ---------------------------------------------------------------- live API (optional)
def jpeg_b64(image_path):
    """The Lambda tells Bedrock the image is JPEG, so always send JPEG bytes."""
    buf = io.BytesIO()
    Image.open(image_path).convert("RGB").save(buf, "JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def call_api(image_path, prompt):
    import requests

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    url = os.environ.get("API_URL", "")
    if not url or "your-api-id" in url:
        sys.exit("Set API_URL in your .env (see .env.example) before using --call-api.")

    print(f"Calling {url} ...")
    resp = requests.post(
        url,
        json={"image_base64": jpeg_b64(image_path), "text_input": prompt, "metadata": {"source": "demo_video"}},
        timeout=90,
    )
    data = resp.json()
    if data.get("status") != "success":
        sys.exit(f"API returned an error: {data.get('message', resp.text)}")
    return data["reply"]


# ---------------------------------------------------------------- scenes
# Each scene is a function (t, dur) -> PIL.Image, where t is seconds into the scene.

def scene_title(t, dur):
    img = background()
    d = ImageDraw.Draw(img)
    a1, a2, a3 = appear(t, 0.1), appear(t, 0.6), appear(t, 1.1)
    d.rectangle([60, 250, 60 + int(80 * a1), 256], fill=GREEN)
    d.text((60, 280 + int(14 * (1 - a1))), PROJECT_NAME, font=font("bold", 64), fill=mix(BG, TEXT, a1))
    d.text((62, 370), "Field image + instruction in, practical zoning plan out — powered by Amazon Bedrock.",
           font=font("regular", 24), fill=mix(BG, MUTED, a2))
    x = 60
    for i, (label, color) in enumerate([("AWS Lambda", ORANGE), ("API Gateway", ORANGE),
                                        ("Amazon Bedrock · Nova Pro", TEAL), ("Amazon S3", ORANGE),
                                        ("Python · boto3", GREEN)]):
        x = chip(d, x, 440, label, color, appear(t, 1.1 + i * 0.15, 0.4))
    return img


def scene_architecture(t, dur):
    img = background()
    d = ImageDraw.Draw(img)
    header(d, "How it works", "One POST request, one multimodal model call", appear(t, 0))

    boxes = [("Client", "base64 image + prompt", GREEN),
             ("API Gateway", ENDPOINT, ORANGE),
             ("AWS Lambda", "lambda_function.py", ORANGE),
             ("Amazon Bedrock", "Nova Pro (image + text)", TEAL)]
    bw, bh, top = 240, 130, 285
    gap = (W - 120 - bw * len(boxes)) / (len(boxes) - 1)
    xs = [60 + i * (bw + gap) for i in range(len(boxes))]

    # request packet travels left -> right, then the reply travels back underneath
    p = clamp((t - 0.8) / 2.6) * (len(boxes) - 1)  # 0..3 across the boxes
    back = clamp((t - 3.8) / 1.6)

    for i, x in enumerate(xs[:-1]):  # arrows
        y = top + bh / 2
        x1, x2 = x + bw + 8, xs[i + 1] - 8
        d.line([(x1, y), (x2, y)], fill=PANEL_EDGE, width=3)
        lit = clamp(p - i)
        if lit > 0:
            d.line([(x1, y), (lerp(x1, x2, lit), y)], fill=GREEN, width=3)
        d.polygon([(x2, y), (x2 - 10, y - 7), (x2 - 10, y + 7)], fill=GREEN if lit >= 1 else PANEL_EDGE)

    for i, (x, (name, sub, color)) in enumerate(zip(xs, boxes)):
        a = appear(t, 0.15 * i, 0.5)
        active = p >= i - 0.02
        edge = color if active else PANEL_EDGE
        d.rounded_rectangle([x, top, x + bw, top + bh], radius=16, fill=mix(BG, PANEL, a),
                            outline=mix(BG, edge, a), width=3 if active else 2)
        d.text((x + 20, top + 26), name, font=font("bold", 24), fill=mix(BG, TEXT, a))
        sfont = font("regular", 16)
        for k, line in enumerate(wrap(d, sub, sfont, bw - 40)):
            d.text((x + 20, top + 66 + k * 22), line, font=sfont, fill=mix(BG, MUTED, a))

    if 0 < p < len(boxes) - 1:  # packet on the request path
        i = int(p)
        x1, x2 = xs[i] + bw + 8, xs[i + 1] - 8
        cx, cy = lerp(x1, x2, p - i), top + bh / 2
        d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=GREEN)

    # reply path along the bottom
    yb = top + bh + 90
    xr, xl = xs[-1] + bw / 2, xs[0] + bw / 2
    path_col = mix(PANEL_EDGE, TEAL, ease(back * 3))
    d.line([(xr, top + bh + 6), (xr, yb), (xl, yb), (xl, top + bh + 6)], fill=path_col, width=3, joint="curve")
    if back > 0:
        lit_x = lerp(xr, xl, back)
        d.line([(xr, yb), (lit_x, yb)], fill=TEAL, width=3)
        if back < 1:
            d.ellipse([lit_x - 8, yb - 8, lit_x + 8, yb + 8], fill=TEAL)
    label = '200 OK  ·  { "status": "success", "reply": "..." }'
    lf = font("mono", 18)
    lw = d.textlength(label, font=lf)
    d.text(((W - lw) / 2, yb + 18), label, font=lf, fill=mix(BG, TEAL, appear(t, 4.0)))
    return img


def make_image_panel(field_img):
    """Field image fitted into the left panel with rounded corners."""
    box_w, box_h = 520, 520
    im = field_img.copy()
    im.thumbnail((box_w, box_h))
    return im, rounded(im)


def draw_image_panel(img, panel, a):
    im, mask = panel
    x = 60 + (520 - im.size[0]) // 2
    y = 150 + (520 - im.size[1]) // 2
    faded = Image.blend(Image.new("RGB", im.size, BG), im, a)
    img.paste(faded, (x, y), mask)
    ImageDraw.Draw(img).text((60, 150 + 520 + 10), "Input: field image with highlighted area",
                             font=font("regular", 15), fill=mix(BG, MUTED, a))


def scene_request(t, dur, panel, b64_preview, kb, prompt_lines, prompt_font, prompt_lh, type_time):
    img = background()
    d = ImageDraw.Draw(img)
    header(d, "Step 1 · Request", "Send the image and an instruction", appear(t, 0))
    draw_image_panel(img, panel, appear(t, 0.1))

    x0 = 620
    a = appear(t, 0.3)
    d.rounded_rectangle([x0, 150, W - 60, 670], radius=16, fill=mix(BG, PANEL, a), outline=mix(BG, PANEL_EDGE, a), width=2)
    d.text((x0 + 28, 174), ENDPOINT, font=font("mono", 20), fill=mix(BG, ORANGE, a))
    d.text((x0 + 28, 222), "image_base64", font=font("semibold", 16), fill=mix(BG, MUTED, a))
    d.text((x0 + 28, 246), f"{b64_preview}…  ({kb} KB)", font=font("mono", 17), fill=mix(BG, TEXT, a))
    d.text((x0 + 28, 296), "text_input", font=font("semibold", 16), fill=mix(BG, MUTED, a))

    chars = sum(len(l) + 1 for l in prompt_lines)
    n = int(chars * clamp((t - 0.9) / type_time))
    if t > 0.9:
        draw_typed(d, x0 + 28, 322, prompt_lines, prompt_font, TEXT, n, prompt_lh, t)
    return img


def scene_response(t, dur, panel, reply_lines, reply_font, reply_lh, type_time):
    img = background()
    d = ImageDraw.Draw(img)
    header(d, "Step 2 · Response", "Nova Pro returns a practical zoning plan", appear(t, 0))
    draw_image_panel(img, panel, 1.0)

    x0 = 620
    d.rounded_rectangle([x0, 150, W - 60, 670], radius=16, fill=PANEL, outline=mix(PANEL_EDGE, TEAL, appear(t, 0.2)), width=2)
    a = appear(t, 0.2)
    d.text((x0 + 28, 174), "200 OK", font=font("mono", 20), fill=mix(BG, GREEN, a))
    d.text((x0 + 120, 174), '"status": "success"', font=font("mono", 20), fill=mix(BG, MUTED, a))
    d.text((x0 + 28, 222), "reply", font=font("semibold", 16), fill=mix(BG, MUTED, a))

    chars = sum(len(l) + 1 for l in reply_lines)
    n = int(chars * clamp((t - 0.6) / type_time))
    if t > 0.6:
        draw_typed(d, x0 + 28, 248, reply_lines, reply_font, TEXT, n, reply_lh, t, cursor_color=TEAL)
    return img


def scene_end(t, dur):
    img = background()
    d = ImageDraw.Draw(img)
    a1, a2, a3 = appear(t, 0.1), appear(t, 0.5), appear(t, 0.9)
    name_f = font("bold", 52)
    nw = d.textlength(PROJECT_NAME, font=name_f)
    d.text(((W - nw) / 2, 270), PROJECT_NAME, font=name_f, fill=mix(BG, TEXT, a1))
    url_f = font("mono", 24)
    uw = d.textlength(REPO_URL, font=url_f)
    d.text(((W - uw) / 2, 350), REPO_URL, font=url_f, fill=mix(BG, GREEN, a2))
    stack = "Python  ·  AWS Lambda  ·  API Gateway  ·  Amazon Bedrock  ·  Amazon S3"
    sf = font("regular", 20)
    sw = d.textlength(stack, font=sf)
    d.text(((W - sw) / 2, 405), stack, font=sf, fill=mix(BG, MUTED, a3))
    return img


# ---------------------------------------------------------------- render
def render(scenes, mp4_path):
    cmd = [FFMPEG, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    bg = background()
    total = sum(int(dur * FPS) for dur, _ in scenes)
    done = 0
    for dur, fn in scenes:
        frames = int(dur * FPS)
        for f in range(frames):
            t = f / FPS
            frame = fn(t, dur)
            fade = ease(min(t / FADE, (dur - t) / FADE, 1.0))
            if fade < 1:
                frame = Image.blend(bg, frame, fade)
            proc.stdin.write(frame.tobytes())
            done += 1
            if done % FPS == 0:
                print(f"\r  rendering {done * 100 // total:3d}%", end="", flush=True)
    proc.stdin.close()
    proc.wait()
    print("\r  rendering 100%")
    if proc.returncode != 0:
        sys.exit("ffmpeg failed while writing the MP4.")


def make_gif(mp4_path, gif_path, width=800, fps=10):
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=128:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp4_path), "-vf", vf, "-loop", "0", str(gif_path)],
                   check=True)


def main():
    ap = argparse.ArgumentParser(description="Render a demo video for the README.")
    ap.add_argument("--image", help="Field image to show (default: generates demo/sample_field.jpg)")
    ap.add_argument("--zones", type=int, default=4, help="Number of zones in the prompt (default 4)")
    ap.add_argument("--reply", help="Model reply text to show (default: the sample reply from the README)")
    ap.add_argument("--call-api", action="store_true", help="Call your deployed API (API_URL in .env) for a real reply")
    ap.add_argument("--out", default=str(Path(__file__).parent), help="Output folder (default: demo/)")
    ap.add_argument("--no-gif", action="store_true", help="Skip the GIF")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    image_path = args.image or make_sample_field(out / "sample_field.jpg")
    prompt = PROMPT_TEMPLATE.format(zones=args.zones)

    if args.call_api:
        reply = call_api(image_path, prompt)
    elif args.reply:
        reply = args.reply
    else:
        reply = SAMPLE_REPLY
        if args.zones != 4:
            print("Note: the sample reply describes 4 zones. Pass --reply or --call-api for a matching reply.")
    reply = clean_reply(reply)

    field = Image.open(image_path).convert("RGB")
    panel = make_image_panel(field)
    b64 = jpeg_b64(image_path)
    kb = len(b64) * 3 // 4 // 1024

    # Wrap text once up front so it never reflows while it types out.
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    text_w = W - 60 - 620 - 56
    p_font, p_lines, p_lh = fit_text(measure, prompt, "regular", text_w, 670 - 322 - 24)
    r_font, r_lines, r_lh = fit_text(measure, reply, "regular", text_w, 670 - 248 - 24,
                                    sizes=(28, 26, 24, 22, 20, 18, 16, 15, 14))

    # Typing speed ~70 characters/second, then hold so people can read it.
    p_type = clamp(len(prompt) / 70, 2.5, 6.0)
    r_type = clamp(len(reply) / 70, 2.5, 8.0)

    scenes = [
        (4.0, scene_title),
        (6.5, scene_architecture),
        (0.9 + p_type + 2.0, lambda t, d: scene_request(t, d, panel, b64[:18], kb, p_lines, p_font, p_lh, p_type)),
        (0.6 + r_type + 3.5, lambda t, d: scene_response(t, d, panel, r_lines, r_font, r_lh, r_type)),
        (3.5, scene_end),
    ]

    mp4 = out / "demo.mp4"
    print(f"Writing {mp4}")
    render(scenes, mp4)
    scene_title(3.0, 4.0).save(out / "poster.png")

    if not args.no_gif:
        gif = out / "demo.gif"
        print(f"Writing {gif}")
        make_gif(mp4, gif)

    for f in [mp4, out / "demo.gif", out / "poster.png"]:
        if f.exists():
            print(f"  {f}  {f.stat().st_size / 1_048_576:.1f} MB")
    print("Done. Keep each file under 10 MB for GitHub uploads on a free plan.")


if __name__ == "__main__":
    main()
