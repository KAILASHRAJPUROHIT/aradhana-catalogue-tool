"""
Aradhana Jewellers — Model Library Generator (v2)
Philosophy:
  - Female model = same woman as reference photos, but in EDITORIAL/LUXURY styling
    (not store uniform — beautiful silk sarees, lehengas, great makeup, polished skin)
  - 3 variants per pose = SAME pose, 3 DIFFERENT STUDIO BACKGROUNDS
  - Result: 3 interchangeable versions of each pose for creative variety

Run: python generate_model_library.py
"""
import sys, os, json, time, base64, io
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE       = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
MODELS_DIR = os.path.join(BASE, "models")
FEMALE_DIR = os.path.join(MODELS_DIR, "female")
MALE_DIR   = os.path.join(MODELS_DIR, "male")
KIDS_DIR   = os.path.join(MODELS_DIR, "kids")

for d in (FEMALE_DIR, MALE_DIR, KIDS_DIR):
    os.makedirs(d, exist_ok=True)

# ── 3 STUDIO BACKGROUNDS (same pose, different BG each variant) ───────────────

BG = {
    "A": "Soft ivory/cream studio backdrop, diffused side lighting, airy and bright",
    "B": "Warm champagne gold tones, subtle warm bokeh, luxury editorial ambiance",
    "C": "Deep charcoal grey studio, dramatic low-key lighting, jewellery glows against dark",
}

# ── FEMALE MODEL STYLING ──────────────────────────────────────────────────────

FEMALE_BASE = (
    "IMPORTANT: Use the woman in the reference photo (image 1) as the model. "
    "Maintain her exact face, skin tone, and features. "
    "However, DO NOT use her store uniform. Instead, style her in: "
    "a luxurious deep jewel-tone silk saree (burgundy, emerald, or navy) OR "
    "an elegant lehenga for bridal/festive shots. "
    "Full editorial makeup — defined eyes, perfect skin, glossy or matte lips, "
    "contoured and glowing complexion. Hair styled beautifully — swept up, "
    "loose waves, or elegant bun depending on the shot. "
    "She must look like a high-end jewellery catalogue model — polished, "
    "sophisticated, aspirational. This is a luxury brand shoot."
)

# ── MALE MODEL ────────────────────────────────────────────────────────────────

MALE_BASE = (
    "IMPORTANT: Use the man in the reference photo (image 1) as the model. "
    "Maintain his exact face, skin tone, and features. "
    "Style him in premium outfits — bandhgala suit, crisp linen shirt, or rich silk kurta "
    "depending on the shot context. "
    "Well-groomed, confident, aspirational — high-end jewellery catalogue model."
)

# ── KIDS MODEL ────────────────────────────────────────────────────────────────

KIDS_GIRL_BASE = (
    "An adorable Indian girl, 6-8 years old, fair complexion, beautiful features, "
    "bright natural smile, dressed in a gorgeous festive lehenga or silk frock "
    "in rich colours — gold, pink, or red. "
    "Hair neatly styled with accessories, light festive look, genuinely joyful and charming."
)

KIDS_BOY_BASE = (
    "An adorable Indian boy, 6-8 years old, fair complexion, handsome features, "
    "bright natural smile, dressed in a smart kurta or sherwani in deep blue, "
    "maroon, or ivory. Well groomed, cheerful and naturally confident."
)

# ── STUDIO QUALITY ────────────────────────────────────────────────────────────

QUALITY = (
    "Professional luxury editorial photography. "
    "High-end retouching — flawless but natural skin, no over-smoothing. "
    "The model looks real, three-dimensional, polished. "
    "NO jewellery visible on model — this is a blank reference pose. "
    "Square 1:1 format, ready for jewellery compositing."
)

# ── POSE LIBRARY (zone × 3 BG variants) ──────────────────────────────────────
# Format: (output_file, model_type, pose_description, camera_spec)
# 3 entries per pose zone — same pose, backgrounds A/B/C

def make_entries(prefix, model_type, pose, camera):
    return [
        (f"{prefix}_bgA.jpg", model_type, pose, camera, "A"),
        (f"{prefix}_bgB.jpg", model_type, pose, camera, "B"),
        (f"{prefix}_bgC.jpg", model_type, pose, camera, "C"),
    ]

