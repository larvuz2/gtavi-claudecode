---
name: auto-post
description: Upload or schedule finished clips to TikTok (and later Reels, Shorts, X) through the Upload-Post API. Use when the user says "post it", "schedule today's clips", or asks how to connect automatic uploads.
---

# Auto post

Service: Upload-Post, Basic plan, $24 per month ($16 per month billed yearly). Chosen 2026-11-19 because one request with a local file posts publicly to TikTok, and the same request reaches Instagram, YouTube and X. Free backup: Zernio (free for 2 accounts, 3 calls per upload). TikTok's own API is not an option: unaudited apps can only post privately.

## One-time setup (the human does this, about 15 minutes)

1. Sign up at upload-post.com and take the Basic plan.
2. Manage Users: create a profile. Its name is `UPLOAD_POST_USER`.
3. In that profile, connect TikTok.
4. API Keys: generate a key. In a Claude Code cloud session, save it through the secure credential form for `api.upload-post.com` (header `Authorization`, prefix `Apikey`); elsewhere set `UPLOAD_POST_KEY`. Never paste it in chat or commit it.
5. Set `UPLOAD_POST_USER` to the profile name. Then post one clip with the human watching.

## Post

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/post.py" <clip.mp4> --caption "text #gta6" [--at 2026-11-20T18:00:00 --tz America/Mexico_City] [--go]
```

Without `--go` it prints the caption and fields and posts nothing. It refuses to post a clip that has no source credit.

## Rules

- Only clips that passed `rule-check`, including its clean-language checks. The first post of any new format goes to the human for a "yes".
- At most 15 posts per TikTok account in 24 hours (TikTok's limit, shared by every tool). Space posts at least 2 hours apart.
- A new TikTok account: post the first few videos by hand in the app before using the API, so the account does not look automated.
- The API cannot use TikTok's trending sounds. The clip's own audio is the sound.
- If the upload answers with an error about the active-user cap, reconnect TikTok in Upload-Post and retry. Do not resend on a timeout: check the status first.
- After each post, add the row to `scoreboard.csv` and the source to `log.md`.

`post.py` follows Upload-Post's documentation and has not yet been run against a live account. Run the first real post with the human watching.
