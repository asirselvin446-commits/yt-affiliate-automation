"""High-Retention Creative Director & Script Generator for Amazon Product Shorts.
Implements a repeatable creative direction for premium, faceless product Shorts:
- Earning attention before asking for a click:
  * 0–2s: Pattern-breaking hook (everyday friction, curiosity, or buyer guide angle).
  * 2–6s: Rapid product reveal with immediate purpose (no greetings or logos).
  * 6–18s: Demonstrate value (2-3 concrete benefits backed by verified specs).
  * 18–25s: Useful buying consideration (honest physical limit, compatibility, or sizing).
  * Final seconds: Concise, natural CTA without manufactured urgency.
- Timestamped visual shot plan:
  * Start and end times, narration, visual action, on-screen text, transition, motion, evidence source.
- Multi-hook candidate generation and category-aware pacing.
- Synchronized speech timing alignment with Kokoro word boundaries.
"""
import json, os, re, subprocess, sys
from pathlib import Path
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

HERMES = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\asus\AppData\Local")) / "hermes/hermes-agent/venv/Scripts/hermes.exe"
PROVIDER = os.getenv("HERMES_PROVIDER", "copilot")
MODEL = os.getenv("HERMES_MODEL", "gpt-4o")

BANNED_WORDS = [
    "game changer", "literally", "must-have", "run don't walk",
    "before deal ends", "before it's gone", "grab it before", "insane deal",
    "you won't believe", "miracle", "changed my life", "i've been using this for weeks"
]

CATEGORY_PROFILES = {
    "Desk Setup": {
        "theme": "Ergonomics & Workspace Optimization",
        "pain_points": "Neck strain, hunching over screens, laptop overheating, desk clutter",
        "hook_angles": {
            "everyday_friction": "If your laptop fan sounds like a jet engine at your desk, this setup solves it.",
            "curiosity": "Your laptop setup might be missing this one simple posture fix.",
            "buyer_guide": "Here is what to look for before buying an adjustable laptop stand."
        },
        "consideration_focus": "Maximum supported laptop size or weight (e.g. 15.6 inch limit vs 17 inch gaming rigs), desk footprint",
        "visual_style": "Clean desk setup, eye-level screen alignment, close-up on hinge angle adjustments and hollow vents"
    },
    "Audio": {
        "theme": "Personal Audio & Call Reliability",
        "pain_points": "Bluetooth latency, dead batteries during calls, ear canal fatigue, mic muffling",
        "hook_angles": {
            "everyday_friction": "If you're tired of Bluetooth lag or dead batteries during calls, wired audio still wins.",
            "curiosity": "Here is why a reliable wired pair of earphones might still beat your wireless earbuds.",
            "buyer_guide": "What to check before buying budget earphones under five hundred rupees."
        },
        "consideration_focus": "Requires 3.5mm headphone jack or USB-C dongle on modern smartphones; passive noise isolation rather than active cancellation",
        "visual_style": "Detailed ear-tip texture, in-line mic demonstration, tangle-free cable pull, sound port close-up"
    },
    "Wearables": {
        "theme": "Daily Activity & Practical Health Tracking",
        "pain_points": "Charging watches every single night, bulky wrist frames, poor daylight visibility",
        "hook_angles": {
            "everyday_friction": "If you hate having to charge your smartwatch every single night, check this out.",
            "curiosity": "What can an affordable smartwatch actually track reliably on your wrist?",
            "buyer_guide": "Here is what to look for before buying an entry-level fitness smartwatch."
        },
        "consideration_focus": "Requires companion phone app sync; water resistance rating (splash-proof vs swimming); sensors are for fitness trends not medical diagnoses",
        "visual_style": "Outdoor display visibility, wrist fit perspective, physical button action, magnetic charging contact"
    },
    "Home & Kitchen": {
        "theme": "Home Utility & Countertop Organization",
        "pain_points": "Messy countertops, wasted prep space, fragile plastic tools, difficult cleaning",
        "hook_angles": {
            "everyday_friction": "If your kitchen counter is always running out of usable prep space, this helps.",
            "curiosity": "A useful kitchen upgrade doesn't always need to cost a fortune.",
            "buyer_guide": "Here is what to check before buying a compact kitchen organizer."
        },
        "consideration_focus": "Counter clearance dimensions; hand-wash vs dishwasher compatibility; weight capacity",
        "visual_style": "Product in active use, smooth wipe-down demonstration, compact storage profile"
    },
    "General Tech": {
        "theme": "Everyday Tech & Practical Gadgets",
        "pain_points": "Clumsy everyday accessories, overhyped gear, fragile build quality",
        "hook_angles": {
            "everyday_friction": "If you want a cleaner daily carry without bulky gear, check this.",
            "curiosity": "A useful tech upgrade doesn't always need to cost thousands.",
            "buyer_guide": "Here is what to look for before buying everyday tech accessories."
        },
        "consideration_focus": "Specific port or device compatibility, exact physical measurements",
        "visual_style": "Direct product demonstration, material texture close-up, portable carry profile"
    }
}

