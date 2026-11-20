---
name: viral-clips
description: Find the moments that are already going viral and turn one into a 15 to 30 second TikTok clip with the source credited. Use when the user wants "the most viral clip", the next video for the page, a daily batch, or asks what to post now.
---

# Viral clips

Viewers on Twitch already clipped and upvoted the best moments. Start from those instead of scanning hours of stream.

## 1. Rank

`python "${CLAUDE_PLUGIN_ROOT}/scripts/clips.py" --lang en` writes `clips.md`: the top Twitch clips of the last 24 h, ranked by views per hour. Use `--game` for another game and `--period LAST_WEEK` for a wider window.

## 2. Choose

Take the top 8. Drop sexual content (strip club, nudity: TikTok removes it), story spoilers in launch week, drama about real people, and clips whose title you cannot confirm on screen. Prefer awe, surprise and laughter: an easter egg, a physics accident, a chase. Check `log.md` so no source is used twice.

## 3. Look before cutting

`python "${CLAUDE_PLUGIN_ROOT}/scripts/moments.py" <clip url>` downloads it and transcribes it. Then make a frame sheet with a timestamp every 2 seconds and read it. Decide:

- Where the subject first appears. The clip starts there.
- Which seconds are dead. They become jump cuts.
- Where the payoff peaks. The clip ends there.
- Where the action sits in the frame, left to right, over time.

Compare the transcript with the game's own subtitles on screen (crop the bottom strip of one frame per second). When the dialogue is the game's, write the lines into a json file, `[[start, end, "text"], ...]` in source seconds, and pass `--lines file.json`: the captions then match the game word for word. A wrong caption is worse than none.

Expect the top of the list to be sexual content (strip clubs, nudity). Skip it, and skip clips where the joke is an adult brand or sign.

## 4. Cut

Read `skills/hook-writer/references/hook-evidence.md` first.

Gameplay without a webcam, or action spread across the frame:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/cut.py" jobs/<id> --layout focus --name gta6_dog_jetski \
  --segments "14.6-20.3,24.2-27.4,30.6-41.9" --focus "0:0.62,8.9:0.60,12.2:0.47" \
  --hook "GTA 6 has a DOG riding a jet ski"
```

- `--segments`: the parts to keep, in source seconds. They are joined with jump cuts.
- `--focus`: where the 4:5 window looks, as `output second:centre x` (0 = left edge, 1 = right). It glides between keyframes. Two keyframes 0.01 s apart make a hard switch at a jump cut.
- The hook stays on screen for the whole clip, above the video.
- `--trim-bottom 0.15`: drops the bottom 15% of the source first, which removes the game's small subtitles and a streamer's own burned-in captions.

Streamer with a webcam and a reaction worth showing: `--layout react --cam auto --title "CaseOh FLIPPED a plane in GTA 6 and it LANDED anyway"`. `--segments` and `--lines` work here too.

Target 15 to 30 seconds. Then look at frame 1 and a frame sheet of the result. The subject of the hook must be visible in frame 1 and never cropped out.

## Clean language

**Clean language, every clip.** No swear word may be heard or read. `cut.py` mutes every swear in the audio (streamer and game characters) and leaves swears out of the captions; `check.py` re-transcribes the finished clip with two speech models and fails it if any swear is still heard or shown. Write the real game subtitle text, swears included, in `--lines` files, so their timing helps the mute. Never pass `--allow-profanity` for a page post.

## 5. Check and hand over

Run `rule-check`. Write the caption in this order:

```
Nobody told us GTA 6 had THIS 🐕        <- hook: curiosity or tension, under 8 words, does not repeat the on-video title

Would you let him drive? 👇             <- a question anyone can answer in one word: drives comments

#gta6 #gtavi #gaming #fyp + 1 topic tag

🎥 LIRIK on Twitch (twitch.tv/lirik)    <- streamer credit, always last
```

The streamer's name goes only in the credit line at the end. The hook must be true to the clip. `post.py` adds the credit line if it is missing. Log the source URL in `log.md`.

## 6. Deliver to the human

Never paste raw video URLs or bare file cards in chat. Add every finished clip to the human's **Clip Drop** artifact (one page, grouped by day, newest day first): a thumbnail, a Download button that opens the hosted MP4 (`treg host clip.mp4 --content-type video/mp4`, 7-day link), a Copy caption button, and the link's expiry date. Republish the same artifact so the link the human has keeps working, and reply with that one link.
