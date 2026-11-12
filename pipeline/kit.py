"""Reel kit: brief -> spec, using ready-made, tested scene blocks. Never hand-write coordinates.

Usage:  python pipeline/kit.py briefs/<id>.json      (writes specs/<id>.json, exits 1 on LAYOUT PROBLEMS)

Brief:
{
  "id": "002_slug", "case": "002", "style": "board",          # "board" (default, Evidence Board) or "dossier"
  "series": "The Last Mistake", "speed": 0.95,                  # voice is always am_michael (channel rule)
  "beats": [                                                   # one beat = one spoken phrase
    {"say": "...", "cap": "...", "pause": 0.3,                 # cap/pause optional
     "show": {"kind": "suspect", ...}},                        # optional: starts a new scene at this beat
    ...
  ],
  "cover": {...}, "sources": [...], "post": {...}               # copied as-is
}
Beat 0 must have a "show" (the hook frame); everything in it is on screen at frame 0.
"@n" below = beat n of THIS scene (0 = the beat with the show). Stamps: {"text", "sub", "color": "red"|"ink",
"at": n, "delay": seconds}.

BOARD kinds (one corkboard; items stay pinned; red string links each clue to the one before):
  suspect  hook. title (tape at top), label, illo (hooded), stamps (max 3, slots: top-right, bottom, middle)
  card     index card in the next zigzag slot. title, lines (max 5), font (hand|type), red=[i], hidden=[i]
           (black bar until "reveal": n), stamp, link (default true = string from the previous clue)
  photo    halftone polaroid in the next slot. illo (laptop|library|hooded), label, stamp, link
  note     yellow sticky (max 2 per Reel: side, then bottom). lines (max 3), link (default false)
  name     name tag lands under the suspect photo; camera returns there. text, stamp
  verdict  stamps (max 2) beside the suspect; camera pulls back to the top of the board
  finale   zoom out to the whole board, red circle round the revealed lines, then the logo at @1.
           follow ("FOLLOW FOR CASE 003"), circle (default true)

DOSSIER kinds (halftone dossier, one page per scene):
  folder   hook. subject, label (folder tab), file_label, stamps (max 3; the 3rd gets a paper veil behind it)
  subject  polaroid + typed fields (max 3; field i at "field_at"[i], default @1, @2, @2) + stamp
  log      search log. title, sub, query, rows=[{label, frac}] (max 5, last is red + circled), stamp
  post     forum post card. header, user (circled), body (max 3 lines, typed from @1), stamp
  reveal   post with a hidden line pair revealed at "reveal": n. header, user, body (max 3), hidden (2 lines),
           tags={from, to, at} (red string between two name tags), stamp
  place    location photo + date stamp, typed note at @1, exhibit photo dropped on top at @2 with stamp.
           photo={illo,label}, date={text,sub}, note, exhibit={illo,label}, stamp
  verdict  title + 2 stamps (@0, @1)
  ending   dark page: lines (max 2, typed), tagline, logo at @1. follow
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx
from fx import W, H

CAP_TOP = 1370              # nothing important may sit below this on screen (caption zone)
INK, RED = "ink", "red"


def st(s, x, y, size, rot, at, seed, color=None, delay=None):
    return {"type": "stamp", "text": s["text"], "sub": s.get("sub"), "color": s.get("color", color or RED), "size": size,
            "rot": rot, "seed": seed, "x": x, "y": y, "at": at, "delay": s.get("delay", 0.5 if delay is None else delay)}


# =========================== BOARD ===========================
BW, LX, RX, ROW0, ROWSTEP = 2700, 930, 1770, 2000, 680


def fr(x, y, z=1.0): return [round(x, 1), round(y + 0.06 * H / z, 1), z]


def side_pin(e, side):
    import engine
    im = engine.el_image(e); w, h = im.width, im.height
    return [round(e["x"] + (w / 2 - 140 if side == "L" else -w / 2 + 140 if side == "R" else 0), 1), round(e["y"] - h / 2 + 120, 1)]


class Board:
    def __init__(self, n_chain, n_notes):
        self.last_row = ROW0 + ROWSTEP * (n_chain // 2)          # chain slot i sits in row (i+1)//2
        self.bottom_note = (BW / 2 + 40, self.last_row + 630)
        self.bh = int(max(4800, self.last_row + (1600 if n_notes >= 2 else 1440)))
        self.chain = []; self.notes = 0; self.sus = None; self.sus_pin = None; self.last_hidden = None

    def slot(self, i):
        side = "R" if i % 2 == 0 else "L"
        return side, (RX if side == "R" else LX), ROW0 + ROWSTEP * ((i + 1) // 2)


def board_block(kind, s, b, nb, B):
    def at(n=0): return b + min(n, nb - 1)
    first = -1 if b == 0 else at()
    els = []; cam = None; cam_end = None; move = 0.55
    if kind == "suspect":
        els.append({"type": "tape", "text": s.get("title", "WHO IS IT?"), "x": BW / 2, "y": 300, "w": 1800, "rot": 1.5, "at": first, "pin": False})
        p = {"type": "polaroid", "illo": s.get("illo", "hooded"), "w": 660, "label": s.get("label", "SUSPECT"), "x": LX, "y": 1080, "rot": 2, "at": first}
        p["pin"] = side_pin(p, "L"); els.append(p); B.sus = p; B.sus_pin = p["pin"]
        slots = [(LX + 230, 760, 110, -7, 11, INK), (LX, 1440, 92, 6, 4, RED), (LX, 1080, 112, -9, 5, RED)]
        for i, sm in enumerate(s.get("stamps", [])[:3]):
            x, y, size, rot, seed, c = slots[i]
            els.append(st(sm, x, y, size, rot, at(sm.get("at", i)), seed, c, 0.6))
        cam, cam_end = fr(LX, 1080, 0.90), fr(LX, 1080, 1.0)
    elif kind in ("card", "photo"):
        i = len(B.chain); side, x, y = B.slot(i)
        if kind == "card":
            e = {"type": "card", "title": s["title"], "lines": s["lines"], "line_font": s.get("font", "hand"), "red": s.get("red", []),
                 "w": 760, "x": x, "y": y, "rot": 0 if s.get("hidden") else (-2 if side == "R" else 2), "at": at()}
            if s.get("hidden"):
                e["hidden"] = s["hidden"]; e["reveal_at"] = at(s.get("reveal", 1)); e["red"] = sorted(set(e["red"]) | set(s["hidden"]))
                B.last_hidden = e
        else:
            e = {"type": "polaroid", "illo": s.get("illo", "laptop"), "w": 600, "label": s.get("label", "EXHIBIT"), "x": x, "y": y,
                 "rot": -4 if side == "R" else 4, "at": at()}
        e["pin"] = side_pin(e, side); els.append(e)
        if s.get("link", True):
            prev = B.chain[-1]["pin"] if B.chain else B.sus_pin
            els.append({"type": "string", "a": prev, "b": e["pin"], "at": at(s.get("link_at", 0)), "delay": s.get("link_delay", 0.9), "dur": 0.6})
        if s.get("stamp"):
            els.append(st(s["stamp"], x + 40, y - 30, s["stamp"].get("size", 130), -9, at(s["stamp"].get("at", nb - 1)), 15, delay=1.0))
        B.chain.append(e); cam = fr(x, y)
    elif kind == "note":
        x, y, rot = ((LX - 60, ROW0 + 80, 4) if B.notes == 0 else (*B.bottom_note, -3)); B.notes += 1
        e = {"type": "sticky", "lines": s["lines"][:3], "w": 440 if B.notes == 1 else 540, "x": x, "y": y, "rot": rot, "at": at(s.get("at", 0)),
             "delay": s.get("delay", 0.2)}
        e["pin"] = side_pin(e, "C"); els.append(e)
        if s.get("link") and B.chain:
            els.append({"type": "string", "a": B.chain[-1]["pin"], "b": e["pin"], "at": at(s.get("link_at", 0)), "delay": 0.9, "dur": 0.5})
        cam = fr(x, y - 40, 0.95) if B.notes == 1 else fr(x, y - 150, 0.9)
    elif kind == "name":
        els.append({"type": "tag", "text": s["text"], "x": LX, "y": 1650, "rot": -4, "at": at(s.get("at", 0)), "delay": s.get("delay", 0.55), "pin": False})
        if s.get("stamp"): els.append(st(s["stamp"], LX + 70, 760, 120, 8, at(s["stamp"].get("at", 0)), 13, delay=1.1))
        cam = fr(LX, 1250, 0.9)
    elif kind == "verdict":
        slots = [(RX, 900, 116, -6, 16, INK), (RX + 20, 1260, 132, 8, 17, RED)]
        for i, sm in enumerate(s.get("stamps", [])[:2]):
            x, y, size, rot, seed, c = slots[i]
            els.append(st(sm, x, y, size, rot, at(sm.get("at", i)), seed, c, 0.2))
        cam, cam_end = fr(BW / 2, 1150, 0.66), fr(BW / 2, 1150, 0.70)
    elif kind == "finale":
        if s.get("circle", True) and B.last_hidden is not None:
            import engine
            e = B.last_hidden; rows = engine.card_rows(e); hid = sorted(e["hidden"])
            box = [rows[hid[0]][0] - 30, rows[hid[0]][1] - 30, rows[hid[-1]][2] + 20, rows[hid[-1]][3] + 30]
            els.append({"type": "circle", "box": box, "at": at(), "delay": 0.6, "dur": 0.7, "width": 14, "seed": 3})
        els.append({"type": "logo", "title": s.get("title", "THE LAST MISTAKE"), "follow": s.get("follow", "FOLLOW FOR THE NEXT CASE"),
                    "at": at(1), "delay": -0.25, "veil": True, "y": 820})
        cam = [BW / 2, B.bh / 2, H / B.bh]; move = 1.0
    else:
        raise ValueError("unknown board scene kind: " + kind)
    return els, cam, cam_end, move


# =========================== DOSSIER ===========================
def dossier_block(kind, s, b, nb):
    def at(n=0): return b + min(n, nb - 1)
    first = -1 if b == 0 else at()
    els = []; extra = {}
    T = lambda text, x, y, a, **k: dict(type="text", text=text, x=x, y=y, at=a, **k)
    if kind == "folder":
        els.append({"type": "folder", "subject": s["subject"], "label": s.get("label", "CASE"), "file_label": s.get("file_label", "FILE NO. 001  |  CLASSIFIED"),
                    "x": W / 2, "y": 830, "scale": 0.9, "at": first})
        slots = [(W / 2, 395, 100, -4, 11, INK), (W / 2 + 60, 1010, 84, -7, 4, RED), (W / 2, 780, 128, -9, 5, RED)]
        for i, sm in enumerate(s.get("stamps", [])[:3]):
            x, y, size, rot, seed, c = slots[i]; a = at(sm.get("at", i))
            if i == 2: els.append({"type": "veil", "color": "paper", "alpha": 170, "at": a, "delay": sm.get("delay", 0.5) - 0.2, "dur": 0.25})
            els.append(st(sm, x, y, size, rot, a, seed, c, 0.6))
    elif kind == "subject":
        im_h = int(580 * fx.ILLO_ASPECT["hooded"]) + 26 + 90 + 72
        els.append({"type": "polaroid", "illo": "hooded", "w": 580, "look": "dossier", "label": s.get("label", "SUBJECT"), "x": W / 2, "y": 300 + im_h / 2,
                    "anim": "slide", "clip": [230, -im_h / 2 + 10], "at": first})
        fa = s.get("field_at", [1, 2, 2]); last = None
        for i, fld in enumerate(s.get("fields", [])[:3]):
            a = at(fa[i] if i < len(fa) else 2); dl = 0.3 if i == 0 else (0.1 if last != a else 1.0)
            els.append(T(fld, 120, 1070 + 56 * i, a, delay=dl, font="type", size=42, mode="type", cps=30)); last = a
        if s.get("stamp"): els.append(st(s["stamp"], W / 2 + 200, 1190, 62, -4, at(s["stamp"].get("at", nb - 1)), 8, delay=2.3))
    elif kind == "log":
        rows = s["rows"][:5]
        els += [{"type": "panel", "x": 90, "y": 300, "w": 900, "h": 900, "color": [246, 241, 229], "at": first},
                T(s.get("title", "SEARCH LOG"), 140, 335, first, font="anton", size=64, mode="show"),
                T(s.get("sub", ""), 140, 420, first, font="courierb", size=28, color="grey", mode="show"),
                {"type": "searchbox", "x": 140, "y": 490, "w": 800, "text": s["query"], "at": first, "delay": 0.6, "cps": 9}]
        ra = at(1); els.append({"type": "rows", "x": 150, "y": 630, "gap": 108, "rows": rows, "at": ra, "delay": 0.3, "step": 0.45})
        ly = 630 + 108 * (len(rows) - 1); rend = 0.3 + 0.45 * len(rows)
        els.append({"type": "circle", "box": [125, ly - 25, 965, ly + 65], "at": ra, "delay": rend + 0.1, "dur": 0.6, "seed": 2})
        if s.get("stamp"): els.append(st(s["stamp"], W / 2 + 120, 1250, 70, -6, ra, 9, delay=rend + 0.7))
    elif kind in ("post", "reveal"):
        top = 300
        els += [{"type": "panel", "x": 80, "y": top, "w": 920, "h": 760, "header": s["header"], "at": first},
                T("user:", 110, top + 120, first, font="courier", size=44, color=(90, 90, 90), mode="show"),
                T(s["user"], 260, top + 116, first, font="courierb", size=56, mode="show")]
        if kind == "post":
            els.append({"type": "circle", "box": [235, top + 100, 260 + fx.font("courierb", 56).getlength(s["user"]) + 25, top + 195], "at": first, "delay": 0.6, "dur": 0.6, "seed": 1})
            for i, ln in enumerate(s["body"][:3]):
                els.append(T(ln, 110, top + 260 + 78 * i, at(1), delay=-0.6 + 0.8 * i if b + 1 < b + nb else 0.8 * i, font="type", size=52, cps=34))
            if s.get("stamp"): els.append(st(s["stamp"], 760, 930, 80, 8, at(s["stamp"].get("at", 1)), 12, delay=1.8))
        else:
            for i, ln in enumerate(s["body"][:3]):
                els.append(T(ln, 110, top + 240 + 74 * i, at(1), delay=-0.4 + 0.7 * i, font="type", size=50, cps=36))
            ey = top + 500; ha = at(1)
            for i, ln in enumerate(s["hidden"][:2]):
                els.append(T(ln, 110, ey + 72 * i, ha, delay=1.4, font="courierb", size=60, color="red", mode="show"))
            els.append({"type": "redbar", "box": [100, ey - 6, 860, ey + 150], "at": ha, "delay": 1.4, "reveal_at": at(s.get("reveal", 2)), "delay2": 0.2})
            tg = s.get("tags")
            if tg:
                ta = at(tg.get("at", 3))
                for (x, y), lab in (((160, 1240), tg["from"]), ((760, 1220), tg["to"])):
                    els.append({"type": "tagbox", "text": lab, "x": x, "y": y, "at": ta, "delay": -0.1})
                els.append({"type": "string", "a": [270, 1270], "b": [570, 1250], "at": ta, "delay": 0.05, "dur": 0.5, "width": 7, "sag": 0, "dots": True,
                            "via": [460, 1180]})
            if s.get("stamp"): els.append(st(s["stamp"], W / 2, 1040, 88, -8, at(s["stamp"].get("at", tg.get("at", 3) if tg else nb - 1)), 13, delay=0.5))
    elif kind == "place":
        ph = s.get("photo", {"illo": "library", "label": ""})
        ex = s.get("exhibit")
        lib = {"type": "polaroid", "illo": ph.get("illo", "library"), "w": 720, "look": "dossier", "label": ph.get("label"), "x": W / 2, "y": 590,
               "anim": "slide", "at": first}
        if ex: lib.update(hide_at=at(2), hide_delay=-0.2)          # the exhibit photo replaces it
        els.append(lib)
        if s.get("date"): els.append(st(s["date"], 330, 975, 66, 4, first if b == 0 else at(), 14, INK, 1.0))
        if s.get("note"): els.append(T(s["note"], 110, 1110, at(1), delay=0.4, font="type", size=40, color="red", cps=30))
        if ex:
            els.append({"type": "polaroid", "illo": ex.get("illo", "laptop"), "w": 620, "look": "dossier", "label": ex.get("label"), "x": W / 2,
                        "y": 600, "anim": "slide", "at": at(2), "delay": -0.2})
        if s.get("stamp"): els.append(st(s["stamp"], W / 2 + 170, 760, 96, -9, at(s["stamp"].get("at", 2)), 15, delay=1.3))
    elif kind == "verdict":
        els += [T(s.get("title", "VERDICT"), 120, 420, first, font="anton", size=90, mode="show"),
                {"type": "rule", "x": 120, "y": 540, "w": 840, "at": first}]
        slots = [(W / 2, 760, 120, -6, 16, INK), (W / 2 + 20, 1030, 130, 9, 17, RED)]
        for i, sm in enumerate(s.get("stamps", [])[:2]):
            x, y, size, rot, seed, c = slots[i]
            els.append(st(sm, x, y, size, rot, at(sm.get("at", i)), seed, c, 0.15 if i == 0 else 0.25))
    elif kind == "ending":
        for i, ln in enumerate(s.get("lines", [])[:2]):
            els.append(T(ln, W / 2, 620 + 84 * i, first, delay=0.3 + 0.6 * i, font="courierb", size=64, color="white", align="center", cps=26))
        if s.get("tagline"): els.append(T(s["tagline"], W / 2, 820, first, delay=1.8, font="courier", size=34, color="dim", align="center", mode="show"))
        els.append({"type": "logo", "title": s.get("title", "THE LAST MISTAKE"), "follow": s.get("follow", "FOLLOW FOR THE NEXT CASE"),
                    "at": at(1), "delay": -0.2, "veil": False, "y": 950})
        extra = {"bg": "dark", "no_caps": True}
    else:
        raise ValueError("unknown dossier scene kind: " + kind)
    return els, extra


# =========================== build ===========================
def build_spec(brief):
    beats = brief["beats"]; style = brief.get("style", "board")
    starts = [i for i, bt in enumerate(beats) if bt.get("show")]
    if not starts or starts[0] != 0: raise ValueError("beat 0 must have a 'show' (the hook frame)")
    phrases = []
    for i, bt in enumerate(beats):
        ph = {"say": bt["say"], "cap": bt.get("cap", bt["say"])}
        ph["pause"] = bt.get("pause", 0.4 if (i + 1 in starts or i == len(beats) - 1) else 0.22); phrases.append(ph)
    shows = [beats[b]["show"] for b in starts]
    B = Board(sum(1 for s in shows if s["kind"] in ("card", "photo")), sum(1 for s in shows if s["kind"] == "note")) if style == "board" else None
    scenes = []
    for k, b in enumerate(starts):
        nxt = starts[k + 1] if k + 1 < len(starts) else len(beats); sh = shows[k]
        sc = {"until": nxt if k + 1 < len(starts) else "end", "kind": sh["kind"]}
        if style == "board":
            els, cam, cam_end, move = board_block(sh["kind"], sh, b, nxt - b, B)
            sc.update(cam=cam, move=move, els=els)
            if cam_end: sc["cam_end"] = cam_end
        else:
            els, extra = dossier_block(sh["kind"], sh, b, nxt - b); sc.update(els=els, **extra)
        scenes.append(sc)
    case = brief.get("case", brief["id"].split("_")[0])
    spec = {"id": brief["id"], "style": style, "series": brief.get("series", "The Last Mistake"), "voice": "am_michael",
            "speed": brief.get("speed", 0.95), "header": {"left": f"CASE FILE {case}", "right": "THE LAST MISTAKE"},
            "phrases": phrases, "scenes": scenes}
    if style == "board": spec["world"] = [BW, B.bh]
    for k in ("cover", "sources", "post"): spec[k] = brief[k]
    return spec


# =========================== layout check ===========================
def _tw(fontname, size, text): return fx.font(fontname, size).getlength(text)


def layout_check(spec):
    """Catches the usual mistakes before any render: text wider than its card/frame, things under the captions."""
    P = []
    board = spec["style"] == "board"
    if board:
        import engine
        bw, bh = spec["world"]
    for k, sc in enumerate(spec["scenes"]):
        for e in sc["els"]:
            t = e["type"]; name = e.get("text") or e.get("title") or e.get("label") or t
            if t == "card":
                lf = ("hand", 66) if e.get("line_font", "hand") == "hand" else ("type", 56)
                if _tw("courierb", 50, e["title"]) > e.get("w", 760) - 60: P.append(f'scene {k}: card title too wide: "{e["title"]}"')
                for ln in e["lines"]:
                    if _tw(*lf, ln) > e.get("w", 760) - 60: P.append(f'scene {k}: card line too wide ({int(_tw(*lf, ln))}px > {e.get("w", 760) - 60}): "{ln}"')
                if len(e["lines"]) > 5: P.append(f"scene {k}: card has more than 5 lines")
            if t == "sticky":
                for ln in e["lines"]:
                    if _tw("marker", 76, ln) > e.get("w", 440) - 40: P.append(f'scene {k}: sticky line too wide: "{ln}" (max {e.get("w", 440) - 40}px)')
            if t == "tape" and _tw("marker", 86, e["text"]) > e.get("w", 1800) - 80: P.append(f'scene {k}: board title too wide: "{e["text"]}"')
            if t == "tag" and _tw("anton", 96, e["text"]) > 1300: P.append(f'scene {k}: name tag too wide: "{e["text"]}"')
            if t == "stamp":
                sw = fx.stamp_width(e["text"], e["size"], e.get("sub"))
                lim = 1000
                if sw > lim: P.append(f'scene {k}: stamp too wide ({sw}px > {lim}): "{e["text"]}"')
                if not board and e["y"] + 110 > CAP_TOP + 40: P.append(f'scene {k}: stamp under the captions: "{e["text"]}"')
            if t == "text" and not board:
                f = fx.font(e.get("font", "type"), e.get("size", 44)); w = f.getlength(e["text"])
                x0 = e["x"] - w / 2 if e.get("align") == "center" else e["x"]
                if x0 < 60 or x0 + w > W - 60: P.append(f'scene {k}: text off the page ({int(w)}px): "{e["text"]}"')
                if e["y"] + e.get("size", 44) > CAP_TOP and not sc.get("no_caps"): P.append(f'scene {k}: text under the captions: "{e["text"]}"')
            if t == "tagbox" and _tw("anton", 46, e["text"]) > 520: P.append(f'scene {k}: name tag too wide: "{e["text"]}"')
        if board:
            # the scene's new item must be on screen and above the captions
            cx, cy, z = sc.get("cam_end", sc["cam"]) if sc.get("kind") in ("suspect",) else sc["cam"]
            vw, vh = W / z, H / z
            x0 = max(0, min(bw - vw, cx - vw / 2)); y0 = max(0, min(bh - vh, cy - vh / 2))
            focus = [e for e in sc["els"] if e["type"] in ("polaroid", "card", "sticky", "tag")]
            if sc.get("kind") == "finale": focus = []
            for e in focus[-1:]:
                im = engine.el_image(e); ex0, ey0 = e["x"] - im.width / 2 + 40, e["y"] - im.height / 2 + 40
                ex1, ey1 = e["x"] + im.width / 2 - 50, e["y"] + im.height / 2 - 60
                sx0, sx1 = (ex0 - x0) * z, (ex1 - x0) * z; sy0, sy1 = (ey0 - y0) * z, (ey1 - y0) * z
                if sx0 < -5 or sx1 > W + 5: P.append(f"scene {k} ({sc['kind']}): item cut off at the side of the frame")
                if sy1 > CAP_TOP and sc.get("kind") != "name": P.append(f"scene {k} ({sc['kind']}): item runs under the captions (bottom at {int(sy1)}px)")
                if sy0 < 60: P.append(f"scene {k} ({sc['kind']}): item cut off at the top")
    n = len(spec["phrases"])
    for k, sc in enumerate(spec["scenes"]):
        for e in sc["els"]:
            if e.get("at", -1) >= n: P.append(f"scene {k}: element timed after the last beat")
    return P


if __name__ == "__main__":
    brief = json.load(open(sys.argv[1])); spec = build_spec(brief)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "specs", f'{spec["id"]}.json'); os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(spec, open(out, "w"), indent=1, ensure_ascii=False)
    print("wrote", os.path.relpath(out, root))
    probs = layout_check(spec)
    if probs: print("LAYOUT PROBLEMS:\n  " + "\n  ".join(probs)); sys.exit(1)
    print("layout ok")
