"""Kokoro TTS worker (runs inside reels/tts-venv, Python 3.12).

  tts-venv/Scripts/python.exe kokoro_tts.py request.json
request: {"voice": "af_heart", "speed": 1.08, "lines": [{"id": "hook", "text": "...", "out": "path.wav"}]}
prints JSON: {"lines": [{"id", "out", "duration", "words": [[t0, t1, word], ...]}]}
"""
import json, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
import soundfile as sf
from kokoro import KPipeline

SR = 24000


def main():
    req = json.load(open(sys.argv[1], encoding="utf-8"))
    voice = req.get("voice", "af_heart")
    pipe = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")
    out = []
    for ln in req["lines"]:
        chunks, words, offset = [], [], 0.0
        for res in pipe(ln["text"], voice=voice, speed=float(req.get("speed", 1.0))):
            audio = res.audio.numpy() if hasattr(res.audio, "numpy") else np.asarray(res.audio)
            for tok in (res.tokens or []):
                if tok.start_ts is None or tok.end_ts is None or not tok.text.strip():
                    continue
                w = tok.text.strip()
                if words and not any(c.isalnum() for c in w):      # punctuation token -> glue to previous word
                    words[-1][2] += w; continue
                words.append([round(offset + tok.start_ts, 3), round(offset + tok.end_ts, 3), w])
            chunks.append(audio); offset += len(audio) / SR
        audio = np.concatenate(chunks) if chunks else np.zeros(SR // 4)
        # trim leading/trailing silence (keep 40 ms)
        nz = np.where(np.abs(audio) > 0.01)[0]
        lead = 0.0
        if len(nz):
            a, b = max(0, nz[0] - int(0.04 * SR)), min(len(audio), nz[-1] + int(0.06 * SR))
            lead = a / SR; audio = audio[a:b]
        words = [[max(0, w[0] - lead), max(0, w[1] - lead), w[2]] for w in words]
        sf.write(ln["out"], audio, SR)
        out.append({"id": ln["id"], "out": ln["out"], "duration": round(len(audio) / SR, 3), "words": words})
    print(json.dumps({"lines": out}))


if __name__ == "__main__":
    main()
