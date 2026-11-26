"""Horizontal (1920x1080) dev-diary cut for Reddit and YouTube: kept parts of a gameplay video (with speed-ups),
a calm narration from narrate.py, sentence subtitles at the bottom, a "DEV DIARY" title tag at the start and a
"2x SPEED" badge whenever footage is sped up.

usage: python devdiary.py --src gameplay.mov --segments "63.5-66.5,84-92@2,..." --lines narr/lines.json \
         --voice narr/voice.wav --title "How you pick your next map" --out media/edits/dd_map_travel.mp4
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from cut import concat_segments, parse_segments, ts, esc

W, H = 1920, 1080


def chunks(text, a, b, max_chars=84):
    """Split a narration line into subtitle chunks (by sentence, then by words), timed by length."""
    parts = [p for p in re.split(r"(?<=[.?!:])\s+", text.strip()) if p]
    out = []
    for p in parts:
        while len(p) > max_chars:
            cut = p.rfind(" ", 0, max_chars)
            out.append(p[:cut]); p = p[cut + 1:]
        out.append(p)
    total = sum(len(x) for x in out) or 1
    t, res = a, []
    for x in out:
        d = (b - a) * len(x) / total
        res.append((t, t + d, x)); t += d
    return res


def wrap2(s, width=46):
    if len(s) <= width:
        return s
    mid = len(s) // 2
    left, right = s.rfind(" ", 0, mid + 6), s.find(" ", mid - 6)
    cut = left if left > 0 and (right < 0 or mid - left <= right - mid) else right
    return s[:cut] + "\\N" + s[cut + 1:] if cut > 0 else s


def big_words(spec, end, size=232, y=470, max_w=1760):
    """'THE@4.7,CLOWN@5.2,...' -> one ASS event per word, laid out centred over lines that fit max_w, each word
    slamming in (scale 160% -> 100%) on its own time and all fading out together at `end`."""
    from PIL import ImageFont
    words = [(w.strip().rsplit("@", 1)[0], float(w.rsplit("@", 1)[1])) for w in spec.split(",") if w.strip()]
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Black.otf", size)
    except OSError:
        font = ImageFont.load_default()
    k = 0.828  # libass draws Inter Black at 0.828x the PIL advance width at the same size (measured)
    space = font.getlength(" ") * k
    lines, cur, cw = [], [], 0.0
    for w, t in words:
        brk = w.startswith("|")  # "|WORD@t" starts a new line
        w = w.lstrip("|")
        wl = font.getlength(w) * k
        if cur and (brk or cw + space + wl > max_w):
            lines.append((cur, cw)); cur, cw = [], 0.0
        cw = cw + (space if cur else 0) + wl; cur.append((w, t, wl))
    if cur:
        lines.append((cur, cw))
    lh = size * 1.05
    top = y - lh * (len(lines) - 1) / 2
    ev = []
    for li, (ws, width) in enumerate(lines):
        x = W / 2 - width / 2
        for w, t, wl in ws:
            cx, cy = x + wl / 2, top + li * lh
            ev.append(f"Dialogue: 3,{ts(t)},{ts(end)},Big,,0,0,0,,{{\\an5\\pos({cx:.0f},{cy:.0f})\\fad(40,220)"
                      f"\\fscx165\\fscy165\\frz-6\\t(0,140,\\fscx96\\fscy96\\frz1)\\t(140,230,\\fscx100\\fscy100\\frz0)}}{esc(w)}")
            x += wl + space
    return ev, (min(t for _, t in words) if words else 0.0)


def build_ass(lines, title, tag, fast, total, t0=0.0, words="", words_end=0.0):
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter SemiBold,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,3,14,0,2,200,200,150,1
Style: Tag,Inter ExtraBold,30,&H00FFFFFF,&H00FFFFFF,&H007F45E8,&H007F45E8,-1,0,0,0,100,100,2,0,3,12,0,7,150,64,190,1
Style: Title,Inter Black,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,3,16,0,7,150,64,246,1
Style: Big,Inter Black,232,&H0042C5F4,&H0042C5F4,&H0014233B,&HA0000000,0,0,0,0,100,100,0,0,1,14,8,5,40,40,0,1
Style: Badge,Inter ExtraBold,30,&H00000000,&H00000000,&H0000E5FF,&H0000E5FF,-1,0,0,0,100,100,2,0,3,10,0,8,64,64,110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    wstart = None
    if words:
        bw, wstart = big_words(words, words_end)
        ev += bw
    for a, b, text, *_ in lines:
        if wstart is not None and wstart - 0.8 <= a <= words_end:
            continue  # the big title already says it
        for s, e, c in chunks(text, a, b):
            ev.append(f"Dialogue: 0,{ts(s)},{ts(e)},Sub,,0,0,0,,{{\\fad(80,80)}}{wrap2(esc(c))}")
    if tag:  # empty --tag and --title skip these
        ev.append(f"Dialogue: 1,{ts(t0)},{ts(t0 + 4.6)},Tag,,0,0,0,,{{\\fad(150,250)}}{esc(tag)}")
    if title:
        ev.append(f"Dialogue: 1,{ts(t0)},{ts(t0 + 4.6)},Title,,0,0,0,,{{\\fad(150,250)}}{esc(title)}")
    for a, b, sp in fast:
        ev.append(f"Dialogue: 1,{ts(a)},{ts(b)},Badge,,0,0,0,,{sp:g}× SPEED")
    return hdr + "\n".join(ev) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--segments", required=True)
    ap.add_argument("--lines", required=True); ap.add_argument("--voice", required=True)
    ap.add_argument("--title", default=""); ap.add_argument("--title-start", type=float, default=0.0); ap.add_argument("--tag", default="CAPYVERSE  ·  DEV DIARY")
    ap.add_argument("--bed-gain", type=float, default=0.25); ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--title-words", default="", help='big centred title thrown word by word: "THE@4.72,CLOWN@5.18,..."')
    ap.add_argument("--title-end", type=float, default=0.0)
    ap.add_argument("--music", default="", help="background music file, kept under the voice and ducked while it speaks")
    ap.add_argument("--music-gain", type=float, default=0.3)
    a = ap.parse_args()
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    segs = parse_segments(a.segments)
    joined = concat_segments(a.src, segs, out.with_suffix(".src.mp4"))
    fast, t = [], 0.0
    for x, y, sp in segs:
        d = (y - x) / sp
        if sp > 1:
            fast.append((round(t, 2), round(t + d, 2), sp))
        t += d
    total = t
    lines = json.loads(Path(a.lines).read_text(encoding="utf-8"))
    ass = out.with_suffix(".ass")
    ass.write_text(build_ass(lines, a.title, a.tag, fast, total, a.title_start, a.title_words, a.title_end), encoding="utf-8")
    sub = str(ass).replace("\\", "/").replace(":", "\\:")
    graph = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,"
             f"subtitles='{sub}'[vo];[0:a]volume={a.bed_gain}[bed];[1:a]apad[vox];")
    ins = ["-i", str(joined), "-i", a.voice]
    if a.music:  # music under everything, pushed further down whenever the voice speaks
        ins += ["-stream_loop", "-1", "-i", a.music]
        graph += (f"[vox]asplit[vox][key];[2:a]aresample=48000,volume={a.music_gain},afade=t=in:d=1.2,"
                  f"afade=t=out:st={max(0, total - 1.8):.2f}:d=1.8[mus];"
                  f"[mus][key]sidechaincompress=threshold=0.05:ratio=2.5:attack=60:release=500[md];"
                  f"[bed][vox][md]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]")
    else:
        graph += "[bed][vox]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph,
                    "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)], check=True)
    from clean import heard_bad
    left = heard_bad(out, language=a.lang) + heard_bad(out, model="small", language=a.lang)
    print(f"{out} {total:.1f}s, fast parts {fast}, swears heard: {[w for _, _, w in left] or 'none'}")
    if left:
        sys.exit(1)


if __name__ == "__main__":
    main()