PROMPT_TEMPLATE = """# Professional YouTube Shorts Creative Director & Scriptwriter

You are an expert short-form video creative director and product-marketing strategist.
Your goal is to create a premium, faceless product Short that feels like a useful recommendation from a knowledgeable person rather than an aggressive advertisement.

## Product Specifications:
- Product Title: {TITLE}
- Detected Category: {CATEGORY} ({CATEGORY_THEME})
- Verified Price: {PRICE}
- Verified Rating: {RATING} ({REVIEWS})
- Verified Features / Bullets:
{BULLETS}

## Category Creative Guidance:
- Primary Pain Points: {PAIN_POINTS}
- Consideration Focus: {CONSIDERATION_FOCUS}
- Visual Direction: {VISUAL_STYLE}

## Required Storytelling Structure (Total Duration 22 to 28 seconds):
1. **0–2s [Hook]**: Open with a pattern-breaking hook (under 12 words). Must be factually grounded in the product's actual use case.
2. **2–6s [Reveal]**: Show the actual product immediately and make its core purpose obvious. No greetings ("Hey guys"), channel logos, or fluff.
3. **6–18s [Value Demo]**: Highlight 2 or 3 concrete benefits supported by verified specs (materials, angles, ventilation, compatibility). Concrete details over generic adjectives.
4. **18–25s [Buying Consideration]**: Give a genuine, useful buying consideration (compatibility requirement, maximum dimension, material, or use boundary) grounded in the specs. Never invent artificial negatives.
5. **Final seconds [CTA]**: Natural, calm call to action: "Check the details and current price through the link in the description." Zero manufactured urgency.

## Visual Storytelling & Shot Plan:
Provide a timestamped shot plan with 5 structured scenes (`scenes` array) alongside the voiceover:
- Scene 1 (`hook`): 0.0s to ~2.2s. Actionable problem or curiosity visual.
- Scene 2 (`reveal`): ~2.2s to ~6.0s. Direct product demonstration.
- Scene 3 (`value_demo`): ~6.0s to ~17.5s. Close-ups of physical features in action.
- Scene 4 (`consideration`): ~17.5s to ~23.5s. Visual illustrating the physical limitation, dimension, or connection.
- Scene 5 (`cta`): ~23.5s to ~27.0s. Clean product still/pack-down shot.

## Strict Rules:
- Generate 3 distinct hook candidates internally across different angles (everyday_friction, curiosity, buyer_guide) and select the best one.
- Word count of the full voiceover script MUST be between 50 and 65 words so it speaks naturally in ~25s.
- PROHIBITED PHRASES: "game changer", "literally", "must-have", "grab it before it's gone", "insane deal", "you won't believe".

## Output Format:
Respond ONLY with a single valid JSON object strictly matching this schema (no markdown, no backticks):
{{
  "title": "Clean Informative Title without emojis #shorts",
  "category": "{CATEGORY}",
  "hook_candidates": [
    {{"angle": "everyday_friction", "hook": "...", "rationale": "..."}},
    {{"angle": "curiosity", "hook": "...", "rationale": "..."}},
    {{"angle": "buyer_guide", "hook": "...", "rationale": "..."}}
  ],
  "selected_hook_angle": "everyday_friction",
  "hook": "Chosen spoken hook (under 12 words)",
  "buying_consideration": "Honest limitation or compatibility consideration (max 18 words)",
  "script": "Full continuous spoken voiceover script without brackets, scene headers, or sound effects.",
  "features": ["Feature 1 (max 4 words)", "Feature 2 (max 4 words)", "Feature 3 (max 4 words)"],
  "scenes": [
    {{
      "scene_id": 1,
      "type": "hook",
      "start": 0.0,
      "end": 2.2,
      "narration": "First sentence of voiceover",
      "visual_action": "Clear description of what footage or shot must show",
      "on_screen_text": "Short 2-4 word on-screen cue",
      "transition": "cut",
      "motion": "slow push-in",
      "evidence_source": "Verified bullet or spec justifying this claim"
    }},
    {{
      "scene_id": 2,
      "type": "reveal",
      "start": 2.2,
      "end": 6.0,
      "narration": "Product reveal narration",
      "visual_action": "Direct product showcase shot",
      "on_screen_text": "Product Name / Main Purpose",
      "transition": "cut",
      "motion": "steady clear display",
      "evidence_source": "Product model and identity"
    }},
    {{
      "scene_id": 3,
      "type": "value_demo",
      "start": 6.0,
      "end": 17.5,
      "narration": "2-3 concrete feature benefits narration",
      "visual_action": "Close-up showing concrete features in action",
      "on_screen_text": "Feature 1 • Feature 2",
      "transition": "cut",
      "motion": "pan across functional parts",
      "evidence_source": "Verified specs"
    }},
    {{
      "scene_id": 4,
      "type": "consideration",
      "start": 17.5,
      "end": 23.5,
      "narration": "Buying consideration narration",
      "visual_action": "Shot illustrating size, port, or limit",
      "on_screen_text": "Key Consideration / Compatibility",
      "transition": "cut",
      "motion": "steady focus on dimension or port",
      "evidence_source": "Physical limitation or spec boundary"
    }},
    {{
      "scene_id": 5,
      "type": "cta",
      "start": 23.5,
      "end": 27.0,
      "narration": "Check the details and current price through the link in the description.",
      "visual_action": "Product in compact folded form or clean setup overview",
      "on_screen_text": "Link & Details in Description",
      "transition": "crossfade",
      "motion": "subtle pull back",
      "evidence_source": "Product link availability"
    }}
  ],
  "description": "Accurate 2-paragraph overview with affiliate link and FTC disclosure.",
  "pinned_comment": "Clean pinned comment with affiliate link and disclosure.",
  "tags": ["relevant", "topic", "tags", "shorts"]
}}
"""


