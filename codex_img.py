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
             status_fn=None) -> dict:
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
        f"- You must treat image 1 as a photograph and perform a PRECISE CUTOUT of the jewellery\n"
        f"- The output jewellery must be PIXEL-IDENTICAL to the original photograph — same shape, "
        f"same stone colours and positions, same gold texture and filigree pattern, same dangles\n"
        f"- Do NOT recreate, redraw, stylise, simplify, or 'improve' the design in any way\n"
        f"- If the original has red rubies at specific positions — they must be at those exact positions\n"
        f"- If the original has a specific dangle drop shape — it must be that exact shape\n"
        f"- Any deviation from the original design is a FAILURE\n\n"
        f"EXTRACTION RULES:\n"
        f"- Remove the display stand, holder, velvet prop, price tags and ALL non-jewellery elements\n"
        f"- Keep ONLY the bare metal jewellery pieces, exactly as photographed\n\n"

        f"COMPOSITION RULES — follow these exactly every time:\n"
        f"1. PEDESTAL: if the background has a white circular pedestal/plinth, place both earrings "
        f"   ON TOP of the pedestal surface, centered on it\n"
        f"2. SIZE — CRITICAL: the earrings must be LARGE and PROMINENT. "
        f"   Each earring should fill 45–60% of the pedestal diameter. "
        f"   The jewellery must be the dominant visual element — bold and showcase-worthy. "
        f"   Do NOT make them small or timid — they must command attention\n"
        f"3. PAIR PLACEMENT: both pieces side by side, horizontally centered, "
        f"   with a small equal gap between them (gap = roughly 10–15% of earring width)\n"
        f"4. VERTICAL: earrings sit firmly on the pedestal surface — "
        f"   not floating in air, not tiny at the bottom\n"
        f"5. SYMMETRY: both pieces exactly the same size, same height, perfectly mirrored\n"
        f"6. BACKGROUND: reproduce image 3 EXACTLY as-is — same scale, same crop, "
        f"   same zoom level, same composition. Do NOT alter it in any way\n"
        f"7. WATERMARK PRESERVATION — CRITICAL: image 3 contains an 'ARADHANA JEWELLERS' "
        f"   watermark/logo. This watermark MUST appear in the output exactly as it appears "
        f"   in image 3 — do NOT remove, hide, blur or alter it under any circumstances\n"
        f"8. LIGHTING: use the same studio lighting as image 3\n"
        f"9. NO additional text, numbers or extra branding beyond what is already in image 3\n\n"

        f"Read the item code from the tag in image 2 and reply: LABEL: <code>"
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
    m = _re2.search(r"LABEL[:\s]+([A-Z][A-Z0-9/_-]{1,18})", full_text)
    if m and " " not in m.group(1):
        label = m.group(1).strip()
        _st(f"🏷️ Label from response: {label}")
    else:
        _st(f"⚠ Label not found in response — using fallback ({label})")

    if not result_b64:
        return {"output": None, "label": label, "error": "No image in response"}

    # Save output
    import re as _re
    safe = _re.sub(r'[/\\:*?"<>|]', '_', label or "studio")
    out_path = os.path.join(OUTPUT, f"{safe}_codex.png")
    os.makedirs(OUTPUT, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(result_b64))

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
