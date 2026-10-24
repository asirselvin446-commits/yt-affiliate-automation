"""Video Rendering Engine for Vertical (9:16) Amazon Product YouTube Shorts.
Uses real YouTube product review/demo footage:
- 1080x1920 vertical canvas
- Blurred background of the real video scaled to fill 1080x1920
- Sharp crisp original footage centered with rounded borders or letterbox
- Top Amazon Product & Price badge
- Bottom creator attribution pill ('Source: @Creator on YouTube')
- Animated karaoke subtitles synchronized with Kokoro-82M TTS voiceover
"""
import json, math, os, shutil, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
_system_ffmpeg = shutil.which("ffmpeg")
FFMPEG = Path(_system_ffmpeg) if _system_ffmpeg else (Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe")
WIDTH, HEIGHT = 1080, 1920
FPS = 30


def create_top_product_overlay(title: str, price: str, rating: float, out_png: Path):
    """Creates a transparent PNG with a sleek glassmorphic Amazon product banner at top."""
    banner = Image.new("RGBA", (WIDTH, 340), (0, 0, 0, 0))
    draw = ImageDraw.Draw(banner)
    
    # Dark frosted card background
    draw.rounded_rectangle([40, 60, WIDTH - 40, 300], radius=24, fill=(18, 22, 32, 230), outline=(255, 255, 255, 40), width=2)
    
    # Fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 36)
        font_price = ImageFont.truetype("arialbd.ttf", 46)
        font_rating = ImageFont.truetype("arialbd.ttf", 32)
    except Exception:
        font_title = ImageFont.load_default()
        font_price = ImageFont.load_default()
        font_rating = ImageFont.load_default()
        
    # Title (truncated if long)
    clean_title = title if len(title) <= 52 else title[:49] + "..."
    draw.text((70, 90), clean_title, fill=(255, 255, 255, 255), font=font_title)
    
    # Price Pill (Amazon Yellow)
    if price:
        px = 70
        pw = len(price) * 28 + 36
        draw.rounded_rectangle([px, 160, px + pw, 230], radius=14, fill=(255, 153, 0, 255))
        draw.text((px + 18, 170), price, fill=(20, 20, 20, 255), font=font_price)
        
    # Rating Pill (Emerald Green)
    if rating:
        rx = 70 + (len(price) * 28 + 56 if price else 0)
        rtxt = f"RATING: {rating:.1f}/5"
        rw = len(rtxt) * 20 + 36
        draw.rounded_rectangle([rx, 166, rx + rw, 226], radius=14, fill=(16, 185, 129, 255))
        draw.text((rx + 18, 176), rtxt, fill=(255, 255, 255, 255), font=font_rating)
        
    # Verified label
    draw.text((70, 250), "AMAZON VERIFIED DEAL", fill=(180, 200, 225, 255), font=font_rating)

    banner.save(out_png, "PNG")


def create_bottom_attribution_pill(creator: str, out_png: Path):
    """Creates a transparent attribution badge at the bottom for fair-use creator credit."""
    pill = Image.new("RGBA", (WIDTH, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pill)
    
    try:
        font = ImageFont.truetype("arialbd.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
        
    text = f"Source: @{creator} on YouTube"
    tw = len(text) * 16 + 50
    x1 = (WIDTH - tw) // 2
    x2 = x1 + tw
    draw.rounded_rectangle([x1, 30, x2, 85], radius=28, fill=(10, 10, 14, 210), outline=(255, 255, 255, 30), width=1)
    draw.text((x1 + 25, 42), text, fill=(220, 225, 235, 255), font=font)
    
    pill.save(out_png, "PNG")


def generate_subtitles_ass(timings: dict, out_ass: Path):
    """Creates animated word-level ASS subtitles centered cleanly above bottom attribution."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,66,&H00FFFFFF,&H0000FFFF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,6,0,2,50,50,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    words = timings.get("words", [])
    if not words:
        out_ass.write_text(header, encoding="utf-8")
        return

    events = []
    chunk_size = 4
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        start_sec = chunk[0]["start"]
        end_sec = chunk[-1]["end"]
        
        def to_ts(s):
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            return f"{int(h):d}:{int(m):02d}:{s:05.2f}"
            
        t_start = to_ts(start_sec)
        t_end = to_ts(end_sec)
        
        line_text = " ".join(w["word"] for w in chunk)
        # Highlight active phrase in radiant amber-gold
        events.append(f"Dialogue: 0,{t_start},{t_end},Karaoke,,0,0,0,,{{\\c&H00D4FF&}}{line_text}")

    content = header + "\n".join(events) + "\n"
    out_ass.write_text(content, encoding="utf-8")


def render_video(proj_dir: Path) -> Path:
    proj_dir = Path(proj_dir)
    meta = json.loads((proj_dir / "project.json").read_text(encoding="utf-8"))
    timings = json.loads((proj_dir / "timings.json").read_text(encoding="utf-8"))
    duration = timings["duration"]
    
    out_dir = proj_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    final_video = out_dir / "final.mp4"
    cover_jpg = out_dir / "cover.jpg"
    
    # 1. Check for real footage video
    footage_candidates = [
        proj_dir / "assets/real_footage.mp4",
        proj_dir / "real_footage.mp4",
        proj_dir / "footage.mp4"
    ]
    source_video = None
    for c in footage_candidates:
        if c.exists():
            source_video = c
            break
            
    if not source_video:
        raise RuntimeError(f"No real footage video found in {proj_dir}. Real YouTube footage is required.")
        
    creator = meta.get("creator") or meta.get("yt_creator") or "YouTube Creator"
    title = meta.get("title", "Amazon Viral Find")
    price = meta.get("price", "")
    rating = meta.get("rating", 4.3)
    
    # 2. Prepare visual badge overlays
    top_badge_png = proj_dir / "top_badge.png"
    bottom_credit_png = proj_dir / "bottom_credit.png"
    create_top_product_overlay(title, price, rating, top_badge_png)
    create_bottom_attribution_pill(creator, bottom_credit_png)
    
    # 3. Subtitles ASS
    ass_path = proj_dir / "subs.ass"
    generate_subtitles_ass(timings, ass_path)
    
    # 4. FFmpeg Composite Graph:
    # Input 0: real_footage.mp4 (looped if source duration < voiceover duration)
    # Input 1: voice.mp3 (Kokoro-82M TTS audio)
    # Input 2: top_badge.png
    # Input 3: bottom_credit.png
    #
    # Video Filter:
    # - Background: scale real video to 1080x1920 (crop/fill) + gblur (sigma=35)
    # - Foreground: scale real video to width=1080, preserve aspect ratio
    # - Overlay foreground at center of background
    # - Overlay top badge at (0, 0)
    # - Overlay bottom credit at (0, 1800)
    # - Apply ASS subtitles
    
    ass_esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
    
    filter_complex = (
        # 1. Background blurred fill
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        # 2. Crisp centered main video
        "[0:v]scale=1080:-2:force_original_aspect_ratio=decrease[fg];"
        # 3. Stack centered foreground over blurred background
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        # 4. Overlay top Amazon product badge
        "[base][2:v]overlay=0:0[with_top];"
        # 5. Overlay bottom attribution badge
        "[with_top][3:v]overlay=0:1780[with_badges];"
        # 6. Burn karaoke subtitles
        f"[with_badges]ass={ass_esc}[vfinal]"
    )
    
    cmd = [
        str(FFMPEG), "-y",
        "-stream_loop", "-1", "-i", str(source_video),
        "-i", str(proj_dir / "voice.mp3"),
        "-i", str(top_badge_png),
        "-i", str(bottom_credit_png),
        "-filter_complex", filter_complex,
        "-map", "[vfinal]",
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration:.2f}",
        str(final_video)
    ]
    
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg render failed:\n{r.stderr[-800:]}")
        
    # Generate cover thumbnail snapshot from second 2 of final video
    thumb_cmd = [
        str(FFMPEG), "-y",
        "-ss", "00:00:02.000",
        "-i", str(final_video),
        "-vframes", "1",
        "-q:v", "2",
        str(cover_jpg)
    ]
    subprocess.run(thumb_cmd, capture_output=True)
    
    return final_video


if __name__ == "__main__":
    test_proj = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./test_project")
    rendered = render_video(test_proj)
    print(f"Rendered video successfully at: {rendered}")
