"""Unit and regression tests for Affiliate Shorts pipeline.
Validates QA gate, subtitle generation, video aspect ratio handling,
candidate relevance scoring, script sanitization, and overlay styling.
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
            assert h <= 140  # Compact header, down from 340px!


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
        
        # Meta with banned word and missing FTC disclosure
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


if __name__ == "__main__":
    test_sanitize_script_removes_slop()
    test_source_yt_candidate_scoring()
    test_top_product_overlay_compact_and_clean()
    test_subtitles_ass_generation()
    test_qa_catches_invalid_project()
    test_qa_catches_banned_words_and_missing_disclosure()
    print("All pipeline unit tests passed successfully!")
