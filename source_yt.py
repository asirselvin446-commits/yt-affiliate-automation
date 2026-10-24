"""YouTube Clip Sourcer for Real Product Footage.
Finds authentic review, unboxing, and demo footage of the exact Amazon product on YouTube.
Scores candidates by exact brand/model relevance, filters out comparisons and roundups,
and preserves comprehensive creator and source provenance metadata.
"""
import datetime as dt
import json, math, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
venv_py = HERE / ".venv" / "Scripts" / "python.exe"
if venv_py.exists():
    PY = venv_py
elif (HERE / ".venv" / "bin" / "python").exists():
    PY = HERE / ".venv" / "bin" / "python"
else:
    PY = Path(sys.executable)

_system_ffmpeg = shutil.which("ffmpeg")
FFMPEG = Path(_system_ffmpeg) if _system_ffmpeg else (Path.home() / "AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe")

NEGATIVE_KEYWORDS = re.compile(
    r"\b(compilation|podcast|reaction|live|full movie|animation|ai generated|roblox|minecraft|gta|"
    r"vs|versus|comparison|compare|which is better|top \d+|best \d+|\d+ best|buying guide|"
    r"drop test|fake|clone|replica|teardown|disassembly|speed test|parody|meme)\b",
    re.I
)

POSITIVE_KEYWORDS = re.compile(
    r"\b(review|unboxing|hands on|demonstration|first look|detailed review|in depth|usage|setup)\b",
    re.I
)


