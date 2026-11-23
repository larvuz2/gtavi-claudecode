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

## 4. Write and voice the narration

Spec file per clip (see `jobs/_capy/spec/*.json`), then
`python scripts/narrate.py spec.json --out jobs/_capy/narr_<clip>`.

- Voice: Gemini 3.8 Flash TTS through treg, voice `Fenrir`, style "very fast, high-energy Latin American Spanish gaming streamer reacting live on stream, amazed, laughing, punchy". About $0.001 per line.
- Streamer voice: first person, reacting ("¡No, no, no!", "Espera…"), short lines of 2 to 3 seconds, a question at the end that anyone can answer in a comment.
- Spoken text has no ALL CAPS (the TTS spells them); put the emphasis in `caption`.
- Place each line with `at` so its key word falls on the right shot. The narration sets the clip's length.
- Never claim features the footage does not show.

## 5. Cut

```
python scripts/cut.py jobs/<job> --layout focus --name <clip> --segments "..." --focus "..." \
  --lines jobs/_capy/narr_<clip>/lines.json --lines-time output --voice jobs/_capy/narr_<clip>/voice.wav \
  --bed-gain 0.3 --hook "Este capibara pelea con una TROMPETA" [--cap-y 1180]
```

- The game's own audio stays underneath at 30 %.
- On title cards, keep the object centred and raise captions with `--cap-y 1180` so they sit above the card's text.
- Check frame 1 and a 2 fps sheet; fix cropped text or subjects and re-cut.
- Run `rule-check`. Deliver on the Clip Drop page (viral-clips step 6).