LIBRARY = (

    # ── FEMALE EAR / FACE ─────────────────────────────────────────────────────
    *make_entries(
        "female/ear_front", "female",
        "Front-facing portrait from shoulders up, both ears clearly visible, "
        "hair elegantly swept back or tucked behind ears, warm confident expression, "
        "chin slightly lifted, neck long and graceful",
        "85mm f/1.8, shallow DOF, face and ears sharp"
    ),
    *make_entries(
        "female/ear_45", "female",
        "45-degree portrait, model turned slightly right, right ear fully visible, "
        "elegant profile, chin slightly raised, graceful neck curve",
        "85mm f/2.0, 45-degree, near ear in sharp focus"
    ),
    *make_entries(
        "female/ear_profile", "female",
        "Clean side profile, model facing right, left ear fully revealed, "
        "hair swept completely back exposing full ear and neck, "
        "profile is sharp and elegant, chin level",
        "100mm, pure side profile, ear as absolute focal point"
    ),

    # ── FEMALE NECK / CHEST ───────────────────────────────────────────────────
    *make_entries(
        "female/neck_front", "female",
        "Chest-up front portrait, neck and upper chest fully visible, "
        "saree neckline elegant and low enough to show collarbone, "
        "confident warm expression, shoulders back, posture perfect",
        "70-85mm, chest-up framing, neck and collarbone as focal zone"
    ),
    *make_entries(
        "female/neck_45", "female",
        "45-degree chest-up portrait, neck at graceful angle, "
        "saree draping naturally over shoulder, collarbone visible, "
        "eyes looking slightly off-camera, contemplative elegance",
        "70mm, 45-degree, chest and neck visible"
    ),
    *make_entries(
        "female/neck_crop", "female",
        "Intimate neck crop — chin to mid-chest only, no face visible, "
        "neck and collarbone as the canvas, saree neckline framing the zone, "
        "beautiful skin texture visible",
        "100mm tight crop, neck and upper chest only"
    ),

    # ── FEMALE HAND / FINGERS ─────────────────────────────────────────────────
    *make_entries(
        "female/hand_single", "female",
        "Single right hand, fingers elegantly spread, slight downward tilt, "
        "showing dorsal side of hand, manicured natural nails in nude/pink, "
        "saree sleeve creating a soft frame at wrist, hand looks refined and feminine",
        "100mm macro, hand in sharp detail"
    ),
    *make_entries(
        "female/hand_both", "female",
        "Both hands together, fingers gently overlapping or lightly clasped, "
        "soft feminine gesture, both wrists visible, natural graceful pose",
        "85mm, both hands centred in frame"
    ),
    *make_entries(
        "female/hand_closeup", "female",
        "Extreme close-up of fingers only — 3 or 4 fingers slightly fanned, "
        "showing the finger joints clearly, ultra-detail on skin and nails, "
        "soft bokeh background, intimate and precise",
        "100mm macro extreme close-up, fingers only, ultra-sharp"
    ),

    # ── FEMALE WRIST ──────────────────────────────────────────────────────────
    *make_entries(
        "female/wrist_raised", "female",
        "Single wrist raised elegantly at chest height, "
        "inner wrist facing camera, forearm at 45-degree angle, "
        "saree sleeve falling naturally, wrist looks delicate and graceful",
        "100mm, wrist and forearm, inner wrist as focal point"
    ),
    *make_entries(
        "female/wrist_both", "female",
        "Both wrists held together at waist level, palms facing slightly inward, "
        "symmetrical elegant pose, both inner wrists visible side by side",
        "85mm, both wrists centred, symmetrical"
    ),
    *make_entries(
        "female/wrist_profile", "female",
        "Side profile of single wrist, arm extended naturally toward camera, "
        "side view of wrist and lower forearm, "
        "outer wrist bone visible, elegant gesture",
        "100mm, wrist side profile, forearm"
    ),

    # ── FEMALE FEET ───────────────────────────────────────────────────────────
    *make_entries(
        "female/feet_standing", "female",
        "Both feet standing on polished marble or cream stone floor, "
        "toes pointing slightly outward, ankles visible, "
        "saree hem just touching floor at top edge of frame, "
        "elegant foot positioning, clean manicured nails",
        "50-70mm, feet and ankles, looking down from above"
    ),
    *make_entries(
        "female/feet_seated", "female",
        "Seated feet, both feet resting flat on surface or floor, "
        "ankles and lower shin visible, casual yet graceful, "
        "saree or lehenga hem visible at top",
        "70mm, seated feet detail, ankles"
    ),

    # ── FEMALE WAIST ──────────────────────────────────────────────────────────
    *make_entries(
        "female/waist_front", "female",
        "Mid-body crop from bust to upper thigh, "
        "waistline clearly visible, saree pleats falling perfectly, "
        "blouse and saree draping elegant, hands resting naturally at sides",
        "50-70mm, mid-body, waist as hero zone"
    ),

    # ── MALE NECK ────────────────────────────────────────────────────────────
    *make_entries(
        "male/neck_front", "male",
        "Chest-up front portrait, masculine neck and upper chest, "
        "collar of kurta or shirt open slightly at neck, "
        "confident expression, jaw strong, shoulders broad",
        "70-85mm, chest-up, masculine neck prominent"
    ),
    *make_entries(
        "male/neck_45", "male",
        "45-degree chest portrait, neck at powerful angle, "
        "collar styling visible, collar open, strong profile",
        "70mm, 45-degree masculine portrait"
    ),

    # ── MALE HAND ─────────────────────────────────────────────────────────────
    *make_entries(
        "male/hand_single", "male",
        "Single strong masculine right hand, fingers spread with authority, "
        "showing dorsal side, shirt or kurta cuff at wrist, "
        "well-groomed nails, hand looks powerful and refined",
        "100mm macro, masculine hand, strong and crisp"
    ),
    *make_entries(
        "male/hand_both", "male",
        "Both hands loosely clasped or one over the other, "
        "masculine confident pose, suit or kurta sleeve visible at wrist",
        "85mm, both hands, masculine and composed"
    ),

    # ── MALE WRIST ────────────────────────────────────────────────────────────
    *make_entries(
        "male/wrist_raised", "male",
        "Strong masculine wrist raised, inner wrist visible, "
        "shirt cuff or kurta sleeve, forearm looks capable and refined",
        "100mm, masculine wrist and forearm"
    ),
    *make_entries(
        "male/wrist_crossed", "male",
        "Crossed forearms, both wrists clearly visible, "
        "powerful casual pose, suit or smart casual styling",
        "85mm, crossed arms, both wrists"
    ),

    # ── KIDS ──────────────────────────────────────────────────────────────────
    *make_entries(
        "kids/girl_face", "kids_girl",
        "Front face portrait, girl looking at camera, bright genuine smile, "
        "ears visible with hair tucked back, flowers in hair, "
        "natural joyful child expression",
        "85mm f/2.0, child portrait, both ears visible, warm and sweet"
    ),
    *make_entries(
        "kids/girl_neck", "kids_girl",
        "Chest-up portrait, girl's neck and pavadai neckline visible, "
        "traditional gold work at neckline, sweet expression, chin up slightly",
        "70mm, child chest-up, neck and neckline"
    ),
    *make_entries(
        "kids/boy_neck", "kids_boy",
        "Chest-up portrait, boy in silk kurta, neck and collar visible, "
        "mandarin collar or kurta neckline, cheerful and bright",
        "70mm, child chest-up, kurta neckline"
    ),
    *make_entries(
        "kids/girl_hand", "kids_girl",
        "Child's small delicate hands, single hand or both together, "
        "natural playful position, pavadai fabric visible, "
        "tiny manicured nails, utterly adorable",
        "85mm, child hands, small and delicate, soft bokeh"
    ),
)

