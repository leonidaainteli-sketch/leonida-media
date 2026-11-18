"""Leonida Intel vertical video maker (TikTok / Shorts / Reels).

Usage: python3 make_tiktok.py spec.json
spec = {
  "out": "video.mp4",
  "handle": "@leonidaaintel",
  "hook": ["GTA 6 DROPS", "TOMORROW"],          # big pop-in lines, first ~2.5 s
  "hook_sub": "3 things to do tonight",          # optional small line under hook
  "items": [{"title": "Preload is live", "sub": "Since Nov 12"}],
  "cta": "Follow for daily GTA 6 intel",
  "backgrounds": ["path/to/official_screenshot.jpg"]   # optional, cycled per scene
}
No music is embedded on purpose: add a trending sound in the TikTok/YouTube app
(licensed and boosted by the algorithm). A silent AAC track is included.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
BG = (14, 10, 31)
PINK = (255, 61, 139)
ORANGE = (255, 179, 71)
WHITE = (255, 255, 255)
MUTED = (190, 180, 220)
F_BLACK = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
F_SEMI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

# Text stays inside the TikTok safe zone (UI covers bottom ~380 px and right ~140 px)
SAFE_L, SAFE_R = 70, W - 150
SAFE_TOP, SAFE_BOTTOM = 260, H - 420


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=f) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_font(draw, text, path, max_size, max_w):
    size = max_size
    while size > 40:
        f = font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return font(path, size)


def make_sun(size):
    grad = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(grad)
    for y in range(size):
        d.line([(0, y), (size, y)], fill=lerp(PINK, ORANGE, y / size))
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([0, 0, size - 1, size - 1], fill=255)
    y, h, gap = int(size * 0.58), max(2, int(size * 0.018)), int(size * 0.07)
    while y < size:
        md.rectangle([0, y, size, y + h], fill=0)
        y += gap
        h = int(h * 1.35) + 1
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def base_background():
    im = Image.new("RGBA", (W, H), BG + (255,))
    hz = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hz)
    for i in range(H):
        t = i / H
        a = int(120 * max(0, t - 0.45) / 0.55)
        hd.line([(0, i), (W, i)], fill=PINK + (a,))
    im.alpha_composite(hz)
    return im


class Renderer:
    def __init__(self, spec):
        self.spec = spec
        self.base = base_background()
        self.sun = make_sun(900)
        pad = 120
        g = Image.new("RGBA", (900 + 2 * pad, 900 + 2 * pad), (0, 0, 0, 0))
        g.alpha_composite(self.sun, (pad, pad))
        self.sun_glow = g.filter(ImageFilter.GaussianBlur(45))
        self.bgs = []
        for p in spec.get("backgrounds", []) or []:
            if os.path.exists(p):
                img = Image.open(p).convert("RGB")
                self.bgs.append(img)
        self.scenes = self.build_scenes()
        self.duration = sum(s[1] for s in self.scenes)

    def build_scenes(self):
        s = [("hook", 2.6, None)]
        for it in self.spec.get("items", []):
            s.append(("item", 3.0, it))
        s.append(("cta", 2.6, None))
        return s

    def background(self, scene_idx, t_local, dur):
        if self.bgs:
            img = self.bgs[scene_idx % len(self.bgs)]
            # cover-fit then slow Ken Burns zoom
            z = 1.0 + 0.08 * (t_local / dur)
            scale = max(W / img.width, H / img.height) * z
            nw, nh = int(img.width * scale), int(img.height * scale)
            r = img.resize((nw, nh), Image.LANCZOS)
            x, y = (nw - W) // 2, (nh - H) // 2
            frame = r.crop((x, y, x + W, y + H)).convert("RGBA")
            shade = Image.new("RGBA", (W, H), BG + (165,))
            frame.alpha_composite(shade)
            return frame
        frame = self.base.copy()
        # sun slowly rising behind the text
        total_t = sum(sc[1] for sc in self.scenes[:scene_idx]) + t_local
        rise = 1 - total_t / max(self.duration, 0.01)
        sy = int(H * 0.52 + 160 * rise)
        sx = (W - 900) // 2
        frame.alpha_composite(self.sun_glow, (sx - 120, sy - 120))
        frame.alpha_composite(self.sun, (sx, sy))
        return frame

    def draw_text_block(self, frame, lines, t):
        """lines: list of (text, font, color). Pop-in from below with fade."""
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        heights = []
        for text, f, _ in lines:
            bb = d.textbbox((0, 0), text, font=f)
            heights.append(bb[3] - bb[1])
        gap = 28
        total = sum(heights) + gap * (len(lines) - 1)
        y = (SAFE_TOP + SAFE_BOTTOM) // 2 - total // 2 - 120
        for i, (text, f, col) in enumerate(lines):
            p = ease_out((t - i * 0.12) / 0.35)
            off = int((1 - p) * 60)
            alpha = int(255 * p)
            w = d.textlength(text, font=f)
            x = SAFE_L + ((SAFE_R - SAFE_L) - w) / 2
            bb = d.textbbox((0, 0), text, font=f)
            d.text((x + 6, y + off + 8 - bb[1]), text, font=f, fill=(0, 0, 0, int(alpha * 0.55)))
            d.text((x, y + off - bb[1]), text, font=f, fill=col + (alpha,))
            y += heights[i] + gap
        frame.alpha_composite(layer)

    def hook_lines(self, d):
        maxw = SAFE_R - SAFE_L
        out = []
        for i, line in enumerate(self.spec["hook"]):
            f = fit_font(d, line, F_BLACK, 170, maxw)
            out.append((line, f, ORANGE if i == len(self.spec["hook"]) - 1 else WHITE))
        if self.spec.get("hook_sub"):
            f = font(F_BOLD, 62)
            for ln in wrap(d, self.spec["hook_sub"], f, maxw):
                out.append((ln, f, WHITE))
        return out

    def item_lines(self, d, idx, it):
        maxw = SAFE_R - SAFE_L
        out = [(f"{idx}", font(F_BLACK, 200), ORANGE)]
        tf = font(F_BLACK, 104)
        for ln in wrap(d, it["title"], tf, maxw):
            out.append((ln, tf, WHITE))
        if it.get("sub"):
            sf = font(F_SEMI, 58)
            for ln in wrap(d, it["sub"], sf, maxw):
                out.append((ln, sf, MUTED))
        return out

    def cta_lines(self, d):
        maxw = SAFE_R - SAFE_L
        out = []
        cf = font(F_BLACK, 96)
        for ln in wrap(d, self.spec.get("cta", "Follow for daily GTA 6 intel"), cf, maxw):
            out.append((ln, cf, WHITE))
        out.append((self.spec.get("handle", "@leonidaaintel"), font(F_BOLD, 72), ORANGE))
        out.append(("Fan page — not affiliated with Rockstar Games", font(F_SEMI, 36), MUTED))
        return out

    def progress_bar(self, frame, t_global):
        d = ImageDraw.Draw(frame)
        p = t_global / self.duration
        d.rounded_rectangle([SAFE_L, 200, SAFE_R, 212], radius=6, fill=(255, 255, 255, 50))
        d.rounded_rectangle([SAFE_L, 200, SAFE_L + int((SAFE_R - SAFE_L) * p), 212], radius=6, fill=ORANGE + (255,))

    def frame_at(self, t_global):
        acc = 0.0
        for idx, (kind, dur, data) in enumerate(self.scenes):
            if t_global < acc + dur or idx == len(self.scenes) - 1:
                t = t_global - acc
                frame = self.background(idx, t, dur)
                d = ImageDraw.Draw(frame)
                if kind == "hook":
                    lines = self.hook_lines(d)
                elif kind == "item":
                    lines = self.item_lines(d, idx, data)
                else:
                    lines = self.cta_lines(d)
                self.draw_text_block(frame, lines, t)
                self.progress_bar(frame, t_global)
                return frame.convert("RGB")
            acc += dur


def main(spec_path):
    spec = json.load(open(spec_path))
    r = Renderer(spec)
    n = int(r.duration * FPS)
    out = spec.get("out", "video.mp4")
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n):
            r.frame_at(i / FPS).save(os.path.join(tmp, f"f{i:05d}.jpg"), quality=92)
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-framerate", str(FPS), "-i", os.path.join(tmp, "f%05d.jpg"),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", out,
        ], check=True)
    print(out, f"{r.duration:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1])
