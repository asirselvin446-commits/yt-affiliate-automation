"""Kokoro-82M Offline Text-to-Speech synthesizer with word-level boundary alignment.
Ultra-high quality natural voice, zero API credits, zero cloud dependency.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Find Kokoro runtime: prioritize local kokoro_tts.py in same directory or system python
_local_kokoro = HERE / "kokoro_tts.py"
_hermes_kokoro = Path(r"C:\Users\asus\AppData\Local\hermes\profiles\insta\ig-publisher\reels\kokoro_tts.py")
KOKORO_SCRIPT = _local_kokoro if _local_kokoro.exists() else _hermes_kokoro

_hermes_py = Path(r"C:\Users\asus\AppData\Local\hermes\profiles\insta\ig-publisher\reels\tts-venv\Scripts\python.exe")
KOKORO_PY = _hermes_py if _hermes_py.exists() else Path(sys.executable)

_system_ffmpeg = shutil.which("ffmpeg")
FFMPEG = Path(_system_ffmpeg) if _system_ffmpeg else (Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe")
DEFAULT_VOICE = "am_michael"  # American male, energetic product reviewer tone


def build_voiceover(text: str, out_dir: Path, voice: str = DEFAULT_VOICE) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_wav = out_dir / "voice.wav"
    audio_mp3 = out_dir / "voice.mp3"
    timings_path = out_dir / "timings.json"
    req_file = out_dir / "kokoro_req.json"

    req_data = {
        "voice": voice,
        "speed": 1.10,
        "lines": [
            {
                "id": "full_script",
                "text": text,
                "out": str(audio_wav)
            }
        ]
    }
    req_file.write_text(json.dumps(req_data), encoding="utf-8")

    cmd = [str(KOKORO_PY), str(KOKORO_SCRIPT), str(req_file)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        print(f"Kokoro TTS primary attempt failed ({r.returncode}): {r.stderr[:200]}")
        espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak_bin:
            print("Using espeak-ng fallback for voiceover...")
            subprocess.run([espeak_bin, "-v", "en-us", "-s", "145", "-w", str(audio_wav), text], check=True, timeout=60)
            ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
            dur_res = subprocess.run([ffprobe_bin, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio_wav)], capture_output=True, text=True)
            try:
                duration = float(dur_res.stdout.strip())
            except Exception:
                duration = 20.0
            text_words = text.split()
            step = duration / max(1, len(text_words))
            raw_words = [[round(i * step, 3), round((i + 1) * step, 3), w] for i, w in enumerate(text_words)]
        else:
            raise RuntimeError(f"Kokoro TTS failed ({r.returncode}):\n{r.stderr}")
    else:
        res = json.loads(r.stdout.strip())
        line_info = res["lines"][0]
        duration = line_info["duration"]
        raw_words = line_info["words"]

    # Convert to structured word boundaries
    words = []
    for w in raw_words:
        words.append({
            "word": w[2],
            "start": w[0],
            "end": w[1],
            "duration": round(w[1] - w[0], 3)
        })

    # Convert WAV to MP3 using ffmpeg
    subprocess.run([str(FFMPEG), "-y", "-i", str(audio_wav), "-b:a", "192k", str(audio_mp3)],
                   capture_output=True, timeout=30)

    meta = {
        "text": text,
        "voice": voice,
        "audio_file": str(audio_mp3),
        "duration": duration,
        "words": words
    }
    timings_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


if __name__ == "__main__":
    test_text = "If you sit at a desk all day, this 800 rupee Amazon find is literally a game changer."
    out = Path("./test_voice")
    res = build_voiceover(test_text, out)
    print(f"Synthesized {res['duration']:.2f}s audio at {res['audio_file']} with {len(res['words'])} words.")
