"""
Background ChatGPT automation — zero screen interaction.
- Connects to the ONE Chrome already open (port 9222)
- Switches to the Catalogue Tool tab
- Uploads images, types prompt, waits for image
- Downloads image via URL + browser cookies
- User workflow never disturbed
"""
import sys, os, time, json, re, random, tempfile, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

BASE      = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
OUTPUT    = os.path.join(BASE, "output_aradhana")
SESSION   = os.path.join(BASE, "chatgpt_session.json")
CHAT_CFG  = os.path.join(BASE, "chatgpt_config.json")   # persists the saved chat URL
SLOT_LOG  = os.path.join(BASE, "slot_log.json")          # rolling window scheduler

# ── Slot scheduler ────────────────────────────────────────────────────────────
# Each ChatGPT Plus image slot unlocks exactly 3 hours after it was used.
# We log every sent timestamp so we always know to the second when the next
# slot opens — no blind waiting, no guessing.

_WINDOW = 3 * 3600   # 3 hours in seconds
_LIMIT  = 50         # Plus: 50 images per rolling 3-hour window

def _slots_load():
    """Load sent timestamps from disk, drop entries older than 3 hours."""
    now = time.time()
    if os.path.exists(SLOT_LOG):
        try:
            data = json.load(open(SLOT_LOG))
            active = [t for t in data if now - t < _WINDOW]
            return active
        except Exception:
            pass
    return []

def _slots_save(slots):
    with open(SLOT_LOG, "w") as f:
        json.dump(slots, f)

def slot_record(sent_at=None):
    """Call this immediately after a prompt is sent to ChatGPT."""
    slots = _slots_load()
    slots.append(sent_at or time.time())
    _slots_save(slots)

def slot_wait_if_needed(status_fn=None):
    """
    Check if we've hit the 50-image window limit.
    If yes: sleep exactly until the oldest slot expires, then return.
    If no:  return immediately.
    Returns seconds waited (0 if no wait needed).
    """
    def _st(msg):
        print(msg)
        if status_fn:
            status_fn(msg)

    slots = _slots_load()
    if len(slots) < _LIMIT:
        remaining = _LIMIT - len(slots)
        _st(f"⏱ Slots: {len(slots)}/{_LIMIT} used — {remaining} free")
        return 0

    # All 50 slots used — find the oldest one
    oldest = min(slots)
    unlock_at = oldest + _WINDOW
    wait = max(0, unlock_at - time.time())

    if wait <= 0:
        # Already unlocked — prune and continue
        _slots_save([t for t in slots if time.time() - t < _WINDOW])
        return 0

    import datetime
    unlock_str = datetime.datetime.fromtimestamp(unlock_at).strftime("%H:%M:%S")
    _st(f"⏳ All 50 slots used — oldest unlocks at {unlock_str} ({int(wait)}s away)")

    # Sleep in 30s chunks, logging countdown
    slept = 0
    while slept < wait:
        chunk = min(30, wait - slept)
        time.sleep(chunk)
        slept += chunk
        remaining = max(0, wait - slept)
        if remaining > 0:
            _st(f"⏳ Slot cooldown — {int(remaining)}s remaining (unlocks {unlock_str})")

    # Prune expired slots
    _slots_save([t for t in _slots_load() if time.time() - t < _WINDOW])
    _st("✅ Slot unlocked — resuming")
    return wait

def slot_status():
    """Return a human-readable status string for the UI."""
    slots = _slots_load()
    used = len(slots)
    free = _LIMIT - used
    if used == 0:
        return f"Slots: {_LIMIT}/{_LIMIT} free"
    oldest = min(slots)
    unlock_at = oldest + _WINDOW
    wait = max(0, unlock_at - time.time())
    import datetime
    unlock_str = datetime.datetime.fromtimestamp(unlock_at).strftime("%H:%M:%S")
    return f"Slots: {free}/{_LIMIT} free — next unlock {unlock_str} ({int(wait)}s)"

def _load_chat_url():
    if os.path.exists(CHAT_CFG):
        try:
            import json
            return json.load(open(CHAT_CFG)).get("chat_url","")
        except Exception: pass
    return ""

def _save_chat_url(url):
    import json
    cfg = {}
    if os.path.exists(CHAT_CFG):
        try: cfg = json.load(open(CHAT_CFG))
        except: pass
    cfg["chat_url"] = url
    json.dump(cfg, open(CHAT_CFG,"w"))

SAVED_CHAT_URL = _load_chat_url()

def build_prompt(category: str, job_id: str, filename: str = "") -> str:
    """
    Extraction prompt.
    Starts with the raw filename so ChatGPT names the thread after the file —
    makes it trivial to identify which thread belongs to which image.
    job_id is echoed back in the reply so we can confirm the right response.
    """
    label = category.replace("_", " ").title()
    # First word = raw filename → ChatGPT uses it as the thread title
    file_prefix = f"{filename} | " if filename else f"{job_id} | "
    return (
        f"{file_prefix}"
        f"JOB:{job_id} — "
        f"Task: extract the {label} jewellery from image 1 and place it on the background in image 3. "
        "CRITICAL OUTPUT RULES — any violation = failure: "
        "1. NO display stand of any kind in the output. "
        "2. NO price tags, labels, or paper in the output. "
        "3. NO jewellery holder, prop, or display fixture in the output. "
        "4. Output must show ONLY the bare metal jewellery pieces on the background — nothing else from image 1. "
        "5. Do NOT redraw — preserve exact design, colour, and finish from the photo. "
        "6. If a pair: both pieces perfectly straight, symmetrical, evenly spaced. "
        "7. Professional studio lighting on the background from image 3. "
        "8. NO text, numbers, or watermarks anywhere on the output image. "
        f"Reply starting with: JOB:{job_id} LABEL: followed by the actual code you read from the tag in image 2 (example: TP22/147 or JB617)"
    )


def read_tag_label_gemma(tag_path: str) -> str:
    """Read tag label using Gemma 4. Returns empty string on failure."""
    try:
        from google import genai
        from google.genai import types as gt
        from keys import GEMINI_API_KEY
        from PIL import Image as _PIL
        import io
        client = genai.Client(api_key=GEMINI_API_KEY)
        pil = _PIL.open(tag_path).convert("RGB")
        pil.thumbnail((512, 512))
        buf = io.BytesIO(); pil.save(buf, "JPEG", quality=90)
        resp = client.models.generate_content(
            model="gemma-4-31b-it",
            contents=[
                gt.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                "Read this price tag. What is the item code on the FIRST LINE? "
                "Reply with ONLY the code, nothing else. Example: JB617 or DL22/4 or TP22/147"
            ]
        )
        raw = resp.text.strip().split("\n")[0].strip()
        label = re.sub(r"[^\w/\-]", "", raw)[:20]
        return label
    except Exception as e:
        print(f"  Gemma tag read failed: {e}")
        return ""


