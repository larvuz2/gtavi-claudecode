"""Upload a finished clip through Upload-Post (upload-post.com), with the source credit in the caption.

Dry run by default: prints the exact caption and fields. Add --go to really post. Needs UPLOAD_POST_USER (the profile
name from Upload-Post's "Manage Users") and the API key, either as UPLOAD_POST_KEY or as a network secret for
api.upload-post.com (header Authorization, prefix "Apikey"). TikTok allows 15 posts per account per 24 h.
Fields follow docs.upload-post.com/api/upload-video; this script has not been run against a live account yet.

usage: python post.py <clip.mp4> --caption "text" [--platform tiktok ...] [--at 2026-11-20T18:00:00 --tz America/Mexico_City] [--go]
"""
import argparse, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from check import banned_in
from common import load_json

API = "https://api.upload-post.com/api/upload"


def credit_line(meta):
    """'🎥 LIRIK on Twitch (twitch.tv/lirik)' from the clip metadata written by cut.py."""
    ch, url = meta.get("source_channel"), meta.get("source_url") or ""
    if not ch:
        return ""
    if "twitch.tv" in url:
        return f"🎥 {ch} on Twitch (twitch.tv/{url.split('twitch.tv/')[1].split('/')[0]})"
    return f"🎥 {ch}" + (" on YouTube" if "youtu" in url else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("--caption", required=True)
    ap.add_argument("--platform", nargs="+", default=["tiktok"]); ap.add_argument("--at"); ap.add_argument("--tz", default="UTC")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    clip = Path(a.clip); side = clip.with_suffix(".json")
    meta = load_json(side) if side.exists() else {}
    credit = credit_line(meta)
    if not credit and "🎥" not in a.caption:
        sys.exit("no source credit: the clip has no metadata json and the caption has no 🎥 credit line. Not posting.")
    caption = a.caption if "🎥" in a.caption else a.caption.rstrip() + "\n\n" + credit
    if banned_in(caption):
        sys.exit(f"banned terms in caption: {banned_in(caption)}")
    data = [("title", caption), ("user", os.environ.get("UPLOAD_POST_USER", "")), ("privacy_level", "PUBLIC_TO_EVERYONE"),
            ("disable_inbox_fallback", "true"), ("async_upload", "true")] + [("platform[]", p) for p in a.platform]
    if a.at:
        data += [("scheduled_date", a.at), ("timezone", a.tz)]
    print(f"clip: {clip}\nsource: {meta.get('source_url', '')}\n--- caption ---\n{caption}\n--- fields ---")
    for k, v in data[1:]:
        print(f"{k} = {v}")
    if not a.go:
        print("\ndry run. Add --go to post."); return
    if not os.environ.get("UPLOAD_POST_USER"):
        sys.exit("set UPLOAD_POST_USER (the profile name in Upload-Post) first")
    # The key comes from UPLOAD_POST_KEY, or is added by the environment's network secret for api.upload-post.com,
    # which replaces this placeholder on the way out. It is never written to a file or the chat.
    key = os.environ.get("UPLOAD_POST_KEY") or "placeholder-replaced-by-network-secret"
    import requests
    with open(clip, "rb") as f:
        r = requests.post(API, headers={"Authorization": f"Apikey {key}", "Idempotency-Key": clip.stem}, data=data,
                          files={"video": (clip.name, f, "video/mp4")}, timeout=300)
    print(r.status_code, r.text[:800])
    sys.exit(0 if r.ok else 1)


if __name__ == "__main__":
    main()
