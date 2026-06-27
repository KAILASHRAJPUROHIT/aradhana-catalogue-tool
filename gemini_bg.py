"""
Background Gemini automation — mirrors chatgpt_bg.py exactly.
- Connects to a second Chrome on port 9223 (separate profile)
- Uploads jewel + tag + background images
- Sends same extraction prompt
- Waits for image generation (stop button watch)
- Downloads result, deletes chat
- Runs in parallel with ChatGPT engine
"""
import sys, os, time, json, re, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

BASE    = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
OUTPUT  = os.path.join(BASE, "output_aradhana")
CHROME2 = r"C:\Users\kaila\AppData\Local\GeminiCatalogChrome"   # separate profile
PORT2   = 9223

# ── Rotation state ────────────────────────────────────────────────────────────
CHAT_ROTATE_EVERY    = 5
_chat_pair_count     = 0
_current_chat_url    = ""

# Injected by app.py
_JOB_DICT = None

def _status(msg):
    print(f"  [GEMINI] {msg}")
    if _JOB_DICT is not None:
        _JOB_DICT["current"] = msg

# ── Chrome helpers ────────────────────────────────────────────────────────────

def _safe_js(driver, script, timeout=5):
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(driver.execute_script, script)
        try:
            return fut.result(timeout=timeout)
        except Exception:
            return None

def _ensure_chrome2():
    """Launch Gemini-dedicated Chrome on port 9223, then move it to catalogue desktop."""
    import socket as _s, subprocess
    try:
        c = _s.create_connection(("127.0.0.1", PORT2), timeout=2)
        c.close()
        return True
    except OSError:
        pass
    _status("🚀 Starting Gemini Chrome (port 9223)…")
    os.makedirs(CHROME2, exist_ok=True)
    subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        f"--remote-debugging-port={PORT2}",
        f"--user-data-dir={CHROME2}",
        "--no-first-run", "--no-default-browser-check",
        "--homepage=https://gemini.google.com/app",
        "https://gemini.google.com/app",
    ])
    time.sleep(6)
    try:
        import vdesk
        vdesk.push_chrome_to_catalogue_desktop()
    except Exception as e:
        _status(f"vdesk: {e}")
    return False

def connect():
    _ensure_chrome2()
    from selenium.webdriver.chrome.service import Service
    _cd = os.path.join(BASE, "chromedriver.exe")
    _svc = Service(_cd) if os.path.exists(_cd) else None
    for attempt in range(1, 4):
        try:
            opts = Options()
            opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{PORT2}")
            drv = webdriver.Chrome(service=_svc, options=opts) if _svc else webdriver.Chrome(options=opts)
            _ = drv.window_handles
            return drv
        except Exception:
            if attempt == 2: _ensure_chrome2()
            time.sleep(3)
    raise RuntimeError("Gemini Chrome unreachable")

def _chrome_to_background():
    try:
        import ctypes, ctypes.wintypes
        u32 = ctypes.windll.user32
        HWND_BOTTOM = ctypes.wintypes.HWND(1)
        SWP = 0x0002 | 0x0001 | 0x0010
        found = []
        def _cb(h, _):
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(h, buf, 256)
            if "chrome" in buf.value.lower() or "gemini" in buf.value.lower():
                found.append(h)
            return True
        u32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND,
                                           ctypes.wintypes.LPARAM)(_cb), 0)
        for h in found:
            u32.SetWindowPos(h, HWND_BOTTOM, 0, 0, 0, 0, SWP)
    except Exception:
        pass

def _chrome_to_foreground():
    try:
        import ctypes, ctypes.wintypes
        u32 = ctypes.windll.user32
        found = []
        def _cb(h, _):
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(h, buf, 256)
            if "chrome" in buf.value.lower() or "gemini" in buf.value.lower():
                found.append(h)
            return True
        u32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND,
                                           ctypes.wintypes.LPARAM)(_cb), 0)
        for h in found:
            u32.ShowWindow(h, 9)
            u32.SetForegroundWindow(h)
    except Exception:
        pass

# ── Login check ───────────────────────────────────────────────────────────────

def _is_logged_in(driver):
    try:
        url  = (driver.current_url or "").lower()
        body = _safe_js(driver, "return document.body.innerText.substring(0,400);") or ""
        if "accounts.google.com" in url or "signin" in url:
            return False
        if any(p in body.lower() for p in ["sign in", "log in", "get started with google"]):
            return False
        return True
    except Exception:
        return False

