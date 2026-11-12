"""Spec -> video. Renders both looks of The Last Mistake from a spec built by kit.py.

  style "board"   : one big corkboard (spec.world = [w, h]); everything stays pinned once it appears and a
                    camera moves between scenes (scene.cam = [x, y, zoom], zoom 1 = 1080 px of board).
  style "dossier" : one paper page per scene (1080x1920); slow push-in; header bar on top.

Element timing: "at" = beat index (-1 = visible at frame 0), "delay" = seconds after that beat starts.
Nobody should hand-write elements: kit.py makes them from tested layouts.
"""
import json, math, os, random, subprocess
import numpy as np
from PIL import Image, ImageDraw
import fx
from fx import W, H, FPS

DROP, STAMP, FADE, MOVE = 0.35, 0.22, 0.35, 0.55
CAP_Y = {"board": 1480, "dossier": 1460}
DROP_KINDS = ("polaroid", "card", "sticky", "tag", "tape")


# ---------------- timing ----------------
class Clock:
    def __init__(self, spec, times, total):
        self.times, self.total = times, total
        self.scene_t = []
        for k, sc in enumerate(spec["scenes"]):
            st = 0.0 if k == 0 else times[spec["scenes"][k - 1]["until"]][0]
            en = total if sc["until"] == "end" else times[sc["until"]][0]
            self.scene_t.append((st, en))

    def beat(self, b): return 0.0 if b is None or b < 0 else self.times[min(b, len(self.times) - 1)][0]
    def start(self, e): return self.beat(e.get("at", -1)) + (e.get("delay", 0) if e.get("at", -1) >= 0 else 0)
    def scene_at(self, t):
        for k, (a, b) in enumerate(self.scene_t):
            if a <= t < b: return k
        return len(self.scene_t) - 1


def anim_len(e):
    k = e["type"]
    if k in DROP_KINDS: return DROP if e.get("anim", "drop") != "slide" else 0.5
    if k == "folder": return 0.55
    if k == "stamp": return STAMP
    if k in ("string", "circle"): return e.get("dur", 0.6)
    if k == "text":
        if e.get("mode", "type") == "type": return len(e["text"]) / e.get("cps", 28)
        return FADE if e.get("mode") == "fade" else 0
    if k == "rows": return e.get("step", 0.45) * len(e["rows"]) + 0.25
    if k == "searchbox": return len(e["text"]) / e.get("cps", 9)
    if k in ("veil", "logo"): return e.get("dur", 0.4)
    return 0


# ---------------- element images (cached) ----------------
_IMG = {}
def el_image(e):
    key = json.dumps({k: v for k, v in e.items() if k not in ("at", "delay", "x", "y")}, sort_keys=True)
    if key in _IMG: return _IMG[key]
    k = e["type"]; im = None
    if k == "polaroid":
        art = fx.illo(e["illo"], e.get("w", 600))
        if e.get("look", "board") == "board": im = fx.with_shadow(fx.board_polaroid(art, e.get("label", "")))
        else: im = fx.dossier_polaroid(art, e.get("label"))
    elif k == "card":
        im, _ = fx.index_card(e["title"], e["lines"], e.get("w", 760), e.get("h"), e.get("line_font", "hand"), e.get("red", []))
        im = fx.with_shadow(im)
    elif k == "sticky": im = fx.with_shadow(fx.sticky(e["lines"], e.get("w", 440), e.get("h", 420)))
    elif k == "tag": im = fx.with_shadow(fx.name_tag(e["text"]))
    elif k == "tape": im = fx.with_shadow(fx.tape_label(e["text"], e.get("w", 1800)))
    elif k == "folder": im = fx.folder(e["subject"], e.get("label", "CASE"), e.get("file_label", "FILE NO. 001  |  CLASSIFIED"))
    elif k == "stamp":
        im = fx.stamp(e["text"], fx.col(e.get("color", "red")), e.get("size", 110), e.get("rot", -8), e.get("sub"), e.get("seed", 3))
    if im is not None and e.get("rot") and k != "stamp": im = im.rotate(e["rot"], expand=True, resample=Image.BICUBIC)
    _IMG[key] = im
    return im


