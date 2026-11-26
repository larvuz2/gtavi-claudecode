"""Vertical (1080x1920) version of a finished horizontal dev diary: the same cut footage, the same audio track,
re-laid out for phones. A 4:5 window of the action sits in the middle over a blurred fill; sentence subtitles
under it, the word-by-word headline big in the middle, the speed badge on top. Then run dd_intro.py --vertical --chime ""
(the horizontal master already carries the chime).

usage: python devdiary_vertical.py --src out/x_base.src.mp4 --audio out/x_master.mp4 --lines narr/lines.json \
         --segments "..." --title-words "THE@5.79,..." --title-end 8.07 --out out/x_vertical_base.mp4 [--focus 0.5]
"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import devdiary as dd
from cut import parse_segments, ts, esc

W, H = 1080, 1920
WIN_Y, WIN_H = 330, 1350      # 4:5 window: y 330..1680


def build(lines, words, words_end, fast):
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter ExtraBold,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,0,0,0,0,100,100,0,0,3,16,0,2,70,70,150,1
Style: Big,Inter Black,150,&H0042C5F4,&H0042C5F4,&H0014233B,&HA0000000,0,0,0,0,100,100,0,0,1,12,7,5,30,30,0,1
Style: Badge,Inter ExtraBold,40,&H00000000,&H00000000,&H0000E5FF,&H0000E5FF,-1,0,0,0,100,100,2,0,3,12,0,8,64,64,230,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev, wstart = [], None
    if words:
        dd.W, dd.H = W, H                    # lay the headline out for the vertical frame
        bw, wstart = dd.big_words(words, words_end, size=150, y=960, max_w=980)
        ev += bw
    for a, b, text, *_ in lines:
        if wstart is not None and wstart - 0.8 <= a <= words_end:
            continue
        for s, e, c in dd.chunks(text, a, b, max_chars=58):
            ev.append(f"Dialogue: 0,{ts(s)},{ts(e)},Sub,,0,0,0,,{{\\fad(80,80)}}{dd.wrap2(esc(c), 28)}")
    for a, b, sp in fast:
        ev.append(f"Dialogue: 1,{ts(a)},{ts(b)},Badge,,0,0,0,,{sp:g}× SPEED")
    return hdr + "\n".join(ev) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--audio", required=True)
    ap.add_argument("--lines", required=True); ap.add_argument("--segments", required=True)
    ap.add_argument("--title-words", default=""); ap.add_argument("--title-end", type=float, default=0.0)
    ap.add_argument("--focus", type=float, default=0.5, help="centre of the 4:5 window, 0..1 of the width")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fast, t = [], 0.0
    for x, y, sp in parse_segments(a.segments):
        d = (y - x) / sp
        if sp > 1:
            fast.append((round(t, 2), round(t + d, 2), sp))
        t += d
    out = Path(a.out)
    ass = out.with_suffix(".ass")
    ass.write_text(build(json.loads(Path(a.lines).read_text(encoding="utf-8")), a.title_words, a.title_end, fast), encoding="utf-8")
    sub = str(ass).replace("\\", "/").replace(":", "\\:")
    cw = "floor(ih*0.8/2)*2"
    graph = (f"[0:v]crop=iw:floor(ih*0.955/2)*2:0:0,split[a][b];[a]scale=-2:{H},crop={W}:{H},boxblur=28:3,eq=brightness=-0.3:saturation=0.8[bg];"
             f"[b]crop={cw}:ih:(iw-{cw})*{a.focus}:0,scale={W}:{WIN_H},setsar=1[fg];"
             f"[bg][fg]overlay=0:{WIN_Y},fps=30,subtitles='{sub}'[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.src, "-i", a.audio, "-filter_complex", graph, "-map", "[v]",
                    "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(out)


if __name__ == "__main__":
    main()
