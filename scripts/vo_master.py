"""Studio voice-over mastering for narration (cloned or recorded voices).

usage: python vo_master.py in.wav out.wav --preset studio_deep
Presets:
  broadcast    EQ + compression, no pitch change (the first version)
  studio_warm  no pitch change; strong chest and proximity, dry, tight
  studio_deep  1 semitone lower with the voice's own formants kept, chest boost, dry, tight
  studio_deeper 2 semitones lower, formants kept, more low end
Chain: gate -> pitch (rubberband) -> high-pass -> chest/low shelf -> mud cut -> presence -> de-ess -> air ->
compression -> gentle saturation -> limiter -> -16 LUFS. Dry: studio voice-over has no room sound.
Needs: ffmpeg with rubberband, pip install pedalboard.
"""
import argparse, subprocess, sys, tempfile
from pathlib import Path

PRESETS = {
    "broadcast":     {"semitones": 0,  "chest": 5.0, "low": 0.0, "mud": -3.0, "presence": 3.0, "air": 2.0, "sat": 0.0},
    "studio_warm":   {"semitones": 0,  "chest": 5.0, "low": 2.5, "mud": -4.0, "presence": 2.0, "air": 2.5, "sat": 3.0},
    "studio_deep":   {"semitones": -1, "chest": 5.5, "low": 3.0, "mud": -4.0, "presence": 2.0, "air": 2.5, "sat": 3.0},
    "studio_deeper": {"semitones": -2, "chest": 6.0, "low": 3.5, "mud": -4.5, "presence": 2.5, "air": 2.5, "sat": 3.0},
}


def master(src, dst, preset="studio_deep"):
    import numpy as np
    from pedalboard import (Pedalboard, NoiseGate, HighpassFilter, LowShelfFilter, PeakFilter, HighShelfFilter,
                            Compressor, Distortion, Gain, Limiter)
    from pedalboard.io import AudioFile
    p = PRESETS[preset]
    with tempfile.TemporaryDirectory() as td:
        pitched = Path(td) / "p.wav"
        af = "aresample=48000"
        if p["semitones"]:
            ratio = 2 ** (p["semitones"] / 12)
            af = f"rubberband=pitch={ratio:.5f}:formant=preserved:transients=smooth:detector=soft:pitchq=quality,aresample=48000"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", af, "-ac", "1", str(pitched)], check=True)
        with AudioFile(str(pitched)) as f:
            x, sr = f.read(f.frames), f.samplerate
    chain = [
        NoiseGate(threshold_db=-48, ratio=4, attack_ms=2, release_ms=120),
        HighpassFilter(cutoff_frequency_hz=65),
        LowShelfFilter(cutoff_frequency_hz=90, gain_db=p["low"], q=0.7),
        PeakFilter(cutoff_frequency_hz=125, gain_db=p["chest"], q=0.8),       # chest / proximity
        PeakFilter(cutoff_frequency_hz=330, gain_db=p["mud"], q=1.3),         # boxiness of phone recordings
        PeakFilter(cutoff_frequency_hz=2800, gain_db=p["presence"], q=1.0),   # intelligibility
        PeakFilter(cutoff_frequency_hz=6800, gain_db=-3.0, q=3.0),            # sibilance
        HighShelfFilter(cutoff_frequency_hz=11000, gain_db=p["air"], q=0.7),  # air
        Compressor(threshold_db=-24, ratio=3.5, attack_ms=3, release_ms=70),
        Gain(gain_db=4),
    ]
    if p["sat"]:
        chain += [Distortion(drive_db=p["sat"]), Gain(gain_db=-p["sat"] * 0.6)]  # warmth, not grit
    chain += [Compressor(threshold_db=-12, ratio=2, attack_ms=10, release_ms=120), Limiter(threshold_db=-1.5, release_ms=80)]
    y = Pedalboard(chain)(x, sr)
    tmp = Path(str(dst) + ".pre.wav")
    with AudioFile(str(tmp), "w", sr, y.shape[0]) as f:
        f.write(y)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-ar", "48000",
                    "-ac", "1", str(dst)], check=True)
    tmp.unlink()
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--preset", default="studio_deep", choices=sorted(PRESETS))
    a = ap.parse_args()
    print(master(a.src, a.dst, a.preset))
