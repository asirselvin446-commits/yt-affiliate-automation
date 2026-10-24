"""YouTube Clip Sourcer for Real Product Footage.
Finds real review, unboxing, and demo footage of the Amazon product on YouTube
and downloads the best clip using yt-dlp.
"""
import json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = Path(sys.executable)

# Words indicating bad/unusable footage
BAD_KEYWORDS = re.compile(
    r"\b(compilation|podcast|reaction|live|full movie|animation|ai generated|roblox|minecraft|gta)\b",
    re.I
)


def search_and_download_product_clip(product_query: str, dest_dir: Path, max_duration_sec: int = 60) -> dict:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_video = dest_dir / "real_footage.mp4"
    out_info = dest_dir / "real_footage.info.json"
    
    # Clean product query to 3-5 core words (e.g. "Portronics Clamp M2 Car Phone Mount")
    clean_words = [w for w in product_query.split() if len(w) > 1 and not re.match(r"^[0-9]+%$", w)]
    search_term = " ".join(clean_words[:5]) + " review test"
    
    print(f"Searching YouTube for real footage: '{search_term}'...")
    
    # Use yt-dlp search: ytsearch5 to grab top 5 candidates
    search_cmd = [
        str(PY), "-m", "yt_dlp",
        "--no-playlist",
        "--default-search", "ytsearch5",
        "--dump-json",
        f"ytsearch5:{search_term}"
    ]
    
    r = subprocess.run(search_cmd, capture_output=True, text=True, errors="replace", timeout=120)
    if r.returncode != 0 or not r.stdout.strip():
        print(f"Direct review search yielded no dump, trying broader term '{search_term.replace(' review test', '')}'...")
        search_cmd[-1] = f"ytsearch5:{' '.join(clean_words[:4])}"
        r = subprocess.run(search_cmd, capture_output=True, text=True, errors="replace", timeout=120)
        
    candidates = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            title = item.get("title", "")
            dur = item.get("duration", 0)
            if BAD_KEYWORDS.search(title):
                continue
            # Prefer videos with good duration (10s to 180s)
            if 10 <= dur <= 300:
                candidates.append(item)
        except Exception:
            continue
            
    if not candidates:
        raise RuntimeError(f"Could not find any suitable YouTube footage for '{product_query}'")
        
    # Pick candidate with highest view count
    chosen = max(candidates, key=lambda c: c.get("view_count", 0))
    video_url = chosen.get("webpage_url") or f"https://www.youtube.com/watch?v={chosen['id']}"
    creator = chosen.get("uploader") or chosen.get("channel", "YouTube Creator")
    
    print(f"Selected real clip: '{chosen.get('title')}' by @{creator} ({chosen.get('view_count', 0):,} views)")
    
    # Download 1080p/720p MP4
    dl_cmd = [
        str(PY), "-m", "yt_dlp",
        "-q", "--no-progress",
        "--no-playlist",
        "-f", "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "-o", str(out_video),
        video_url
    ]
    
    dl_res = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=180)
    if not out_video.exists():
        raise RuntimeError(f"Failed to download YouTube footage from {video_url}:\n{dl_res.stderr[-300:]}")
        
    meta = {
        "source_url": video_url,
        "video_id": chosen.get("id"),
        "title": chosen.get("title"),
        "creator": creator,
        "duration": chosen.get("duration"),
        "local_file": str(out_video)
    }
    out_info.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Portronics Clamp M2 Car Mount"
    res = search_and_download_product_clip(q, Path("./test_source"))
    print(f"Downloaded footage to {res['local_file']} from creator @{res['creator']}")
