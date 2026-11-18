from PIL import Image, ImageDraw, ImageFont, ImageFilter

BG = (14, 10, 31)
PINK = (255, 61, 139)
ORANGE = (255, 179, 71)
WHITE = (255, 255, 255)
FONT_BLACK = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONT_SEMI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sun(size, stripes=True):
    """Retro sunset disc: pink->orange vertical gradient, dark stripes in lower half."""
    s = size
    grad = Image.new("RGB", (s, s))
    d = ImageDraw.Draw(grad)
    for y in range(s):
        d.line([(0, y), (s, y)], fill=lerp(PINK, ORANGE, y / s))
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([0, 0, s - 1, s - 1], fill=255)
    if stripes:
        y = int(s * 0.58)
        h = max(2, int(s * 0.018))
        gap = int(s * 0.07)
        while y < s:
            md.rectangle([0, y, s, y + h], fill=0)
            y += gap
            h = int(h * 1.35) + 1
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def glow_paste(base, img, pos, radius):
    pad = radius * 3
    c = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    c.alpha_composite(img, (pad, pad))
    c = c.filter(ImageFilter.GaussianBlur(radius))
    base.alpha_composite(c, (pos[0] - pad, pos[1] - pad))


def glow(img, radius):
    return img.filter(ImageFilter.GaussianBlur(radius))


def avatar(path):
    W = 1080
    im = Image.new("RGBA", (W, W), BG + (255,))
    s = sun(760)
    glow_paste(im, s, ((W - 760) // 2, (W - 760) // 2), 40)
    im.alpha_composite(s, ((W - 760) // 2, (W - 760) // 2))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT_BLACK, 420)
    text = "LI"
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (W - tw) // 2 - bb[0]
    y = (W - th) // 2 - bb[1]
    shadow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x + 10, y + 14), text, font=f, fill=(14, 10, 31, 200))
    im.alpha_composite(glow(shadow, 8))
    d.text((x, y), text, font=f, fill=WHITE)
    im.convert("RGB").save(path, quality=95)


def banner(path, W, H, safe_w=None, safe_h=None):
    im = Image.new("RGBA", (W, H), BG + (255,))
    sw = safe_w or W
    sh = safe_h or H
    ox, oy = (W - sw) // 2, (H - sh) // 2
    # horizon glow
    hz = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hz)
    for i in range(H):
        t = i / H
        a = int(110 * max(0, t - 0.35) / 0.65)
        hd.line([(0, i), (W, i)], fill=PINK + (a,))
    im.alpha_composite(hz)
    # sun on the right of the safe area
    ss = int(sh * 1.05)
    s = sun(ss)
    sx = ox + int(sw * 0.04)
    sy = oy + int(sh * 0.12)
    glow_paste(im, s, (sx, sy), int(ss * 0.06))
    im.alpha_composite(s, (sx, sy))
    d = ImageDraw.Draw(im)
    pad = int(sw * 0.05)
    f1 = ImageFont.truetype(FONT_BLACK, int(sh * 0.22))
    f2 = ImageFont.truetype(FONT_SEMI, int(sh * 0.085))
    f3 = ImageFont.truetype(FONT_SEMI, int(sh * 0.055))
    right = ox + sw - pad
    def rtext(y, t, f, col):
        w = d.textlength(t, font=f)
        d.text((right - w, y), t, font=f, fill=col)
    y = oy + int(sh * 0.2)
    rtext(y, "LEONIDA INTEL", f1, WHITE)
    y += int(sh * 0.32)
    rtext(y, "GTA 6 tips · hidden spots · daily news", f2, ORANGE)
    y += int(sh * 0.16)
    rtext(y, "Fan page — not affiliated with Rockstar Games", f3, (190, 180, 220))
    im.convert("RGB").save(path, quality=95)


if __name__ == "__main__":
    avatar("leonida_intel_avatar.jpg")
    banner("leonida_intel_banner_x.jpg", 1500, 500)
    banner("leonida_intel_banner_youtube.jpg", 2560, 1440, 1546, 423)