def _ensure_logged_in(driver):
    if _is_logged_in(driver):
        return True
    _status("🔑 Gemini session expired — please log in. Batch paused.")
    _chrome_to_foreground()
    for tick in range(600):
        time.sleep(1)
        if tick % 15 == 0:
            _status(f"🔑 Waiting for Gemini login… ({600-tick}s)")
        if _is_logged_in(driver):
            _status("✅ Logged in to Gemini — resuming")
            time.sleep(2)
            return True
    _status("❌ Gemini login timeout")
    return False

# ── Chat deletion ─────────────────────────────────────────────────────────────

def _delete_chat(driver, chat_url):
    """Delete a Gemini conversation via its internal API."""
    if not chat_url or "/app/" not in chat_url:
        return False
    try:
        # Gemini chat IDs appear as /app/{id}
        conv_id = chat_url.rstrip("/").split("/app/")[-1].split("?")[0]
        if not conv_id:
            return False
        result = _safe_js(driver, f"""
            return new Promise(resolve => {{
                fetch('/api/conversations/{conv_id}', {{
                    method: 'DELETE',
                    credentials: 'include'
                }})
                .then(r => resolve(r.ok ? 'deleted' : 'err:' + r.status))
                .catch(e => resolve('err:' + e));
            }});
        """, timeout=10)
        if result == "deleted":
            _status(f"🗑 Gemini chat deleted: ...{conv_id[-8:]}")
            return True
        # Fallback: use the 3-dot menu in the sidebar
        _delete_chat_ui(driver)
        return True
    except Exception as e:
        _status(f"⚠ Gemini delete error: {e}")
        return False

def _delete_chat_ui(driver):
    """Fallback: delete via Gemini sidebar UI."""
    try:
        # Find the active chat in sidebar, click three-dots, click delete
        driver.execute_script("""
            const active = document.querySelector('[aria-selected="true"], .conversation-item.active, [class*="selected"]');
            if (active) {
                const more = active.querySelector('[aria-label*="more"], [aria-label*="option"], button[class*="more"]');
                if (more) more.click();
            }
        """)
        time.sleep(0.5)
        driver.execute_script("""
            const items = Array.from(document.querySelectorAll('[role="menuitem"], [class*="menu-item"]'));
            const del = items.find(i => /delete|remove/i.test(i.textContent));
            if (del) del.click();
        """)
        time.sleep(0.5)
        # Confirm dialog
        driver.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const confirm = btns.find(b => /delete|confirm|yes/i.test(b.textContent));
            if (confirm) confirm.click();
        """)
    except Exception:
        pass

# ── Stop button detection (Gemini uses different aria-labels) ─────────────────

_STOP_JS = """
    // Gemini shows a square stop icon button while generating
    // Check buttons, also check for loading spinner / progress indicators
    const stopBtn = Array.from(document.querySelectorAll('button')).some(b => {
        const l = (b.getAttribute('aria-label') || b.getAttribute('data-tooltip') ||
                   b.textContent || '').toLowerCase().trim();
        return l === 'stop' || l === 'stop generating' || l.includes('stop response') ||
               l.includes('cancel') || l === 'stop generation';
    });
    if (stopBtn) return true;
    // Also check for loading indicators (spinner, progress)
    const loading = document.querySelector(
        '.loading-indicator, [class*="loading"], [class*="spinner"], ' +
        'mat-progress-spinner, [class*="generating"], [aria-label*="loading"]'
    );
    return !!loading;