def card_rows(e):
    """Line boxes of a card in its own coordinates (no rotation for cards with hidden lines)."""
    _, rows = fx.index_card(e["title"], e["lines"], e.get("w", 760), e.get("h"), e.get("line_font", "hand"), e.get("red", []))
    h = fx.card_size(e["lines"], e.get("h"))
    x0, y0 = e["x"] - e.get("w", 760) / 2, e["y"] - h / 2
    return [(x0 + 28, y0 + a, x0 + e.get("w", 760) - 50, y0 + b) for a, b in rows]


def pin_xy(e):
    if e.get("pin") is True or e.get("pin") is None:
        im = el_image(e); return (e["x"], e["y"] - im.height / 2 + 120)
    return tuple(e["pin"])


# ---------------- drawing one element ----------------
def hide_t(e, clock):
    return None if e.get("hide_at") is None else clock.beat(e["hide_at"]) + e.get("hide_delay", 0)


def draw_el(c, e, t, t0, ox=0, oy=0, settled=False, fade=1.0):
    """Draw element e onto canvas c (whose top-left is world (ox, oy)). settled=True draws the end state.
    fade < 1 = element is fading out (hide_at)."""
    k = e["type"]; d = ImageDraw.Draw(c)
    if fade < 1.0 and k in DROP_KINDS:
        fx.paste_c(c, el_image(e), e["x"] - ox, e["y"] - oy, 1.0, fade); return
    p = 1.0 if settled else fx.prog(t, t0, max(1e-6, anim_len(e)))
    x, y = e.get("x", 0) - ox, e.get("y", 0) - oy
    if k in DROP_KINDS or k == "folder":
        im = el_image(e)
        if k == "folder":
            fx.paste_c(c, im, x, y - 1000 * (1 - fx.ease_back(p)), e.get("scale", 1.0))
        elif e.get("anim") == "slide":
            a = fx.ease_out(p); fx.paste_c(c, im, x, y + 60 * (1 - a), 1.0, a)
        elif e.get("anim") == "fade":
            fx.paste_c(c, im, x, y, 1.0, fx.ease_out(p))
        else:
            a = fx.ease_out(p); fx.paste_c(c, im, x, y - 90 * (1 - a), 1.08 - 0.08 * a, min(1, a * 2))
        if k == "polaroid" and e.get("clip") and p >= 1: fx.paperclip(d, x + e["clip"][0], y + e["clip"][1])
    elif k == "stamp":
        a = fx.ease_out(p); fx.paste_c(c, el_image(e), x, y, 1 + 0.9 * (1 - a), min(1, a * 1.6))
    elif k == "text":
        f = fx.font(e.get("font", "type"), e.get("size", 44)); txt = e["text"]
        if e.get("mode", "type") == "type" and not settled: txt = txt[:int(max(0, t - t0) * e.get("cps", 28))]
        if not txt: return
        fill = fx.col(e.get("color", "ink"))
        if e.get("mode") == "fade" and not settled: fill = fill + (int(255 * fx.ease_out(p)),)
        xx = x - f.getlength(e["text"]) / 2 if e.get("align") == "center" else x
        yy = y + (e.get("rise", 0) * (1 - fx.ease_out(p)) if e.get("mode") == "fade" else 0)
        d.text((xx, yy), txt, font=f, fill=fill)
    elif k == "string" and e.get("via"):
        pts = [tuple(e["a"]), tuple(e["via"]), tuple(e["b"])]; segs = list(zip(pts[:-1], pts[1:]))
        L = [math.dist(a, b) for a, b in segs]; target = sum(L) * fx.ease_out(p)
        for (a, b), l in zip(segs, L):
            if target <= 0: break
            f = min(1, target / l)
            d.line([(a[0] - ox, a[1] - oy), (a[0] + (b[0] - a[0]) * f - ox, a[1] + (b[1] - a[1]) * f - oy)], fill=fx.RED, width=e.get("width", 7))
            target -= l
        if e.get("dots") and p >= 1:
            for px, py in (e["a"], e["b"]): d.ellipse([px - ox - 12, py - oy - 12, px - ox + 12, py - oy + 12], fill=fx.RED)
    elif k == "string":
        fx.draw_string(d, e["a"], e["b"], fx.ease_out(p), ox, oy, e.get("width", 9), e.get("sag", 60))
        if e.get("dots") and p >= 1:
            for px, py in (e["a"], e["b"]): d.ellipse([px - ox - 12, py - oy - 12, px - ox + 12, py - oy + 12], fill=fx.RED)
    elif k == "circle":
        b = e["box"]; fx.red_circle(d, (b[0] - ox, b[1] - oy, b[2] - ox, b[3] - oy), p, e.get("width", 9), e.get("seed", 0))
    elif k == "panel":
        card, o = fx.shadow_card(e["w"], e["h"], tuple(e.get("color", (250, 247, 238))))
        c.alpha_composite(card, (int(x - o), int(y - o)))
        if e.get("header"):
            d.rectangle([x, y, x + e["w"], y + 80], fill=(60, 64, 72))
            d.text((x + 30, y + 18), e["header"], font=fx.font("courierb", 38), fill=(235, 235, 235))
    elif k == "rows":
        n = len(e["rows"]); step = e.get("step", 0.45)
        for i, r in enumerate(e["rows"]):
            ta = t0 + i * step
            if not settled and t < ta: continue
            a = 1.0 if settled else fx.ease_out(fx.prog(t, ta, 0.25))
            ry = y + i * e.get("gap", 108) + 20 * (1 - a); red = r.get("red") or (i == n - 1 and e.get("last_red", True))
            colr = fx.RED if red else fx.INK
            d.text((x, ry), r["label"], font=fx.font("courierb", 38), fill=colr + (int(255 * a),))
            bc = fx.RED if red else (120, 112, 100)
            d.rectangle([x + 230, ry + 10, x + 230 + 520 * r["frac"], ry + 34], fill=bc + (int(255 * a),))
    elif k == "searchbox":
        d.rectangle([x, y, x + e["w"], y + 90], outline=fx.INK, width=4)
        f = fx.font("type", 56); n = len(e["text"]) if settled else int(max(0, t - t0) * e.get("cps", 9))
        d.text((x + 30, y + 15), e["text"][:n], font=f, fill=fx.INK)
        if not settled and t < e.get("cursor_until", 1e9) and int(t * 2) % 2 == 0:
            tx = x + 30 + f.getlength(e["text"][:n]); d.rectangle([tx + 4, y + 20, tx + 10, y + 75], fill=fx.INK)
    elif k == "tagbox":
        f = fx.font("anton", 46); bw = f.getlength(e["text"])
        d.rectangle([x - bw / 2 - 20, y - 8, x + bw / 2 + 20, y + 66], fill=fx.POLAROID, outline=fx.INK, width=3)
        d.text((x - bw / 2, y), e["text"], font=f, fill=fx.INK)
    elif k == "rule":
        d.line([(x, y), (x + e["w"], y)], fill=fx.INK, width=4)
    elif k == "redbar":
        pass  # drawn as a dynamic overlay (see dyn_overlays)
    elif k == "veil":
        a = fx.ease_out(p); c.alpha_composite(Image.new("RGBA", c.size, fx.col(e.get("color", "paper")) + (int(e.get("alpha", 170) * a),)))
    elif k == "logo":
        pass  # screen overlay