def extract_brand_model(product_query: str) -> tuple[str, str, list[str]]:
    """Extracts likely brand, model, and key keywords from a product title or query."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", product_query)
    words = [w for w in cleaned.split() if len(w) > 1 and not re.match(r"^[0-9]+%$", w)]
    if not words:
        return "", "", []
    brand = words[0]
    model = words[1] if len(words) > 1 else ""
    return brand, model, words[:6]


def score_candidate(item: dict, brand: str, model: str, key_words: list[str]) -> tuple[float, str]:
    """Calculates relevance score for a YouTube search candidate.
    Must score >= 45 to be eligible for production.
    """
    title = item.get("title", "")
    t_lower = title.lower()
    dur = float(item.get("duration") or 60)
    views = int(item.get("view_count") or 0)
    
    # 1. Negative filtering
    if NEGATIVE_KEYWORDS.search(title):
        return -100.0, f"Contains negative keyword in title: '{title}'"
        
    score = 0.0
    
    # 2. Brand match
    if brand and brand.lower() in t_lower:
        score += 35.0
        
    # 3. Model match
    if model and model.lower() in t_lower:
        score += 35.0
        
    # 4. Keyword token overlap
    matched_words = [w for w in key_words if w.lower() in t_lower]
    score += min(20.0, len(matched_words) * 5.0)
    
    # 5. Review / demo focus
    if POSITIVE_KEYWORDS.search(title):
        score += 15.0
        
    # 6. Duration suitability: prefer dedicated 30s-360s review clips
    if 30 <= dur <= 360:
        score += 15.0
    elif 15 <= dur < 30:
        score += 5.0
    elif 360 < dur <= 600:
        score += 5.0
    else:  # Under 15s or over 10m (vlogs / long streams)
        score -= 30.0
        
    # 7. Quality confidence signal from views (log-scaled tie-breaker)
    if views > 0:
        score += min(10.0, math.log10(views + 1) * 2.0)
        
    reason = f"Score: {score:.1f} (brand={brand in t_lower}, model={model in t_lower}, matches={len(matched_words)}, dur={dur}s)"
    return score, reason


def search_and_download_product_clip(
    product_query: str,
    dest_dir: Path,
    brand_hint: str = "",
    model_hint: str = "",
    min_score: float = 45.0
) -> dict:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    raw_video = dest_dir / "raw_footage.mp4"
    out_video = dest_dir / "real_footage.mp4"
    out_info = dest_dir / "real_footage.info.json"
    
    brand, model, key_words = extract_brand_model(product_query)
    if brand_hint:
        brand = brand_hint
    if model_hint:
        model = model_hint
        
    search_queries = [
        f"{brand} {model} review".strip(),
        f"{' '.join(key_words[:3])} unboxing review".strip(),
        f"{' '.join(key_words[:4])}".strip()
    ]
    
    entries = []
    for query in search_queries:
        if not query:
            continue
        print(f"Searching YouTube with query: '{query}'...")
        search_cmd = [
            str(PY), "-m", "yt_dlp",
            "--flat-playlist",
            "--dump-single-json",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=android,web",
            f"ytsearch5:{query}"
        ]
        r = subprocess.run(search_cmd, capture_output=True, text=True, errors="replace", timeout=45)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout.strip())
                new_entries = data.get("entries", [])
                for e in new_entries:
                    if e and e not in entries:
                        entries.append(e)
            except Exception:
                pass
        if len(entries) >= 3:
            break
            
    if not entries:
        raise RuntimeError(f"Could not find any YouTube search results for '{product_query}'")
        
    # Score each candidate
    scored_candidates = []
    for item in entries:
        if not item:
            continue
        sc, reason = score_candidate(item, brand, model, key_words)
        if sc >= min_score:
            scored_candidates.append((sc, item, reason))
            
    if not scored_candidates:
        raise RuntimeError(
            f"No suitable verified YouTube review footage found matching '{product_query}' (brand: '{brand}', model: '{model}'). "
            f"All candidates failed strict relevance criteria to prevent publishing mismatched footage."
        )
        
    # Sort by score descending
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, chosen, best_reason = scored_candidates[0]
    
    video_url = chosen.get("url") or f"https://www.youtube.com/watch?v={chosen.get('id')}"
    creator = chosen.get("uploader") or chosen.get("channel") or "YouTube Creator"
    views = chosen.get("view_count") or 0
    duration = float(chosen.get("duration") or 60)
    
    print(f"Selected verified clip: '{chosen.get('title')}' by @{creator} (score: {best_score:.1f}, {views:,} views)")
    
    # Download raw footage
    dl_cmd = [
        str(PY), "-m", "yt_dlp",
        "-q", "--no-progress",
        "--no-playlist",
        "--extractor-args", "youtube:player_client=android,web",
        "-f", "bv*[height<=1080]+ba/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "-o", str(raw_video),
        video_url
    ]
    
    dl_res = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=180)
    if not raw_video.exists():
        # Fallback format if merge failed
        dl_cmd[6] = "best[ext=mp4]/best"
        subprocess.run(dl_cmd, capture_output=True, text=True, timeout=120)
        
    if not raw_video.exists():
        raise RuntimeError(f"Failed to download YouTube footage from {video_url}:\n{dl_res.stderr[-300:]}")
        
    # Trim initial talking-head intro (skip first 3.5s if video is longer than 40s)
    # to jump straight into product footage
    trim_start = 3.5 if duration > 40 else 0.0
    if trim_start > 0:
        trim_cmd = [
            str(FFMPEG), "-y",
            "-ss", f"{trim_start:.2f}",
            "-i", str(raw_video),
            "-c", "copy",
            str(out_video)
        ]
        subprocess.run(trim_cmd, capture_output=True)
    
    if not out_video.exists() or out_video.stat().st_size == 0:
        shutil.copy2(raw_video, out_video)
        
    raw_video.unlink(missing_ok=True)
    
    # Save provenance metadata
    meta = {
        "source_url": video_url,
        "video_id": chosen.get("id"),
        "title": chosen.get("title"),
        "creator": creator,
        "channel_url": chosen.get("uploader_url") or f"https://www.youtube.com/@{creator.replace(' ', '')}",
        "duration": duration,
        "view_count": views,
        "relevance_score": round(best_score, 2),
        "reason": best_reason,
        "local_file": str(out_video),
        "retrieved_at": dt.datetime.now().isoformat()
    }
    out_info.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "STRIFF Adjustable Laptop Stand"
    res = search_and_download_product_clip(q, Path("./test_source"))
    print(f"Downloaded footage to {res['local_file']} from creator @{res['creator']}")