# ── CODEX CALL ────────────────────────────────────────────────────────────────

def _load_token():
    path = os.path.expanduser("~/.codex/auth.json")
    data = json.load(open(path))
    return data.get("tokens", {}).get("access_token", "")


def _encode_ref(path):
    from PIL import Image as _PIL
    img = _PIL.open(path).convert("RGB")
    img.thumbnail((768, 768))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def generate_one(spec, female_ref_path=None):
    out_file, model_type, pose, camera, bg_key = spec
    out_path = os.path.join(MODELS_DIR, out_file)

    if os.path.exists(out_path):
        print(f"  ✓ EXISTS")
        return out_path

    token = _load_token()
    bg_desc = BG[bg_key]

    # Select model description
    if model_type == "female":
        model_desc = FEMALE_BASE
    elif model_type == "male":
        model_desc = MALE_BASE
    elif model_type == "kids_girl":
        model_desc = KIDS_GIRL_BASE
    else:
        model_desc = KIDS_BOY_BASE

    prompt = (
        f"ARADHANA JEWELLERS — Model Reference Library Image\n\n"
        f"MODEL STYLING:\n{model_desc}\n\n"
        f"POSE:\n{pose}\n\n"
        f"BACKGROUND:\n{bg_desc}\n\n"
        f"CAMERA: {camera}\n\n"
        f"QUALITY:\n{QUALITY}\n\n"
        f"CRITICAL — NO JEWELLERY: The model must have ZERO jewellery visible. "
        f"This is a clean reference pose used for compositing jewellery later. "
        f"Remove any jewellery that appears naturally.\n\n"
        f"Reply last line: REF_DONE: {out_file}"
    )

    content = []
    if model_type == "female" and female_ref_path and os.path.exists(female_ref_path):
        b64 = _encode_ref(female_ref_path)
        content.append({"type": "input_image",
                         "image_url": f"data:image/jpeg;base64,{b64}"})
    content.append({"type": "input_text", "text": prompt})

    payload = {
        "model": "gpt-5.5",
        "stream": True,
        "instructions": "You are a professional luxury fashion photography AI.",
        "input": [{"type": "message", "role": "user", "content": content}],
        "tools": [{"type": "image_generation", "output_format": "png"}],
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "store": False,
        "reasoning": {"effort": "low", "summary": "auto"},
        "text": {"verbosity": "low"},
    }

    import requests as _req
    sess = _req.Session()
    sess.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": "aradhana-model-library/2.0",
    })

    resp = sess.post("https://chatgpt.com/backend-api/codex/responses",
                     json=payload, stream=True, timeout=120)

    if resp.status_code == 429:
        raise Exception("CODEX_RATE_LIMIT")
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

    result_b64 = None
    for raw_line in resp.iter_lines():
        if not raw_line: continue
        line = raw_line.decode("utf-8", errors="replace")
        if not line.startswith("data:"): continue
        data_str = line[5:].strip()
        if data_str == "[DONE]": break
        try:
            evt = json.loads(data_str)
            if evt.get("type") == "response.output_item.done":
                item = evt.get("item", {})
                if item.get("type") == "image_generation_call":
                    result_b64 = item.get("result", "")
        except Exception:
            pass

    if not result_b64:
        raise Exception("No image in response")

    from PIL import Image as _PIL
    png_data = base64.b64decode(result_b64)
    img = _PIL.open(io.BytesIO(png_data)).convert("RGB")
    img.save(out_path, "JPEG", quality=93)
    return out_path


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Clear old library first
    import shutil
    for zone_dir in (FEMALE_DIR, MALE_DIR, KIDS_DIR):
        for f in os.listdir(zone_dir):
            if f.endswith(".jpg"):
                os.remove(os.path.join(zone_dir, f))
    print("Old library cleared.")

    total = len(LIBRARY)
    print(f"{'='*60}")
    print(f"ARADHANA MODEL LIBRARY v2 — {total} reference images")
    print(f"Philosophy: same pose × 3 backgrounds (A=cream / B=gold / C=dark)")
    print(f"Female: editorial glamour styling, NOT store uniform")
    print(f"{'='*60}\n")

    # Find female reference
    female_ref = None
    for fn in ["pose1_front.jpg", "pose2_gesture.jpg", "pose3_45deg.jpg", "reference.jpg"]:
        p = os.path.join(FEMALE_DIR, fn)
        if os.path.exists(p):
            female_ref = p
            print(f"Female reference: {fn}\n")
            break
    if not female_ref:
        print("⚠ No female reference found in models/female/ — AI will generate without face ref\n")

    done, errors = 0, []
    for i, spec in enumerate(LIBRARY, 1):
        out_file, _, pose_preview, _, bg_key = spec
        short_pose = pose_preview[:50].replace('\n','')
        print(f"[{i:02d}/{total}] {out_file} (BG-{bg_key})... ", end="", flush=True)
        try:
            generate_one(spec, female_ref)
            done += 1
            print(f"✓  ({done}/{total} done)")
            time.sleep(3)
        except Exception as e:
            print(f"✗ {e}")
            errors.append((out_file, str(e)))
            if "RATE_LIMIT" in str(e):
                print("  Rate limited — waiting 90s...")
                time.sleep(90)

    print(f"\n{'='*60}")
    print(f"Complete: {done}/{total} generated")
    if errors:
        print(f"Errors: {len(errors)}")
        for f, e in errors:
            print(f"  {f}: {e}")
    print(f"\nLibrary at: {MODELS_DIR}")