def settle_time(e, clock):
    if e.get("at", -1) < 0 and e["type"] not in ("logo",):
        return 0.0          # hook elements: fully on screen at frame 0 (thumbnail + first look), no intro animation
    t0 = clock.start(e)
    end = t0 + anim_len(e)
    if e["type"] == "card" and e.get("hidden"): end = max(end, clock.beat(e["reveal_at"]) + 0.15 + 0.6)
    if e["type"] == "redbar": end = clock.beat(e["reveal_at"]) + e.get("delay2", 0.2) + 0.6
    if e["type"] == "searchbox": end = max(end, clock.beat(e.get("cursor_beat", -1)) if e.get("cursor_beat") is not None else end)
    return end


def dyn_overlays(c, e, t, clock, ox, oy):
    """Black redaction bars that slide away at their reveal beat."""
    d = ImageDraw.Draw(c)
    if e["type"] == "card" and e.get("hidden"):
        rows = card_rows(e); hid = sorted(e["hidden"])
        bx0, by0 = rows[hid[0]][0], rows[hid[0]][1]; bx1, by1 = rows[hid[-1]][2], rows[hid[-1]][3]
        bt = clock.beat(e["reveal_at"]) + 0.15
        if t < bt + 0.6:
            f = fx.ease_out((t - bt) / 0.6) if t > bt else 0
            d.rectangle([bx0 + (bx1 - bx0) * f - ox, by0 - oy, bx1 - ox, by1 + 8 - oy], fill=(14, 13, 12))
    if e["type"] == "redbar":
        b = e["box"]; bt = clock.beat(e["reveal_at"]) + e.get("delay2", 0.2)
        if t < bt + 0.6:
            f = fx.ease_out((t - bt) / 0.6) if t > bt else 0
            d.rectangle([b[0] - ox, b[1] - oy, b[0] + (b[2] - b[0]) * (1 - f) - ox, b[3] - oy], fill=fx.INK)