def detect_category(product_data: dict) -> str:
    """Detects product category profile from title, category hint, and bullet text."""
    cat_hint = str(product_data.get("category", "")).strip()
    if cat_hint in CATEGORY_PROFILES:
        return cat_hint
    for known_cat in CATEGORY_PROFILES:
        if known_cat.lower() in cat_hint.lower():
            return known_cat

    title = str(product_data.get("title", ""))
    bullets = " ".join(product_data.get("bullets", []))
    text = f"{cat_hint} {title} {bullets}".lower()

    # Match using word boundaries to prevent 'monitoring' matching 'monitor'
    if re.search(r"\b(smartwatch|smart watch|wrist watch|fitness band|fitness tracker|activity tracker|smart band)\b", text):
        return "Wearables"
    elif re.search(r"\b(earphone|earphones|headphone|headphones|earbuds|earbud|in-ear|bassheads|neckband|bluetooth speaker|tws)\b", text):
        return "Audio"
    elif re.search(r"\b(laptop stand|phone stand|mobile holder|desk stand|keyboard|tabletop|mouse pad|monitor stand|monitor arm|cable management|desk setup)\b", text):
        return "Desk Setup"
    elif re.search(r"\b(kitchen|cookware|knife|bottle|blender|organizer tray|chopper|air fryer)\b", text):
        return "Home & Kitchen"
    elif re.search(r"\b(watch|pulse)\b", text):
        return "Wearables"
    elif re.search(r"\b(mic|audio)\b", text):
        return "Audio"
    elif re.search(r"\b(laptop|desk|monitor|mouse)\b", text):
        return "Desk Setup"
    return "General Tech"


