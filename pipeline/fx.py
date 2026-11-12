"""Drawing blocks shared by both looks (Evidence Board and halftone dossier).

Everything here is ported unchanged from the Case 001 renderers, so the look stays the same.
Nothing in this file knows about time; engine.py decides when and where things appear.
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H, FPS = 1080, 1920, 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, "assets", "fonts") + "/"

PAPER = (236, 227, 207)       # dossier page
INK = (26, 23, 20)
RED = (196, 38, 30)
MANILA = (214, 182, 124)
CARD = (250, 248, 240)        # index card
POLAROID = (246, 241, 229)
HALFTONE_PAPER = (232, 226, 212)
BLUE = (22, 38, 105)          # handwriting ink
STRING = (185, 24, 22)

_FONTS = {}
FONT_FILES = {"anton": "Anton-Regular.ttf", "type": "SpecialElite-Regular.ttf", "courier": "CourierPrime-Regular.ttf",
              "courierb": "CourierPrime-Bold.ttf", "hand": "Caveat.ttf", "marker": "Marker.ttf"}


def font(name, size):
    key = (name, size)
    if key not in _FONTS:
        f = ImageFont.truetype(FD + FONT_FILES[name], size)
        if name == "hand":
            try: f.set_variation_by_name("Bold")
            except Exception: pass
        _FONTS[key] = f
    return _FONTS[key]


COLORS = {"ink": INK, "red": RED, "blue": BLUE, "paper": PAPER, "grey": (90, 80, 70), "white": (236, 227, 207),
          "dim": (160, 150, 135)}
def col(c): return COLORS.get(c, c) if isinstance(c, str) else tuple(c)


# ---------- easing ----------
def ease_out(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3
def ease_back(x):
    x = max(0.0, min(1.0, x)); c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
def smooth(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)
def prog(t, a, d): return max(0.0, min(1.0, (t - a) / d)) if d > 0 else (1.0 if t >= a else 0.0)


# ---------- backgrounds ----------
def _noise(w, h, rng, scale, blur, amp):
    n = rng.normal(0, 1, (h // scale + 1, w // scale + 1)).astype(np.float32)
    n = np.array(Image.fromarray(((n + 3) * 40).clip(0, 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
                 .filter(ImageFilter.GaussianBlur(blur)), np.float32)
    return (n - n.mean()) / (n.std() + 1e-6) * amp


def paper(color=PAPER, seed=1, w=W, h=H):
    """Dossier page: low-frequency mottling + vignette (no grain)."""
    rng = np.random.default_rng(seed)
    n = _noise(w, h, rng, 16, 30, 4.5)
    yy, xx = np.mgrid[0:h, 0:w]
    v = 1 - 0.16 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    img = (np.array(color, np.float32)[None, None, :] + n[..., None]) * v[..., None]
    return Image.fromarray(img.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


def cork(w, h, seed=3, frame=True):
    """Evidence board cork with a dark wooden edge."""
    rng = np.random.default_rng(seed)
    a = np.array((148, 102, 60), np.float32)[None, None] + (_noise(w, h, rng, 3, 1.0, 13) + _noise(w, h, rng, 12, 20, 10))[..., None]
    yy, xx = np.mgrid[0:h, 0:w]
    v = 1 - 0.30 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    img = Image.fromarray((a * v[..., None]).clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    if frame:
        d = ImageDraw.Draw(img)
        for i in range(40): d.rectangle([i, i, w - 1 - i, h - 1 - i], outline=(70 + i, 45 + i // 2, 25))
    return img


# ---------- halftone illustrations ----------
def halftone(gray, cell=11, ink=INK, paper_col=None, angle=45):
    w, h = gray.size
    big = gray.rotate(angle, expand=True, fillcolor=255)
    bw, bh = big.size
    a = np.array(big, np.float32) / 255.0
    out = Image.new("L", (bw * 2, bh * 2), 0)
    d = ImageDraw.Draw(out)
    for y in range(0, bh, cell):
        for x in range(0, bw, cell):
            dark = 1 - a[y:y + cell, x:x + cell].mean()
            if dark < 0.04: continue
            r = cell * 0.74 * math.sqrt(dark) * 2
            cx, cy = (x + cell / 2) * 2, (y + cell / 2) * 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    out = out.resize((bw, bh), Image.LANCZOS).rotate(-angle, expand=False)
    l, t = (bw - w) // 2, (bh - h) // 2
    mask = out.crop((l, t, l + w, t + h))
    layer = Image.new("RGBA", (w, h), paper_col + (255,) if paper_col else (0, 0, 0, 0))
    layer.paste(Image.new("RGBA", (w, h), ink + (255,)), (0, 0), mask)
    return layer


def illo_hooded(w, h):
    g = Image.fromarray(np.linspace(205, 150, h)[:, None].repeat(w, 1).astype(np.uint8))
    spot = Image.new("L", (w, h), 0); ImageDraw.Draw(spot).ellipse([w * .1, h * .02, w * .9, h * .7], fill=90)
    g = ImageChops.add(g, spot.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(g); cx = w / 2
    d.ellipse([cx - w * .46, h * .62, cx + w * .46, h * 1.35], fill=28)
    d.polygon([(cx - w * .25, h * .70), (cx - w * .23, h * .30), (cx, h * .14), (cx + w * .23, h * .30), (cx + w * .25, h * .70)], fill=22)
    d.ellipse([cx - w * .24, h * .14, cx + w * .24, h * .58], fill=22)
    d.ellipse([cx - w * .14, h * .27, cx + w * .14, h * .58], fill=6)
    return g.filter(ImageFilter.GaussianBlur(3))


def illo_library(w, h):
    g = Image.fromarray(np.linspace(225, 175, h)[:, None].repeat(w, 1).astype(np.uint8)); d = ImageDraw.Draw(g)
    d.rectangle([0, h * .80, w, h], fill=120)
    d.rectangle([w * .06, h * .30, w * .94, h * .82], fill=150)
    d.polygon([(w * .02, h * .32), (w * .5, h * .14), (w * .98, h * .32)], fill=80)
    d.rectangle([w * .06, h * .30, w * .94, h * .36], fill=95)
    for i in range(6):
        x = w * .12 + i * w * .13
        d.rectangle([x, h * .42, x + w * .09, h * .62], fill=55)
        d.rectangle([x + 6, h * .44, x + w * .09 - 6, h * .52], fill=185)
    d.rectangle([w * .42, h * .62, w * .58, h * .82], fill=40)
    d.rectangle([w * .44, h * .645, w * .56, h * .80], fill=200)
    d.ellipse([w * .78, h * .40, w * 1.05, h * .78], fill=70); d.rectangle([w * .9, h * .7, w * .93, h * .84], fill=50)
    return g.filter(ImageFilter.GaussianBlur(2.5))


def illo_laptop(w, h):
    g = Image.fromarray(np.linspace(215, 165, h)[:, None].repeat(w, 1).astype(np.uint8)); d = ImageDraw.Draw(g)
    d.rectangle([0, h * .70, w, h], fill=135)
    d.polygon([(w * .2, h * .12), (w * .8, h * .12), (w * .78, h * .66), (w * .22, h * .66)], fill=30)
    d.polygon([(w * .24, h * .16), (w * .76, h * .16), (w * .745, h * .62), (w * .255, h * .62)], fill=225)
    for i in range(7):
        y = h * .21 + i * h * .055; d.rectangle([w * .29, y, w * (.5 + .2 * ((i * 37) % 5) / 5), y + h * .02], fill=120)
    d.polygon([(w * .22, h * .66), (w * .78, h * .66), (w * .95, h * .82), (w * .05, h * .82)], fill=55)
    d.polygon([(w * .3, h * .70), (w * .7, h * .70), (w * .78, h * .77), (w * .22, h * .77)], fill=90)
    glow = Image.new("L", (w, h), 0); ImageDraw.Draw(glow).ellipse([w * .1, h * .05, w * .9, h * .8], fill=40)
    g = ImageChops.add(g, glow.filter(ImageFilter.GaussianBlur(50)))
    return g.filter(ImageFilter.GaussianBlur(2))


ILLOS = {"hooded": illo_hooded, "library": illo_library, "laptop": illo_laptop}
ILLO_ASPECT = {"hooded": 700 / 660, "library": 640 / 900, "laptop": 450 / 600}   # h / w


def illo(kind, w):
    h = int(w * ILLO_ASPECT[kind]); cell = 16 if w >= 640 else 14 if w >= 560 else 12 if w >= 400 else 10
    return halftone(ILLOS[kind](w, h), cell=cell, paper_col=HALFTONE_PAPER)


# ---------- stamps ----------
def _ink_wear(mask, seed=0, amount=0.35):
    rng = np.random.default_rng(seed)
    n = rng.random((mask.size[1] // 3 + 1, mask.size[0] // 3 + 1))
    n = Image.fromarray((n * 255).astype(np.uint8)).resize(mask.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.2))
    keep = np.array(n) > amount * 255 * 0.55
    return Image.fromarray((np.array(mask) * keep).astype(np.uint8))


_STAMPS = {}
def stamp(text, color=RED, size=110, angle=-8, sub=None, seed=3):
    key = (text, tuple(color), size, angle, sub, seed)
    if key in _STAMPS: return _STAMPS[key]
    f = font("anton", size); bb = f.getbbox(text)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = int(size * 0.32)
    sh = th + pad * 2 + (int(size * 0.42) if sub else 0)
    subw = font("courierb", int(size * 0.34)).getlength(sub) if sub else 0
    sw = int(max(tw, subw)) + pad * 2
    m = Image.new("L", (sw + 20, sh + 20), 0); d = ImageDraw.Draw(m)
    d.rounded_rectangle([10, 10, sw + 10, sh + 10], radius=size // 6, outline=255, width=max(6, size // 14))
    d.text((10 + (sw - tw) / 2 - bb[0], 10 + pad - bb[1]), text, font=f, fill=255)
    if sub:
        fs = font("courierb", int(size * 0.34)); sb = fs.getbbox(sub)
        d.text((10 + (sw - (sb[2] - sb[0])) / 2, 10 + pad + th + size * 0.12), sub, font=fs, fill=255)
    m = _ink_wear(m, seed)
    img = Image.new("RGBA", m.size, tuple(color) + (0,)); img.putalpha(m.point(lambda v: int(v * 0.92)))
    img = img.rotate(angle, expand=True, resample=Image.BICUBIC)
    _STAMPS[key] = img
    return img


def stamp_width(text, size, sub=None):
    f = font("anton", size); bb = f.getbbox(text); pad = int(size * 0.32)
    subw = font("courierb", int(size * 0.34)).getlength(sub) if sub else 0
    return int(max(bb[2] - bb[0], subw)) + pad * 2 + 20


# ---------- paper items ----------
def with_shadow(im, blur=16, off=(10, 16), op=130):
    pad = blur * 3
    out = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    sm = Image.new("L", out.size, 0); sm.paste(im.getchannel("A").point(lambda v: int(v * op / 255)), (pad + off[0], pad + off[1]))
    out.paste((0, 0, 0, 255), (0, 0), sm.filter(ImageFilter.GaussianBlur(blur)))
    out.alpha_composite(im, (pad, pad))
    return out


def card_size(lines, h=None, lh=74, top=92):
    return h or top + lh * len(lines) + 40


def index_card(title, lines, w=760, h=None, line_font="hand", red=(), lh=74, top=92):
    """Ruled index card. Returns (image, list of (y0, y1) per line in card coords)."""
    h = card_size(lines, h, lh, top)
    im = Image.new("RGBA", (w, h), CARD + (255,)); d = ImageDraw.Draw(im)
    d.line([(0, top - 8), (w, top - 8)], fill=(205, 85, 85), width=3)
    for i in range(1, (h - top) // lh + 1): d.line([(0, top - 8 + i * lh), (w, top - 8 + i * lh)], fill=(172, 192, 222), width=2)
    d.text((30, 18), title, font=font("courierb", 50), fill=INK)
    lf = font("hand", 66) if line_font == "hand" else font("type", 56)
    rows = []
    for i, ln in enumerate(lines):
        y = top - 8 + i * lh + 4
        d.text((32, y), ln, font=lf, fill=RED if i in red else BLUE if line_font == "hand" else INK)
        rows.append((y - 2, y + lh - 2))
    return im, rows


def sticky(lines, w=440, h=420, color=(247, 222, 84)):
    im = Image.new("RGBA", (w, h), color + (255,)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 40], fill=tuple(int(c * .93) for c in color) + (255,))
    for i, ln in enumerate(lines): d.text((34, 70 + i * 100), ln, font=font("marker", 76), fill=INK)
    return im


def tape_label(text, w, fs=86):
    im = Image.new("RGBA", (w, 170), (238, 232, 216, 248)); d = ImageDraw.Draw(im)
    f = font("marker", fs); d.text(((w - f.getlength(text)) / 2, 34), text, font=f, fill=INK)
    return im


def board_polaroid(img, label):
    pad, bottom = 36, 130
    im = Image.new("RGBA", (img.width + pad * 2, img.height + pad + bottom), POLAROID + (255,))
    im.alpha_composite(img, (pad, pad))
    ImageDraw.Draw(im).text((pad, pad + img.height + 30), label, font=font("type", 58), fill=INK)
    return im


def name_tag(text):
    f = font("anton", 96); w = int(f.getlength(text)) + 80
    im = Image.new("RGBA", (w, 160), CARD + (255,)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, 159], outline=INK, width=6); d.text((40, 16), text, font=f, fill=INK)
    return im


def shadow_card(w, h, color=(246, 241, 229), shadow=18):
    """Dossier card with soft shadow; returns (image, offset to card corner)."""
    img = Image.new("RGBA", (w + shadow * 4, h + shadow * 4), (0, 0, 0, 0))
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).rectangle([shadow * 2 + 6, shadow * 2 + 10, shadow * 2 + w + 6, shadow * 2 + h + 10], fill=95)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(shadow * 0.7)))
    img.alpha_composite(Image.new("RGBA", (w, h), color + (255,)), (shadow * 2, shadow * 2))
    return img, shadow * 2


def dossier_polaroid(img, label=None, pad=26, bottom=90):
    w, h = img.size
    card, o = shadow_card(w + pad * 2, h + pad + bottom, POLAROID)
    card.alpha_composite(img, (o + pad, o + pad))
    if label: ImageDraw.Draw(card).text((o + pad, o + pad + h + 22), label, font=font("type", 40), fill=INK)
    return card


def folder(subject, label="SILK ROAD", file_label="FILE NO. 001  |  CLASSIFIED"):
    fw, fh = 860, 640
    fol = Image.new("RGBA", (fw + 80, fh + 160), (0, 0, 0, 0))
    sh = Image.new("L", fol.size, 0); ImageDraw.Draw(sh).rectangle([46, 120, fw + 50, fh + 130], fill=110)
    fol.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(16)))
    d = ImageDraw.Draw(fol)
    d.rounded_rectangle([40, 40, 380, 130], radius=14, fill=(196, 164, 108))
    d.rectangle([40, 100, fw + 40, fh + 100], fill=MANILA)
    d.rectangle([40, 100, fw + 40, 112], fill=(196, 164, 108))
    d.rectangle([150, 190, fw - 70, 350], fill=(246, 241, 229)); d.rectangle([150, 190, fw - 70, 350], outline=INK, width=3)
    d.text((180, 210), "SUBJECT:", font=font("courierb", 38), fill=INK)
    d.text((180, 260), subject, font=font("type", 52), fill=INK)
    d.text((70, 55), label, font=font("anton", 48), fill=INK)
    d.text((150, 380), file_label, font=font("courierb", 34), fill=(90, 70, 40))
    return fol


def paperclip(d, x, y):
    d.rounded_rectangle([x, y, x + 46, y + 150], radius=23, outline=(110, 110, 115), width=7)
    d.rounded_rectangle([x + 11, y + 22, x + 35, y + 125], radius=12, outline=(140, 140, 145), width=6)


def pin(d, x, y, r=24):
    d.ellipse([x - r, y - r + 6, x + r, y + r + 6], fill=(0, 0, 0, 90))
    d.ellipse([x - r, y - r, x + r, y + r], fill=(150, 22, 18))
    d.ellipse([x - r * .8, y - r * .9, x + r * .6, y + r * .5], fill=RED)
    d.ellipse([x - r * .45, y - r * .6, x - r * .05, y - r * .2], fill=(255, 220, 210))


def red_circle(d, box, p, width=9, seed=0):
    if p <= 0: return
    x0, y0, x1, y1 = box; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    N = 80; pts = []
    for i in range(int(N * p) + 1):
        a = -2.4 + 2 * math.pi * 1.12 * i / N
        wob = 1 + 0.04 * math.sin(i * 0.4 + seed) + 0.06 * (i / N)
        pts.append((cx + rx * wob * math.cos(a), cy + ry * wob * math.sin(a)))
    if len(pts) > 1: d.line(pts, fill=RED + (235,), width=width, joint="curve")


def string_pts(a, b, p, sag_max=60):
    (x0, y0), (x1, y1) = a, b
    n = 30; L = math.dist(a, b); sag = min(sag_max, L * 0.05)
    return [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n + sag * math.sin(math.pi * i / n)) for i in range(int(n * p) + 1)]


def draw_string(d, a, b, p, ox=0, oy=0, width=9, sag_max=60):
    if p <= 0: return
    pts = [(x - ox, y - oy) for x, y in string_pts(a, b, p, sag_max)]
    if len(pts) > 1:
        if width >= 9: d.line([(x + 4, y + 8) for x, y in pts], fill=(0, 0, 0, 70), width=width + 1)
        d.line(pts, fill=STRING, width=width)


def paste_c(canvas, img, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0: return
    if scale != 1.0:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC)
    if alpha < 1.0:
        img = img.copy(); img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    canvas.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def wrap(text, f, maxw):
    words = text.split(); lines = []; cur = ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if f.getlength(t) > maxw and cur: lines.append(cur); cur = wd
        else: cur = t
    lines.append(cur)
    return lines
