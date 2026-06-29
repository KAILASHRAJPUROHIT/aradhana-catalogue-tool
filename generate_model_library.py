"""
Aradhana Jewellers — Model Library Generator
Generates all ~84 body-zone reference images ONCE.
After this, every product composites jewellery onto these pre-made model photos.

Run once: python generate_model_library.py
"""
import sys, os, json, time, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE       = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
MODELS_DIR = os.path.join(BASE, "models")
FEMALE_DIR = os.path.join(MODELS_DIR, "female")
MALE_DIR   = os.path.join(MODELS_DIR, "male")
KIDS_DIR   = os.path.join(MODELS_DIR, "kids")

for d in (FEMALE_DIR, MALE_DIR, KIDS_DIR):
    os.makedirs(d, exist_ok=True)

# ── Consistent male model description ─────────────────────────────────────────
MALE_CONTEMPORARY = (
    "A handsome South Indian man in his early 30s, clean grooming, sharp features, "
    "confident warm expression. Wearing a well-fitted navy blue bandhgala suit or premium kurta. "
    "Professional, premium, catalogue-ready appearance."
)

MALE_TRADITIONAL = (
    "A handsome South Indian man in his early 30s, traditional festive styling, "
    "rich silk kurta in deep jewel tones (burgundy or deep green), "
    "warm dignified expression, culturally authentic."
)

KIDS_GIRL = (
    "An adorable South Indian girl aged 6-8, bright natural smile, "
    "traditional silk pavadai or pattu skirt in gold and red, "
    "hair neatly done with flowers, innocent and joyful."
)

KIDS_BOY = (
    "An adorable South Indian boy aged 6-8, bright natural smile, "
    "traditional silk kurta in deep blue or maroon, "
    "well groomed, cheerful and natural."
)

STUDIO_LIGHTING = (
    "Soft diffused luxury studio lighting. Clean cream or warm white background. "
    "Natural skin, minimal retouching, professional catalogue quality. "
    "The model's face and hands/neck/wrist (whichever body zone is shown) are the focal point. "
    "NO jewellery visible on the model — this is a base reference photo."
)

# ── Zone generation specs ─────────────────────────────────────────────────────
# Each entry: (output_file, gender, model_desc, shot_description, camera)

FEMALE_REF_NOTE = (
    "IMPORTANT: Use image 1 as the face/appearance reference. "
    "The model in this shot must look IDENTICAL to the woman in image 1 — "
    "same face, same skin tone, same hair, same Aradhana store uniform (navy blue saree with red border). "
)

