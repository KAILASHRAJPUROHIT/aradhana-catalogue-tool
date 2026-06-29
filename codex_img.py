"""
ChatGPT Plus → image generation via backend-api/codex/responses.
Uses the OAuth token from ~/.codex/auth.json (no API key, no extra cost).
Windows-compatible — no fcntl dependency.
Optimised: requests.Session(), 768px input, parallel-safe.
"""
import sys, os, json, base64, time, urllib.request, urllib.error
import requests as _requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Shared session — reuses TLS connection, saves ~200ms per request
_SESSION = _requests.Session()
_SESSION.headers.update({
    "Content-Type":  "application/json",
    "Accept":        "text/event-stream",
    "User-Agent":    "chatgpt-imagegen/0.16.1",
})

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
OUTPUT = os.path.join(BASE, "output_aradhana")
ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"


def _load_token() -> str:
    path = os.path.expanduser("~/.codex/auth.json")
    if not os.path.exists(path):
        raise FileNotFoundError("Run: npx @openai/codex login")
    data = json.load(open(path))
    token = data.get("tokens", {}).get("access_token") or data.get("OPENAI_API_KEY", "")
    if not token:
        raise ValueError("No access_token in ~/.codex/auth.json — run codex login again")
    return token


def _encode_image(path: str, max_edge: int = 768) -> tuple[str, str]:
    """768px is sufficient for ChatGPT's editing model — 40% smaller request body."""
    from PIL import Image
    import io
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_edge, max_edge))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