def verify_image_has_jewellery(img_path: str) -> bool:
    """
    Use Gemma 4 to visually confirm the downloaded image contains jewellery.
    MUCH smarter than edge detection — actual AI vision check.
    Returns True if jewellery is visible, False if blank/empty background.
    """
    try:
        from google import genai
        from google.genai import types as gt
        from keys import GEMINI_API_KEY
        from PIL import Image as _PIL
        import io
        client = genai.Client(api_key=GEMINI_API_KEY)
        pil = _PIL.open(img_path).convert("RGB")
        pil.thumbnail((512, 512))
        buf = io.BytesIO(); pil.save(buf, "JPEG", quality=85)
        resp = client.models.generate_content(
            model="gemma-4-31b-it",
            contents=[
                gt.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                "Is this a product photo showing gold jewellery (earrings, ring, necklace, bangle, etc.)? "
                "Answer YES if jewellery is clearly visible as the main subject. "
                "Answer NO only if the image is blank, shows only a background with NO jewellery, "
                "or shows only a plain stand with no jewellery on it. "
                "A decorative pedestal or platform that is part of the studio background is fine — answer YES. "
                "Reply with only YES or NO."
            ]
        )
        answer = resp.text.strip().upper()
        has_jewellery = answer.startswith("YES")
        print(f"  Gemma verify: {answer} → {'PASS' if has_jewellery else 'BLANK IMAGE'}")
        return has_jewellery
    except Exception as e:
        print(f"  Gemma verify failed ({e}) — assuming valid")
        return True   # fail open, don't block on API errors


def craft_prompt_gemma(jewel_path: str, category: str, job_id: str = "") -> str:
    return build_prompt(category, job_id or "X")

PROMPT = build_prompt("jewellery", "INIT")


def _chrome_to_background():
    """
    Push the Chrome window to the bottom of the Z-order so it never
    covers the user's work. Uses Win32 SetWindowPos — no minimize,
    so JavaScript and image rendering continue unaffected.
    """
    try:
        import ctypes, ctypes.wintypes
        user32      = ctypes.windll.user32
        HWND_BOTTOM = ctypes.wintypes.HWND(1)
        SWP_FLAGS   = 0x0002 | 0x0001 | 0x0010   # NOMOVE | NOSIZE | NOACTIVATE
        found       = []

        def _cb(hwnd, _):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            t = buf.value.lower()
            if "chrome" in t or "chatgpt" in t:
                found.append(hwnd)
            return True

        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(CB(_cb), 0)
        for hwnd in found:
            user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_FLAGS)
    except Exception:
        pass   # non-Windows or permission issue — silently skip


def _chrome_to_foreground():
    """Bring Chrome window to the front so the user can see the login page."""
    try:
        import ctypes, ctypes.wintypes
        user32 = ctypes.windll.user32
        HWND_TOP = ctypes.wintypes.HWND(0)
        found = []
        def _cb(hwnd, _):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if "chrome" in buf.value.lower() or "chatgpt" in buf.value.lower():
                found.append(hwnd)
            return True
        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(CB(_cb), 0)
        for hwnd in found:
            user32.ShowWindow(hwnd, 9)       # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _launch_chrome():
    """Auto-restart Chrome with debug port — called when Chrome dies mid-run."""
    import subprocess
    _status("🔄 Chrome died — auto-restarting")
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            if 'chrome' in p.info['name'].lower():
                p.kill()
    except Exception: pass
    time.sleep(2)
    subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--remote-debugging-port=9222",
        r"--user-data-dir=C:\Users\kaila\AppData\Local\AutoCatalogueChrome",
        "--no-first-run", "--no-default-browser-check"
    ])
    time.sleep(6)
    _status("✅ Chrome restarted")


def connect():
    """
    Connect to Chrome on port 9222.
    If Chrome is dead, auto-restarts it — run never hangs waiting for Chrome.
    """
    from selenium.webdriver.chrome.service import Service
    _cd = os.path.join(BASE, "chromedriver.exe")
    _svc = Service(_cd) if os.path.exists(_cd) else None

    for attempt in range(1, 5):
        try:
            opts = Options()
            opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            driver = webdriver.Chrome(service=_svc, options=opts) if _svc else webdriver.Chrome(options=opts)
            _ = driver.window_handles
            _chrome_to_background()
            return driver
        except Exception as e:
            print(f"  Chrome connect attempt {attempt} failed")
            if attempt == 2:
                _launch_chrome()
            elif attempt < 4:
                time.sleep(4)
    raise RuntimeError("Chrome unreachable even after auto-restart")


def _chrome_alive(driver) -> bool:
    """Quick check that the Chrome session is still responsive."""
    try:
        _ = driver.window_handles
        return True
    except Exception:
        return False


def _is_logged_in(driver) -> bool:
    """Return True if ChatGPT shows an active session (not a login/auth page)."""
    try:
        url   = (driver.current_url or "").lower()
        title = (driver.title or "").lower()
        body  = _safe_js(driver, "return document.body.innerText.substring(0, 400);") or ""
        # Signs we're NOT logged in
        if any(p in url for p in ["login", "auth0", "/auth", "sign-in", "accounts.google"]):
            return False
        if any(p in title for p in ["sign in", "log in", "welcome to chatgpt"]):
            return False
        if any(p in body.lower() for p in ["sign in to chatgpt", "log in to chatgpt",
                                            "welcome back", "get started", "create account"]):
            return False
        return True
    except Exception:
        return False


def _ensure_logged_in(driver) -> bool:
    """
    Check login state. If logged out, bring Chrome to foreground,
    show a notification, and WAIT (up to 10 minutes) for the user to log back in.
    Returns True once logged in, False if timed out.
    """
    if _is_logged_in(driver):
        return True

    # Session lost — alert and wait for manual login
    _status("🔑 SESSION EXPIRED — Please log in to ChatGPT. Batch is paused.")
    _chrome_to_foreground()   # bring Chrome forward so user can see it

    for tick in range(600):   # wait up to 10 minutes
        time.sleep(1)
        if tick % 15 == 0:
            _status(f"🔑 Waiting for login… ({600 - tick}s remaining)")
        if _is_logged_in(driver):
            _status("✅ Logged in — resuming batch")
            time.sleep(2)
            return True

    _status("❌ Login timeout after 10 minutes — batch stopped")
    return False


