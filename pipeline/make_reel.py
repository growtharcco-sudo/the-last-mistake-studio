"""spec.json -> voice -> video -> cover -> queue/<id>/

Usage:
  python pipeline/make_reel.py specs/<id>.json --check    # channel rules only (captions, sources, math)
  python pipeline/make_reel.py specs/<id>.json --sheet    # ONE check image: frame 0 + end of every scene + cover
  python pipeline/make_reel.py specs/<id>.json            # full render into queue/<id>/
"""
import datetime as dt, json, math, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice, engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EM_DASH, EN_DASH = "—", "–"


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
BRAND_TAG = "#thelastmistake"
SLOTS = {"evening": "today 23:30 IST", "morning": "tomorrow 07:30 IST", "test": "end-to-end test only"}


def check_spec(spec, allow_old_sources=False):
    """Channel hard rules. Fails loudly instead of posting something wrong."""
    errs = []
    every = json.dumps(spec, ensure_ascii=False)
    if EM_DASH in every: errs.append("em dash found (channel rule: no em dashes)")
    if EN_DASH in every: errs.append("en dash found (use a comma, colon, 'to' or a hyphen)")
    if spec.get("voice") != "am_michael": errs.append("voice must be am_michael (the channel narrator)")
    post = spec.get("post", {})
    for k in ("post_at", "slot", "instagram_caption", "youtube_title", "youtube_description"):
        if not post.get(k): errs.append(f"post.{k} is missing")
    if post.get("slot") and post["slot"] not in SLOTS: errs.append(f"post.slot must be one of {list(SLOTS)}")
    try:
        if dt.datetime.fromisoformat(post.get("post_at", "")).tzinfo is None: errs.append("post.post_at needs a timezone, like 2026-11-14T23:30:00+05:30")
    except ValueError: errs.append("post.post_at is not an ISO time, like 2026-11-14T23:30:00+05:30")
    # Instagram caption: ends with a real question, then exactly 5 hashtags including the brand tag
    ig = post.get("instagram_caption", "")
    paras = [p.strip() for p in ig.strip().split("\n\n") if p.strip()]
    tags = re.findall(r"#\w+", ig)
    if len(tags) != 5: errs.append(f"Instagram caption needs exactly 5 hashtags, has {len(tags)}")
    if BRAND_TAG not in [t.lower() for t in tags]: errs.append(f"Instagram caption must include {BRAND_TAG}")
    if paras and not all(w.startswith("#") for w in paras[-1].split()): errs.append("Instagram caption must end with the hashtag line")
    if len(paras) < 2 or not paras[-2].rstrip().endswith("?"): errs.append("Instagram caption: the line just before the hashtags must be a real question")
    if len(ig) > 2200: errs.append("Instagram caption over 2,200 characters")
    yt = post.get("youtube_description", "")
    if len(post.get("youtube_title", "")) > 70: errs.append("YouTube title over 70 characters")
    if "#shorts" in post.get("youtube_title", "").lower(): errs.append("no #Shorts in the YouTube title")
    if "Sources:" not in yt: errs.append("YouTube description needs a 'Sources:' list")
    if "#Shorts" not in yt: errs.append("YouTube description must end with 3 hashtags including #Shorts")
    if len(re.findall(r"#\w+", yt)) != 3: errs.append("YouTube description needs exactly 3 hashtags")
    # sources fetched today; every number backed by a Python-checked calculation
    src = spec.get("sources", [])
    if not src: errs.append("sources is empty: every fact needs a source")
    today = dt.datetime.now(IST).date().isoformat()
    for i, s in enumerate(src):
        if not s.get("url", "").startswith("http"): errs.append(f"sources[{i}] has no url")
        if not allow_old_sources and s.get("fetched") != today: errs.append(f"sources[{i}] must be fetched today ({today}), has {s.get('fetched')}")
    for i, m in enumerate(spec.get("math", [])):
        try:
            v = eval(m["expr"], {"__builtins__": {}}, {"round": round, "abs": abs, "min": min, "max": max, "int": int, "float": float, "sum": sum, "math": math})
            if abs(v - float(m["expect"])) > float(m.get("tol", 0.005)) * max(1, abs(float(m["expect"]))):
                errs.append(f"math[{i}] {m['expr']} = {v}, but the script says {m['expect']}")
        except Exception as e:
            errs.append(f"math[{i}] could not run: {e}")
    nums = re.findall(r"\d", " ".join(p.get("cap", p.get("say", "")) for p in spec.get("phrases", [])))
    if nums and not spec.get("math"): errs.append("the script has numbers but math is empty: put every number in math, checked in Python")
    if not any(e.get("at") == -1 for e in spec["scenes"][0]["els"]): errs.append("scene 1 needs the hook on frame 0 (build the spec with kit.py)")
    if errs: raise SystemExit("SPEC CHECK FAILED:\n- " + "\n- ".join(errs))


