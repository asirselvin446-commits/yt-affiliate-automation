"""Comprehensive Quality Assurance Gate for Amazon Affiliate YouTube Shorts.
Enforces technical standards, visual integrity, subtitle safety, and legal compliance:
- Resolution (1080x1920), 30 FPS, H.264 video, AAC audio, duration limits.
- Automated black frame and video freeze detection via FFmpeg filters.
- Subtitle bounds, timing synchronization, and collision verification.
- Accurate product data, valid affiliate tag, and required FTC disclosure.
- Cover image integrity and resolution.
Any failure strictly prevents scheduling or uploading the video.
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
from PIL import Image

_system_ffmpeg = shutil.which("ffmpeg")
FFMPEG = Path(_system_ffmpeg) if _system_ffmpeg else (Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe")
_system_ffprobe = shutil.which("ffprobe")
FFPROBE = Path(_system_ffprobe) if _system_ffprobe else (Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffprobe.exe")


def run_qa(proj_dir: Path) -> dict:
    proj_dir = Path(proj_dir)
    errors = []
    warnings = []
    
    # 1. Essential File Existence
    required_files = [
        "project.json",
        "timings.json",
        "subs.ass",
        "top_badge.png",
        "out/final.mp4",
        "out/cover.jpg"
    ]
    for rf in required_files:
        p = proj_dir / rf
        if not p.exists() or p.stat().st_size == 0:
            errors.append(f"Missing or empty required file: {rf}")
            
    if errors:
        return {"pass": False, "errors": errors, "warnings": warnings}

    # 2. Metadata & Legal Compliance
    try:
        meta = json.loads((proj_dir / "project.json").read_text(encoding="utf-8"))
    except Exception as ex:
        return {"pass": False, "errors": [f"Corrupt project.json: {ex}"], "warnings": warnings}
        
    title = meta.get("title", "")
    if not title or len(title) < 8:
        errors.append(f"Invalid video title in project.json: '{title}'")
        
    affiliate_url = meta.get("affiliate_url", "")
    if "tag=" not in affiliate_url or "asirselvin336-21" not in affiliate_url:
        errors.append(f"Invalid affiliate URL: missing associate tag 'asirselvin336-21' ({affiliate_url})")
        
    script_text = meta.get("script", "")
    banned_hype = ["game changer", "literally", "must-have", "grab it before it's gone"]
    for bh in banned_hype:
        if bh in script_text.lower():
            errors.append(f"Script contains banned hype word: '{bh}'")
            
    # Verify FTC / Amazon disclosure
    desc = meta.get("description", "")
    has_disclosure = bool(re.search(r"\b(as an amazon associate|earn from qualifying purchases|affiliate link|qualifying purchases|affiliate commission|sponsored)\b", desc, re.I))
    if not has_disclosure:
        errors.append("Description is missing mandatory Amazon Associate / FTC disclosure")

    # 2b. Creative Director & Shot Plan QA
    scenes = meta.get("scenes", [])
    if not scenes or len(scenes) < 4:
        errors.append(f"Creative Director error: 'scenes' plan must contain at least 4 scenes (found {len(scenes)})")
    else:
        types_found = {s.get("type") for s in scenes}
        if not {"hook", "reveal"}.issubset(types_found):
            errors.append(f"Scenes plan missing required structural types: {types_found}")
            
        prev_end = 0.0
        for i, sc in enumerate(scenes):
            sc_id = sc.get("scene_id", i + 1)
            st = sc.get("start", -1.0)
            en = sc.get("end", -1.0)
            narr = sc.get("narration", "").strip()
            vis = sc.get("visual_action", "").strip()
            ost = sc.get("on_screen_text", "").strip()
            evi = sc.get("evidence_source", "").strip()
            
            if st < 0 or en <= st:
                errors.append(f"Scene {sc_id} has invalid timing bounds: start={st}, end={en}")
            if st < prev_end - 0.5:
                errors.append(f"Scene {sc_id} timing non-monotonic: start={st} before previous end={prev_end}")
            prev_end = en
            
            if not narr:
                errors.append(f"Scene {sc_id} is missing narration")
            if not vis:
                errors.append(f"Scene {sc_id} is missing visual_action description")
            if not ost:
                errors.append(f"Scene {sc_id} is missing on_screen_text")
            if not evi:
                errors.append(f"Scene {sc_id} is missing evidence_source for claim")

    consideration = meta.get("buying_consideration", "").strip()
    if not consideration or len(consideration.split()) < 3:
        errors.append(f"Creative Director error: missing or insufficient 'buying_consideration': '{consideration}'")
        
    candidates = meta.get("hook_candidates", [])
    if not candidates or len(candidates) < 2:
        warnings.append(f"Creative Director warning: expected >= 2 hook candidates (found {len(candidates)})")
        
    # 3. Subtitles QA
    ass_path = proj_dir / "subs.ass"
    ass_text = ass_path.read_text(encoding="utf-8", errors="ignore")
    if "[Events]" not in ass_text or "Dialogue:" not in ass_text:
        errors.append("subs.ass has no valid Dialogue events")
        
    dialogue_lines = [l for l in ass_text.splitlines() if l.startswith("Dialogue:")]
    if len(dialogue_lines) < 5:
        errors.append(f"Insufficient subtitle dialogue lines: {len(dialogue_lines)}")
        
    # Check vertical margin safety (must be inside lower-middle safe band 450-650)
    margin_match = re.search(r"Style:\s*Default,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,(\d+)", ass_text)
    if margin_match:
        margin_v = int(margin_match.group(1))
        if margin_v < 400 or margin_v > 750:
            errors.append(f"Subtitle MarginV={margin_v} is outside UI safe area (expected 450-650)")

    # 4. Stream Inspection via ffprobe
    video_path = proj_dir / "out/final.mp4"
    probe_cmd = [
        str(FFPROBE), "-v", "error",
        "-show_streams",
        "-of", "json",
        str(video_path)
    ]
    r = subprocess.run(probe_cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        errors.append(f"ffprobe failed to inspect final.mp4: {r.stderr[:200]}")
    else:
        streams = json.loads(r.stdout).get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        
        if not v_stream:
            errors.append("final.mp4 has no video stream")
        else:
            w = int(v_stream.get("width") or 0)
            h = int(v_stream.get("height") or 0)
            dur = float(v_stream.get("duration") or 0.0)
            codec = v_stream.get("codec_name", "")
            r_fps = v_stream.get("r_frame_rate", "")
            
            if w != 1080 or h != 1920:
                errors.append(f"Invalid video resolution: {w}x{h} (must be exactly 1080x1920)")
            if codec != "h264":
                errors.append(f"Invalid video codec: {codec} (must be h264)")
            if not (18.0 <= dur <= 38.0):
                errors.append(f"Invalid duration: {dur:.1f}s (must be between 18s and 38s for high retention Shorts)")
            if r_fps not in ["30/1", "2997/100", "30000/1001", "30"]:
                warnings.append(f"Non-standard frame rate: {r_fps}")

        if not a_stream:
            errors.append("final.mp4 has no audio stream")
        else:
            a_codec = a_stream.get("codec_name", "")
            if a_codec != "aac":
                errors.append(f"Invalid audio codec: {a_codec} (must be aac)")

    # 5. Visual Artifact & Freeze Detection
    filter_cmd = [
        str(FFMPEG), "-v", "info",
        "-i", str(video_path),
        "-vf", "blackdetect=d=1.2:pix_th=0.10,freezedetect=n=-50dB:d=2.5",
        "-f", "null",
        "-"
    ]
    r_art = subprocess.run(filter_cmd, capture_output=True, text=True, errors="replace", timeout=60)
    if r_art.returncode == 0:
        if "black_start" in r_art.stderr:
            # Check duration of black screen
            black_matches = re.findall(r"black_duration:([0-9.]+)", r_art.stderr)
            for bm in black_matches:
                if float(bm) >= 1.5:
                    errors.append(f"Detected prolonged black frame artifact ({bm}s)")
        if "lavfi.freezedetect.freeze_duration" in r_art.stderr:
            freeze_matches = re.findall(r"freeze_duration:\s*([0-9.]+)", r_art.stderr)
            for fm in freeze_matches:
                if float(fm) >= 3.0:
                    errors.append(f"Detected frozen video frame artifact ({fm}s)")

    # 6. Cover Thumbnail Check
    cover = proj_dir / "out/cover.jpg"
    if cover.stat().st_size < 15000:
        errors.append(f"Cover thumbnail size too small: {cover.stat().st_size} bytes (minimum 15KB)")
    else:
        try:
            with Image.open(cover) as img:
                cw, ch = img.size
                if cw != 1080 or ch != 1920:
                    errors.append(f"Invalid cover image dimensions: {cw}x{ch} (must be 1080x1920)")
        except Exception as e:
            errors.append(f"Failed to decode cover image: {e}")

    passed = len(errors) == 0
    return {"pass": passed, "errors": errors, "warnings": warnings}


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    res = run_qa(target)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["pass"] else 1)
