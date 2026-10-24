"""Video Rendering Engine for Vertical (9:16) Amazon Product YouTube Shorts.
Engineered for high retention, premium aesthetics, and visual clarity:
- Output: 1080x1920, 9:16, 30 FPS, H.264 video, AAC audio.
- Intelligent aspect ratio handling:
    * Vertical (9:16) sources: Clean full-screen presentation (zero blurred background).
    * Landscape (16:9) sources: 4:3 center-cropped action framing with darkened ambient backdrop.
    * Square (1:1 / 4:5) sources: Centered foreground with restrained ambient depth.
- Compact glassmorphic top product badge (price/rating only when verified).
- Completely removed artificial bottom attribution pills or replacement watermarks.
- Synchronized semantic karaoke captions with safe UI margins.
"""
import json, math, os, shutil, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
_system_ffmpeg = shutil.which("ffmpeg")
FFMPEG = Path(_system_ffmpeg) if _system_ffmpeg else (Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe")
_system_ffprobe = shutil.which("ffprobe")
FFPROBE = Path(_system_ffprobe) if _system_ffprobe else (Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffprobe.exe")

WIDTH, HEIGHT = 1080, 1920
FPS = 30


def get_video_info(video_path: Path) -> dict:
    """Probes video dimensions, duration, and frame rate via ffprobe."""
    cmd = [
        str(FFPROBE), "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,r_frame_rate,codec_name",
        "-of", "json",
        str(video_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        return {"width": 1920, "height": 1080, "duration": 0.0, "ar": 1.777}
    try:
        data = json.loads(r.stdout).get("streams", [{}])[0]
        w = int(data.get("width") or 1920)
        h = int(data.get("height") or 1080)
        dur = float(data.get("duration") or 0.0)
        return {
            "width": w,
            "height": h,
            "ar": round(w / h, 4) if h > 0 else 1.777,
            "duration": dur,
            "codec": data.get("codec_name", "")
        }
    except Exception:
        return {"width": 1920, "height": 1080, "duration": 0.0, "ar": 1.777}


def create_top_product_overlay(title: str, price: str, rating: float, out_png: Path):
    """Creates a sleek, compact glassmorphic product header at top safe area (Y: 40-130).
    Never obscures the main action; shows verified price and rating only when present.
    """
    banner = Image.new("RGBA", (WIDTH, 140), (0, 0, 0, 0))
    draw = ImageDraw.Draw(banner)
    
    # Sleek frosted capsule
    x1, y1, x2, y2 = 40, 40, WIDTH - 40, 130
    draw.rounded_rectangle([x1, y1, x2, y2], radius=18, fill=(16, 20, 28, 220), outline=(255, 255, 255, 35), width=1)
    
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 28)
        font_badge = ImageFont.truetype("arialbd.ttf", 24)
    except Exception:
        font_title = ImageFont.load_default()
        font_badge = ImageFont.load_default()
        
    curr_x = x2 - 20
    
    # Verified Price Pill (only when price is provided)
    if price and price.strip():
        price_clean = price.strip()
        pw = len(price_clean) * 16 + 24
        px = curr_x - pw
        draw.rounded_rectangle([px, y1 + 14, curr_x, y2 - 14], radius=10, fill=(255, 153, 0, 240))
        draw.text((px + 12, y1 + 22), price_clean, fill=(18, 18, 18, 255), font=font_badge)
        curr_x = px - 14

    # Verified Rating Pill (only when rating > 0)
    if rating and float(rating) > 0.0:
        rtxt = f"{float(rating):.1f}/5"
        rw = len(rtxt) * 16 + 24
        rx = curr_x - rw
        draw.rounded_rectangle([rx, y1 + 14, curr_x, y2 - 14], radius=10, fill=(16, 185, 129, 230))
        draw.text((rx + 12, y1 + 22), rtxt, fill=(255, 255, 255, 255), font=font_badge)
        curr_x = rx - 16

    # Product Title (measured and truncated cleanly to fit remaining space)
    max_title_w = curr_x - (x1 + 24)
    clean_title = title.strip()
    # Strip emojis to avoid missing glyph square boxes
    clean_title = clean_title.encode("ascii", "ignore").decode("ascii").strip()
    
    while len(clean_title) > 8:
        bbox = draw.textbbox((0, 0), clean_title, font=font_title)
        if (bbox[2] - bbox[0]) <= max_title_w:
            break
        clean_title = clean_title[:-4] + "..."
        
    draw.text((x1 + 24, y1 + 24), clean_title, fill=(245, 248, 255, 255), font=font_title)
    banner.save(out_png, "PNG")


def generate_subtitles_ass(timings: dict, out_ass: Path):
    """Generates synchronized ASS karaoke subtitles inside the safe lower-middle area.
    Groups words into short semantic clauses (2-4 words) with radiant active word highlight.
    """
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,66,&H00FFFFFF,&H0000FFFF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,5,2,2,80,80,540,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    words = timings.get("words", [])
    if not words:
        out_ass.write_text(header, encoding="utf-8")
        return

    # Semantic chunking based on speech pauses, punctuation, and clause rhythm
    chunks = []
    curr = []
    for w in words:
        curr.append(w)
        txt = w["word"]
        char_len = sum(len(x["word"]) for x in curr)
        has_punct = any(p in txt for p in [".", ",", "!", "?", ";", ":"])
        gap = (w["start"] - curr[-2]["end"]) if len(curr) >= 2 else 0.0
        if has_punct or len(curr) >= 3 or char_len >= 18 or gap > 0.22:
            chunks.append(curr)
            curr = []
    if curr:
        chunks.append(curr)

    def to_ts(s: float) -> str:
        m, sec = divmod(s, 60.0)
        h, m = divmod(m, 60.0)
        cs = int(round((sec - int(sec)) * 100))
        if cs >= 100:
            cs = 99
        return f"{int(h):d}:{int(m):02d}:{int(sec):02d}.{cs:02d}"

    events = []
    for chunk in chunks:
        for idx, active_w in enumerate(chunk):
            st = to_ts(active_w["start"])
            en = to_ts(active_w["end"])
            parts = []
            for j, w in enumerate(chunk):
                # Clean word for ASS format
                word_clean = w["word"].replace("{", "").replace("}", "").strip()
                if j == idx:
                    # Highlight active spoken word in golden amber
                    parts.append(r"{\c&H0000E5FF&}" + word_clean + r"{\c&H00FFFFFF&}")
                else:
                    parts.append(word_clean)
            line_text = " ".join(parts)
            events.append(f"Dialogue: 0,{st},{en},Default,,0,0,0,,{line_text}")

    content = header + "\n".join(events) + "\n"
    out_ass.write_text(content, encoding="utf-8")


def render_video(proj_dir: Path) -> Path:
    """Renders 1080x1920 vertical video with intelligent aspect ratio handling,
    compact product overlay, and synchronized karaoke captions.
    """
    proj_dir = Path(proj_dir)
    meta = json.loads((proj_dir / "project.json").read_text(encoding="utf-8"))
    timings = json.loads((proj_dir / "timings.json").read_text(encoding="utf-8"))
    duration = timings["duration"]
    
    out_dir = proj_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    final_video = out_dir / "final.mp4"
    temp_video = out_dir / "final.tmp.mp4"
    cover_jpg = out_dir / "cover.jpg"
    
    # 1. Locate source footage
    footage_candidates = [
        proj_dir / "assets/real_footage.mp4",
        proj_dir / "real_footage.mp4",
        proj_dir / "footage.mp4"
    ]
    source_video = None
    for c in footage_candidates:
        if c.exists() and c.stat().st_size > 0:
            source_video = c
            break
            
    if not source_video:
        raise RuntimeError(f"No source footage found in {proj_dir}. Real footage is required.")
        
    title = meta.get("title", "Featured Amazon Product")
    price = meta.get("price", "")
    rating = meta.get("rating", 0.0)
    
    # 2. Top compact badge overlay
    top_badge_png = proj_dir / "top_badge.png"
    create_top_product_overlay(title, price, rating, top_badge_png)
    
    # 3. ASS subtitles
    ass_path = proj_dir / "subs.ass"
    generate_subtitles_ass(timings, ass_path)
    
    try:
        ass_esc = ass_path.relative_to(Path.cwd()).as_posix()
    except Exception:
        ass_esc = ass_path.as_posix()
        if ":" in ass_esc:
            ass_esc = ass_esc.replace(":", "\\\\:")
            
    # 4. Aspect Ratio Detection & Filtergraph
    info = get_video_info(source_video)
    ar = info["ar"]
    print(f"Source video dimensions: {info['width']}x{info['height']} (aspect ratio: {ar:.3f})")
    
    if ar < 0.85:
        # Case A: Portrait / Vertical source (9:16 Shorts/Reels/TikTok)
        # Full-screen vertical video — zero blurred background
        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[vprod];"
            "[vprod][2:v]overlay=0:0[with_badge];"
            f"[with_badge]ass={ass_esc}[vfinal]"
        )
    elif 0.85 <= ar <= 1.25:
        # Case B: Square / Near-Square (1:1, 4:5)
        # Scaled to width 1080, centered over darkened ambient frosted background
        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5,drawbox=color=black@0.65:replace=0[bg];"
            "[0:v]scale=1080:-2:force_original_aspect_ratio=decrease,drawbox=color=white@0.15:t=1[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            "[base][2:v]overlay=0:0[with_badge];"
            f"[with_badge]ass={ass_esc}[vfinal]"
        )
    else:
        # Case C: Landscape source (16:9, 4:3)
        # 4:3 center-cropped action window (1080x810) placed in upper-middle (Y: 280),
        # leaving ample safe space for compact header above and subtitles below
        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,drawbox=color=black@0.65:replace=0[bg];"
            "[0:v]crop=ih*4/3:ih:(iw-ih*4/3)/2:0,scale=1080:810,drawbox=color=white@0.15:t=1[fg];"
            "[bg][fg]overlay=(W-w)/2:280[base];"
            "[base][2:v]overlay=0:0[with_badge];"
            f"[with_badge]ass={ass_esc}[vfinal]"
        )
        
    cmd = [
        str(FFMPEG), "-y",
        "-stream_loop", "-1", "-i", str(source_video),
        "-i", str(proj_dir / "voice.mp3"),
        "-i", str(top_badge_png),
        "-filter_complex", filter_complex,
        "-map", "[vfinal]",
        "-map", "1:a",
        "-r", str(FPS),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration:.2f}",
        str(temp_video)
    ]
    
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=600)
    if r.returncode != 0:
        temp_video.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg render failed:\n{r.stderr[-800:]}")
        
    if not temp_video.exists() or temp_video.stat().st_size < 100000:
        raise RuntimeError(f"Render output invalid or empty: {temp_video}")
        
    shutil.move(str(temp_video), str(final_video))
    
    # 5. Generate cover thumbnail snapshot from 2.5s
    thumb_cmd = [
        str(FFMPEG), "-y",
        "-ss", "00:00:02.500",
        "-i", str(final_video),
        "-vframes", "1",
        "-q:v", "2",
        str(cover_jpg)
    ]
    subprocess.run(thumb_cmd, capture_output=True)
    
    # Clean up obsolete attribution pill if present from previous builds
    (proj_dir / "bottom_credit.png").unlink(missing_ok=True)
    
    return final_video


if __name__ == "__main__":
    test_proj = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./test_project")
    rendered = render_video(test_proj)
    print(f"Rendered video successfully at: {rendered}")
