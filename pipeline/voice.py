"""Narration: Kokoro "Michael" (am_michael), slightly deepened, clean and dry (no echo). Channel rule.

synth(phrases, wav, voice, speed) -> (wav, [(start, end) per phrase], total seconds)
Model files (~330 MB) are downloaded once into ~/.cache/kokoro.
"""
import os, subprocess, urllib.request
import numpy as np

CACHE = os.path.expanduser("~/.cache/kokoro")
URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
SR = 24000
LEAD = 0.12          # silence before the first word
# The narrator's sound. Do not change without James saying so.
VOICE_FILTER = ("highpass=f=60,rubberband=pitch=0.93:formant=preserved,bass=g=3:f=120,"
                "acompressor=threshold=-20dB:ratio=3:attack=5:release=90,aresample=48000")


def _model():
    os.makedirs(CACHE, exist_ok=True)
    for f in FILES:
        p = os.path.join(CACHE, f)
        if not os.path.exists(p):
            print("downloading", f); urllib.request.urlretrieve(URL + f, p + ".part"); os.replace(p + ".part", p)
    from kokoro_onnx import Kokoro
    return Kokoro(*(os.path.join(CACHE, f) for f in FILES))


def synth(phrases, wav, voice="am_michael", speed=0.95):
    import soundfile as sf
    k = _model(); lang = "en-gb" if voice.startswith("b") else "en-us"
    out = [np.zeros(int(SR * LEAD), np.float32)]; t = LEAD; times = []
    for ph in phrases:
        a, _ = k.create(ph["say"], voice=voice, speed=speed, lang=lang)
        a = a.astype(np.float32); idx = np.where(np.abs(a) > 0.01)[0]
        a = a[max(0, idx[0] - 240):idx[-1] + 480]
        times.append((round(t, 3), round(t + len(a) / SR, 3)))
        out.append(a); t += len(a) / SR
        g = ph.get("pause", 0.22); out.append(np.zeros(int(SR * g), np.float32)); t += g
    raw = wav[:-4] + ".raw.wav"
    sf.write(raw, np.concatenate(out), SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", VOICE_FILTER, wav], check=True)
    os.remove(raw)
    return wav, times, round(t, 3)
