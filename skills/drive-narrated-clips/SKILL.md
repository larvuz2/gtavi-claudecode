---
name: drive-narrated-clips
description: Turn a gameplay or trailer video from a Google Drive link into 15 to 30 second vertical clips with an AI streamer-style narrator, captions and a hook. Use when the user shares a Drive video of their own game (Capyverse) and wants viral clips.
---

# Drive videos to narrated clips

Source: a Google Drive link the human sends. Footage is the human's own game, so no streamer credit is needed.

## 1. Get the video

The Drive connector cannot download files over 10 MB. Download with
`curl -sSL -o jobs/_capy/<name>.mp4 "https://drive.usercontent.google.com/download?id=<FILE_ID>&export=download&confirm=t"`
(works when the file is shared by link). Read its title and size with the connector's `get_file_metadata` first.

## 2. Map the footage

- One frame per second sheet with timestamps, then 2 fps sheets of the promising stretches.
- `ffmpeg ... -vf "select='gt(scene,0.3)',showinfo"` lists the scene cuts: cut only on those, never mid-shot.
- Check for speech (Whisper). Trailers are usually music only, so the narration carries the story.
- Note title cards (text that a vertical crop will cut) and black fades (skip them).

## 3. Pick the moments (why, in order)

1. **Frame 1 must stop the scroll**: the most absurd or striking image in the video (confetti blast, a giant clown), not the logo or the intro.
2. **One idea per clip**: weapons, a boss, co-op. Two clips from one video = two different promises.
3. **Escalation**: each shot bigger than the last; end on the best visual or loop back to the opening image.
4. **High arousal**: surprise, absurdity, danger (Berger & Milkman). Calm shots only as a breath before a reveal.
5. **Every key word lands on its shot**: when the voice says "Groove Gun", the Groove Gun is on screen.

## 4. Write and voice the reactions (not a narration)

Three friends playing live and reacting to exactly what is on screen: shouts, laughs, "¡wey, wey, wey!", "¡no manches!". Never an ad voice. Spec per clip in `jobs/_capy/spec/*.json`, then
`python scripts/narrate.py spec.json --out jobs/_capy/narr2_<clip>`.

- Speakers (Gemini 3.8 Flash TTS via treg, about $0.001 a line): A `Fenrir` (male, intense, white captions), B `Puck` (male, goofy, light blue), C `Kore` (female, screams and laughs, pink). Each line has `who`, `text`, `mood` (shocked, laughing, panicking...) and `at`.
- `"tempo": 1.25` (1.3 for montages): real streamers talk fast.
- Lines of 1 to 6 words, one reaction per shot. A key word lands on its shot ("¡chuza!" as the pins fall).
- `"caption": ""` makes a shout or laugh that can overlap others without a caption.
- Spoken text has no ALL CAPS (the TTS spells them); put the emphasis in `caption`.
- Never claim features the footage does not show.

## 5. Cut

```
python scripts/cut.py jobs/<job> --layout focus --name <clip> --segments "..." --focus "..." \
  --lines jobs/_capy/narr_<clip>/lines.json --lines-time output --voice jobs/_capy/narr_<clip>/voice.wav \
  --bed-gain 0.3 --lang es --hook "Este capibara pelea con una TROMPETA" [--cap-y 1180]
```

- The game's own audio stays underneath at 30 %.
- `--lang es`: the swear check listens in Spanish (forced English heard "no manches" as "damn").
- When the game shows big text low on screen, move captions below it with `--cap-y 1540` or above it with `--cap-y 1180`.
- On title cards, keep the object centred and raise captions with `--cap-y 1180` so they sit above the card's text.
- Check frame 1 and a 2 fps sheet; fix cropped text or subjects and re-cut.
- Run `rule-check`. Deliver on the Clip Drop page (viral-clips step 6).

## Two kinds of video

**Social clips** (TikTok, Reels, Shorts): the vertical process above. Hooks, chaos, three streamer voices.

**Dev diaries** (Reddit, then vertical once approved): developer to developer, what we built and why.

1. Horizontal first. The human approves the horizontal cut on the Clip Drop page; only then make the vertical version. Both must end up on the page.
2. English for Reddit (r/IndieDev, r/indiegames, r/gamedev). One idea per video, matched to the director's idea list.
3. Narration: one calm voice (`Charon`, style "calm, friendly indie game developer talking to fellow developers in a devlog video, relaxed, conversational, unhurried, warm", tempo 1.05). Say only what the footage shows; design reasoning is fine, invented tech details are not. End with one tip and one question for the comments.
4. Speed: walking, menus and software footage at 2x or 3x (`a-b@2`), the feature itself at 1x, small UI text at 0.5x so it can be read. A "2× SPEED" badge appears automatically.
5. Render: `python scripts/devdiary.py --src <video> --segments "..." --lines narr/lines.json --voice narr/voice.wav --title "How you pick your next map" --out jobs/<x>/out/<name>.mp4`
   (1920x1080, sentence subtitles above the HUD, "CAPYVERSE · DEV DIARY" tag for the first 4.6 s, swear check).
6. For the Clip Drop page, two-pass encode under 20 MB (about 18 MB) and keep the `_master.mp4` for direct uploads. The page copy is a Reddit TITLE and BODY, not a TikTok caption.

## Dev diary voice: Bob (approved)

Bob's cloned voice (Fish Audio private voice `fadb671a817e4d6e820b63903b83c636`, via treg) mastered with `scripts/vo_master.py --preset studio_warm`. Spec: `"engine": "fish"`, `"reference_id"`, `"master": false`, then master the voice.wav with Studio Warm before `devdiary.py`. Example: `example_dev_diary_spec.json`. Spell "Capy-verse" in spoken text so it is not read as "Capybars".

Footage from the developer comes as short pieces: editing in the engine (Blueprints, particle editor, curves) then testing that change in game. Cut each pair as editor at 3x, then the test at 1x, with the narration line that names the change landing on the test.
