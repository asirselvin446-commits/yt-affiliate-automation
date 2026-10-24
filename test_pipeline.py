"""Unit and regression tests for Affiliate Shorts pipeline.
Validates QA gate, subtitle generation, video aspect ratio handling,
candidate relevance scoring, script sanitization, overlay styling,
and Creative Director multi-category structured scene planning.
"""
import json, tempfile
from pathlib import Path
import pytest
from PIL import Image

import qa
import render
import scriptwriter
import source_yt


def test_sanitize_script_removes_slop():
    slop = "This 500 rupee Amazon find is literally a game changer for your desk. Grab it before it's gone!"
    cleaned = scriptwriter.sanitize_script(slop)
    assert "game changer" not in cleaned.lower()
    assert "literally" not in cleaned.lower()
    assert "before it's gone" not in cleaned.lower()
    assert "500 rupee" in cleaned


def test_source_yt_candidate_scoring():
    # Exact review
    good_item = {
        "title": "Portronics MODESK Universal Mobile Holder Stand Review & Price",
        "duration": 180,
        "view_count": 5000
    }
    score, reason = source_yt.score_candidate(good_item, "Portronics", "MODESK", ["Portronics", "MODESK", "Mobile", "Stand"])
    assert score >= 50.0

    # Negative comparison
    comp_item = {
        "title": "Top 10 Best Phone Stands 2026 vs Portronics MODESK",
        "duration": 600,
        "view_count": 50000
    }
    score_comp, reason_comp = source_yt.score_candidate(comp_item, "Portronics", "MODESK", ["Portronics", "MODESK"])
    assert score_comp < 0.0

    # Unrelated video
    unrelated_item = {
        "title": "Minecraft Speedrun vs Pro Gamer",
        "duration": 300,
        "view_count": 1000000
    }
    score_unrelated, _ = source_yt.score_candidate(unrelated_item, "Portronics", "MODESK", ["Portronics"])
    assert score_unrelated < 0.0


def test_top_product_overlay_compact_and_clean():
    with tempfile.TemporaryDirectory() as tmp:
        out_png = Path(tmp) / "top_badge.png"
        render.create_top_product_overlay(
            title="STRIFF Adjustable Laptop Stand",
            price="₹499",
            rating=4.3,
            out_png=out_png
        )
        assert out_png.exists()
        with Image.open(out_png) as img:
            w, h = img.size
            assert w == 1080
            assert h <= 140  # Compact header, down from 340px


def test_subtitles_ass_generation():
    with tempfile.TemporaryDirectory() as tmp:
        out_ass = Path(tmp) / "subs.ass"
        mock_timings = {
            "duration": 12.0,
            "words": [
                {"word": "If", "start": 0.0, "end": 0.25},
                {"word": "your", "start": 0.25, "end": 0.50},
                {"word": "laptop", "start": 0.50, "end": 0.85},
                {"word": "heats", "start": 0.85, "end": 1.20},
                {"word": "up,", "start": 1.20, "end": 1.55},
                {"word": "this", "start": 1.55, "end": 1.80},
                {"word": "stand", "start": 1.80, "end": 2.10},
                {"word": "improves", "start": 2.10, "end": 2.45},
                {"word": "airflow.", "start": 2.45, "end": 2.90}
            ]
        }
        render.generate_subtitles_ass(mock_timings, out_ass)
        assert out_ass.exists()
        content = out_ass.read_text(encoding="utf-8")
        assert "[Events]" in content
        assert "Style: Default" in content
        assert "MarginV, 540" in content or "540,1" in content
        assert "\\c&H0000E5FF&" in content  # Active golden highlight
        assert content.count("Dialogue:") == 9