def generate(jewel_path: str, tag_path: str, bg_path: str,
             category: str = "earrings", label: str = "studio",
             status_fn=None, model_prompt_override: str = None) -> dict:
    """
    Send 3 images to ChatGPT via the Codex endpoint and get back a generated image.
    Returns {"output": path, "label": label, "error": None} or {"error": ...}
    """
    def _st(msg):
        print(f"  [CODEX] {msg}")
        if status_fn: status_fn(msg)

    _st("Loading OAuth token…")
    try:
        token = _load_token()
    except Exception as e:
        return {"output": None, "label": label, "error": str(e)}

    _st("Encoding 3 images…")
    try:
        b64_jewel, mime_j = _encode_image(jewel_path)
        b64_tag,   mime_t = _encode_image(tag_path)
        b64_bg,    mime_b = _encode_image(bg_path)
    except Exception as e:
        return {"output": None, "label": label, "error": f"Image encode error: {e}"}

    cat_label = category.replace("_", " ").title()
    prompt = (
        f"You have 3 images: image 1 = {cat_label} jewellery photo, "
        f"image 2 = price tag, image 3 = studio background scene.\n\n"

        f"TASK: Extract ONLY the bare metal {cat_label} from image 1 and "
        f"composite it onto the background scene in image 3.\n\n"

        f"CRITICAL — THIS IS A PHOTOGRAPHIC COMPOSITING TASK, NOT A GENERATION TASK:\n"
        f"- Treat image 1 as a photograph and perform a PRECISE CUTOUT of the jewellery\n"
        f"- The output jewellery must match the original photograph exactly — same shape, "
        f"same stone colours and positions, same gold texture and filigree pattern, same dangles\n"
        f"- Do NOT recreate, redraw, stylise, simplify, or 'improve' the design in any way\n"
        f"- Any deviation from the original design is a FAILURE\n\n"
        f"CRITICAL — BLACK AREAS IN THE SOURCE IMAGE:\n"
        f"- The raw jewellery photograph was taken on a BLACK VELVET background\n"
        f"- Any BLACK or DARK areas that appear INSIDE the jewellery design are NOT black metal "
        f"and NOT black gemstones — they are HOLLOW OPENWORK GAPS in the filigree/metalwork\n"
        f"- These hollow gaps must be TRANSPARENT in the cutout, so the background (image 3) "
        f"shows through them naturally — like looking through a hole in the metal\n"
        f"- Only remove the outer black background — the inner hollow gaps must remain open\n"
        f"- Do NOT fill hollow areas with black, do NOT add black material that was not there\n\n"
        f"EXTRACTION RULES:\n"
        f"- Remove the display stand, holder, velvet prop, price tags and ALL non-jewellery elements\n"
        f"- Keep ONLY the bare metal jewellery with transparent hollow areas intact\n\n"

        f"COMPOSITION RULES — follow these exactly every time:\n"
        f"1. PEDESTAL — MANDATORY: EVERY earring pair MUST be placed ON TOP of the white "
        f"   circular pedestal/plinth in the background. The bottom of the earrings must be "
        f"   physically touching and resting on the flat top surface of the pedestal. "
        f"   The earrings must NOT float in air, NOT appear in front of the background wall, "
        f"   NOT be placed below the pedestal edge. They sit ON the pedestal surface like "
        f"   objects placed on a table — the pedestal supports them from below\n"
        f"2. SIZE — CRITICAL: make the earrings as LARGE as possible. "
        f"   Each earring should fill 60–75% of the pedestal diameter. "
        f"   The pair together should nearly span the full width of the pedestal. "
        f"   Jewellery must be the HERO — bold, large, impossible to miss. "
        f"   If in doubt, go BIGGER\n"
        f"3. PAIR PLACEMENT: both pieces side by side, horizontally centered on pedestal, "
        f"   equal small gap between them\n"
        f"4. SYMMETRY: both pieces exactly same size, same height, perfectly mirrored\n"
        f"5. BACKGROUND: reproduce image 3 EXACTLY as-is — same scale, crop, zoom, composition\n"
        f"6. WATERMARK — CRITICAL: the 'ARADHANA JEWELLERS' logo/watermark in image 3 MUST "
        f"   appear in the output UNCHANGED — do NOT remove, fade, blur or alter it\n"
        f"7. VIGNETTE: apply a subtle dark vignette around the outer edges of the image "
        f"   (gentle darkening of corners and edges) to draw the eye toward the jewellery "
        f"   in the centre. The vignette should be soft and elegant — not heavy\n"
        f"8. LIGHTING: warm studio lighting as in image 3, with a subtle glow/sparkle "
        f"   behind or beneath the earrings on the pedestal to make them shimmer\n"
        f"9. NO additional text, numbers or extra branding beyond what is already in image 3\n\n"

        f"After generating the image, output ONLY this on the last line:\n"
        f"LABEL: <exact item code from tag in image 2>\n"
        f"Example: LABEL: TP22/30\n"
        f"Do NOT write 'LABEL:' anywhere else in your reply."
    )

    payload = {
        "model": "gpt-5.5",
        "stream": True,
        "instructions": "You are an image generation assistant.",
        "input": [{
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": f"data:{mime_j};base64,{b64_jewel}"},
                {"type": "input_image", "image_url": f"data:{mime_t};base64,{b64_tag}"},
                {"type": "input_image", "image_url": f"data:{mime_b};base64,{b64_bg}"},
                {"type": "input_text",  "text": prompt},
            ]
        }],
        "tools": [{"type": "image_generation", "output_format": "png"}],
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "store": False,
        "reasoning": {"effort": "low", "summary": "auto"},
        "include": ["reasoning.encrypted_content"],
        "text": {"verbosity": "low"},
    }

    _SESSION.headers["Authorization"] = f"Bearer {token}"
    _st("Sending to Codex endpoint…")

    result_b64  = None
    text_chunks = []   # collect text delta to extract LABEL

    try:
        resp = _SESSION.post(ENDPOINT, json=payload, stream=True, timeout=120)
        if resp.status_code == 429 or "rate" in resp.text[:200].lower():
            return {"output": None, "label": label,
                    "error": f"CODEX_RATE_LIMIT: {resp.text[:100]}"}
        if resp.status_code != 200:
            return {"output": None, "label": label,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

        _st("⬛ Generating…")
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="replace")
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                evt = json.loads(data_str)
                t   = evt.get("type", "")

                # Capture text output (contains LABEL: TP22/157)
                if t in ("response.output_text.delta", "response.text.delta"):
                    text_chunks.append(evt.get("delta", ""))
                elif t == "response.output_item.done":
                    item = evt.get("item", {})
                    if item.get("type") == "message":
                        # Full text message — extract label
                        for block in item.get("content", []):
                            if block.get("type") == "output_text":
                                text_chunks.append(block.get("text", ""))
                    elif item.get("type") == "image_generation_call":
                        result_b64 = item.get("result", "")
                        _st("✅ Image received!")
            except json.JSONDecodeError:
                pass

    except Exception as e:
        return {"output": None, "label": label, "error": str(e)}

    # Parse LABEL from text response
    full_text = "".join(text_chunks)
    import re as _re2

    # Try tight pattern first: LABEL followed by colon/space then the code
    # Code format examples: TP22/30  JB617  E2QS0  TP18/8
    m = _re2.search(r"LABEL\s*[:\-]\s*([A-Z][A-Z0-9/_-]{1,15})(?=[^A-Z0-9/_-]|$)", full_text)
    if not m:
        # Wider fallback
        m = _re2.search(r"LABEL[:\s]+([A-Z0-9]{2,18}(?:[/_-][A-Z0-9]+)?)", full_text)

    if m:
        raw = m.group(1).strip().rstrip(".")
        # Strip accidental "LABEL" suffix that sometimes appears
        raw = _re2.sub(r"LABEL.*$", "", raw, flags=_re2.IGNORECASE).strip("/_- ")
        if len(raw) >= 2 and " " not in raw:
            label = raw
            _st(f"🏷️ Label: {label}")
        else:
            _st(f"⚠ Label parse gave bad result '{raw}' — using fallback ({label})")
    else:
        _st(f"⚠ Label not found in response — using fallback ({label})")

    if not result_b64:
        return {"output": None, "label": label, "error": "No image in response"}

    # Save output
    import re as _re
    safe = _re.sub(r'[/\\:*?"<>|]', '_', label or "studio")
    out_path = os.path.join(OUTPUT, f"{safe}.jpg")
    os.makedirs(OUTPUT, exist_ok=True)
    # Codex returns PNG — convert to JPEG for consistent file format
    from PIL import Image as _PIL
    import io as _io2
    png_data = base64.b64decode(result_b64)
    img = _PIL.open(_io2.BytesIO(png_data)).convert("RGB")
    img.save(out_path, "JPEG", quality=92)

    sz = os.path.getsize(out_path)
    _st(f"✓ Saved {label} ({sz//1024}KB) → {out_path}")
    return {"output": out_path, "label": label, "error": None}


if __name__ == "__main__":
    # Quick test
    PROC = os.path.join(BASE, "processing")
    jewels = sorted([f for f in os.listdir(PROC) if "_jewel" in f.lower()])
    tags   = sorted([f for f in os.listdir(PROC) if "_tag" in f.lower()])
    bgs    = [f for f in os.listdir(os.path.join(BASE, "backgrounds")) if f.endswith(".png")]

    if not jewels:
        print("No staged files in processing\\")
        sys.exit(1)

    result = generate(
        jewel_path=os.path.join(PROC, jewels[0]),
        tag_path=os.path.join(PROC, tags[0] if tags else jewels[0]),
        bg_path=os.path.join(BASE, "backgrounds", bgs[0]),
        category="earrings",
        label="CODEX_TEST"
    )
    print("\nResult:", result)
