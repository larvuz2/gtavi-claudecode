"""Cut one candidate into a finished vertical clip.

1080x1920, 30 fps, word-by-word burned captions (slurs and swears masked), hook box in the first seconds,
loudness normalised to -14 LUFS. Writes jobs/<id>/edits/clip_<n>.mp4 + .json (metadata for check.py).

usage: python cut.py jobs/<id> --pick 1 [--layout fill|blur|focus|facecam|react] [--hook "TEXT"]
                     [--segments "12.3-20,23.8-27.3"] (jump cuts, source seconds) [--focus "0:0.62,8:0.45"] [--hook-secs 0]
                     [--lines lines.json] (captions from the game's own subtitles) [--trim-bottom 0.1] (hide burned-in overlays)
                     [--cam auto|x:y:w:h] [--title "TEXT" --title-style box|outline --title-secs 0] [--captions word|bubble|none]
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import load_json, run, save_json, tool

W, H = 1080, 1920


def _font():
    """Arial Black where it exists (Windows, macOS), else the heaviest sans installed (Linux servers)."""
    import shutil, subprocess
    if not shutil.which("fc-list"):
        return "Arial Black"
    have = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout.lower()
    for f in ("Arial Black", "Anton", "Montserrat Black", "Inter Black", "DejaVu Sans"):
        if f.lower() in have:
            return f
    return "Arial Black"


FONT = _font()


def ts(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


import re as _re
_SLURS = _re.compile(r"\b(nigg\w*|n[i1]gg?a\w*|f[a@]gg?\w*|retard\w*|tranny\w*|chink\w*|spic\w*|kike\w*)\b", _re.I)


_SWEARS = _re.compile(r"\b(fuck\w*|motherfuck\w*|shit\w*|bitch\w*|cunt\w*|dick\w*|pussy\w*|asshole\w*|bastard\w*|whore\w*|slut\w*)\b", _re.I)


def _mask(m):
    w = m.group(0)
    return w[0] + '*' * (len(w) - 1)


def clean(s, profanity=False):
    """Slurs are always masked (n-word -> n****); hard swears too unless profanity=True."""
    s = _SLURS.sub(_mask, s)
    return s if profanity else _SWEARS.sub(_mask, s)


def esc(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def wrap(text, width):
    lines, cur = [], ''
    for wd in text.split():
        if cur and len(cur) + 1 + len(wd) > width:
            lines.append(cur); cur = wd
        else:
            cur = (cur + ' ' + wd).strip()
    return lines + ([cur] if cur else [])


def build_ass(words, s0, e0, hook, cap_y, title=None, caps='word', profanity=False, hook_secs=2.6, hook_y=170, hook_fs=68):
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial Black,92,&H00FFFFFF,&H0000E5FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: Hook,Arial Black,68,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,70,70,170,1
Style: TitleBox,Arial Black,66,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,1,0,0,5,40,40,0,1
Style: TitleOut,Arial Black,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,9,2,8,50,50,0,1
Style: Bubble,Arial,58,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,16,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    ws = [dict(w, w=clean(w["w"], True)) for w in words if s0 <= w["s"] < e0 and w["w"]]  # slurs masked always
    if not profanity:  # clean-language rule: swears are left out of the captions
        from clean import drop_bad
        ws = drop_bad(ws)
    # groups of up to 3 words, break on punctuation or pauses
    groups, cur = [], []
    for w in ws:
        if cur and (len(cur) == 3 or w["s"] - cur[-1]["e"] > 0.6 or cur[-1]["w"][-1:] in ".?!,"):
            groups.append(cur); cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    hook_end = ((e0 - s0) if hook_secs <= 0 else hook_secs) if hook else 0
    for gi, g in enumerate(groups):
        g_end = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else g[-1]["e"] + 0.4
        g_end = min(g_end, g[-1]["e"] + 0.8)
        for k, w in enumerate(g):
            a = w["s"] - s0; b = (g[k + 1]["s"] - s0) if k + 1 < len(g) else g_end - s0
            if b <= a:
                continue
            parts = []
            for j, x in enumerate(g):
                t = esc(x["w"].upper())
                parts.append("{\\c&H0000E5FF&}" + t + "{\\c&H00FFFFFF&}" if j == k else t)
            pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if k == 0 else ""
            if caps == 'bubble':
                if k == 0:
                    txt = esc(' '.join(x['w'] for x in g)).strip()
                    txt = txt[:1].upper() + txt[1:]
                    ev.append(f"Dialogue: 0,{ts(a)},{ts(g_end - s0)},Bubble,,0,0,0,,{{\\pos({W // 2},{cap_y})}}{pop}{txt}")
                continue
            ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\pos({W // 2},{cap_y})}}{pop}{' '.join(parts)}")
    if title:  # reaction title: (style, text, y, seconds)
        st, text, ty, secs = title
        end = (e0 - s0) if secs <= 0 else secs
        lines = wrap(esc(text), 26 if st == 'box' else 24)
        body = '\\N'.join(lines)
        if st == 'box':
            ev.append(f"Dialogue: 2,{ts(0)},{ts(end)},TitleBox,,0,0,0,,{{\\pos({W // 2},{ty})}}{body}")
        else:
            ev.append(f"Dialogue: 2,{ts(0)},{ts(end)},TitleOut,,0,0,0,,{{\\pos({W // 2},{ty})\\an8}}{body}")
        hook = ''
    if hook:
        body_h = "\\N".join(wrap(esc(hook), 22 if hook_fs <= 70 else 19))
        ev.append(f"Dialogue: 1,{ts(0)},{ts(hook_end)},Hook,,0,0,0,,{{\\an8\\fs{hook_fs}\\pos({W // 2},{hook_y})\\fad(0,180)\\fscx92\\fscy92\\t(0,120,\\fscx100\\fscy100)}}{body_h}")
    return hdr.replace("Arial Black", FONT) + "\n".join(ev) + "\n"


CAP_Y = {"fill": 1380, "blur": 1460, "facecam": 1120, "react": 1560, "focus": 1420}
FOCUS_Y, FOCUS_H = 320, 1350  # focus layout: a 4:5 window on the action, title above it, both inside TikTok's safe area


def focus_x(keys, cw):
    """Piecewise-linear crop x from "t:cx,t:cx" keyframes (output seconds : centre as a fraction of the width)."""
    pts = sorted((float(a), float(b)) for a, b in (k.split(":") for k in keys.split(",")))
    px = lambda c: f"(iw*{c:.4f}-{cw}/2)"
    e = px(pts[-1][1])
    for (t0, c0), (t1, c1) in reversed(list(zip(pts, pts[1:]))):
        e = f"if(lt(t,{t1}),{px(c0)}+({px(c1)}-{px(c0)})*(t-{t0})/{max(t1 - t0, 0.01)},{e})"
    e = f"if(lt(t,{pts[0][0]}),{px(pts[0][1])},{e})"
    return f"max(0,min(iw-{cw},{e}))".replace(",", "\\,")


def parse_segments(spec):
    """"12-20,7.3-9.3@0.5" -> [(12, 20, 1.0), (7.3, 9.3, 0.5)]: source seconds, then a speed (0.5 = half-speed replay)."""
    out = []
    for p in (x.strip() for x in spec.split(",") if x.strip()):
        rng, _, sp = p.partition("@")
        a, b = (float(x) for x in rng.split("-"))
        out.append((a, b, float(sp) if sp else 1.0))
    return out


def lines_to_words(lines):
    """[[start, end, "text"], ...] in source seconds -> word timings spread evenly over each line."""
    out = []
    for a, b, text in lines:
        ws = text.split(); step = (b - a) / max(len(ws), 1)
        out += [{"w": w, "s": round(a + i * step, 2), "e": round(a + (i + 1) * step, 2)} for i, w in enumerate(ws)]
    return out


def concat_segments(src, segs, dst):
    """Join the kept parts of the source into one file (near-lossless), so every layout works on jump cuts."""
    parts = "".join(f"[0:v]trim={x:.3f}:{y:.3f},setpts=(PTS-STARTPTS)/{sp}[v{i}];[0:a]atrim={x:.3f}:{y:.3f},asetpts=PTS-STARTPTS,"
                    + (f"atempo={sp}," if sp != 1 else "")
                    + f"afade=t=in:d=0.03,afade=t=out:st={max(0, (y - x) / sp - 0.03):.3f}:d=0.03[a{i}];" for i, (x, y, sp) in enumerate(segs))
    graph = parts + "".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[v][a]"
    run([tool("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-c:a", "aac", "-b:a", "256k", str(dst)])
    return dst


def remap_words(words, segs):
    """Words on the output timeline after jump cuts."""
    out, off = [], 0.0
    for a, b, sp in segs:
        out += [dict(w, s=round(off + (w["s"] - a) / sp, 2), e=round(off + (min(w["e"], b) - a) / sp, 2)) for w in words if a <= w["s"] < b]
        off += (b - a) / sp
    return out, off
TOP = 730  # react layout: face panel height = seam y (even)
GAME_H = H - TOP  # 1190


def even(n):
    return int(n) // 2 * 2


def video_filter(layout, cam, ass, band=None, cam_side='right', src=None, game_x=None, face_expr=None, inp='[0:v]', focus=None, trim_bottom=0.0):
    """Layout + burned-caption filter graph ending in [vo]. Reused by translate.py."""
    if layout == "fill":
        v = f"[0:v]scale=-2:{H},crop={W}:{H}[v]"
    elif layout == "focus":
        cw = "floor(ih*0.8/2)*2"
        v = (f"[0:v]split[a][b];[a]scale=-2:{H},crop={W}:{H},boxblur=30:3,eq=brightness=-0.28[bg];"
             f"[b]crop={cw}:ih:{focus_x(focus or '0:0.5', cw)}:0,scale={W}:{FOCUS_H},setsar=1[fg];[bg][fg]overlay=0:{FOCUS_Y}[v]")
    elif layout == "blur":
        v = (f"[0:v]split[a][b];[a]scale=-2:{H},crop={W}:{H},boxblur=24:2,eq=brightness=-0.08[bg];"
             f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2-80[v]")
    elif layout == 'react':
        sw, sh = src
        if face_expr:  # tracked face crop (no cam frame)
            cw, chh, ex, ey = face_expr
            top = f"crop={cw}:{chh}:{ex}:{ey}"
        else:
            x, y, w, h = map(float, cam.split(':'))
            cw, chh = even(sw * w), even(sh * h)
            top = f"crop={cw}:{chh}:{even(sw * x)}:{even(sh * y)}"
        gw = even(sw * GAME_H / sh) if sw * GAME_H / sh >= W else W
        gx = game_x if game_x is not None else ((gw - W) if cam_side == 'left' else 0)
        pre = ""
        if trim_bottom > 0:  # game panel only: drop the source's bottom (a streamer's burned-in captions); the cam stays whole
            gh_src = sh * (1 - trim_bottom)
            gw2 = even(sw * GAME_H / gh_src) if sw * GAME_H / gh_src >= W else W
            gx = min(gw2 - W, gx * gw2 / gw); gw = gw2
            pre = f"crop=iw:floor(ih*{1 - trim_bottom:.3f}/2)*2:0:0,"
            trim_bottom = 0.0
        v = (f"[0:v]split[a][b];[a]{top},scale={W}:{TOP}:force_original_aspect_ratio=increase,crop={W}:{TOP},setsar=1[cam];"
             f"[b]{pre}scale={gw}:{GAME_H},crop={W}:{GAME_H}:{even(gx)}:0,setsar=1[game];[cam][game]vstack[v]")
        if band:
            y0, bh, secs = band
            en = f":enable='lte(t,{secs})'" if secs > 0 else ''
            v = v[:-3] + f"[v0];[v0]drawbox=x=0:y={y0}:w=iw:h={bh}:color=white@1:t=fill{en}[v]"
    else:
        x, y, w, h = map(float, cam.split(":"))
        v = (f"[0:v]split[a][b];[a]crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},scale={W}:{int(H * 0.38)}:force_original_aspect_ratio=increase,"
             f"crop={W}:{int(H * 0.38)}[cam];[b]scale=-2:{H - int(H * 0.38)},crop={W}:{H - int(H * 0.38)}[game];[cam][game]vstack[v]")
    sub = str(ass).replace("\\", "/").replace(":", "\\:")
    if trim_bottom > 0:  # cut off the bottom of the source (a streamer's own burned-in captions, alerts)
        v = f"{inp}crop=iw:floor(ih*{1 - trim_bottom:.3f}/2)*2:0:0[trim];" + v.replace("[0:v]", "[trim]", 1)
        return v + f";[v]fps=30,subtitles='{sub}'[vo]"
    return v.replace("[0:v]", inp) + f";[v]fps=30,subtitles='{sub}'[vo]"


def game_offset(video, s0, e0, src, cam_box):
    """Pick the x offset of the 1080-wide game crop that avoids static overlays (viewer counters,
    alerts, chat boxes) and the webcam. Static = pixels that barely change across sampled frames
    but carry edges (text/graphics)."""
    try:
        import cv2, numpy as np
    except ImportError:
        return None
    sw, sh = src
    gw = even(sw * GAME_H / sh)
    if gw <= W:
        return 0
    cap = cv2.VideoCapture(str(video)); frames = []
    for k in range(12):
        cap.set(cv2.CAP_PROP_POS_MSEC, (s0 + (e0 - s0) * (k + 0.5) / 12) * 1000)
        ok, f = cap.read()
        if ok:
            frames.append(cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (gw, GAME_H)).astype(np.float32))
    cap.release()
    if len(frames) < 4:
        return None
    st = np.stack(frames)
    std = st.std(0); med = np.median(st, 0)
    edges = cv2.Canny(med.astype(np.uint8), 60, 160) > 0
    bad = (std < 6) & cv2.dilate(edges.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    x, y, w, h = cam_box  # the cam itself also counts as overlay
    bad[int(y * GAME_H):int((y + h) * GAME_H), int(x * gw):int((x + w) * gw)] = True
    col = bad.sum(0).astype(np.float64); cs = np.concatenate([[0], np.cumsum(col)])
    best, bx = None, 0
    camcols = np.zeros(gw); camcols[int(x * gw):int((x + w) * gw)] = 1; cc = np.concatenate([[0], np.cumsum(camcols)])
    for ox in range(0, gw - W + 1, 8):
        # never show the cam twice; otherwise stay near the centre (game subtitles and action sit there),
        # moving off-centre only when that clearly removes a static overlay (counters, alerts, chat)
        if cc[ox + W] - cc[ox] > 0 and (cc[-1] < gw - W):
            continue
        cost = (cs[ox + W] - cs[ox]) * 0.2 + abs(ox - (gw - W) / 2) * GAME_H * 0.05
        if best is None or cost < best:
            best, bx = cost, ox
    return bx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job"); ap.add_argument("--pick", type=int, default=1)
    ap.add_argument("--layout", choices=["fill", "blur", "focus", "facecam", "react"], default="blur")
    ap.add_argument("--title", default="", help="reaction title, e.g. 'Speed REALIZED why GTA 6 took 13 YEARS'")
    ap.add_argument("--title-style", choices=["box", "outline"], default="box")
    ap.add_argument("--title-secs", type=float, default=0, help="0 = whole clip")
    ap.add_argument("--captions", choices=["word", "bubble", "none"], default="word")
    ap.add_argument("--hook", default="")
    ap.add_argument("--allow-profanity", action="store_true", help="keep swear words in audio and captions (off by default)")
    ap.add_argument("--cam", default="auto", help="auto (find the webcam) or x:y:w:h fractions")
    ap.add_argument("--start", type=float); ap.add_argument("--end", type=float)
    ap.add_argument("--segments", default="", help='jump cuts in source seconds, e.g. "12.3-20,23.8-27.3,29.5-41.8"')
    ap.add_argument("--focus", default="0:0.5", help='focus layout: "t:cx,..." keyframes, output seconds : centre x fraction')
    ap.add_argument("--hook-secs", type=float, default=None, help="seconds the hook stays; 0 = whole clip (default for focus)")
    ap.add_argument("--name", default="", help="output file stem, default clip_<pick>")
    ap.add_argument("--lines", default="", help='json [[start, end, "text"], ...] in source seconds: captions from the game subtitles')
    ap.add_argument("--lines-time", choices=["source", "output"], default="source",
                    help="output: --lines times are already on the finished clip's timeline (narration from narrate.py)")
    ap.add_argument("--voice", default="", help="narration track (narrate.py voice.wav), mixed over the clip's own audio")
    ap.add_argument("--cap-y", type=int, default=0, help="caption centre height in px (default per layout); raise it above on-screen text")
    ap.add_argument("--bed-gain", type=float, default=0.3, help="volume of the clip's own audio under --voice")
    ap.add_argument("--trim-bottom", type=float, default=0.0, help="fill/blur/focus/react: drop this fraction of the source's bottom (react: game panel only)")
    a = ap.parse_args()
    d = Path(a.job); c = load_json(d / "candidates.json")
    pick = next(x for x in c["candidates"] if x["n"] == a.pick)
    s0 = a.start if a.start is not None else pick["start"]; e0 = a.end if a.end is not None else pick["end"]
    words = load_json(d / "transcript.json")
    if a.lines:
        words = lines_to_words(load_json(a.lines))
    out_words = words if (a.lines and a.lines_time == "output") else None  # already on the output timeline
    segs = parse_segments(a.segments)
    out = d / "edits"; out.mkdir(exist_ok=True)
    stem = a.name or f"clip_{a.pick}"
    orig_source = c["source"]
    if segs:  # join the kept parts first; everything after works on the joined file from 0 to its end
        c["source"] = str(concat_segments(orig_source, segs, out / f"{stem}.src.mp4"))
        words, total = remap_words(words, segs)
        s0, e0 = 0.0, total
    if out_words is not None:  # narration captions: shift onto the cut's own time base (s0 is 0 after --segments)
        words = [dict(w, s=w["s"] + s0, e=w["e"] + s0) for w in out_words]
    layout, cam, side = a.layout, a.cam, 'right'
    face_expr = None
    if layout in ('react', 'facecam') and cam == 'auto':
        from facecam import find_cam
        r = find_cam(c['source'], s0, e0)
        if layout == 'react' and r.get('mode') not in ('cam', 'face'):
            sys.exit(f"skipped: no streamer face over gameplay in this moment ({r.get('mode')}: {r.get('reason', '')}). "
                     "React clips need the game on screen with the cam as a separate box. Pick another moment or stream.")
        if layout == 'react':
            from facecam import has_gameplay, face_crop_expr
            if not has_gameplay(c['source'], s0, e0, r['box']):
                sys.exit("skipped: the area outside the webcam is not gameplay (same scene or no game on screen). "
                         "Pick a moment where GTA 6 is on screen.")
            if r.get('mode') == 'face' and r.get('face_track'):
                from common import ffprobe as _fp
                _vs = [x for x in _fp(c['source'])['streams'] if x.get('codec_type') == 'video'][0]
                from facecam import inner_edges
                sw_, sh_ = int(_vs['width']), int(_vs['height'])
                bnd = inner_edges(c['source'], s0, e0, r['face'], sw_, sh_)
                print(f'facecam: cam borders L{bnd[0]} T{bnd[1]} R{bnd[2]} B{bnd[3]} px')
                fe = face_crop_expr(r['face_track'], sw_, sh_, W, TOP, bounds=bnd)
                face_expr = (fe['w'], fe['h'], fe['x'], fe['y'])
                print(f"facecam: no clean cam frame, tracking the face ({r.get('summary', '')})")
        if r.get('mode') in ('cam', 'face'):
            bx = list(r['box'])
            if r['mode'] == 'face':  # no webcam frame: widen the face crop so it is not a blurry close-up
                cx, cy = bx[0] + bx[2] / 2, bx[1] + bx[3] / 2
                bw, bh = min(1.0, bx[2] * 2.6), min(1.0, bx[3] * 2.2)
                bx = [min(max(0.0, cx - bw / 2), 1 - bw), min(max(0.0, cy - bh / 2), 1 - bh), bw, bh]
            cam = ':'.join(f'{v:.4f}' for v in bx)
            side = 'left' if r['box'][0] + r['box'][2] / 2 < 0.5 else 'right'
            print(f"facecam: {r.get('mode')} box {cam} ({r.get('summary', '')})")
        else:
            print(f"facecam: no stable face found ({r.get('reason', '')}), using the blur layout")
            layout = 'blur'
    elif layout in ('react', 'facecam') and cam != 'auto':
        side = 'left' if float(cam.split(':')[0]) + float(cam.split(':')[2]) / 2 < 0.5 else 'right'
    cap_y = a.cap_y or CAP_Y[layout]
    title, band = None, None
    if a.title and layout == 'react':
        n = len(wrap(a.title, 26 if a.title_style == 'box' else 24))
        if a.title_style == 'box':
            bh = n * 78 + 44
            band = (TOP - bh // 2, bh, a.title_secs)
            title = ('box', a.title, TOP, a.title_secs)
        else:
            title = ('outline', a.title, TOP + 40, a.title_secs)
    ass = out / f"{stem}.ass"
    hook_secs = a.hook_secs if a.hook_secs is not None else (0 if layout == "focus" else 2.6)
    caps = a.captions
    cap_words = words if caps != 'none' else []
    c_s, c_e = s0, e0
    ass.write_text(build_ass(cap_words, c_s, c_e, a.hook, cap_y, title=title, caps=caps, profanity=a.allow_profanity,
                             hook_secs=hook_secs, hook_y=120 if layout == "focus" else 170, hook_fs=80 if layout == "focus" else 68), encoding="utf-8")
    src = None; gx = None
    if layout == 'react':
        from common import ffprobe
        vs = [x for x in ffprobe(c['source'])['streams'] if x.get('codec_type') == 'video'][0]
        src = (int(vs['width']), int(vs['height']))
        gx = game_offset(c['source'], s0, e0, src, [float(t) for t in cam.split(':')])
    mp4 = out / f"{stem}.mp4"
    if a.trim_bottom and layout == "facecam":
        sys.exit("--trim-bottom works with fill, blur, focus and react")
    v = video_filter(layout, cam, ass, band=band, cam_side=side, src=src, game_x=gx, face_expr=face_expr, focus=a.focus,
                     trim_bottom=a.trim_bottom)
    muted = []
    if not a.allow_profanity:  # clean-language rule: silence every swear heard, plus any the captions know about
        from clean import heard_bad, is_bad, merge, mute_filter
        hits = heard_bad(c["source"], s0, e0)
        cap_hits = [(w["s"] - c_s, w["e"] - c_s, w["w"]) for w in cap_words if c_s <= w["s"] < c_e and is_bad(w["w"])]
        # start early: the first sound of a word is enough to hear it
        muted = merge([(x - 0.25, max(y, x + 0.45)) for x, y, _ in hits] + [(x - 0.25, y + 0.25) for x, y, _ in cap_hits])
        muted = [(max(0.0, float(x)), min(float(e0 - s0), float(y))) for x, y in muted]
        print(f"clean: heard {[h[2] for h in hits]}, captions {[h[2] for h in cap_hits]}, muted {muted}")
    def audio_args(extra_inputs_from=1):
        """Audio: the clip's own sound (muted where it swears), or that sound as a quiet bed under the narration."""
        mute = (mute_filter(muted) + ",") if muted else ""
        if not a.voice:
            return [], ["-map", "0:a?", "-af", mute + "loudnorm=I=-14:TP=-1.5:LRA=11"], None
        n = extra_inputs_from
        graph = (f"[0:a]{mute}volume={a.bed_gain}[bed];[{n}:a]apad[vox];"
                 f"[bed][vox]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]")
        return ["-i", a.voice], ["-map", "[ao]"], graph
    vin, vmap, agraph = audio_args()
    io = ["-ss", f"{s0:.2f}", "-to", f"{e0:.2f}", "-i", c["source"], *vin,
          "-filter_complex", v + (";" + agraph if agraph else ""), "-map", "[vo]", *vmap]
    run([tool("ffmpeg"), "-y", "-v", "error", *io,
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
         "-ar", "48000", "-movflags", "+faststart", str(mp4)])
    if not a.allow_profanity:  # verify the finished clip like check.py does; mute anything still heard, re-mux the audio only
        for rnd in range(4):
            left = heard_bad(mp4) + heard_bad(mp4, model="small") + heard_bad(mp4, offset=2.5) + heard_bad(mp4, model="small", offset=2.5)
            if not left:
                break
            muted = merge(muted + [(max(0.0, float(x) - 0.25), float(max(y, x + 0.45))) for x, y, _ in left], pad=0.05)
            muted = [(max(0.0, float(x)), min(float(e0 - s0), float(y))) for x, y in muted]
            print(f"clean: still heard {[(round(float(x), 1), w) for x, _, w in left]}, muted {muted}")
            tmp = mp4.with_suffix(".tmp.mp4")
            if a.voice:  # a swear in the narration or the bed: mute the whole mix there
                remix = ["-i", a.voice, "-filter_complex",
                         f"[1:a]{mute_filter(muted)},volume={a.bed_gain}[bed];[2:a]apad,{mute_filter(muted)}[vox];"
                         f"[bed][vox]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]",
                         "-map", "0:v", "-map", "[ao]"]
            else:
                remix = ["-map", "0:v", "-map", "1:a", "-af", f"{mute_filter(muted)},loudnorm=I=-14:TP=-1.5:LRA=11"]
            run([tool("ffmpeg"), "-y", "-v", "error", "-i", str(mp4), "-ss", f"{s0:.2f}", "-to", f"{e0:.2f}", "-i", c["source"],
                 *remix, "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(tmp)])
            tmp.replace(mp4)
        else:
            print("clean: WARNING swears still heard after 4 rounds; do not post this clip")
    info = c.get("info", {})
    save_json(out / f"{stem}.json", {"file": str(mp4), "start": s0, "end": e0, "segments": segs, "muted": muted, "clean": not a.allow_profanity, "source_views": info.get("view_count"), "layout": layout, "hook": a.hook or a.title, "title": a.title, "cam": cam,
                                            "source_file": orig_source, "source_url": info.get("webpage_url"), "source_title": info.get("title"),
                                            "source_channel": info.get("channel") or info.get("uploader")})
    print(mp4)


if __name__ == "__main__":
    main()