LIBRARY = [
    # ── FEMALE BODY ZONES (3 variants each) ──────────────────────────────────

    # Ear / Face zone
    ("female/ear_v1.jpg",
     "female", FEMALE_REF_NOTE,
     "85mm portrait, model facing camera directly, ears clearly visible, "
     "hair neatly tucked behind both ears, warm natural smile, shoulders visible",
     "85mm lens, f/1.8, shallow depth of field on face"),

    ("female/ear_v2.jpg",
     "female", FEMALE_REF_NOTE,
     "45-degree portrait, model turned slightly right, right ear fully visible, "
     "graceful neck line, elegant profile angle",
     "85mm lens, f/2.0, face and ear sharp"),

    ("female/ear_v3.jpg",
     "female", FEMALE_REF_NOTE,
     "Side profile shot, model facing right, left ear fully revealed, "
     "hair swept cleanly back, elegant neck curve visible",
     "100mm lens, pure side profile, ear as focal point"),

    # Neck zone
    ("female/neck_v1.jpg",
     "female", FEMALE_REF_NOTE,
     "Chest-up front portrait, neck and upper chest fully visible, "
     "saree neckline elegant, collarbone showing, confident warm expression",
     "70mm lens, chest-up framing"),

    ("female/neck_v2.jpg",
     "female", FEMALE_REF_NOTE,
     "45-degree chest-up portrait, neck at slight angle, "
     "saree draping naturally over shoulder, graceful neckline",
     "70mm lens, 45-degree, chest visible"),

    ("female/neck_v3.jpg",
     "female", FEMALE_REF_NOTE,
     "Close neck crop, chin to chest, neck and collarbone as focal point, "
     "saree neckline clean, no face — intimate product focus",
     "100mm close crop, neck and chest only"),

    # Hand / Fingers zone
    ("female/hand_v1.jpg",
     "female", FEMALE_REF_NOTE,
     "Single right hand elegantly posed, fingers slightly spread, "
     "showing palm side slightly, manicured natural nails, "
     "wrist and lower forearm visible, saree sleeve at wrist",
     "100mm macro, hand sharp"),

    ("female/hand_v2.jpg",
     "female", FEMALE_REF_NOTE,
     "Both hands together, fingers interlaced or overlapping, "
     "elegant feminine hand pose, natural nails, wrists visible",
     "85mm, both hands in frame"),

    ("female/hand_v3.jpg",
     "female", FEMALE_REF_NOTE,
     "Fingers close-up, single hand, fingers pointing gently downward, "
     "ultra-close detail on fingers only, soft bokeh background",
     "100mm macro extreme close-up, fingers only"),

    # Wrist zone
    ("female/wrist_v1.jpg",
     "female", FEMALE_REF_NOTE,
     "Single wrist raised elegantly at chest height, wrist turned to show inner wrist, "
     "forearm visible, saree sleeve creating natural frame",
     "100mm, wrist and forearm, sharp detail"),

    ("female/wrist_v2.jpg",
     "female", FEMALE_REF_NOTE,
     "Both wrists together at waist level, palms facing slightly inward, "
     "elegant symmetrical wrist pose, feminine and graceful",
     "85mm, both wrists in frame, centred"),

    ("female/wrist_v3.jpg",
     "female", FEMALE_REF_NOTE,
     "Single wrist raised toward camera, arm extended naturally, "
     "profile of wrist showing side of forearm, elegant gesture",
     "100mm, wrist profile, forearm visible"),

    # Feet zone
    ("female/feet_v1.jpg",
     "female", FEMALE_REF_NOTE,
     "Standing feet close-up, both feet on marble floor, "
     "elegant foot positioning, toes pointing slightly outward, "
     "ankles and lower shins visible, saree hem just visible at top",
     "70mm, feet and ankles, marble floor"),

    ("female/feet_v2.jpg",
     "female", FEMALE_REF_NOTE,
     "Seated feet, both feet resting on floor or surface, "
     "casual elegant positioning, ankles visible, graceful",
     "85mm, seated feet detail"),

    ("female/feet_v3.jpg",
     "female", FEMALE_REF_NOTE,
     "Walking feet captured mid-step, slight motion, "
     "one foot forward, ankles in gentle movement, candid",
     "70mm, walking feet, slight motion blur on background"),

    # Waist zone
    ("female/waist_v1.jpg",
     "female", FEMALE_REF_NOTE,
     "Mid-body crop from chest to upper thigh, "
     "waistline clearly visible, saree draping at waist, elegant pose",
     "70mm, mid-body, waist as focal point"),

    ("female/waist_v2.jpg",
     "female", FEMALE_REF_NOTE,
     "Three-quarter body, waist and hips visible, "
     "model standing straight, full saree draping visible at waist",
     "50mm, three-quarter body"),

    # ── MALE BODY ZONES ───────────────────────────────────────────────────────

    ("male/neck_v1.jpg",
     "male", MALE_CONTEMPORARY,
     "Chest-up front portrait, neck and upper chest visible, "
     "collar of kurta or shirt open slightly at neck, confident expression",
     "70mm, chest-up, masculine"),

    ("male/neck_v2.jpg",
     "male", MALE_CONTEMPORARY,
     "45-degree chest portrait, neck at angle, "
     "collar styling visible, confident profile",
     "70mm, 45-degree masculine portrait"),

    ("male/neck_v3.jpg",
     "male", MALE_TRADITIONAL,
     "Traditional kurta neck close-up, mandarin collar, "
     "neck and chest as focal point, dignified expression",
     "85mm, neck and chest, traditional"),

    ("male/hand_v1.jpg",
     "male", MALE_CONTEMPORARY,
     "Single masculine right hand, fingers slightly spread, "
     "strong capable hand pose, shirt or suit cuff at wrist",
     "100mm macro, masculine hand"),

    ("male/hand_v2.jpg",
     "male", MALE_CONTEMPORARY,
     "Both hands loosely clasped or one hand resting on the other, "
     "masculine confident hand pose, suit or kurta sleeve visible",
     "85mm, both hands, masculine"),

    ("male/hand_v3.jpg",
     "male", MALE_TRADITIONAL,
     "Hand in traditional pose, fingers extended, "
     "kurta sleeve at wrist, rich fabric visible, dignified",
     "100mm, traditional hand pose"),

    ("male/wrist_v1.jpg",
     "male", MALE_CONTEMPORARY,
     "Strong masculine wrist raised, inner wrist visible, "
     "shirt cuff or kurta sleeve rolled slightly, confident",
     "100mm, masculine wrist"),

    ("male/wrist_v2.jpg",
     "male", MALE_CONTEMPORARY,
     "Crossed forearms, both wrists visible, "
     "casual powerful pose, suit or smart casual",
     "85mm, crossed arms, both wrists"),

    ("male/wrist_v3.jpg",
     "male", MALE_TRADITIONAL,
     "Single wrist in traditional gesture, kurta sleeve, "
     "dignified hand position, warm toned background",
     "100mm, traditional wrist pose"),

    # ── KIDS ──────────────────────────────────────────────────────────────────

    ("kids/face_girl_v1.jpg",
     "kids_girl", KIDS_GIRL,
     "Front face portrait, girl looking at camera, bright smile, "
     "ears visible, flowers in hair, joyful and natural",
     "85mm, child portrait, both ears visible"),

    ("kids/face_girl_v2.jpg",
     "kids_girl", KIDS_GIRL,
     "45-degree portrait, girl looking slightly sideways, "
     "one ear visible, playful expression",
     "85mm, 45-degree child portrait"),

    ("kids/neck_girl_v1.jpg",
     "kids_girl", KIDS_GIRL,
     "Chest-up portrait, neck and pavadai neckline visible, "
     "traditional gold thread work at neck area, sweet expression",
     "70mm, child chest-up"),

    ("kids/neck_boy_v1.jpg",
     "kids_boy", KIDS_BOY,
     "Chest-up portrait, boy in kurta, neck visible, "
     "mandarin collar or kurta neckline, cheerful smile",
     "70mm, child chest-up, kurta"),

    ("kids/hand_girl_v1.jpg",
     "kids_girl", KIDS_GIRL,
     "Child's small delicate hands, both hands together or single hand, "
     "natural playful pose, pavadai fabric visible",
     "85mm, child hands, delicate"),
]

