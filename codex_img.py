"""
ChatGPT Plus → image generation via backend-api/codex/responses.
Uses the OAuth token from ~/.codex/auth.json (no API key, no extra cost).
Windows-compatible — no fcntl dependency.
"""
import sys, os, json, base64, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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


def _encode_image(path: str, max_edge: int = 1024) -> tuple[str, str]:
    from PIL import Image
    import io
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_edge, max_edge))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
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
        f"You have 3 images: image 1 = {cat_label} jewellery, "
        f"image 2 = price tag, image 3 = background. "
        f"Extract ONLY the bare metal {cat_label} from image 1 — "
        f"remove the display stand, holder, price tags and props completely. "
        f"Place the jewellery centred on the background from image 3. "
        f"If a pair: both pieces perfectly straight, symmetrical, evenly spaced. "
        f"Professional studio lighting. NO text, watermarks, or numbers. "
        f"Preserve exact design, colour and finish — do NOT redraw. "
        f"Read the item code from the tag in image 2 and reply: "
        f"LABEL: <code>"
    )

    payload = {
        "model": "gpt-4o",
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

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": "chatgpt-imagegen/0.16.1",
    }

    _st("Sending to ChatGPT codex endpoint…")
    body = json.dumps(payload).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers=headers, method="POST")

    result_b64 = None
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            _st("Streaming response…")
            buf = b""
            for chunk in iter(lambda: resp.read(4096), b""):
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        evt = json.loads(data_str)
                        t = evt.get("type", "")
                        if t == "response.image_generation_call.in_progress":
                            _st("⬛ Generating image…")
                        elif t == "response.image_generation_call.partial_image":
                            _st(f"  partial ({evt.get('partial_image_index',0)})")
                        elif t == "response.output_item.done":
                            item = evt.get("item", {})
                            if item.get("type") == "image_generation_call":
                                result_b64 = item.get("result", "")
                                _st("✅ Image received!")
                    except json.JSONDecodeError:
                        pass

    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")[:300]
        return {"output": None, "label": label, "error": f"HTTP {e.code}: {body_txt}"}
    except Exception as e:
        return {"output": None, "label": label, "error": str(e)}

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
