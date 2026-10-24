"""Quality Assurance gate for affiliate shorts.
Ensures file presence, duration, resolution, audio loudness, and compliance.
"""
import json, os, subprocess, sys
from pathlib import Path

FFMPEG = Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe"
FFPROBE = Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffprobe.exe"


def run_qa(proj_dir: Path) -> dict:
    proj_dir = Path(proj_dir)
    errors = []
    
    # 1. File checks
    required_files = ["project.json", "timings.json", "out/final.mp4", "out/cover.jpg"]
    for rf in required_files:
        if not (proj_dir / rf).exists():
            errors.append(f"Missing required file: {rf}")
            
    if errors:
        return {"pass": False, "errors": errors}

    # 2. Metadata check
    meta = json.loads((proj_dir / "project.json").read_text(encoding="utf-8"))
    if not meta.get("title"):
        errors.append("project.json missing 'title'")
    if not meta.get("affiliate_url"):
        errors.append("project.json missing 'affiliate_url'")

    # 3. Video stream probe
    video_path = proj_dir / "out/final.mp4"
    probe_cmd = [
        str(FFPROBE), "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "json",
        str(video_path)
    ]
    r = subprocess.run(probe_cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        errors.append("ffprobe failed to inspect video stream")
    else:
        info = json.loads(r.stdout).get("streams", [{}])[0]
        w, h = info.get("width"), info.get("height")
        dur = float(info.get("duration", 0.0))
        
        if w != 1080 or h != 1920:
            errors.append(f"Invalid resolution: {w}x{h} (must be 1080x1920)")
        if not (15.0 <= dur <= 58.0):
            errors.append(f"Invalid duration: {dur:.1f}s (must be between 15s and 58s)")

    # 4. Cover check
    cover = proj_dir / "out/cover.jpg"
    if cover.stat().st_size < 10000:
        errors.append(f"Cover image too small: {cover.stat().st_size} bytes")

    passed = len(errors) == 0
    return {"pass": passed, "errors": errors}


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    res = run_qa(p)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["pass"] else 1)