def _wait_for_input_ready(driver, wait, tag=""):
    """
    Wait until the ChatGPT input box is ready and not disabled.
    Handles 'Stop generating' state where input is locked.
    """
    for _ in range(20):
        try:
            inp = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.ProseMirror')))
            # Check if a previous response is still generating (stop button visible)
            stop_btn = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="Stop"]')
            if stop_btn:
                _status(f"{tag}⏳ Waiting for previous response to finish")
                time.sleep(3)
                continue
            if inp.get_attribute("contenteditable") == "true":
                return inp
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError("Input box never became ready")


def _copy_image_to_clipboard(img_path):
    """Copy image to Windows clipboard as DIB — works with Ctrl+V in any browser."""
    import win32clipboard
    from PIL import Image as _Img
    import io as _io
    img = _Img.open(img_path).convert("RGB")
    buf = _io.BytesIO()
    img.save(buf, "BMP")
    bmp_data = buf.getvalue()[14:]  # strip 14-byte BMP file header → raw DIB
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
    win32clipboard.CloseClipboard()


def _upload_with_verify(driver, wait, files, tag=""):
    """
    Paste images into ChatGPT via clipboard (Ctrl+V) — one at a time.
    Avoids file input lookups, dedup warnings, and popup dialogs entirely.
    """
    files = files[:3]

    # Find the ChatGPT input box
    input_el = None
    for sel in ['div#prompt-textarea', 'div[contenteditable="true"]',
                '#prompt-textarea', 'textarea']:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                if el.is_displayed():
                    input_el = el
                    break
            if input_el:
                break
        except Exception:
            pass

    if not input_el:
        # Fallback to old file-input method if clipboard approach can't find input
        _status(f"{tag}⚠ Input not found — falling back to file input")
        try:
            fi = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[type="file"]')))
            for f in files:
                fi.send_keys(f)
                time.sleep(1)
        except Exception as e:
            _status(f"{tag}⚠ File input fallback failed: {e}")
        return

    input_el.click()
    time.sleep(0.3)

    for idx, img_path in enumerate(files, 1):
        _copy_image_to_clipboard(img_path)
        time.sleep(0.3)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(1.0)   # wait for ChatGPT to render the thumbnail

        # Dismiss any popup that appears (duplicate image warning etc.)
        driver.execute_script("""
            document.querySelectorAll('button').forEach(b => {
                const t = (b.textContent || '').trim();
                if (['OK','Ok','Got it','Dismiss','Yes','Continue'].includes(t)) b.click();
            });
        """)
        _status(f"{tag}📋 Image {idx}/3 pasted")


def _detect_rate_limit(driver) -> bool:
    """Detect ChatGPT hard rate limit — cannot proceed at all."""
    try:
        text = (_safe_js(driver, "return document.body.innerText;") or "").lower()
        return any(p in text for p in [
            "you've reached", "too many requests", "rate limit",
            "try again in", "please slow down", "usage limit"
        ])
    except Exception:
        return False


def _detect_soft_warning(driver) -> dict:
    """
    Detect ChatGPT soft warnings — yellow banners or tooltip messages that
    appear mid-session BEFORE a hard block. The current image may still complete.
    Returns {"warned": bool, "text": str}
    """
    WARNING_PHRASES = [
        "creating images quickly",
        "you're generating images quickly",
        "generating a lot of images",
        "image generation limit",
        "approaching your limit",
        "you've used most",
        "slow down",
        "limit reached",
        "you can continue",          # "You can continue but may be limited"
        "temporarily limited",
        "generation may be slower",
        "your image generation",
    ]
    try:
        result = _safe_js(driver, """
            // Check banners, toasts, tooltips — elements that appear as overlays
            const selectors = [
                '[class*="warning"]', '[class*="banner"]', '[class*="toast"]',
                '[class*="alert"]',   '[class*="notice"]', '[role="alert"]',
                '[class*="limit"]',   '[class*="quota"]',  '[data-testid*="warn"]'
            ];
            const texts = [];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    const t = (el.innerText || '').trim();
                    if (t.length > 5 && t.length < 300) texts.push(t);
                });
            });
            return texts.join(' | ');
        """) or ""

        result_lower = result.lower()
        matched = next((p for p in WARNING_PHRASES if p in result_lower), None)

        if matched:
            return {"warned": True, "text": result[:200]}

        # Also check full body for warning phrases as fallback
        body = (_safe_js(driver, "return document.body.innerText;") or "").lower()
        matched = next((p for p in WARNING_PHRASES if p in body), None)
        if matched:
            return {"warned": True, "text": f"[body] matched: {matched}"}

        return {"warned": False, "text": ""}
    except Exception:
        return {"warned": False, "text": ""}


SINGLE_CHAT_URL = _load_chat_url() or "https://chatgpt.com"

# ── Chat rotation state ───────────────────────────────────────────────────────
# Reuse the same chat for CHAT_ROTATE_EVERY pairs, then delete and open fresh.
CHAT_ROTATE_EVERY = 5        # rotate after this many pairs
_chat_pair_count  = 0        # pairs processed in current chat
_current_chat_url = ""       # URL of the chat currently in use


def _delete_chat(driver, chat_url: str) -> bool:
    """
    Delete a ChatGPT conversation via its internal API.
    Uses the browser's existing session cookies — no extra auth needed.
    Returns True on success, False on failure (non-fatal).
    """
    if not chat_url or "/c/" not in chat_url:
        return False
    try:
        # Extract conversation UUID from URL  e.g. /c/6a3e5c84-d694-83e8-...
        conv_id = chat_url.rstrip("/").split("/c/")[-1].split("?")[0]
        if not conv_id:
            return False

        result = _safe_js(driver, f"""
            return new Promise(resolve => {{
                fetch('/backend-api/conversation/{conv_id}', {{
                    method: 'DELETE',
                    headers: {{
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + (
                            document.cookie.split('; ')
                            .find(c => c.startsWith('__Secure-next-auth.session-token'))
                            ?.split('=')[1] || ''
                        )
                    }},
                    credentials: 'include'
                }})
                .then(r => resolve(r.ok ? 'deleted' : 'err:' + r.status))
                .catch(e => resolve('err:' + e));
            }});
        """, timeout=10)

        if result == "deleted":
            _status(f"🗑 Chat deleted: ...{conv_id[-8:]}")
            return True
        else:
            _status(f"⚠ Chat delete failed: {result}")
            return False
    except Exception as e:
        _status(f"⚠ Chat delete error: {e}")
        return False

# Injected by app.py at startup — avoids circular import
_JOB_DICT = None

def _status(msg):
    """Push a one-liner to the live progress bar."""
    if _JOB_DICT is not None:
        _JOB_DICT["current"] = msg
    print(f"  [{msg}]")

