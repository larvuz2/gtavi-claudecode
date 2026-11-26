"""Synthesize the dev-diary "reveal" chime: a soft riser and a rising celesta run into a bright chord, then a shimmer
tail. 3 s, volume ramps up then down. Deterministic (fixed seed), so it is the same sound every time.

usage: python sfx_reveal.py brand/reveal_chime.wav [--seconds 3]
"""
import argparse
import numpy as np

SR = 48000


def bell(f, dur, amp=1.0, decay=1.4):
    t = np.arange(int(dur * SR)) / SR
    # celesta / glockenspiel partials (slightly inharmonic), each decaying faster than the last
    parts = [(1.0, 1.0, 1.0), (2.0, 0.45, 1.8), (2.76, 0.25, 2.6), (5.4, 0.12, 4.0), (8.93, 0.05, 6.0)]
    y = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * decay * d) for m, a, d in parts)
    attack = np.minimum(1, t / 0.004)
    return amp * y * attack


def note(name):
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    return 440 * 2 ** ((names[name[0]] + 12 * (int(name[1:]) + 1) - 69) / 12)


def make(seconds=3.0, seed=7):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = np.zeros((2, n))

    def add(sig, start, pan=0.0):
        i = int(start * SR); j = min(n, i + len(sig))
        out[0, i:j] += sig[: j - i] * (1 - pan) ** 0.5
        out[1, i:j] += sig[: j - i] * (1 + pan) ** 0.5

    # 1. airy riser 0 -> 0.62 s (band-passed noise swelling up)
    t = np.arange(int(0.65 * SR)) / SR
    noise = rng.standard_normal(len(t))
    k = np.ones(40) / 40
    hiss = noise - np.convolve(noise, k, "same")            # crude high-pass: air, not rumble
    add(0.05 * hiss * (t / t[-1]) ** 2.5, 0.0)
    # 2. rising celesta run (pentatonic), panned left to right
    run = ["G5", "A5", "C6", "D6", "E6", "G6", "A6", "C7"]
    for i, nm in enumerate(run):
        add(bell(note(nm), 1.2, 0.16 + 0.02 * i, 2.4), 0.05 + i * 0.075, pan=-0.6 + 1.2 * i / (len(run) - 1))
    # 3. the "ta-da": bright chord at 0.66 s
    for nm, p in (("C6", -0.3), ("E6", 0.3), ("G6", -0.1), ("C7", 0.1), ("E7", 0.0)):
        add(bell(note(nm), seconds - 0.66, 0.30, 1.1), 0.66, pan=p)
    # 4. shimmer: tiny high bells, thinning out
    pent = ["C7", "D7", "E7", "G7", "A7", "C8"]
    for _ in range(26):
        st = 0.7 + rng.random() ** 1.6 * 1.9
        add(bell(note(pent[rng.integers(len(pent))]), 0.6, 0.05 * (1 - (st - 0.7) / 2.2), 4.0), st, pan=rng.uniform(-0.8, 0.8))
    # simple stereo room: a few early reflections
    for d, g in ((0.031, 0.35), (0.047, 0.28), (0.083, 0.2), (0.127, 0.14)):
        sh = int(d * SR)
        out[0, sh:] += g * out[1, :-sh]
        out[1, sh:] += g * out[0, :-sh]
    # overall ramp: in over 0.35 s, hold, out from 1.6 s to the end (smooth)
    tt = np.arange(n) / SR
    env = np.minimum(1, tt / 0.35) * np.where(tt < 1.6, 1, np.cos(np.clip((tt - 1.6) / (seconds - 1.6), 0, 1) * np.pi / 2) ** 2)
    out *= env
    out /= np.abs(out).max() / 0.89
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dst"); ap.add_argument("--seconds", type=float, default=3.0)
    a = ap.parse_args()
    y = make(a.seconds)
    try:
        from pedalboard import Pedalboard, Reverb, HighpassFilter
        y = Pedalboard([HighpassFilter(250), Reverb(room_size=0.55, wet_level=0.22, dry_level=0.85, width=1.0)])(y.astype(np.float32), SR)
        tt = np.arange(y.shape[1]) / SR
        y *= np.where(tt < a.seconds - 0.4, 1, np.clip((a.seconds - tt) / 0.4, 0, 1))
        y /= np.abs(y).max() / 0.89
    except ImportError:
        pass
    import wave
    pcm = (np.clip(y.T, -1, 1) * 32767).astype(np.int16)
    with wave.open(a.dst, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print(a.dst)
