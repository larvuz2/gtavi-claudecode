"""Dev-diary opening: "DEV" pops in big and centred when Bob says "dev", "DIARY" lands under it when he says
"diary", the gameplay behind dims, then both punch out. Laid over a finished horizontal video.

usage: python dd_intro.py in.mp4 out.mp4 --dev 1.9 --diary 2.75 --end 3.7
Art: brand/dev_alpha.png, brand/diary_alpha.png (transparent wooden-sign word marks).
"""
import argparse, math, subprocess, tempfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1920, 1080, 30


def pop(t):
    """Scale over time since appearance: 0.55 -> overshoot 1.08 -> settle 1.0 (back-out ease, 0.28 s)."""
    if t <= 0:
        return 0
    if t >= 0.28:
        return 1.0
    x = t / 0.28
    c = 2.2
    return 0.55 + 0.45 * (1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2)


def frame(t, dev, diary, end, a_dev, a_diary):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out_k = 0.0 if t < end - 0.25 else min(1.0, (t - (end - 0.25)) / 0.25)    # punch out in the last 0.25 s
    for art, t0, cy, width in ((a_dev, dev, 395, 980), (a_diary, diary, 760, 1060)):
        s = pop(t - t0)
        if s <= 0:
            continue
        s *= 1 + 0.35 * out_k
        alpha = 1 - out_k
        w = max(2, int(width * s)); h = max(2, int(art.height * w / art.width))
        a = art.resize((w, h), Image.LANCZOS)
        if alpha < 1:
            a.putalpha(a.getchannel("A").point(lambda v: int(v * alpha)))
        tilt = (-2.5 if art is a_dev else 2.0) * (1 - min(1, (t - t0) / 0.28))
        if abs(tilt) > 0.05:
            a = a.rotate(tilt, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(a, (W // 2 - a.width // 2, cy - a.height // 2))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--dev", type=float, required=True); ap.add_argument("--diary", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--chime", default=str(ROOT / "brand/reveal_chime.wav"), help="reveal sound started on DIARY ('' for none)")
    ap.add_argument("--chime-gain", type=float, default=0.6)
    a = ap.parse_args()
    a_dev = Image.open(ROOT / "brand/dev_alpha.png").convert("RGBA")
    a_diary = Image.open(ROOT / "brand/diary_alpha.png").convert("RGBA")
    with tempfile.TemporaryDirectory() as td:
        n = int(math.ceil(a.end * FPS))
        for i in range(n):
            frame(i / FPS, a.dev, a.diary, a.end, a_dev, a_diary).save(f"{td}/f{i:04d}.png")
        dim = f"eq=brightness=-0.22:saturation=0.75:enable='lt(t,{a.end - 0.15})'"
        graph = (f"[0:v]{dim},boxblur=6:1:enable='lt(t,{a.end - 0.15})'[bg];"
                 f"[1:v]format=rgba,setpts=PTS-STARTPTS[ov];[bg][ov]overlay=0:0:eof_action=pass:format=auto[v]")
        ins = ["-i", a.src, "-framerate", str(FPS), "-i", f"{td}/f%04d.png"]
        amap, acodec = ["-map", "0:a"], ["-c:a", "copy"]
        if a.chime:  # the reveal chime lands with DIARY
            ins += ["-i", a.chime]
            ms = int(a.diary * 1000)
            graph += (f";[2:a]volume={a.chime_gain},adelay={ms}|{ms}[c];"
                      f"[0:a][c]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]")
            amap, acodec = ["-map", "[a]"], ["-c:a", "aac", "-b:a", "192k"]
        subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[v]", *amap, "-c:v", "libx264",
                        "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", *acodec, "-movflags", "+faststart", a.dst],
                       check=True)
    print(a.dst)


if __name__ == "__main__":
    main()