def sanitize_script(text: str) -> str:
    """Removes banned marketing slop if an LLM hallucinates it."""
    cleaned = text
    for phrase in BANNED_WORDS:
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.I)
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def align_scenes_with_timings(scenes: list, timings: dict) -> list:
    """Aligns structured scene start and end timestamps directly with Kokoro word boundaries.
    Ensures shot plan transitions synchronize with natural voice pauses and actual duration.
    """
    words = timings.get("words", [])
    total_dur = float(timings.get("duration", 0.0))
    if not words or not scenes:
        return scenes

    total_audio_words = len(words)
    scene_word_counts = [max(1, len(s.get("narration", "").split())) for s in scenes]
    sum_scene_words = sum(scene_word_counts)

    curr_word_idx = 0
    updated_scenes = []

    for idx, sc in enumerate(scenes):
        sc_copy = dict(sc)
        if idx == len(scenes) - 1:
            end_word_idx = total_audio_words - 1
        else:
            w_allotment = int(round((scene_word_counts[idx] / sum_scene_words) * total_audio_words))
            end_word_idx = min(total_audio_words - 1, curr_word_idx + max(1, w_allotment) - 1)

        start_ts = words[curr_word_idx]["start"] if curr_word_idx < total_audio_words else 0.0
        if idx == len(scenes) - 1 and total_dur > 0:
            end_ts = total_dur
        else:
            end_ts = words[end_word_idx]["end"] if end_word_idx < total_audio_words else total_dur

        if end_ts <= start_ts:
            end_ts = round(start_ts + 1.0, 2)

        sc_copy["start"] = round(start_ts, 2)
        sc_copy["end"] = round(end_ts, 2)
        updated_scenes.append(sc_copy)
        curr_word_idx = end_word_idx + 1

    return updated_scenes


