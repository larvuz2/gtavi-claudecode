"""AI narration for a clip: speak each line with Gemini TTS (through treg), lay the lines on the clip's
timeline and write the voice track plus caption lines for cut.py.

usage: python narrate.py spec.json --out jobs/<id>/narration
spec.json:
{
  "voice": "Fenrir",
  "style": "excited Latin American Spanish gaming streamer reacting live, fast, amazed",
  "gap": 0.15,
  "tempo": 1.25,                                                             # optional speed-up, pitch kept
  "speakers": {"A": {"voice": "Fenrir", "style": "...", "color": "FFFFFF"}},  # optional; a line picks one with "who"
  "lines": [
    {"text": "Espera... ¿ese capibara dispara confeti con una trompeta?",   # spoken (no ALL CAPS: TTS spells them)
     "caption": "Espera… ¿ese capibara dispara CONFETI con una trompeta?",   # shown (optional, defaults to text)
     "at": 0.2}                                                              # output second (optional: right after the last line)
  ]
}
Writes <out>/voice.wav (the whole voice track, 48 kHz) and <out>/lines.json ([[start, end, caption]] in output
seconds, for cut.py --lines ... --lines-time output). Each spoken line is cached by its text, voice and style.
"""
import argparse, base64, hashlib, json, subprocess, sys
from pathlib import Path

TOOL = "google-ai.voice-gen.gemini-3-8-flash-tts"


def speak(text, voice, style, cache):
    key = hashlib.sha1(f"{voice}|{style}|{text}".encode()).hexdigest()[:16]
    wav = cache / f"{key}.wav"
    if wav.exists():
        return wav
    body = {"contents": [{"parts": [{"text": text, "speechMetadata": {"style": style}}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    req = cache / f"{key}.req.json"
    req.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["treg", "--json", "call", TOOL, "--method", "POST", "--query", "model=gemini-3.8-flash-tts",
                        "--data", f"@{req}"], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        part = d["result"]["candidates"][0]["content"]["parts"][0]["inlineData"]
    except Exception:
        sys.exit(f"TTS failed for {text!r}: {r.stdout[:300]} {r.stderr[:300]}")
    raw = cache / f"{key}.raw.wav"
    raw.write_bytes(base64.b64decode(part["data"]))
    # trim leading and trailing silence, resample to 48 kHz mono
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse", "-ar", "48000", "-ac", "1", str(wav)],
                   check=True)
    print(f"tts: {text[:50]!r} -> {wav.name} (charged {d.get('_treg', {}).get('charged_micro')} micro-USD)")
    return wav


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"; cache.mkdir(exist_ok=True)
    voice, style, gap = spec.get("voice", "Fenrir"), spec.get("style", ""), float(spec.get("gap", 0.15))
    speakers = spec.get("speakers", {})  # "A": {"voice": "Fenrir", "style": "...", "color": "FFFFFF"}
    t, placed = 0.0, []
    for ln in spec["lines"]:
        who = speakers.get(ln.get("who", ""), {})
        v = ln.get("voice", who.get("voice", voice))
        st = ", ".join(x for x in (who.get("style", style), ln.get("mood", "")) if x)
        wav = speak(ln["text"], v, st, cache)
        tempo = float(ln.get("tempo", spec.get("tempo", 1.0)))
        if tempo != 1.0:  # faster delivery, same pitch (real streamers talk fast)
            fast = wav.with_name(f"{wav.stem}.x{tempo:g}.wav")
            if not fast.exists():
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-af", f"atempo={tempo}", str(fast)], check=True)
            wav = fast
        d = duration(wav)
        cap = ln.get("caption", ln["text"])
        start = float(ln["at"]) if "at" in ln else t
        if cap:  # captioned lines never overlap each other; uncaptioned shouts may overlap anything
            start = max(start, t)
        placed.append((start, start + d, cap, wav, who.get("color", "")))
        if cap:
            t = start + d + gap
    # one voice track: each line delayed to its start, mixed
    ins, chains = [], []
    for i, (s, e, _, wav, _c) in enumerate(placed):
        ins += ["-i", str(wav)]
        chains.append(f"[{i}:a]adelay={int(s * 1000)}:all=1[d{i}]")
    graph = ";".join(chains) + ";" + "".join(f"[d{i}]" for i in range(len(placed))) + \
        f"amix=inputs={len(placed)}:normalize=0:duration=longest[v]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[v]", "-ar", "48000", "-ac", "1",
                    str(out / "voice.wav")], check=True)
    lines = [[round(s, 2), round(e, 2), cap] + ([col] if col else []) for s, e, cap, _, col in placed if cap]
    (out / "lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    for s, e, cap, _w, _c in placed:
        print(f"{s:6.2f}-{e:6.2f}  {cap or '(shout, no caption)'}")
    print(f"voice: {out / 'voice.wav'} ({duration(out / 'voice.wav'):.1f}s)")


if __name__ == "__main__":
    main()
