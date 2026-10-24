"""Viral script generator for Amazon affiliate YouTube Shorts.
Invokes Hermes agent using GitHub Copilot (gpt-4o) with zero Claude credits.
"""
import json, os, re, subprocess, sys
from pathlib import Path
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

HERMES = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\asus\AppData\Local")) / "hermes/hermes-agent/venv/Scripts/hermes.exe"
PROVIDER = os.getenv("HERMES_PROVIDER", "copilot")
MODEL = os.getenv("HERMES_MODEL", "gpt-4o")

PROMPT_TEMPLATE = """# YouTube Shorts Viral Amazon Product Scriptwriter

You are an expert viral copywriter specializing in YouTube Shorts for Amazon finds, life savers, and viral tech gear.
Write an engaging, high-retention 25 to 35 second spoken script for the following Amazon product.

## Product Details:
- Title: {TITLE}
- Price: {PRICE}
- Rating: {RATING} ({REVIEWS})
- Key Highlights:
{BULLETS}

## Video Structure Rules:
1. Hook (0-3s): Stop the scroll immediately. Bold, curious claim or relatable frustration (e.g., "If you sit at a desk all day, this 800 rupee Amazon find is literally a game changer...").
2. Core Features (3-20s): Walk through the 3 best things it does. Keep it punchy, concrete, visual.
3. Social Proof (20-25s): Mention the rating / review count.
4. Call To Action (25-30s): Tell the viewer: "The link is pinned in the comments and description so you can grab it before the deal ends."

## Output Requirements:
You must output a single valid JSON object strictly matching this format, with NO Markdown code blocks and NO other text:
{{
  "title": "Viral YouTube Shorts Title with 1 Emoji and #shorts",
  "hook": "Spoken opening hook sentence",
  "script": "Full spoken voiceover text without any stage directions or brackets, written to be read aloud smoothly.",
  "features": [
    "Short 3-word on-screen feature badge 1",
    "Short 3-word on-screen feature badge 2",
    "Short 3-word on-screen feature badge 3"
  ],
  "description": "Engaging 2-paragraph description explaining the product, followed by the affiliate link and legal disclosure.",
  "pinned_comment": "Direct pinned comment with link placeholder and disclosure.",
  "tags": ["amazonfinds", "techgadgets", "shorts", "musthaves"]
}}
"""


def generate_script(product_data: dict, out_file: Path) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        TITLE=product_data.get("title", ""),
        PRICE=product_data.get("price", ""),
        RATING=product_data.get("rating", 4.3),
        REVIEWS=product_data.get("reviews", ""),
        BULLETS="\n".join(f"- {b}" for b in product_data.get("bullets", [])[:4])
    )
    
    # Check if OPENROUTER_API_KEY is available for direct zero-credit cloud generation
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        import requests
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free"),
            "messages": [
                {"role": "system", "content": "You are a viral YouTube Shorts copywriter. You must output strictly valid JSON conforming to the requested schema. No conversational filler."},
                {"role": "user", "content": prompt}
            ]
        }
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        if r.status_code == 200:
            res_content = r.json()["choices"][0]["message"]["content"]
            try:
                cleaned = re.sub(r"^```(?:json)?\s*", "", res_content, flags=re.MULTILINE)
                cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
                data = json.loads(cleaned)
                out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                return data
            except Exception:
                m = re.search(r"(\{.*\})", res_content, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                        return data
                    except Exception:
                        pass

    query_file = out_file.parent / "script_prompt.md"
    query_file.write_text(prompt, encoding="utf-8")

    cmd = [
        str(HERMES), "chat",
        "--provider", PROVIDER,
        "-m", MODEL,
        "--query-file", str(query_file),
        "-Q", "--yolo"
    ]

    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    stdout = r.stdout.strip()
    
    # Extract JSON from output
    try:
        cleaned = re.sub(r"^```(?:json)?\s*", "", stdout, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
        data = json.loads(cleaned)
    except Exception:
        m = re.search(r"(\{.*\})", stdout, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
        else:
            raise RuntimeError(f"Failed to parse script JSON from output:\n{stdout[:400]}")

    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


if __name__ == "__main__":
    import re
    mock_data = {
        "title": "Portronics Clamp M2 Adjustable Car Phone Mount",
        "price": "₹399",
        "rating": 4.2,
        "reviews": "8,400+ reviews",
        "bullets": [
            "360 degree rotation for portrait and landscape viewing",
            "One-touch quick release button to grab your phone in seconds",
            "Strong suction gel pad that never falls off bumpy roads"
        ]
    }
    p = Path("./test_script.json")
    res = generate_script(mock_data, p)
    print(f"Generated script: {res['title']}")
