"""YouTube Clip Sourcer for Real Product Footage.
Finds real review, unboxing, and demo footage of the Amazon product on YouTube
and downloads the best clip using yt-dlp.
"""
import json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = Path(sys.executable)

BAD_KEYWORDS = re.compile(
    r"\b(compilation|podcast|reaction|live|full movie|animation|ai generated|roblox|minecraft|gta)\b",
    re.I
)


def search_and_download_product_clip(product_query: str, dest_dir: Path, max_duration_sec: int = 60) -> dict:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_video = dest_dir / "real_footage.mp4"
    out_info = dest_dir / "real_footage.info.json"
    
    # Strip non-alphanumeric punctuation (like '&', '|', quotes)
    cleaned_query = re.sub(r"[^a-zA-Z0-9\s]", " ", product_query)
    clean_words = [w for w in cleaned_query.split() if len(w) > 1 and not re.match(r"^[0-9]+%$", w)]
    search_term = " ".join(clean_words[:4]) + " review"
    
    print(f"Searching YouTube for real footage: '{search_term}'...")
    
    # Use yt-dlp flat-playlist single json search (instant, zero throttling)
    search_cmd = [
        str(PY), "-m", "yt_dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--no-playlist",
        "--extractor-args", "youtube:player_client=android,web",
        f"ytsearch5:{search_term}"
    ]
    
    r = subprocess.run(search_cmd, capture_output=True, text=True, errors="replace", timeout=60)
    entries = []
    if r.returncode == 0 and r.stdout.strip():
        try:
            data = json.loads(r.stdout.strip())
            entries = data.get("entries", [])
        except Exception:
            entries = []
            
    if not entries:
        # Fallback to broader 2-3 word query
        fallback_term = " ".join(clean_words[:3]) + " gadget"
        print(f"Direct review query empty, retrying with '{fallback_term}'...")
        search_cmd[-1] = f"ytsearch5:{fallback_term}"
        r = subprocess.run(search_cmd, capture_output=True, text=True, errors="replace", timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout.strip())
                entries = data.get("entries", [])
            except Exception:
                entries = []
                
    candidates = []
    for item in entries:
        if not item:
            continue
        title = item.get("title", "")
        dur = item.get("duration") or 60
        if BAD_KEYWORDS.search(title):
            continue
        # Allow review clips between 10s and 600s
        if 10 <= dur <= 600:
            candidates.append(item)
            
    if not candidates and entries:
        candidates = entries[:2]
        
    if not candidates:
        raise RuntimeError(f"Could not find any suitable YouTube footage for '{product_query}'")
        
    # Pick candidate with highest view count
    chosen = max(candidates, key=lambda c: c.get("view_count") or 0)
    video_url = chosen.get("url") or f"https://www.youtube.com/watch?v={chosen.get('id')}"
    creator = chosen.get("uploader") or chosen.get("channel") or "YouTube Creator"
    views = chosen.get("view_count") or 0
    
    print(f"Selected real clip: '{chosen.get('title')}' by @{creator} ({views:,} views)")
    
    # Download 1080p/720p MP4 with android client
    dl_cmd = [
        str(PY), "-m", "yt_dlp",
        "-q", "--no-progress",
        "--no-playlist",
        "--extractor-args", "youtube:player_client=android,web",
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "-o", str(out_video),
        video_url
    ]
    
    dl_res = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=180)
    if not out_video.exists():
        # Fallback format if merge failed
        dl_cmd[6] = "best[ext=mp4]/best"
        subprocess.run(dl_cmd, capture_output=True, text=True, timeout=120)
        
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
    q = sys.argv[1] if len(sys.argv) > 1 else "STRIFF Adjustable Laptop Stand"
    res = search_and_download_product_clip(q, Path("./test_source"))
    print(f"Downloaded footage to {res['local_file']} from creator @{res['creator']}")