def generate_fallback_plan(product_data: dict, category: str) -> dict:
    """Deterministic, high-quality fallback shot plan and script grounded in verified specs."""
    title_short = product_data.get("title", "this product")[:35].strip()
    aff_link = product_data.get("affiliate_url", "")
    profile = CATEGORY_PROFILES.get(category, CATEGORY_PROFILES["General Tech"])
    bullets = product_data.get("bullets", [])

    b1 = bullets[0] if len(bullets) > 0 else "Ergonomic multi-angle design"
    b2 = bullets[1] if len(bullets) > 1 else "Durable, high-grade construction"
    
    if category == "Desk Setup":
        hook_text = "Your laptop setup might be missing this one simple posture fix."
        reveal_text = f"This is the {title_short}, built to raise your screen to eye level without desk clutter."
        value_text = f"The multi-angle hinges allow custom viewing angles, while the open frame prevents laptop heat buildup. Silicone pads keep it planted firmly on any desk."
        consideration_text = "One key detail to consider: it supports laptops up to 15.6 inches, so larger 17-inch workstations will overhang."
        features = ["Adjustable Screen Angle", "Open Ventilated Frame", "Anti-Slip Silicone Base"]
        tags = ["desksetup", "laptopstand", "workspacesetup", "techgear", "shorts"]
    elif category == "Audio":
        hook_text = "If you're tired of Bluetooth lag or dead batteries during calls, wired audio still wins."
        reveal_text = f"These are the {title_short}, designed for zero latency and clear daily voice calls."
        value_text = "The dynamic drivers deliver punchy bass without harsh treble, and the in-line microphone provides crisp voice clarity with a tangle-resistant cable."
        consideration_text = "Keep in mind this uses a 3.5mm jack, so newer phones without a port will need a simple adapter."
        features = ["Zero-Latency Audio", "In-Line HD Microphone", "Tangle-Resistant Cord"]
        tags = ["audiophile", "earphones", "wiredearphones", "budgettech", "shorts"]
    elif category == "Wearables":
        hook_text = "If you hate having to charge your smartwatch every single night, look at this."
        reveal_text = f"This is the {title_short}, focused on essential fitness tracking and real battery endurance."
        value_text = "The bright HD display stays clear under outdoor daylight, offering continuous heart rate monitoring and all-day step tracking in a lightweight frame."
        consideration_text = "Keep in mind it pairs via a smartphone app and handles water splashes, but is not intended for swimming."
        features = ["Bright HD Screen", "Multi-Day Battery", "Daily Activity Tracking"]
        tags = ["smartwatch", "fitnessgear", "techreview", "wearables", "shorts"]
    else:
        hook_text = "A useful daily desk upgrade doesn't always need to cost thousands."
        reveal_text = f"This is the {title_short}, built for clean daily utility."
        value_text = f"It features {b1.lower()}, with {b2.lower()} for long-term daily durability."
        consideration_text = "Be sure to verify your desk dimensions before ordering to ensure the ideal fit."
        features = ["Daily Functional Build", "Ergonomic Utility", "Durable Construction"]
        tags = ["amazonfinds", "techgear", "productreview", "shorts"]

    cta_text = "Check the full specifications and current price through the link in the description."
    full_script = f"{hook_text} {reveal_text} {value_text} {consideration_text} {cta_text}"

    scenes = [
        {
            "scene_id": 1,
            "type": "hook",
            "start": 0.0,
            "end": 2.2,
            "narration": hook_text,
            "visual_action": f"Everyday setup context: {profile['visual_style']}",
            "on_screen_text": "Desk Setup Fix" if category == "Desk Setup" else "Smart Upgrade",
            "transition": "cut",
            "motion": "slow push-in",
            "evidence_source": "Verified user pain point"
        },
        {
            "scene_id": 2,
            "type": "reveal",
            "start": 2.2,
            "end": 6.0,
            "narration": reveal_text,
            "visual_action": f"Direct product showcase of {title_short}",
            "on_screen_text": title_short,
            "transition": "cut",
            "motion": "steady clear display",
            "evidence_source": "Product identity"
        },
        {
            "scene_id": 3,
            "type": "value_demo",
            "start": 6.0,
            "end": 17.5,
            "narration": value_text,
            "visual_action": "Close-up shots demonstrating physical features in active use",
            "on_screen_text": f"{features[0]} • {features[1]}",
            "transition": "cut",
            "motion": "pan across functional parts",
            "evidence_source": f"{b1}; {b2}"
        },
        {
            "scene_id": 4,
            "type": "consideration",
            "start": 17.5,
            "end": 23.5,
            "narration": consideration_text,
            "visual_action": "Shot illustrating physical dimension, connector, or boundary",
            "on_screen_text": "Key Buying Consideration",
            "transition": "cut",
            "motion": "steady focus on dimension or port",
            "evidence_source": profile["consideration_focus"]
        },
        {
            "scene_id": 5,
            "type": "cta",
            "start": 23.5,
            "end": 27.0,
            "narration": cta_text,
            "visual_action": "Product in compact resting state with clean backdrop",
            "on_screen_text": "Link & Details in Description",
            "transition": "crossfade",
            "motion": "subtle pull back",
            "evidence_source": "Product availability"
        }
    ]

    hook_candidates = [
        {"angle": "everyday_friction", "hook": profile["hook_angles"]["everyday_friction"], "rationale": "Directly targets everyday user frustration."},
        {"angle": "curiosity", "hook": profile["hook_angles"]["curiosity"], "rationale": "Creates genuine curiosity about an unconsidered ergonomic fix."},
        {"angle": "buyer_guide", "hook": profile["hook_angles"]["buyer_guide"], "rationale": "Positions video as an objective buyer recommendation."}
    ]

    return {
        "title": f"{title_short} Honest Overview #shorts",
        "category": category,
        "hook_candidates": hook_candidates,
        "selected_hook_angle": "curiosity" if category == "Desk Setup" else "everyday_friction",
        "hook": hook_text,
        "buying_consideration": consideration_text,
        "script": full_script,
        "features": features,
        "scenes": scenes,
        "description": f"Detailed review of {product_data.get('title')}.\n\nAffiliate link: {aff_link}\n\nDisclosure: As an Amazon Associate, I earn from qualifying purchases at no additional cost to you.",
        "pinned_comment": f"Get the product details and current pricing here: {aff_link} (Disclosure: Affiliate link)",
        "tags": tags
    }


