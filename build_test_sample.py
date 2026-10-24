import json, os, shutil
from pathlib import Path
import daily
import qa
import render
import scriptwriter
import voice

PROJ_DIR = Path("projects/20261025-B07XCM6T4N")
assert PROJ_DIR.exists(), f"{PROJ_DIR} does not exist"

# 1. Load generated test script data from Creative Director
script_data = json.loads(Path("test_script.json").read_text(encoding="utf-8"))
old_meta = json.loads((PROJ_DIR / "project.json").read_text(encoding="utf-8"))

# 2. Update project metadata
updated_meta = {
    **old_meta,
    **script_data
}

# 3. Synthesize natural voiceover via Kokoro-82M
print(f"Synthesizing voiceover for script ({len(script_data['script'].split())} words)...")
voice_res = voice.build_voiceover(script_data["script"], PROJ_DIR)
print(f"Voice synthesized: duration = {voice_res['duration']:.2f}s, words = {len(voice_res['words'])}")

# 4. Align structured scene timestamps with physical speech word boundaries
updated_scenes = scriptwriter.align_scenes_with_timings(script_data["scenes"], voice_res)
updated_meta["scenes"] = updated_scenes
(PROJ_DIR / "project.json").write_text(json.dumps(updated_meta, indent=2, ensure_ascii=False), encoding="utf-8")

print("\n--- Structured Scene Plan (Voice Aligned) ---")
for s in updated_scenes:
    print(f"Scene {s['scene_id']} [{s['type']} | {s['start']}s -> {s['end']}s]:")
    print(f"  Narration: {s['narration']}")
    print(f"  Visual Action: {s['visual_action']}")
    print(f"  On-Screen Text: {s['on_screen_text']}")
    print(f"  Transition / Motion: {s.get('transition')} / {s.get('motion')}")
    print(f"  Evidence: {s['evidence_source']}")

# 5. Render video
print("\nRendering video with intelligent framing & subtitles...")
final_video = render.render_video(PROJ_DIR)
print(f"Video rendered successfully: {final_video}")

# 6. Run QA Validation
print("\nRunning comprehensive QA validation...")
qa_res = qa.run_qa(PROJ_DIR)
print("QA Status:", "PASS" if qa_res["pass"] else "FAIL")
if qa_res["errors"]:
    print("Errors:", qa_res["errors"])
if qa_res["warnings"]:
    print("Warnings:", qa_res["warnings"])
assert qa_res["pass"], f"QA failed: {qa_res['errors']}"
