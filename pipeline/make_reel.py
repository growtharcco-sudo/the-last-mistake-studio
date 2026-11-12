"""spec.json -> voice -> video -> cover -> queue/<id>/

Usage:
  python pipeline/make_reel.py specs/<id>.json --sheet    # ONE check image: frame 0 + end of every scene + cover
  python pipeline/make_reel.py specs/<id>.json            # full render into queue/<id>/
"""
import json, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice, engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EM_DASH, EN_DASH = "—", "–"


def check_spec(spec):
    """Channel hard rules. Fails loudly instead of making something wrong."""
    errs = []
    txt = json.dumps(spec, ensure_ascii=False)
    if EM_DASH in txt or EN_DASH in txt: errs.append("em/en dash found (channel rule: no em dashes, use commas or colons)")
    if spec.get("voice") != "am_michael": errs.append("voice must be am_michael (the channel narrator)")
    if not spec.get("sources"): errs.append("sources is empty: every fact needs a source")
    post = spec.get("post", {})
    for k in ("instagram_caption", "youtube_title", "youtube_description"):
        if not post.get(k): errs.append(f"post.{k} is missing")
    ig = post.get("instagram_caption", ""); tags = [w for w in ig.split() if w.startswith("#")]
    if "#thelastmistake" not in tags: errs.append("Instagram caption must include #thelastmistake")
    if not 3 <= len(tags) <= 5: errs.append(f"Instagram caption needs 3 to 5 hashtags, has {len(tags)}")
    if len(post.get("youtube_title", "")) > 70: errs.append("YouTube title over 70 characters")
    if "AI narration" not in post.get("youtube_description", ""): errs.append("YouTube description must say 'AI narration'")
    if errs: raise SystemExit("SPEC CHECK FAILED:\n- " + "\n- ".join(errs))


def main():
    path = sys.argv[1]; spec = json.load(open(path)); check_spec(spec)
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