# ---------------- per-frame ----------------
class Renderer:
    def __init__(self, spec, times, total):
        self.spec, self.clock = spec, Clock(spec, times, total)
        self.style = spec.get("style", "board")
        if self.style == "board":
            self.bw, self.bh = spec["world"]
            self.base = fx.cork(self.bw, self.bh)
        else:
            self.bw, self.bh = W, H
            self.paper = fx.paper(); self.dark = fx.paper((20, 18, 16), 7)
        self.caps = [(times[i][0], times[i][1] + 0.2, ph.get("cap", ph["say"])) for i, ph in enumerate(spec["phrases"])]
        self.cache = {}
        # camera keyframes (board)
        if self.style == "board":
            K = []; prev = None
            for k, sc in enumerate(spec["scenes"]):
                st, en = self.clock.scene_t[k]; cam = sc["cam"]; end = sc.get("cam_end", cam)
                if prev is None: K.append((st, *cam))
                else:
                    K.append((st, *prev)); K.append((st + sc.get("move", MOVE), *cam))
                K.append((en, *end)); prev = end
            self.K = K

    def cam(self, t):
        K = self.K
        for (t0, x0, y0, z0), (t1, x1, y1, z1) in zip(K[:-1], K[1:]):
            if t0 <= t <= t1:
                f = fx.smooth((t - t0) / max(1e-6, t1 - t0))
                return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, math.exp(math.log(z0) + (math.log(z1) - math.log(z0)) * f)
        return K[-1][1:]

    def active(self, t):
        """Elements that can be on screen at t: board = all scenes so far; dossier = current scene."""
        sc = self.spec["scenes"]
        if self.style == "board":
            k = self.clock.scene_at(t); return [e for s in sc[:k + 1] for e in s["els"]], k
        k = self.clock.scene_at(t); return sc[k]["els"], k

    def frame(self, t):
        els, k = self.active(t)
        cl = self.clock
        live = [e for e in els if (cl.start(e) <= t or e.get("at", -1) < 0) and not (hide_t(e, cl) is not None and t >= hide_t(e, cl) + 0.3)]
        settled = [e for e in live if settle_time(e, cl) <= t and e["type"] not in ("logo",) and hide_t(e, cl) is None]
        key = (k if self.style == "dossier" else 0, tuple(id(e) for e in settled))
        if self.cache.get("key") != key:
            w = self.base.copy() if self.style == "board" else Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for e in settled: draw_el(w, e, t, cl.start(e), settled=True)
            if self.style == "board":
                d = ImageDraw.Draw(w)
                for e in settled:
                    if e["type"] in ("polaroid", "card", "sticky") and e.get("pin", True) is not False: fx.pin(d, *pin_xy(e))
            self.cache = {"key": key, "w": w}
        world = self.cache["w"]
        anim = [e for e in live if e not in settled and e["type"] != "logo"]
        shake = any(e["type"] == "stamp" and 0 <= t - cl.start(e) < 0.3 for e in live)
        if self.style == "board":
            cx, cy, z = self.cam(t)
            if shake: cx += random.uniform(-12, 12) / z; cy += random.uniform(-12, 12) / z
            vw, vh = W / z, H / z
            x0 = max(0, min(self.bw - vw, cx - vw / 2)); y0 = max(0, min(self.bh - vh, cy - vh / 2))
            ix0, iy0 = int(x0), int(y0)
            crop = world.crop((ix0, iy0, ix0 + int(math.ceil(vw)) + 1, iy0 + int(math.ceil(vh)) + 1))
            for e in anim: draw_el(crop, e, t, cl.start(e), ix0, iy0)
            for e in live: dyn_overlays(crop, e, t, cl, ix0, iy0)
            d = ImageDraw.Draw(crop)
            for e in anim:
                if e["type"] in ("polaroid", "card", "sticky") and e.get("pin", True) is not False and t >= cl.start(e) + DROP * 0.9:
                    px, py = pin_xy(e); fx.pin(d, px - ix0, py - iy0)
            out = crop.resize((int(round(crop.width * z)), int(round(crop.height * z))), Image.LANCZOS if z < 0.9 else Image.BICUBIC)
            ox, oy = int((x0 - ix0) * z), int((y0 - iy0) * z)
            out = out.crop((ox, oy, ox + W, oy + H))
            dark = False
        else:
            st, en = cl.scene_t[k]
            layer = world.copy()
            for e in anim:
                h = hide_t(e, cl); fade = 1.0 if h is None or t < h else 1 - fx.ease_out((t - h) / 0.3)
                draw_el(layer, e, t, cl.start(e), fade=fade)
            for e in live: dyn_overlays(layer, e, t, cl, 0, 0)
            z = 1.0 + 0.035 * ((t - st) / max(en - st, 1))
            ox = oy = 0
            if shake: ox, oy = random.randint(-9, 9), random.randint(-9, 9)
            lw, lh = int(W * z), int(H * z)
            layer = layer.resize((lw, lh), Image.BICUBIC).crop(((lw - W) // 2 - ox, (lh - H) // 2 - oy, (lw - W) // 2 - ox + W, (lh - H) // 2 - oy + H))
            dark = self.spec["scenes"][k].get("bg") == "dark"
            out = (self.dark if dark else self.paper).copy(); out.alpha_composite(layer)
            self.header(out, dark)
        logo = [e for e in live if e["type"] == "logo"]
        if logo: self.logo(out, logo[0], t, cl.start(logo[0]))
        elif not self.spec["scenes"][k].get("no_caps"):
            cap = next((c for (a, b, c) in self.caps if a <= t < b), "")
            self.caption(out, cap)
        return out.convert("RGB")

    def header(self, c, dark):
        h = self.spec.get("header", {}); d = ImageDraw.Draw(c); colr = fx.PAPER if dark else fx.INK
        d.text((70, 150), h.get("left", "CASE FILE"), font=fx.font("anton", 44), fill=fx.RED)
        r = h.get("right", "THE LAST MISTAKE"); f = fx.font("anton", 44)
        d.text((W - 70 - f.getbbox(r)[2], 150), r, font=f, fill=colr)
        d.line([(70, 222), (W - 70, 222)], fill=colr, width=4); d.line([(70, 232), (W - 70, 232)], fill=colr, width=1)

    def caption(self, c, text):
        if not text: return
        f = fx.font("courierb", 50); d = ImageDraw.Draw(c)
        lines = fx.wrap(text, f, 880); lh = 64; y0 = CAP_Y[self.style] - lh * len(lines) / 2
        for i, ln in enumerate(lines):
            bw = f.getlength(ln); x = (W - bw) / 2; y = y0 + i * lh
            d.rectangle([x - 18, y - 6, x + bw + 18, y + lh - 4], fill=(20, 18, 16))
            d.text((x, y), ln, font=f, fill=fx.PAPER)

    def logo(self, c, e, t, t0):
        a = fx.ease_out(fx.prog(t, t0, 0.4))
        if e.get("veil", True): c.alpha_composite(Image.new("RGBA", (W, H), (12, 11, 10, int(205 * a))))
        d = ImageDraw.Draw(c)
        f2 = fx.font("anton", 150); txt = e.get("title", "THE LAST MISTAKE"); bw = f2.getlength(txt)
        if bw > 960: f2 = fx.font("anton", int(150 * 960 / bw)); bw = f2.getlength(txt)
        y = e.get("y", 820)
        d.text(((W - bw) / 2, y + 30 * (1 - a)), txt, font=f2, fill=fx.RED + (int(255 * a),))
        if t > t0 + 0.9 and e.get("follow"):
            f3 = fx.font("courierb", 42); d.text(((W - f3.getlength(e["follow"])) / 2, y + 210), e["follow"], font=f3, fill=fx.PAPER)


# ---------------- sound ----------------
def sfx(spec, clock, total, path):
    import soundfile as sf
    from scipy.signal import lfilter
    SR = 48000; N = int((total + 0.5) * SR); t = np.arange(N) / SR
    rng = np.random.default_rng(1); lp = lambda x, a: lfilter([1 - a], [1, -a], x)
    out = np.zeros(N)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t)
    drone = (np.sin(2 * np.pi * 55 * t) + 0.6 * np.sin(2 * np.pi * 82.4 * t + 1) + 0.35 * np.sin(2 * np.pi * 110.3 * t)) * (0.6 + 0.4 * lfo)
    out += (drone * 0.05 + lp(rng.normal(0, 1, N), 0.995) * 0.09) * np.minimum(1, t / 1.5) * np.minimum(1, (total + 0.5 - t) / 1.0)
    def put(at, s):
        i = int(max(0, at) * SR); e = min(N, i + len(s)); out[i:e] += s[:e - i]
    def thud(at, g=1.0):
        n = int(0.45 * SR); tt = np.arange(n) / SR
        put(at, (np.sin(2 * np.pi * (62 + 40 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9) * 0.9 + lp(rng.normal(0, 1, n), 0.6) * np.exp(-tt * 90) * 0.6) * g * 0.5)
    def tap(at):
        n = int(0.12 * SR); tt = np.arange(n) / SR
        put(at, lp(rng.normal(0, 1, n), 0.3) * np.exp(-tt * 60) * 0.35 + np.sin(2 * np.pi * 180 * tt) * np.exp(-tt * 40) * 0.3)
    def whoosh(at):
        n = int(0.5 * SR); tt = np.arange(n) / SR; nz = rng.normal(0, 1, n)
        put(at - 0.1, (lp(nz, 0.93) - lp(nz, 0.995)) * np.sin(np.pi * tt / 0.5) ** 2 * 0.28)
    for sc in spec["scenes"]:
        for e in sc["els"]:
            if e.get("at", -1) < 0: continue
            if e["type"] == "stamp": thud(clock.start(e))
            elif e["type"] in DROP_KINDS + ("folder",): tap(clock.start(e) + 0.33)
            elif e["type"] == "logo": thud(clock.start(e), 1.3)
    for st, _ in clock.scene_t[1:]: whoosh(st)
    sf.write(path, (out / max(1, np.abs(out).max() / 0.9)).astype(np.float32), SR)


# ---------------- entry points ----------------
def _encode_range(args):
    spec, times, total, a, b, path, seed = args
    random.seed(seed); r = Renderer(spec, times, total)
    tmp = path[:-4] + ".tmp.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-profile:v", "high", tmp], stdin=subprocess.PIPE)
    for fi in range(a, b): p.stdin.write(r.frame(fi / FPS).tobytes())
    p.stdin.close(); p.wait()
    if p.returncode != 0: raise SystemExit("ffmpeg failed on part " + path)
    os.replace(tmp, path)