def _get_driver():
    """Get or create the persistent Chrome driver."""
    return connect()

_BATCH_CHAT_URL = ""   # fresh chat per batch, set when batch starts

def start_batch_chat(driver):
    """
    Reuse the saved persistent chat — no new chat opened per batch.
    Chrome stays VISIBLE during startup so user can see it loading.
    """
    global _BATCH_CHAT_URL
    # Find the ChatGPT tab
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "chatgpt" in driver.current_url.lower() or "openai" in driver.current_url.lower():
            break
    else:
        driver.switch_to.window(driver.window_handles[0])

    saved = SAVED_CHAT_URL or _BATCH_CHAT_URL
    if saved and "/c/" in saved:
        if driver.current_url.rstrip("/") != saved.rstrip("/"):
            driver.get(saved)
            time.sleep(3)
        _BATCH_CHAT_URL = saved
        _status(f"💬 Chat ready — starting batch")
    else:
        driver.get("https://chatgpt.com")
        time.sleep(4)
        _BATCH_CHAT_URL = driver.current_url
        _status("🆕 ChatGPT open — will save chat after first message")
    # Do NOT push to background here — let user see Chrome is alive

def switch_to_chatgpt_tab(driver, pair_num=None):
    """
    Return to the batch chat started at job begin.
    Same chat for all images in this batch, new chat next batch.
    """
    global _BATCH_CHAT_URL
    tag = f"Pair {pair_num} " if pair_num else ""

    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "chatgpt" in driver.current_url.lower() or "openai" in driver.current_url.lower():
            break
    else:
        driver.switch_to.window(driver.window_handles[0])

    target = _BATCH_CHAT_URL or "https://chatgpt.com"
    if driver.current_url.rstrip("/") != target.rstrip("/"):
        driver.get(target)
        time.sleep(3)

    # Once ChatGPT assigns a /c/ id, persist it so the same chat survives restarts
    if "/c/" in driver.current_url and (not _BATCH_CHAT_URL or "/c/" not in _BATCH_CHAT_URL):
        _BATCH_CHAT_URL = driver.current_url
        _save_chat_url(_BATCH_CHAT_URL)
        _status(f"{tag}💾 Chat saved: …{_BATCH_CHAT_URL[-20:]}")

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    _chrome_to_background()

    return True


def _recovery_loop(driver, pair_num, deadline):
    """
    4-level recovery — each level shown as a one-liner in the progress bar.
    Level 1 (45s):  scroll + dismiss dialogs + check rate limit
    Level 2 (90s):  reload the chat page + re-check login
    Level 3 (150s): close tab + reopen chat URL
    Level 4 (210s): nuclear — quit Chrome, restart, re-login
    Returns driver (possibly a fresh one after nuclear reset).
    """
    tag = f"Pair {pair_num}"
    elapsed = int(time.time() - (deadline - 420))   # 420 = our timeout

    # Rate limit check at any point
    try:
        if _detect_rate_limit(driver):
            _status(f"{tag} 🚦 Rate limited — waiting 60s")
            time.sleep(60)
            return driver
    except Exception: pass

    if 45 < elapsed <= 90:
        _status(f"{tag} ⏳ Slow response — scrolling & clearing dialogs")
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            dismiss_dialogs(driver)
            _ensure_logged_in(driver)
        except Exception: pass

    elif 90 < elapsed <= 150:
        _status(f"{tag} 🔄 Level 2 — reloading chat page")
        try:
            driver.get(SINGLE_CHAT_URL)
            time.sleep(5)
            _ensure_logged_in(driver)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception: pass

    elif 150 < elapsed <= 210:
        _status(f"{tag} 🔄 Level 3 — reopening tab")
        try:
            # Open a new tab to the chat
            driver.execute_script(f"window.open('{SINGLE_CHAT_URL}', '_blank');")
            time.sleep(2)
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(4)
            _ensure_logged_in(driver)
        except Exception:
            try: driver.get(SINGLE_CHAT_URL); time.sleep(4)
            except Exception: pass

    elif elapsed > 210:
        _status(f"{tag} ☢️ Level 4 — nuclear browser restart")
        try: driver.quit()
        except Exception: pass
        time.sleep(3)
        try:
            driver = connect()
            driver.get("https://chat.openai.com")
            time.sleep(2)
            with open(SESSION, "r") as fh:
                for c in json.load(fh):
                    try: driver.add_cookie(c)
                    except Exception: pass
            driver.get(SINGLE_CHAT_URL)
            time.sleep(5)
            _status(f"{tag} ✅ Browser restarted — resuming")
        except Exception as e:
            _status(f"{tag} ❌ Restart failed: {e}")

    return driver


def _safe_js(driver, script, timeout=5):
    """Run execute_script with a hard timeout so a hung Chrome never freezes the thread."""
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(driver.execute_script, script)
        try:
            return fut.result(timeout=timeout)
        except (_cf.TimeoutError, Exception):
            return None


def _wait_for_generation(driver, deadline, tag=""):
    """
    Soft 1-second poll that watches ONLY the stop button.
    Phase 1: wait for stop to APPEAR  (confirms ChatGPT started, up to 45s)
    Phase 2: wait for stop to DISAPPEAR (generation done)
    Returns: "done" | "reload" | "deadline" | "maybe_done"
    No image scanning, no label parsing — zero interference with generation.
    """
    _STOP_JS = """
        return Array.from(document.querySelectorAll('button')).some(b => {
            const l = (b.getAttribute('aria-label') || '').toLowerCase();
            const t = (b.getAttribute('data-testid') || '').toLowerCase();
            return l.includes('stop') || t.includes('stop');
        });
    """

    # Phase 1 — wait up to 45s for stop button to appear
    appeared = False
    appear_by = time.time() + 45
    while time.time() < min(appear_by, deadline):
        time.sleep(1)
        vis = _safe_js(driver, _STOP_JS)
        if vis:
            appeared = True
            _status(f"{tag}⬛ ChatGPT generating…")
            break

    if not appeared:
        _status(f"{tag}⏳ No stop button seen — checking for result")
        return "maybe_done"

    # Phase 2 — wait for stop to disappear (generation complete)
    gen_start = time.time()
    consecutive_fails = 0
    while time.time() < deadline:
        time.sleep(1)
        vis = _safe_js(driver, _STOP_JS)

        if vis is None:
            # execute_script timed out — Chrome hung
            consecutive_fails += 1
            _status(f"{tag}⚠️ Chrome unresponsive ({consecutive_fails}x)")
            if consecutive_fails >= 5:
                _status(f"{tag}🔄 Chrome hung — aborting pair")
                return "deadline"
            continue
        consecutive_fails = 0

        waited = int(time.time() - gen_start)
        if waited > 0 and waited % 15 == 0:
            _status(f"{tag}⬛ Generating… {waited}s")

        if not vis:
            _status(f"{tag}✅ Generation done ({waited}s)")
            return "done"

        # Check for rate limit during generation
        if waited > 0 and waited % 20 == 0:
            rl = _safe_js(driver, """
                const t = (document.body.innerText || '').toLowerCase();
                return ['too many requests','rate limit','please slow down',
                        'try again in','you\'ve sent too many'].some(p => t.includes(p));
            """)
            if rl:
                _status(f"{tag}⏳ Rate limited mid-generation — cooling 90s")
                time.sleep(90)
                return "rate_limit"

        if waited > 300:
            _status(f"{tag}🔄 5min+ generating — reloading page")
            return "reload"

    return "deadline"