def main():
    path = sys.argv[1]; spec = json.load(open(path)); check_spec(spec, "--allow-old-sources" in sys.argv)
    if "--check" in sys.argv: print("spec check ok"); return
    out = os.path.join(ROOT, "queue", spec["id"]); os.makedirs(out, exist_ok=True)
    wav = os.path.join(out, "voice.wav")
    _, times, total = voice.synth(spec["phrases"], wav, spec["voice"], spec.get("speed", 0.95))
    json.dump({"phrase_times": times, "total": total}, open(os.path.join(out, "timing.json"), "w"), indent=1)
    if "--sheet" in sys.argv:
        clock = engine.Clock(spec, times, total)
        ts = [0.0] + [round(en - 0.25, 2) for _, en in clock.scene_t]
        base = os.path.join(out, "check")
        engine.render(spec, times, total, wav, base, stills=ts)
        from PIL import Image, ImageDraw
        ims = [Image.open(f"{base}.still_{t:05.1f}.png").resize((360, 640), Image.LANCZOS) for t in ts]
        cov = os.path.join(out, "cover.png"); engine.cover(spec, cov)
        ims.append(Image.open(cov).resize((360, 640), Image.LANCZOS))
        cols = min(5, len(ims)); rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (360 * cols, 640 * rows), (20, 20, 22)); d = ImageDraw.Draw(sheet)
        labels = ["frame 0"] + [f"{sc['kind']} end" for sc in spec["scenes"]] + ["cover"]
        for i, im in enumerate(ims):
            x, y = (i % cols) * 360, (i // cols) * 640; sheet.paste(im, (x, y))
            d.rectangle([x, y, x + 8 + 7 * len(labels[i]), y + 18], fill=(0, 0, 0)); d.text((x + 4, y + 3), labels[i], fill=(255, 255, 0))
        sheet.save(os.path.join(out, "sheet.png"))
        for t in ts: os.remove(f"{base}.still_{t:05.1f}.png")
        os.remove(wav)
        print("check sheet:", os.path.relpath(os.path.join(out, "sheet.png"), ROOT), f"({total:.1f}s, {len(spec['scenes'])} scenes)")
        return
    if "--stills" in sys.argv:            # debugging only; the routine uses --sheet
        ts = [0.0] + [round((s + e) / 2, 2) for s, e in times]
        engine.render(spec, times, total, wav, os.path.join(out, "check"), stills=ts); print("stills in", out); return
    mp4 = os.path.join(out, "video.mp4")
    engine.render(spec, times, total, wav, mp4)
    engine.cover(spec, os.path.join(out, "cover.png"))
    os.remove(wav)
    shutil.copy(path, os.path.join(out, "spec.json"))
    json.dump(spec["post"], open(os.path.join(out, "post.json"), "w"), indent=1, ensure_ascii=False)
    print(f"ready: {os.path.relpath(mp4, ROOT)} ({total:.1f}s)")


if __name__ == "__main__":
    main()
