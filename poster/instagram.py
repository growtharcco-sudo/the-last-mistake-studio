"""Publish a Reel with the Instagram API with Instagram Login (graph.instagram.com).

Needs: IG_USER_ID, IG_TOKEN (long-lived Instagram user token with instagram_business_basic +
instagram_business_content_publish). The video must be reachable at a public URL (GitHub Pages).
"""
import os, time, requests

VER = os.environ.get("IG_API_VERSION", "v26.0")


def _env(name):
    """Secrets pasted with their label ("IG_TOKEN = ...") or stray spaces/quotes still work."""
    v = os.environ.get(name, "").strip()
    if "=" in v and v.split("=", 1)[0].strip().upper() == name: v = v.split("=", 1)[1].strip()
    return v.strip().strip('"').strip("'").strip()


def _base(token):
    """Instagram-login tokens start with IG...; Facebook/Unified-login (system user) tokens start with EAA."""
    host = "graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com"
    return f"https://{host}/{VER}"


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API error {r.status_code}: {r.text[:500]}")
    return r.json()


def _create(BASE, user_id, token, caption, cover_url, ai_label, video_url=None, resumable=False, share=True):
    data = {"media_type": "REELS", "caption": caption, "share_to_feed": "true" if share else "false", "access_token": token}
    if resumable: data["upload_type"] = "resumable"
    else: data["video_url"] = video_url
    if cover_url: data["cover_url"] = cover_url
    if ai_label: data["is_ai_generated"] = "true"
    r = requests.post(f"{BASE}/{user_id}/media", data=data, timeout=60)
    if r.status_code >= 400 and ai_label and "is_ai_generated" in r.text:   # older API versions: retry without the label
        data.pop("is_ai_generated"); r = requests.post(f"{BASE}/{user_id}/media", data=data, timeout=60)
    return _check(r)


def _upload_file(token, container, path):
    """Resumable upload: send the file itself, so Meta doesn't have to fetch a URL."""
    uri = container.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VER}/{container['id']}"
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        r = requests.post(uri, data=f, timeout=600, headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    if r.status_code >= 400: raise RuntimeError(f"Instagram direct upload error {r.status_code}: {r.text[:300]}")


def wait_ready(BASE, cid, token, tries=40, wait=15):
    """Poll until Instagram has processed the video. Returns the final status dict."""
    st = {}
    for _ in range(tries):
        st = _check(requests.get(f"{BASE}/{cid}", params={"fields": "status_code,status", "access_token": token}, timeout=30))
        if st.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"): return st
        time.sleep(wait)
    return st


def make_container(video_url, caption, cover_url=None, local_path=None, ai_label=True, share=True, token=None, user_id=None):
    """Create a processed Reel container: by link first, then by direct upload if Meta can't fetch the link
    (errors like 2207077 / 2207052 / 2207003). Returns (container_id, how)."""
    token = token or _env("IG_TOKEN"); user_id = user_id or _env("IG_USER_ID"); BASE = _base(token)
    c = _create(BASE, user_id, token, caption, cover_url, ai_label, video_url=video_url, share=share)
    st = wait_ready(BASE, c["id"], token)
    if st.get("status_code") == "FINISHED": return c["id"], "link"
    if not local_path: raise RuntimeError(f"Instagram could not process the video: {st}")
    print("  Instagram could not fetch the link (" + str(st.get("status")) + "), uploading the file directly")
    c = _create(BASE, user_id, token, caption, cover_url, ai_label, resumable=True, share=share)
    _upload_file(token, c, local_path)
    st = wait_ready(BASE, c["id"], token)
    if st.get("status_code") != "FINISHED": raise RuntimeError(f"Instagram could not process the video (direct upload): {st}")
    return c["id"], "direct upload"


def publish_reel(video_url, caption, cover_url=None, ai_label=True, token=None, user_id=None, local_path=None):
    token = token or _env("IG_TOKEN"); user_id = user_id or _env("IG_USER_ID"); BASE = _base(token)
    cid, how = make_container(video_url, caption, cover_url, local_path, ai_label, True, token, user_id)
    mid = _check(requests.post(f"{BASE}/{user_id}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=60))["id"]
    link = _check(requests.get(f"{BASE}/{mid}", params={"fields": "permalink", "access_token": token}, timeout=30)).get("permalink")
    return {"ig_media_id": mid, "ig_permalink": link, "ig_upload": how}


def refresh_token(token):
    """Instagram-login tokens last 60 days; refreshing returns a fresh 60-day token.
    Facebook/system-user tokens (EAA...) are refreshed differently or never expire, so they are returned unchanged."""
    if token.startswith("EAA"): return token
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30)
    return _check(r)["access_token"]