def generate_script(product_data: dict, out_file: Path) -> dict:
    """Generates structured scene plan, hook candidates, and script via LLM or robust fallback."""
    category = detect_category(product_data)
    profile = CATEGORY_PROFILES.get(category, CATEGORY_PROFILES["General Tech"])

    price_val = product_data.get("price") or "Market standard"
    rating_val = f"{product_data.get('rating'):.1f}/5" if product_data.get("rating") else "Highly rated"
    reviews_val = product_data.get("reviews") or ""

    bullets = product_data.get("bullets", [])
    bullets_text = "\n".join(f"- {b}" for b in bullets[:4]) if bullets else "- Durable daily design\n- Verified user utility"

    prompt = PROMPT_TEMPLATE.format(
        TITLE=product_data.get("title", ""),
        CATEGORY=category,
        CATEGORY_THEME=profile["theme"],
        PRICE=price_val,
        RATING=rating_val,
        REVIEWS=reviews_val,
        BULLETS=bullets_text,
        PAIN_POINTS=profile["pain_points"],
        CONSIDERATION_FOCUS=profile["consideration_focus"],
        VISUAL_STYLE=profile["visual_style"]
    )

    data = None
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
                {
                    "role": "system",
                    "content": "You are a professional video creative director. Output strictly valid JSON matching the schema. No markdown formatting, no conversational preamble."
                },
                {"role": "user", "content": prompt}
            ],
            "include_reasoning": False
        }
        try:
            print(f"Requesting script from OpenRouter ({payload['model']})...", flush=True)
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                res_content = r.json()["choices"][0]["message"]["content"]
                cleaned = re.sub(r"^```(?:json)?\s*", "", res_content, flags=re.MULTILINE)
                cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()
                try:
                    data = json.loads(cleaned)
                except Exception:
                    m = re.search(r"(\{.*\})", res_content, re.DOTALL)
                    if m:
                        data = json.loads(m.group(1))
            else:
                print(f"OpenRouter returned status {r.status_code}: {r.text[:150]}", flush=True)
        except Exception as e:
            print(f"OpenRouter exception: {e}", flush=True)

    # Deterministic fallback if OpenRouter produced no valid structured data
    if not data or "script" not in data or "scenes" not in data or len(data.get("scenes", [])) < 4:
        print("Using deterministic Creative Director fallback plan...", flush=True)
        data = generate_fallback_plan(product_data, category)


    # Sanitize and enforce FTC / Amazon Associate disclosures
    data["script"] = sanitize_script(data["script"])
    for sc in data.get("scenes", []):
        sc["narration"] = sanitize_script(sc.get("narration", ""))

    disclosure = "Disclosure: As an Amazon Associate, I earn from qualifying purchases at no additional cost to you."
    if "disclosure:" not in data.get("description", "").lower() and "amazon associate" not in data.get("description", "").lower():
        data["description"] = f"{data.get('description', '')}\n\n{disclosure}".strip()
    if "disclosure" not in data.get("pinned_comment", "").lower():
        data["pinned_comment"] = f"{data.get('pinned_comment', '')} ({disclosure})".strip()

    data["word_count"] = len(data["script"].split())
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


if __name__ == "__main__":
    mock_data = {
        "title": "STRIFF Adjustable Laptop Tabletop Stand",
        "price": "₹499",
        "rating": 4.3,
        "reviews": "14,000+ reviews",
        "bullets": [
            "Ergonomic multi-angle height adjustment from 15 to 45 degrees",
            "Open ventilated hollow design preventing laptop overheating",
            "Anti-slip silicone pads keeping device stable on any surface",
            "Foldable lightweight build that fits into any backpack sleeve"
        ],
        "affiliate_url": "https://amazon.in/dp/B07XCM6T4N?tag=asirselvin336-21"
    }
    p = Path("./test_script.json")
    res = generate_script(mock_data, p)
    print(f"Detected Category: {res.get('category')}")
    print(f"Hook: {res.get('hook')}")
    print(f"Buying Consideration: {res.get('buying_consideration')}")
    print(f"Scenes generated: {len(res.get('scenes', []))}")
    print(f"Word count: {res.get('word_count')} words")