def test_creative_director_multi_category_generation():
    # 1. Desk Setup
    desk_prod = {
        "title": "STRIFF Adjustable Laptop Tabletop Stand",
        "price": "₹499",
        "rating": 4.3,
        "bullets": ["Multi-angle adjustment 15 to 45 degrees", "Hollow ventilated cooling", "Silicone pads"],
        "affiliate_url": "https://amazon.in/dp/B07XCM6T4N?tag=asirselvin336-21"
    }
    cat_desk = scriptwriter.detect_category(desk_prod)
    assert cat_desk == "Desk Setup"
    plan_desk = scriptwriter.generate_fallback_plan(desk_prod, cat_desk)
    assert len(plan_desk["hook_candidates"]) == 3
    assert any(h["angle"] == "everyday_friction" for h in plan_desk["hook_candidates"])
    assert any(h["angle"] == "curiosity" for h in plan_desk["hook_candidates"])
    assert any(h["angle"] == "buyer_guide" for h in plan_desk["hook_candidates"])
    assert len(plan_desk["scenes"]) == 5
    assert "15.6 inch" in plan_desk["buying_consideration"] or "overhang" in plan_desk["buying_consideration"]

    # 2. Audio
    audio_prod = {
        "title": "boAt Bassheads 100 in-Ear Wired Earphones with Mic",
        "price": "₹399",
        "rating": 4.1,
        "bullets": ["10mm dynamic drivers", "In-line high definition microphone", "Tangle-free cable"],
        "affiliate_url": "https://amazon.in/dp/B071Z8M4KX?tag=asirselvin336-21"
    }
    cat_audio = scriptwriter.detect_category(audio_prod)
    assert cat_audio == "Audio"
    plan_audio = scriptwriter.generate_fallback_plan(audio_prod, cat_audio)
    assert len(plan_audio["hook_candidates"]) == 3
    assert "3.5mm" in plan_audio["buying_consideration"]
    assert len(plan_audio["scenes"]) == 5

    # 3. Wearables
    wear_prod = {
        "title": "Noise ColorFit Pulse Grand Smart Watch with 1.69 inch HD Display",
        "price": "₹1,299",
        "rating": 4.0,
        "bullets": ["1.69 inch HD display", "60 sports modes and health monitoring", "Fast charge"],
        "affiliate_url": "https://amazon.in/dp/B09NVPSCQT?tag=asirselvin336-21"
    }
    cat_wear = scriptwriter.detect_category(wear_prod)
    assert cat_wear == "Wearables"
    plan_wear = scriptwriter.generate_fallback_plan(wear_prod, cat_wear)
    assert len(plan_wear["hook_candidates"]) == 3
    assert "app" in plan_wear["buying_consideration"].lower() or "swimming" in plan_wear["buying_consideration"].lower()
    assert len(plan_wear["scenes"]) == 5


def test_align_scenes_with_timings():
    mock_scenes = [
        {"scene_id": 1, "type": "hook", "narration": "If your laptop fan sounds like a jet engine."},
        {"scene_id": 2, "type": "reveal", "narration": "This is the STRIFF tabletop laptop stand."},
        {"scene_id": 3, "type": "value_demo", "narration": "It lifts your display to eye level and keeps airflow open."},
        {"scene_id": 4, "type": "consideration", "narration": "Keep in mind it fits up to 15.6 inch machines."},
        {"scene_id": 5, "type": "cta", "narration": "Check the full specifications and price through the link in the description."}
    ]
    mock_words = []
    t = 0.0
    for i in range(45):
        mock_words.append({"word": f"w{i}", "start": round(t, 2), "end": round(t + 0.45, 2)})
        t += 0.55
    
    aligned = scriptwriter.align_scenes_with_timings(mock_scenes, {"words": mock_words, "duration": 24.5})
    assert len(aligned) == 5
    assert aligned[0]["start"] == 0.0
    assert aligned[-1]["end"] == 24.5
    for i in range(len(aligned) - 1):
        assert aligned[i]["start"] < aligned[i]["end"]
        assert aligned[i]["end"] <= aligned[i+1]["start"] + 0.5


def test_qa_catches_invalid_project():
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp)
        # Empty project
        res = qa.run_qa(proj)
        assert not res["pass"]
        assert any("Missing or empty" in e for e in res["errors"])


def test_qa_catches_banned_words_and_missing_disclosure():
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp)
        (proj / "out").mkdir()
        (proj / "top_badge.png").write_bytes(b"dummy")
        (proj / "subs.ass").write_text("[Events]\nDialogue: 0,0,1,Default,,0,0,0,,test\n" * 6, encoding="utf-8")
        (proj / "timings.json").write_text("{}", encoding="utf-8")
        (proj / "out/cover.jpg").write_bytes(b"0" * 20000)
        
        # Meta with banned word, missing disclosure, and missing scenes
        meta = {
            "title": "Valid Long Enough Title",
            "affiliate_url": "https://amazon.in/dp/B07XCM6T4N?tag=asirselvin336-21",
            "script": "This laptop stand is literally a game changer for everyone.",
            "description": "Buy it now without disclosure"
        }
        (proj / "project.json").write_text(json.dumps(meta), encoding="utf-8")
        (proj / "out/final.mp4").write_bytes(b"dummy")
        
        res = qa.run_qa(proj)
        assert not res["pass"]
        assert any("banned hype word" in e for e in res["errors"])
        assert any("missing mandatory Amazon Associate / FTC disclosure" in e for e in res["errors"])
        assert any("Creative Director error" in e for e in res["errors"])


if __name__ == "__main__":
    test_sanitize_script_removes_slop()
    test_source_yt_candidate_scoring()
    test_top_product_overlay_compact_and_clean()
    test_subtitles_ass_generation()
    test_creative_director_multi_category_generation()
    test_align_scenes_with_timings()
    test_qa_catches_invalid_project()
    test_qa_catches_banned_words_and_missing_disclosure()
    print("All pipeline and Creative Director unit tests passed successfully!")
