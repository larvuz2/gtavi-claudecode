"""Clean language: find swear words in what is said and in the captions, so the clip has none.

Rule for every clip (on by default in cut.py, checked by check.py):
- Audio: every swear word heard (streamer or game character) is muted to silence.
- Captions: swear words are left out, not starred.
Slurs are treated the same way. cut.py --allow-profanity turns this off.
"""
import re, subprocess, sys
import numpy as np

SWEAR = re.compile(
    r"^(fuck\w*|f[u*]+ck\w*|motherfuck\w*|shit\w*|bullshit\w*|bitch\w*|cunt\w*|dick\w*|cock\w*|pussy\w*|ass|asses|asshole\w*|"
    r"bastard\w*|whore\w*|slut\w*|damn\w*|goddamn\w*|hell|crap\w*|piss\w*|wtf|stfu|"
    r"nigg\w*|n[i1]gg?a\w*|f[a@]gg?\w*|retard\w*|tranny\w*|chink\w*|spic\w*|kike\w*)$", re.I)

_MODEL = {}


def core(word):
    return re.sub(r"[^\w*']", "", word).strip("'").lower()


def is_bad(word):
    w = core(word)
    return bool(w) and ("*" in w or bool(SWEAR.match(w)))


def drop_bad(words):
    """Caption words with swears left out. 'What the fuck?' -> 'What the…?'"""
    out = []
    for w in words:
        if not is_bad(w["w"]):
            out.append(dict(w)); continue
        tail = re.sub(r"^.*?([.?!,…]*)$", r"\1", w["w"])
        if out and w["s"] - out[-1]["e"] < 0.8:
            prev = out[-1]["w"].rstrip(".,!?…")
            out[-1] = dict(out[-1], w=prev + "…" + tail.replace(".", "").replace("…", ""), e=w["e"])
    return out


def _model(name):
    if name not in _MODEL:
        from faster_whisper import WhisperModel
        _MODEL[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODEL[name]


def _pcm(media, start=0.0, end=None):
    """16 kHz mono, with quiet speech lifted (game dialogue under a loud streamer)."""
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}"] + (["-to", f"{end:.3f}"] if end else []) + \
          ["-i", str(media), "-vn", "-af", "highpass=f=100,lowpass=f=7000,dynaudnorm=f=150:g=7", "-ac", "1", "-ar", "16000",
           "-f", "s16le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.int16).astype(np.float32) / 32768


def heard_bad(media, start=0.0, end=None, model="medium", chunk=5.0, hop=2.5, offset=0.0):
    """Swears spoken in media[start:end]: [(s, e, word)] relative to start.
    Transcribes overlapping short chunks: on a whole clip Whisper skips quiet or overlapping lines and its word
    times drift; on 5 s pieces it hears more and times words closely. A hit in any chunk counts."""
    pcm = _pcm(media, start, end)
    sr, hits = 16000, []
    n = len(pcm) / sr
    t = -offset if offset else 0.0  # offset shifts the chunk edges, so a word cut at one edge is whole in another pass
    while t < n:
        seg = pcm[int(max(0.0, t) * sr):int(min(n, t + chunk) * sr)]
        if len(seg) > sr * 0.5:
            segs, _ = _model(model).transcribe(seg, word_timestamps=True, vad_filter=False, beam_size=5, language="en",
                                               condition_on_previous_text=False)
            hits += [(round(max(0.0, t) + x.start, 2), round(max(0.0, t) + x.end, 2), x.word.strip()) for s in segs for x in (s.words or [])
                     if is_bad(x.word)]
        if t + chunk >= n:
            break
        t += hop
    out = []  # the same word found by two overlapping chunks -> one hit
    for h in sorted(hits):
        if out and h[0] < out[-1][1] + 0.3 and core(h[2])[:4] == core(out[-1][2])[:4]:
            out[-1] = (min(out[-1][0], h[0]), max(out[-1][1], h[1]), out[-1][2])
        else:
            out.append(h)
    return out


def merge(windows, pad=0.12):
    out = []
    for a, b in sorted((max(0, a - pad), b + pad) for a, b in windows):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(round(a, 2), round(b, 2)) for a, b in out]


def mute_filter(windows):
    """ffmpeg audio filter that silences the windows (output seconds), or '' when there are none."""
    if not windows:
        return ""
    return "volume=0:enable='" + "+".join(f"between(t,{a},{b})" for a, b in windows) + "'"


if __name__ == "__main__":
    for h in heard_bad(sys.argv[1]):
        print(h)