def make_unique(src):
    """Create a content-unique copy so ChatGPT doesn't flag as duplicate."""
    ext  = os.path.splitext(src)[1].lower()
    dst  = os.path.join(tempfile.mkdtemp(), f"u_{int(time.time())}_{random.randint(0,9999)}.jpg")
    img  = Image.open(src).convert("RGB")
    ts   = int(time.time())
    ImageDraw.Draw(img).point(
        (random.randint(0, img.width-1), random.randint(0, img.height-1)),
        fill=(ts % 255, random.randint(0, 255), random.randint(0, 255))
    )
    img.save(dst, quality=98)
    return dst


def dismiss_dialogs(driver):
    driver.execute_script("""
        document.querySelectorAll('button').forEach(b => {
            if (['OK','Ok','Got it','Dismiss'].includes(b.textContent.trim())) b.click();
        });
    """)


def download_image(driver, img_el, save_path):
    """
    Download the generated image WITHOUT screen interaction.
    1. Try element.screenshot() — direct pixel capture
    2. Try fetching the URL with browser cookies
    3. Fall back to full-page screenshot cropped to element bounds
    """
    # Method 1: element screenshot (works if element is in DOM + rendered)
    try:
        img_el.screenshot(save_path)
        size = os.path.getsize(save_path)
        if size > 10000:  # real image, not blank
            print(f"  Downloaded via element.screenshot ({size//1024}KB)")
            return True
    except Exception as e:
        print(f"  element.screenshot failed: {e}")

    # Method 2: fetch URL with browser cookies
    src = img_el.get_attribute("src") or ""
    if src and src.startswith("http"):
        try:
            cookies = driver.get_cookies()
            opener = urllib.request.build_opener()
            opener.addheaders = [
                ("User-Agent", driver.execute_script("return navigator.userAgent;")),
                ("Cookie", "; ".join(f"{c['name']}={c['value']}" for c in cookies))
            ]
            with opener.open(src, timeout=15) as resp:
                data = resp.read()
            with open(save_path, "wb") as f:
                f.write(data)
            print(f"  Downloaded via URL fetch ({len(data)//1024}KB)")
            return True
        except Exception as e:
            print(f"  URL fetch failed: {e}")

    # Method 3: CDP screenshot of element bounding box
    try:
        rect = driver.execute_script("""
            const r = arguments[0].getBoundingClientRect();
            return {x:r.left, y:r.top, w:r.width, h:r.height};
        """, img_el)
        if rect and rect["w"] > 50:
            from PIL import Image as PILImage
            import base64, io
            # Get page screenshot via CDP
            result = driver.execute_cdp_cmd("Page.captureScreenshot", {"format": "jpeg", "quality": 95})
            img_data = base64.b64decode(result["data"])
            full = PILImage.open(io.BytesIO(img_data))
            # Crop to element
            dpr = driver.execute_script("return window.devicePixelRatio || 1;")
            x, y, w, h = [int(v * dpr) for v in [rect["x"], rect["y"], rect["w"], rect["h"]]]
            cropped = full.crop((x, y, x+w, y+h))
            cropped.save(save_path, quality=95)
            print(f"  Downloaded via CDP crop ({w}x{h})")
            return True
    except Exception as e:
        print(f"  CDP crop failed: {e}")

    return False


def _is_empty_background(img_path: str) -> bool:
    """
    Detect when ChatGPT returned just the backdrop with no jewellery.
    Measures edge density in the centre 60% — bare velvet/satin scores
    very low (~2-3); a jewellery piece on top scores 5+.
    """
    try:
        from PIL import Image as _PIL
        import numpy as _np
        img  = _PIL.open(img_path).convert("L")
        w, h = img.size
        cx0, cy0 = int(w * 0.2), int(h * 0.2)
        cx1, cy1 = int(w * 0.8), int(h * 0.8)
        crop = _np.array(img.crop((cx0, cy0, cx1, cy1)), dtype=_np.float32)
        gy = _np.abs(_np.diff(crop, axis=0)).mean()
        gx = _np.abs(_np.diff(crop, axis=1)).mean()
        score = (gx + gy) / 2
        empty = score < 4.5
        print(f"  BG-check edge score: {score:.2f} → {'EMPTY' if empty else 'OK'}")
        return empty
    except Exception as e:
        print(f"  BG-check failed: {e}")
        return False