def render(spec, times, total, wav, out, stills=None, workers=2):
    """Full render to out (mp4), or with stills=[t...] write <out>.still_<t>.png per time."""
    if stills is not None:
        r = Renderer(spec, times, total)
        for t in stills: r.frame(min(t, total - 0.05)).save(f"{out}.still_{t:05.1f}.png")
        return
    N = int(round(total * FPS)); parts = max(2, workers * 3)
    work = os.path.dirname(out); bounds = [(N * i // parts, N * (i + 1) // parts) for i in range(parts)]
    jobs = [(spec, times, total, a, b, os.path.join(work, f"part{i}.mp4"), i) for i, (a, b) in enumerate(bounds)]
    from multiprocessing import Pool
    with Pool(workers) as pool: pool.map(_encode_range, jobs)
    lst = os.path.join(work, "parts.txt")
    open(lst, "w").write("".join(f"file '{os.path.basename(j[5])}'\n" for j in jobs))
    vid = os.path.join(work, "video_only.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid], check=True)
    sfxp = os.path.join(work, "sfx.wav"); sfx(spec, Clock(spec, times, total), total, sfxp)
    mix = os.path.join(work, "mix.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-i", sfxp, "-filter_complex",
                    "[1:a]volume=0.55[s];[s][0:a]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=300[sd];"
                    "[0:a][sd]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9,aresample=48000[a]",
                    "-map", "[a]", "-t", f"{N / FPS:.3f}", mix], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", out], check=True)
    for j in jobs: os.remove(j[5])
    for f in (lst, vid, sfxp, mix): os.remove(f)


def cover(spec, path):
    """Thumbnail 1080x1920: case tape, big hook card, payoff line."""
    cv = spec["cover"]
    if spec.get("style", "board") == "board":
        c = fx.cork(W, H, seed=9)
    else:
        c = fx.paper()
    d = ImageDraw.Draw(c)
    tape = fx.with_shadow(fx.tape_label(cv.get("kicker", "CASE FILE"), 900, 64)).rotate(2, expand=True, resample=Image.BICUBIC)
    fx.paste_c(c, tape, W / 2, 330)
    lines = cv["big"] if isinstance(cv["big"], list) else [cv["big"]]
    card = Image.new("RGBA", (900, 160 + 190 * len(lines)), fx.CARD + (255,)); cd = ImageDraw.Draw(card)
    for i, ln in enumerate(lines):
        f = fx.font("anton", 170)
        while f.getlength(ln) > 820: f = fx.font("anton", f.size - 6)
        cd.text(((900 - f.getlength(ln)) / 2, 60 + 190 * i), ln, font=f, fill=fx.RED if i == len(lines) - 1 else fx.INK)
    fx.paste_c(c, fx.with_shadow(card).rotate(-3, expand=True, resample=Image.BICUBIC), W / 2, 860)
    if cv.get("sub"):
        st = fx.stamp(cv["sub"], fx.RED, 84, 6, seed=41); fx.paste_c(c, st, W / 2, 1330)
    d = ImageDraw.Draw(c); fx.pin(d, W / 2, 860 - (160 + 190 * len(lines)) / 2 + 40, 30)
    c.convert("RGB").save(path)