"""

def _wait_for_generation(driver, deadline, tag="[G]"):
    # Phase 1: wait for stop button to appear
    appeared = False
    appear_by = time.time() + 45
    while time.time() < min(appear_by, deadline):
        time.sleep(1)
        vis = _safe_js(driver, _STOP_JS)
        if vis:
            appeared = True
            _status(f"{tag}⬛ Gemini generating…")
            break
    if not appeared:
        _status(f"{tag}⏳ No stop button seen — checking for result")
        return "maybe_done"

    # Phase 2: wait for stop to disappear
    gen_start = time.time()
    consecutive_fails = 0
    while time.time() < deadline:
        time.sleep(1)
        vis = _safe_js(driver, _STOP_JS)
        if vis is None:
            consecutive_fails += 1
            if consecutive_fails >= 5:
                _status(f"{tag}🔄 Chrome hung — aborting")
                return "deadline"
            continue
        consecutive_fails = 0
        waited = int(time.time() - gen_start)
        if waited > 0 and waited % 15 == 0:
            _status(f"{tag}⬛ Generating… {waited}s")
        if not vis:
            _status(f"{tag}✅ Done ({waited}s)")
            return "done"
        if waited > 300:
            return "reload"
    return "deadline"

# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(category, job_id, filename=""):
    label = category.replace("_", " ").title()
    prefix = f"{filename} | " if filename else f"{job_id} | "
    return (
        f"{prefix}"
        f"JOB:{job_id} — "
        f"Task: extract the {label} jewellery from image 1 and place it on the background in image 3. "
        "CRITICAL OUTPUT RULES — any violation = failure: "
        "1. NO display stand of any kind in the output. "
        "2. NO price tags, labels, or paper in the output. "
        "3. NO jewellery holder, prop, or display fixture in the output. "
        "4. Output must show ONLY the bare metal jewellery pieces on the background. "
        "5. Do NOT redraw — preserve exact design, colour, and finish from the photo. "
        "6. If a pair: both pieces perfectly straight, symmetrical, evenly spaced. "
        "7. Professional studio lighting on the background from image 3. "
        "8. NO text, numbers, or watermarks anywhere on the output image. "
        "9. OUTPUT QUALITY: render at maximum resolution — ultra-sharp, crisp edges on every "
        "detail of the jewellery, deep metallic lustre, gem colours vivid and accurate. "
        "The final image must look like a professional luxury jewellery photoshoot — "
        "magazine-grade sharpness, no blur, no soft focus, no noise. "
        f"Reply starting with: JOB:{job_id} LABEL: followed by the actual code from the tag in image 2"
    )

# ── Make images unique (prevent deduplication) ───────────────────────────────

def make_unique(src):
    from PIL import Image, ImageDraw
    import random, tempfile
    img = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, 2, 2], fill=(random.randint(200,255), 0, 0))
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(tmp.name, "JPEG", quality=95)
    return tmp.name

# ── Clipboard helpers ─────────────────────────────────────────────────────────

def _copy_img_clipboard(img_path):
    """
    Copy image to Windows clipboard in PNG format.
    Chrome reads the registered 'PNG' clipboard format — much more reliable
    than CF_DIB (BMP) which can render as a grey square in browser inputs.
    """
    import win32clipboard, io as _io
    from PIL import Image as _I

    img = _I.open(img_path).convert("RGB")
    buf = _io.BytesIO()
    img.save(buf, "PNG")
    png_data = buf.getvalue()

    # Register "PNG" as a clipboard format — Chrome prioritises this
    PNG_FORMAT = win32clipboard.RegisterClipboardFormat("PNG")

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(PNG_FORMAT, png_data)
    win32clipboard.CloseClipboard()


# ── Main process function ─────────────────────────────────────────────────────

def process(jewel_path, tag_path, bg_path, category="earrings",
            pair_num=None, job_id=None):
    import pyperclip, base64 as _b64, requests as _req
    global _current_chat_url
    tag = f"[G:{pair_num}] " if pair_num else "[G] "

    driver = connect()

    # ── 1. Navigate to a fresh Gemini chat every single time ─────────────────
    # No rotation, no reuse — each pair gets a clean blank chat.
    # Gemini generates in 3-8s so the 2s navigation cost is negligible.
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "gemini.google.com" in driver.current_url:
            break
    else:
        driver.switch_to.window(driver.window_handles[0])

    # Navigate to fresh chat first — THEN delete the old one in background
    # so deletion never blocks or navigates away from our new chat
    _prev_chat_url = _current_chat_url
    _current_chat_url = ""

    _status(f"{tag}💬 Opening fresh Gemini chat")
    driver.get("https://gemini.google.com/app")
    time.sleep(2.5)

    # Delete previous chat now that we're safely on a new page
    if _prev_chat_url:
        _delete_chat(driver, _prev_chat_url)

    if not _ensure_logged_in(driver):
        return {"label": None, "output": None, "error": "Gemini: not logged in"}

    # ── 2. Wait for input to be ready ────────────────────────────────────────
    input_el = None
    for _ in range(10):
        input_el = driver.execute_script("""
            const rt = document.querySelector('rich-textarea');
            if (rt) return rt.querySelector('[contenteditable="true"]');
            return null;
        """)
        if input_el:
            break
        time.sleep(0.5)

    if not input_el:
        return {"label": None, "output": None, "error": "Gemini: input not ready"}

    # ── 3. Paste 3 images one by one, verify each before moving on ───────────
    _status(f"{tag}📋 Pasting 3 images — waiting for each thumbnail")
    input_el.click()
    time.sleep(0.5)

    def _count_thumbnails():
        """Count image thumbnails currently visible in the Gemini input area."""
        try:
            return driver.execute_script("""
                // Thumbnails appear as img tags inside the input container
                const input = document.querySelector('rich-textarea') ||
                              document.querySelector('[class*="input"]');
                if (!input) return 0;
                return input.querySelectorAll('img').length;
            """) or 0
        except Exception:
            return 0

    pasted_count = 0
    for idx, img_path in enumerate([jewel_path, tag_path, bg_path], 1):
        before = _count_thumbnails()
        _copy_img_clipboard(img_path)
        time.sleep(0.4)

        # Keep focus on input and paste
        input_el.click()
        time.sleep(0.2)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()

        # Wait up to 5s for the thumbnail to appear
        for _ in range(10):
            time.sleep(0.5)
            after = _count_thumbnails()
            if after > before:
                pasted_count += 1
                _status(f"{tag}  ✓ image {idx}/3 confirmed ({after} thumbnails)")
                break
        else:
            _status(f"{tag}  ⚠ image {idx}/3 thumbnail not confirmed — continuing")

        time.sleep(0.3)

    if pasted_count < 3:
        _status(f"{tag}  ⚠ Only {pasted_count}/3 images confirmed — still sending")

    # ── 4. Paste prompt text ─────────────────────────────────────────────────
    _filename = os.path.splitext(os.path.basename(jewel_path))[0]
    _jid = job_id or re.sub(r"[^A-Za-z0-9]", "", _filename)[:12]
    prompt = build_prompt(category, _jid, filename=_filename)

    # Keep focus and paste text
    input_el.click()
    time.sleep(0.3)
    pyperclip.copy(prompt)
    time.sleep(0.2)
    ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
    time.sleep(0.5)

    # Verify prompt appeared
    txt_check = driver.execute_script("""
        const rt = document.querySelector('rich-textarea');
        return rt ? rt.innerText : '';
    """) or ""
    if len(txt_check.strip()) < 10:
        _status(f"{tag}  ⚠ Prompt not visible — trying send_keys")
        input_el.click()
        input_el.send_keys(prompt)
        time.sleep(0.3)

    _status(f"{tag}📝 {pasted_count}/3 images + prompt ready — sending now")

    # ── 5. Snapshot all current images BEFORE sending ─────────────────────────
    pre_srcs = set()
    try:
        pre_srcs = set(driver.execute_script(
            "return Array.from(document.querySelectorAll('img'))"
            ".map(i=>i.src||'').filter(s=>s);"
        ) or [])
    except Exception:
        pass

    # ── 6. ONLY NOW send — after all images + prompt confirmed ────────────────
    time.sleep(0.3)   # brief pause to make sure Gemini has processed everything
    sent = driver.execute_script("""
        const btn = Array.from(document.querySelectorAll('button')).find(b =>
            /send/i.test(b.getAttribute('aria-label') || b.title || ''));
        if (btn && !btn.disabled) { btn.click(); return true; }
        return false;
    """)
    if not sent:
        input_el.send_keys(Keys.RETURN)
    _status(f"{tag}📤 Sent — polling every second for result")

    # Save chat URL for later deletion
    time.sleep(1)
    try:
        if "/app/" in driver.current_url:
            _current_chat_url = driver.current_url
    except Exception:
        pass

    _chrome_to_background()

    # ── 7. Per-second polling for generated image ─────────────────────────────
    # Gemini typically finishes in 3-15 seconds.
    # We poll every second looking for a NEW large image that wasn't in pre_srcs.
    label   = None
    img_src = None
    start   = time.time()

    for tick in range(120):  # up to 2 minutes
        time.sleep(1)
        try:
            driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
            all_imgs = driver.find_elements(By.TAG_NAME, "img")
            best_src, best_area = None, 0
            for el in all_imgs:
                try:
                    s = el.get_attribute("src") or ""
                    if not s or s in pre_srcs:
                        continue
                    if "svg" in s or "favicon" in s or "avatar" in s or "thumbnail" in s:
                        continue
                    sz = el.size
                    w, h = sz.get("width", 0), sz.get("height", 0)
                    if w < 150 or h < 150:
                        continue
                    if w * h > best_area:
                        best_area = w * h
                        best_src  = s
                except Exception:
                    pass
            if best_src:
                img_src = best_src
                _status(f"{tag}⚡ Image found at {tick+1}s ({int(best_area**0.5)}px): {best_src[:80]}")
                break
            if tick % 10 == 9:
                _status(f"{tag}⏳ Still generating… {tick+1}s")
        except Exception as e:
            _status(f"{tag}  tick {tick}: {e}")

    if not img_src:
        return {"label": None, "output": None, "error": "Gemini: image not found in 2 minutes"}

    # ── 8. Read label from response ───────────────────────────────────────────
    try:
        txt = driver.execute_script("return document.body.innerText;") or ""
        m = re.search(r"LABEL[:\s]+([A-Z0-9][A-Z0-9/_-]{1,18})", txt, re.I)
        if m and " " not in m.group(1):
            label = m.group(1).strip()
            _status(f"{tag}🏷️ {label}")
    except Exception:
        pass

    # ── 9. Download the image ─────────────────────────────────────────────────
    safe = re.sub(r'[/\\:*?"<>|]', '_', label or "studio")
    out  = os.path.join(OUTPUT, f"{safe}_gemini.png")

    # ── Download — NO navigation or deletion here ─────────────────────────────
    # The next process() call navigates to /app fresh anyway, so deleting
    # the chat here just causes an unwanted reload. Skip it.

    # Method A: Python requests with session cookies
    try:
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        ua      = driver.execute_script("return navigator.userAgent;")
        resp    = _req.get(img_src, cookies=cookies,
                           headers={"User-Agent": ua}, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 5000:
            with open(out, "wb") as f: f.write(resp.content)
            _status(f"{tag}✓ {label} saved ({len(resp.content)//1024}KB)")
            return {"label": label, "output": out, "error": None}
        _status(f"{tag}  requests: {resp.status_code} — trying canvas")
    except Exception as e:
        _status(f"{tag}  requests failed: {e} — trying canvas")

    # Method B: canvas toDataURL
    escaped = img_src.replace("'", "\\'")
    b64 = driver.execute_script(f"""
        return new Promise(resolve => {{
            const img = Array.from(document.querySelectorAll('img'))
                .find(i => i.src === '{escaped}' || i.currentSrc === '{escaped}');
            if (!img) {{ resolve(null); return; }}
            const c = document.createElement('canvas');
            c.width  = img.naturalWidth  || img.offsetWidth  || 1024;
            c.height = img.naturalHeight || img.offsetHeight || 1024;
            c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
            resolve(c.toDataURL('image/png').split(',')[1]);
        }});
    """)
    if b64:
        data = _b64.b64decode(b64)
        with open(out, "wb") as f: f.write(data)
        _status(f"{tag}✓ {label} saved via canvas ({len(data)//1024}KB)")
        return {"label": label, "output": out, "error": None}

    # Method C: browser fetch
    b64 = driver.execute_script("""
        return new Promise(resolve => {
            fetch(arguments[0], {credentials:'include'})
                .then(r=>r.blob())
                .then(b=>{const fr=new FileReader();
                          fr.onload=()=>resolve(fr.result);
                          fr.readAsDataURL(b);})
                .catch(()=>resolve(null));
        });
    """, img_src)
    if b64 and b64.startswith("data:image"):
        data = _b64.b64decode(b64.split(",", 1)[1])
        with open(out, "wb") as f: f.write(data)
        _status(f"{tag}✓ {label} saved via fetch ({len(data)//1024}KB)")
        return {"label": label, "output": out, "error": None}

    return {"label": label, "output": None,
            "error": f"Gemini: all download methods failed for {img_src[:60]}"}

    return {"label": label, "output": None, "error": "Gemini: all download methods failed"}