def process(jewel_path, tag_path, bg_path, is_first=False, category="jewellery", pair_num=None, job_id=None):
    """
    Full pipeline using a SINGLE persistent chat thread.
    Smart recovery: 4-level escalation if ChatGPT/browser hangs.
    All status shown as one-liners in the progress bar.
    """
    tag = f"Pair {pair_num} " if pair_num else ""

    _status(f"{tag}🔌 Connecting to Chrome")
    driver = connect()
    wait   = WebDriverWait(driver, 30)

    # Verify Chrome is alive
    if not _chrome_alive(driver):
        _status(f"{tag}🔌 Chrome dropped — reconnecting")
        driver = connect()
        wait = WebDriverWait(driver, 30)

    # Check slot availability BEFORE opening the chat
    slot_wait_if_needed(status_fn=lambda m: _status(f"{tag}{m}"))

    global _chat_pair_count, _current_chat_url

    # Switch to ChatGPT window
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "chatgpt" in driver.current_url.lower() or "openai" in driver.current_url.lower():
            break
    else:
        driver.switch_to.window(driver.window_handles[0])

    # Decide: reuse current chat OR rotate to a new one
    need_new_chat = (
        _chat_pair_count == 0              # first pair
        or _chat_pair_count >= CHAT_ROTATE_EVERY  # rotation threshold reached
        or not _current_chat_url           # no chat URL saved yet
        or "/c/" not in _current_chat_url  # not in an assigned chat
    )

    if need_new_chat:
        # Delete the old chat before opening a new one
        if _current_chat_url and "/c/" in _current_chat_url:
            _delete_chat(driver, _current_chat_url)
            _current_chat_url = ""
        _status(f"{tag}💬 New chat  [{slot_status()}]")
        driver.get("https://chatgpt.com")
        time.sleep(2)
        _chat_pair_count = 0
    else:
        # Stay in current chat — just scroll to bottom so input is visible
        _status(f"{tag}💬 Reusing chat ({_chat_pair_count}/{CHAT_ROTATE_EVERY} pairs used)  [{slot_status()}]")
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
        except Exception:
            pass

    # Check login
    if not _ensure_logged_in(driver):
        return {"label": None, "output": None,
                "error": "Session expired — user did not log in within 10 minutes"}
    time.sleep(0.5)

    # Build prompt with unique job_id embedded
    # Raw filename (no extension) — becomes the ChatGPT thread title
    _filename = os.path.splitext(os.path.basename(jewel_path))[0]
    _jid = job_id or re.sub(r"[^A-Za-z0-9]", "", _filename)[:12]
    _status(f"{tag}📝 Building prompt (job:{_jid})")
    prompt = build_prompt(category, _jid, filename=_filename)

    # Upload 3 unique images with thumbnail verification
    _status(f"{tag}📎 Uploading 3 images")
    files = [make_unique(p) for p in [jewel_path, tag_path, bg_path]]
    try:
        _upload_with_verify(driver, wait, files, tag)
    except Exception as e:
        _status(f"{tag}⚠️ Upload error: {e} — retrying")
        try:
            dismiss_dialogs(driver)
            time.sleep(2)
            fi = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"]')))
            for f in files:
                fi.send_keys(f); time.sleep(2)
        except Exception as e2:
            _status(f"{tag}❌ Upload failed twice: {e2}")

    dismiss_dialogs(driver)
    time.sleep(0.5)

    # Wait for input to be ready (not locked by previous generation)
    _status(f"{tag}✍️ Sending prompt via clipboard paste")
    try:
        import pyperclip
        inp = _wait_for_input_ready(driver, wait, tag)
        driver.execute_script("arguments[0].click(); arguments[0].focus();", inp)
        time.sleep(0.3)
        # Paste prompt via clipboard — avoids character-by-character send_keys slowness
        pyperclip.copy(prompt)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(0.5)
        # Try clicking send button, fall back to Enter
        sent = driver.execute_script("""
            const btn = document.querySelector(
                'button[data-testid="send-button"], button[aria-label*="Send"]');
            if (btn && !btn.disabled) { btn.click(); return true; }
            return false;
        """)
        if not sent:
            inp.send_keys(Keys.RETURN)
    except Exception as e:
        _status(f"{tag}⚠️ Prompt send error: {e}")

    # Snapshot all image URLs that exist RIGHT NOW (uploaded inputs)
    # so we can ignore them later and only grab the newly generated image
    try:
        _existing_srcs = set(driver.execute_script("""
            return Array.from(document.querySelectorAll('img'))
                .map(i => i.src || i.currentSrc || '')
                .filter(s => s.length > 0);
        """) or [])
    except Exception:
        _existing_srcs = set()

    # Record slot usage timestamp — this is the moment that counts for the 3hr window
    _sent_at = time.time()
    slot_record(_sent_at)
    _status(f"{tag}📋 Slot logged at {time.strftime('%H:%M:%S')}  [{slot_status()}]")

    # Save chat URL after message sent (ChatGPT assigns /c/... now)
    # and increment rotation counter
    _chat_pair_count += 1
    try:
        time.sleep(1)   # brief wait for URL to update to /c/...
        cur = driver.current_url
        if "/c/" in cur:
            _current_chat_url = cur
    except Exception:
        pass

    # Prompt sent — push Chrome to background now (generation runs fine minimised)
    _chrome_to_background()
    _status(f"{tag}⏳ Prompt sent — watching stop button ({len(_existing_srcs)} existing imgs)")
    time.sleep(1)

    label = None

    def _scan_for_image():
        """
        Scan ALL images on the page — pick the largest non-icon,
        non-user-uploaded image. Returns (img_index, scope) or None.
        """
        try:
            result = driver.execute_script("""
                const allImgs = Array.from(document.querySelectorAll('img'));
                let best = -1, bestArea = 0, bestSrc = '';
                allImgs.forEach((img, i) => {
                    const src = img.src || img.currentSrc || '';
                    if (!src) return;
                    if (src.startsWith('data:image/svg')) return;  // skip SVG icons
                    if (src.includes('/emoji/') || src.includes('favicon')) return;

                    const w = img.naturalWidth  || img.offsetWidth  || 0;
                    const h = img.naturalHeight || img.offsetHeight || 0;

                    // If dimensions available use them; otherwise trust the src exists
                    if (w > 0 && h > 0) {
                        if (w < 50 || h < 50) return;
                        const ratio = w / (h || 1);
                        if (ratio < 0.25 || ratio > 4.0) return;
                    }

                    const area = (w * h) || 10000; // unknown size gets low score
                    if (area > bestArea) {
                        bestArea = area;
                        best = i;
                        bestSrc = src.substring(0, 100);
                    }
                });
                return best >= 0 ? {idx: best, area: bestArea, src: bestSrc} : null;
            """)
            if not result:
                return None
            _status(f"{tag}   img[{result['idx']}] area={result['area']} src={result['src']}")
            return result["idx"]
        except Exception as e:
            _status(f"{tag}   scan error: {e}")
            return None

    def _read_label():
        """
        Read tag label. Priority:
        1. Parse LABEL: from LAST assistant message only (tight regex — no spaces allowed)
        2. Gemma reads the tag image file directly
        """
        # Method 1: last assistant message text only
        try:
            msg_text = driver.execute_script("""
                const msgs = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
                return msgs.length ? msgs[msgs.length-1].innerText : '';
            """) or ""
            # Tight pattern: label code has no spaces — letters/digits/slash/dash only
            m = re.search(r"LABEL[:\s]+([A-Z0-9][A-Z0-9/_-]{1,18})", msg_text, re.I)
            if m:
                candidate = m.group(1).strip().rstrip(".")
                # Reject if it looks like prose
                if " " not in candidate and len(candidate) >= 2:
                    return candidate
        except Exception:
            pass

        # Method 2: Gemma reads the tag image
        try:
            from google import genai
            from google.genai import types as gt
            from PIL import Image as _PIL
            from keys import GEMINI_API_KEY
            client = genai.Client(api_key=GEMINI_API_KEY)
            pil = _PIL.open(tag_path).convert("RGB")
            pil.thumbnail((512, 512))
            import io as _io
            buf = _io.BytesIO()
            pil.save(buf, "JPEG", quality=90)
            resp = client.models.generate_content(
                model="gemma-4-31b-it",
                contents=[
                    gt.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                    "Read the item code on the FIRST LINE of this price tag. "
                    "Reply with ONLY the code — no spaces, no explanation. Example: TP22/157"
                ]
            )
            raw = resp.text.strip().split()[0]
            lbl = re.sub(r"[^\w/_-]", "", raw)[:20]
            if len(lbl) >= 2:
                _status(f"{tag}🏷️ Gemma label: {lbl}")
                return lbl
        except Exception as e:
            _status(f"{tag}⚠️ Gemma label read failed: {e}")

        return None

    def _download(img_idx):
        """
        Download generated image by element index in last assistant message.
        Method 1: element.screenshot() — no URL needed, always works
        Method 2: browser fetch with credentials (for http/estuary URLs)
        Returns (data_bytes, out_path) or raises.
        """
        nonlocal label
        if not label:
            label = _read_label()
            if label:
                _status(f"{tag}🏷️ Label: {label}")
        safe = re.sub(r'[/\\:*?"<>|]', '_', label or "studio")
        out  = os.path.join(OUTPUT, f"{safe}_chatgpt.jpg")

        # Get the element
        img_el = driver.execute_script("""
            const msgs = Array.from(document.querySelectorAll(
                '[data-message-author-role="assistant"]'));
            if (!msgs.length) return null;
            const last = msgs[msgs.length - 1];
            const imgs = Array.from(last.querySelectorAll('img'));
            return imgs[arguments[0]] || null;
        """, img_idx)

        if not img_el:
            raise Exception("img element not found at download time")

        # Method 1: element screenshot (fastest, no auth needed)
        try:
            img_el.screenshot(out)
            size = os.path.getsize(out)
            if size > 15000:
                _status(f"{tag}📸 Captured via screenshot ({size//1024}KB)")
                with open(out, "rb") as f:
                    data = f.read()
                return data, out
        except Exception as e:
            _status(f"{tag}⚠️ Screenshot failed ({e}) — trying fetch")

        # Method 2: browser fetch with credentials
        import base64 as _b64
        src = img_el.get_attribute("src") or ""
        if not src or src.startswith("blob:"):
            # For blob URLs, read as canvas data
            b64 = driver.execute_script("""
                const img = arguments[0];
                const c = document.createElement('canvas');
                c.width = img.naturalWidth; c.height = img.naturalHeight;
                c.getContext('2d').drawImage(img, 0, 0);
                return c.toDataURL('image/jpeg', 0.95).split(',')[1];
            """, img_el)
            if b64:
                data = _b64.b64decode(b64)
                with open(out, "wb") as f:
                    f.write(data)
                _status(f"{tag}🖼️ Captured via canvas ({len(data)//1024}KB)")
                return data, out

        b64 = driver.execute_script("""
            return new Promise(resolve=>{
                fetch(arguments[0], {credentials:'include'})
                    .then(r=>r.blob())
                    .then(b=>{const fr=new FileReader();fr.onload=()=>resolve(fr.result);fr.readAsDataURL(b);})
                    .catch(e=>resolve('ERROR:'+String(e)));
            });
        """, src)
        if not b64 or not b64.startswith("data:image"):
            raise Exception(f"Fetch failed: {str(b64)[:80]}")
        data = _b64.b64decode(b64.split(",", 1)[1])
        with open(out, "wb") as f:
            f.write(data)
        return data, out

    # ── Step 1: wait for stop button to disappear ─────────────────────────
    gen_status = _wait_for_generation(driver, time.time() + 420, tag)

    if gen_status == "deadline":
        err = f"JOB:{_jid} — timed out waiting for ChatGPT to finish generating"
        _status(f"{tag}❌ {err}")
        return {"label": label, "output": None, "error": err}

    def _click_regenerate():
        """Click the regenerate (↻) button under the last assistant message. Returns True if clicked."""
        try:
            clicked = driver.execute_script("""
                // Try aria-label first
                const byLabel = Array.from(document.querySelectorAll('button')).find(b =>
                    /regenerate|retry|try again/i.test(b.getAttribute('aria-label') || '') ||
                    /regenerate|retry/i.test(b.getAttribute('data-testid') || '')
                );
                if (byLabel) { byLabel.click(); return 'aria-label'; }

                // Fall back: last assistant message toolbar — find circular-arrow SVG button
                const msgs = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
                if (!msgs.length) return null;
                const last = msgs[msgs.length - 1];
                // The toolbar sits just after the message container
                const toolbar = last.closest('[data-message-id]')?.nextElementSibling
                             || last.parentElement?.nextElementSibling
                             || last.nextElementSibling;
                if (toolbar) {
                    const btns = Array.from(toolbar.querySelectorAll('button'));
                    // Regenerate is usually the 5th button (copy/like/dislike/share/regen)
                    // More reliably: it has an SVG with a circular path
                    const regen = btns.find(b => {
                        const svg = b.querySelector('svg');
                        if (!svg) return false;
                        const d = svg.innerHTML || '';
                        return d.includes('M4') || d.includes('rotate') || b.title?.toLowerCase().includes('regen');
                    }) || btns[4];
                    if (regen) { regen.click(); return 'toolbar-btn'; }
                }
                return null;
            """)
            return bool(clicked)
        except Exception:
            return False

    # ── Step 2: check for fast-fail / rate-limit text response ───────────
    time.sleep(2)
    try:
        check = _safe_js(driver, """
            const body = (document.body.innerText || '').toLowerCase();
            const msgs = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
            const last = msgs.length ? (msgs[msgs.length-1].innerText || '').toLowerCase() : '';
            const text = last || body;
            const failed = [
                "can't perform", "cannot perform",
                "editing tool isn't", "editing tool is failing",
                "unable to generate", "i can't generate",
                "failing to attach", "tool is not", "tool isn't",
                "i'm unable", "i am unable", "doesn't support", "does not support"
            ].some(p => text.includes(p));
            const rateLimit = [
                "too many requests", "rate limit", "please slow down",
                "try again in", "you've sent too many", "slow down"
            ].some(p => body.includes(p));
            return {failed, rateLimit};
        """) or {}

        if check.get("rateLimit"):
            _status(f"{tag}⚠️ Rate limited — using slot scheduler to wait precisely")
            waited = slot_wait_if_needed(status_fn=lambda m: _status(f"{tag}{m}"))
            if waited == 0:
                time.sleep(60)
            # Force fresh chat on retry — rate limit may have stale context
            _chat_pair_count = CHAT_ROTATE_EVERY
            _status(f"{tag}🔁 Slot available — retrying with fresh chat")
            return {"label": label, "output": None, "error": "RATE_LIMIT"}

        if check.get("failed"):
            _status(f"{tag}🔁 Tool failure — clicking regenerate")
            if not label:
                label = _read_label()
            if _click_regenerate():
                time.sleep(2)
                _wait_for_generation(driver, time.time() + 300, tag)
                time.sleep(2)
    except Exception:
        pass

    # ── Step 3: find generated image URL ─────────────────────────────────
    from selenium.webdriver.common.by import By
    _status(f"{tag}⏳ Scanning for image (up to 90s)… page={driver.current_url[-50:]}")
    img_src = None

    for tick in range(90):
        try:
            # Use Selenium Python API — more reliable than JS queries
            all_imgs = driver.find_elements(By.TAG_NAME, "img")

            # Log all on first tick
            if tick == 0:
                for el in all_imgs:
                    try:
                        s = el.get_attribute("src") or el.get_attribute("currentSrc") or ""
                        sz = el.size
                        _status(f"{tag}   [{sz['width']}x{sz['height']}] {s[:100]}")
                    except Exception:
                        pass

            # Only consider images that didn't exist before the prompt was sent
            new_imgs = []
            for el in all_imgs:
                try:
                    s = el.get_attribute("src") or el.get_attribute("currentSrc") or ""
                    if s and s not in _existing_srcs:
                        new_imgs.append((s, el))
                except Exception:
                    pass

            # Priority 1: new oaiusercontent URL (generated image CDN)
            for s, el in new_imgs:
                if "oaiusercontent" in s or "files.openai" in s:
                    img_src = s
                    _status(f"{tag}🖼️ New oaiusercontent after {tick}s: {s[:100]}")
                    break
            if img_src:
                break

            # Priority 2: largest NEW image rendered > 200px
            best_src, best_area = None, 0
            for s, el in new_imgs:
                if not s or "svg" in s or "favicon" in s or "avatar" in s:
                    continue
                try:
                    sz = el.size
                    w, h = sz.get("width", 0), sz.get("height", 0)
                    if w > 200 and h > 200 and w * h > best_area:
                        best_area = w * h
                        best_src = s
                except Exception:
                    pass
            if best_src:
                img_src = best_src
                _status(f"{tag}🖼️ Largest new img after {tick}s ({best_area}px²): {best_src[:100]}")
                break

        except Exception as e:
            _status(f"{tag}  err {tick}: {e}")
        time.sleep(1)

    if not img_src:
        err = f"JOB:{_jid} — image not found after 60s"
        _status(f"{tag}❌ {err}")
        return {"label": label, "output": None, "error": err}

    # ── Step 4: read label ────────────────────────────────────────────────
    if not label:
        label = _read_label()
        if label:
            _status(f"{tag}🏷️ Label: {label}")

    safe = re.sub(r'[/\\:*?"<>|]', '_', label or "studio")
    out  = os.path.join(OUTPUT, f"{safe}_chatgpt.png")

    # ── Step 5: download the image ────────────────────────────────────────
    import base64 as _b64

    # Method A: blob: URL → canvas toDataURL
    if img_src.startswith("blob:"):
        _status(f"{tag}⬇️ blob URL — reading via canvas…")
        b64 = driver.execute_script("""
            return new Promise(resolve => {
                const img = Array.from(document.querySelectorAll('img'))
                    .find(i => i.src === arguments[0] || i.currentSrc === arguments[0]);
                if (!img) { resolve(null); return; }
                const c = document.createElement('canvas');
                c.width  = img.naturalWidth  || 1024;
                c.height = img.naturalHeight || 1024;
                c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
                resolve(c.toDataURL('image/png').split(',')[1]);
            });
        """, img_src)
        if b64:
            data = _b64.b64decode(b64)
            with open(out, "wb") as f:
                f.write(data)
            _status(f"{tag}✓ Saved {label} via canvas ({len(data)//1024}KB)")
            return _finish(label, out)

    def _finish(lbl, path):
        """
        Called after every successful save.
        1. Deletes the current chat immediately (image verified, chat no longer needed).
        2. Checks for soft warning — signals 5-min cooldown if found.
        """
        # Delete chat right after confirmed save — keeps sidebar clean
        if _current_chat_url and "/c/" in _current_chat_url:
            _delete_chat(driver, _current_chat_url)

        warn = _detect_soft_warning(driver)
        if warn["warned"]:
            _status(f"{tag}⚠️ Warning detected: {warn['text'][:100]}")
            _status(f"{tag}✅ Pair saved — cooling 5 min before next")
            return {"label": lbl, "output": path, "error": None, "warn_cooldown": True}
        return {"label": lbl, "output": path, "error": None}

    # Method B: HTTP URL → Python requests with browser cookies
    _status(f"{tag}⬇️ Fetching image via requests…")
    try:
        import requests as _req
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}
        resp = _req.get(img_src, cookies=cookies, headers=headers, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 10000:
            with open(out, "wb") as f:
                f.write(resp.content)
            _status(f"{tag}✓ Saved {label} via requests ({len(resp.content)//1024}KB)")
            return _finish(label, out)
        _status(f"{tag}⚠️ requests got {resp.status_code} {len(resp.content)}B — trying browser fetch")
    except Exception as e:
        _status(f"{tag}⚠️ requests failed: {e} — trying browser fetch")

    # Method C: browser fetch (same origin, cookies automatic)
    b64 = driver.execute_script("""
        return new Promise(resolve => {
            fetch(arguments[0], {credentials: 'include'})
                .then(r => r.blob())
                .then(b => { const fr = new FileReader(); fr.onload = () => resolve(fr.result); fr.readAsDataURL(b); })
                .catch(e => resolve('ERR:' + e));
        });
    """, img_src)
    if b64 and b64.startswith("data:image"):
        data = _b64.b64decode(b64.split(",", 1)[1])
        with open(out, "wb") as f:
            f.write(data)
        _status(f"{tag}✓ Saved {label} via browser fetch ({len(data)//1024}KB)")
        return _finish(label, out)

    err = f"JOB:{_jid} — all download methods failed for {img_src[:60]}"
    _status(f"{tag}❌ {err}")
    return {"label": label, "output": None, "error": err}



if __name__ == "__main__":
    result = process(
        jewel_path = os.path.join(BASE, "processing", "001_jewel.jpeg"),
        tag_path   = os.path.join(BASE, "processing", "001_tag.jpeg"),
        bg_path    = os.path.join(BASE, "backgrounds", "earrings.png"),
    )
    print("\nResult:", result)
    if result.get("output"):
        print(f"Image saved: {result['output']}")