# ── Load Codex token ──────────────────────────────────────────────────────────

def _load_token():
    path = os.path.expanduser("~/.codex/auth.json")
    data = json.load(open(path))
    return data.get("tokens", {}).get("access_token", "")

# ── Generate one reference image ──────────────────────────────────────────────

def generate_reference(spec: tuple, female_ref_path: str = None) -> str:
    """Generate one model reference image and save it."""
    import requests, io
    from PIL import Image as _PIL

    out_file, gender, model_desc, pose_desc, camera = spec
    out_path = os.path.join(MODELS_DIR, out_file)

    if os.path.exists(out_path):
        print(f"  ✓ EXISTS: {out_file}")
        return out_path

    token = _load_token()
    if not token:
        raise Exception("No Codex token — run: npx @openai/codex login")

    # Build prompt
    prompt = (
        f"ARADHANA JEWELLERS — Model Library Reference Image\n\n"
        f"MODEL: {model_desc}\n\n"
        f"POSE / SHOT: {pose_desc}\n\n"
        f"CAMERA: {camera}\n\n"
        f"{STUDIO_LIGHTING}\n\n"
        f"CRITICAL: The model must have NO jewellery visible — "
        f"this is a blank reference pose for compositing jewellery onto later.\n"
        f"Remove any jewellery that appears naturally on the model.\n\n"
        f"Output: Square (1:1) professional studio photograph.\n"
        f"Reply on last line: REF_DONE: {out_file}"
    )

    # Build content — include female reference if available
    content = []
    if "female" in gender and female_ref_path and os.path.exists(female_ref_path):
        from PIL import Image as _P
        import io as _io
        img = _P.open(female_ref_path).convert("RGB")
        img.thumbnail((768, 768))
        buf = _io.BytesIO()
        img.save(buf, "JPEG", quality=88)
        b64 = base64.b64encode(buf.getvalue()).decode()
        content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"})

    content.append({"type": "input_text", "text": prompt})

    payload = {
        "model": "gpt-5.5",
        "stream": True,
        "instructions": "You are a professional fashion photography AI.",
        "input": [{"type": "message", "role": "user", "content": content}],
        "tools": [{"type": "image_generation", "output_format": "png"}],
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "store": False,
        "reasoning": {"effort": "low", "summary": "auto"},
        "text": {"verbosity": "low"},
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": "aradhana-model-library/1.0",
    }

    import requests as _req
    sess = _req.Session()
    sess.headers.update(headers)

    result_b64 = None
    resp = sess.post("https://chatgpt.com/backend-api/codex/responses",
                     json=payload, stream=True, timeout=120)

    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

    for raw_line in resp.iter_lines():
        if not raw_line: continue
        line = raw_line.decode("utf-8", errors="replace")
        if not line.startswith("data:"): continue
        data_str = line[5:].strip()
        if data_str == "[DONE]": break
        try:
            import json as _j
            evt = _j.loads(data_str)
            if evt.get("type") == "response.output_item.done":
                item = evt.get("item", {})
                if item.get("type") == "image_generation_call":
                    result_b64 = item.get("result", "")
        except Exception:
            pass

    if not result_b64:
        raise Exception("No image in response")

    # Save as JPEG
    png_data = base64.b64decode(result_b64)
    img = _PIL.open(io.BytesIO(png_data)).convert("RGB")
    img.save(out_path, "JPEG", quality=92)
    print(f"  ✓ SAVED: {out_file} ({os.path.getsize(out_path)//1024}KB)")
    return out_path


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("ARADHANA JEWELLERS — Model Library Generator")
    print(f"Generating {len(LIBRARY)} reference images")
    print("=" * 60)

    # Check for female reference
    female_ref = os.path.join(FEMALE_DIR, "pose1_front.jpg")
    if not os.path.exists(female_ref):
        # Try other poses
        for p in ["pose2_gesture.jpg", "pose3_45deg.jpg", "reference.jpg"]:
            candidate = os.path.join(FEMALE_DIR, p)
            if os.path.exists(candidate):
                female_ref = candidate
                break
        else:
            female_ref = None
            print("⚠ No female reference photo found in models/female/")
            print("  Save one of the 3 Aradhana model photos as models/female/pose1_front.jpg")
            print("  Continuing with AI-described model (no face reference)...")
            print()

    done, errors = 0, []
    for i, spec in enumerate(LIBRARY, 1):
        out_file = spec[0]
        print(f"[{i:02d}/{len(LIBRARY)}] {out_file}...", end=" ", flush=True)
        try:
            generate_reference(spec, female_ref)
            done += 1
            time.sleep(2)   # gentle pacing
        except Exception as e:
            print(f"✗ {e}")
            errors.append((out_file, str(e)))
            if "RATE_LIMIT" in str(e):
                print("  Rate limited — waiting 120s...")
                time.sleep(120)

    print(f"\n{'='*60}")
    print(f"Done: {done}/{len(LIBRARY)} images generated")
    if errors:
        print(f"Errors ({len(errors)}):")
        for f, e in errors: print(f"  {f}: {e}")
    print(f"\nModel library saved to: {MODELS_DIR}")
    print("You can now use these as compositing references in the catalogue tool.")
