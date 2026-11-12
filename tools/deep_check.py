"""End-to-end test of both upload paths. Publishes NOTHING publicly.

1. Hosting: the test video on the media branch (_test/video.mp4) is served by GitHub Pages.
2. Instagram: creates a Reel container from that URL and waits until Instagram has processed it
   (proves token, permissions, hosting and video format). It is never published and expires in 24 h.
3. YouTube: uploads the test video UNLISTED, checks it stays unlisted (= uploads are not locked to private,
   so public uploads work), sets the thumbnail, then DELETES the test video.
"""
import os, sys, time, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "poster"))
import instagram, youtube
from instagram import _env

PAGES = os.environ["PAGES_BASE"].rstrip("/"); url = f"{PAGES}/_test/video.mp4"; cover = f"{PAGES}/_test/cover.png"; ok = True
r = requests.head(url, timeout=30); print("Hosting:", "OK" if r.ok else "FAILED", r.status_code, url); ok &= r.ok

local = "/tmp/t.mp4"; open(local, "wb").write(requests.get(url, timeout=120).content)
try:
    cid, how = instagram.make_container(url, "test", None, local_path=local, share=False)
    print(f"Instagram: processed the test Reel via {how} (NOT published, container expires in 24 h)")
except Exception as e:
    print("Instagram: FAILED", e); ok = False

if os.environ.get("SKIP_YT") == "1":
    print("YouTube: skipped this run")
else:
    vid = None
    try:
        res = youtube.upload_short(local, "Pipeline test (deleted automatically)", "Automated test upload.", privacy="unlisted")
        vid = res["yt_video_id"]; print("YouTube: unlisted test upload OK, API says:", res["yt_privacy"])
        verdict = None
        for _ in range(10):          # unaudited projects get locked to private a little after upload
            time.sleep(30)
            r = requests.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"}, timeout=30)
            verdict = r.status_code
            if r.status_code in (401, 403): break
        stayed = verdict == 200
        print("YouTube visibility:", "STAYED UNLISTED -> public uploads will work" if stayed else f"LOCKED TO PRIVATE (oEmbed {verdict}) -> needs the API audit")
        ok &= stayed
        cov = "/tmp/t_cover.png"; open(cov, "wb").write(requests.get(cover, timeout=60).content)
        print("YouTube thumbnail:", youtube.set_thumbnail(vid, cov, tries=4, wait=30))
    except Exception as e:
        print("YouTube: FAILED", e); ok = False
    finally:
        if vid:
            try: youtube.delete_video(vid); print("YouTube: test video deleted")
            except Exception as e: print("YouTube: could not delete the test video, delete it in YouTube Studio:", e)
print("ALL OK" if ok else "SOMETHING FAILED"); sys.exit(0 if ok else 1)
