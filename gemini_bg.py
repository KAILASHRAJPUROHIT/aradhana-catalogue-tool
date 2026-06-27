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
    """Auto-launch second Chrome on port 9223 if not running."""
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
        "--no-first-run", "--no-default-browser-check"
    ])
    time.sleep(6)
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

# ── Main process function ─────────────────────────────────────────────────────

def process(jewel_path, tag_path, bg_path, category="earrings",
            pair_num=None, job_id=None):
    global _chat_pair_count, _current_chat_url
    tag = f"[G:{pair_num}] " if pair_num else "[G] "

    driver = connect()

    # Switch to Gemini window/tab
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "gemini" in driver.current_url.lower() or "google" in driver.current_url.lower():
            break
    else:
        driver.switch_to.window(driver.window_handles[0])

    # Chat rotation
    need_new = (
        _chat_pair_count == 0
        or _chat_pair_count >= CHAT_ROTATE_EVERY
        or not _current_chat_url
    )
    if need_new:
        if _current_chat_url:
            _delete_chat(driver, _current_chat_url)
            _current_chat_url = ""
        _status(f"{tag}💬 New Gemini chat")
        driver.get("https://gemini.google.com/app")
        time.sleep(3)
        _chat_pair_count = 0
    else:
        _status(f"{tag}💬 Reusing Gemini chat ({_chat_pair_count}/{CHAT_ROTATE_EVERY})")
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
        except Exception:
            pass

    if not _ensure_logged_in(driver):
        return {"label": None, "output": None, "error": "Gemini login timeout"}

    # Build prompt + unique images
    _filename = os.path.splitext(os.path.basename(jewel_path))[0]
    _jid = job_id or re.sub(r"[^A-Za-z0-9]", "", _filename)[:12]
    prompt = build_prompt(category, _jid, filename=_filename)
    files  = [make_unique(p) for p in [jewel_path, tag_path, bg_path]]

    _status(f"{tag}📎 Uploading images to Gemini")

    try:
        # ── Step 1: Upload files ──────────────────────────────────────────
        # Gemini's + button opens a menu → click "Upload file" → file input appears
        all_paths = "\n".join(os.path.abspath(f) for f in files)

        def _try_file_input():
            """Find any file input and send paths. Returns True on success."""
            inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            for fi in inputs:
                try:
                    driver.execute_script("""
                        arguments[0].style.cssText =
                            'display:block!important;visibility:visible!important;opacity:1!important;';
                    """, fi)
                    fi.send_keys(all_paths)
                    return True
                except Exception:
                    continue
            return False

        uploaded = False

        # Method 1: direct file input (sometimes already accessible)
        if _try_file_input():
            uploaded = True
            _status(f"{tag}  files uploaded via direct input")
            time.sleep(2)

        if not uploaded:
            # Method 2: click + button → wait for menu → click upload option
            _status(f"{tag}  clicking + to open upload menu")
            driver.execute_script("""
                // + button has aria-label like "Add more" or just shows "+"
                const btn = Array.from(document.querySelectorAll('button')).find(b => {
                    const l = (b.getAttribute('aria-label') || b.textContent || '').trim();
                    return l === '+' || /^add/i.test(l) || /more options/i.test(l);
                });
                if (btn) btn.click();
            """)
            time.sleep(1.2)

            # Click upload/image option in the menu
            driver.execute_script("""
                const items = Array.from(document.querySelectorAll(
                    '[role="menuitem"], [role="option"], button, li'));
                const upload = items.find(el => {
                    const t = (el.textContent || el.getAttribute('aria-label') || '').toLowerCase();
                    return t.includes('upload') || t.includes('image') || t.includes('photo') ||
                           t.includes('file') || t.includes('computer');
                });
                if (upload) upload.click();
            """)
            time.sleep(1)

            if _try_file_input():
                uploaded = True
                _status(f"{tag}  files uploaded via menu")
                time.sleep(2)

        if not uploaded:
            _status(f"{tag}⚠️ Could not upload files — prompt only")

        # ── Step 2: Find the text input ───────────────────────────────────
        # Gemini uses <rich-textarea> web component with inner contenteditable div
        # or a plain textarea. Try multiple approaches.
        input_el = None

        # Primary: rich-textarea inner div (Gemini's custom component)
        try:
            input_el = driver.execute_script("""
                // Try rich-textarea first (Gemini's custom component)
                const rt = document.querySelector('rich-textarea');
                if (rt) {
                    const inner = rt.querySelector('[contenteditable="true"]') ||
                                  rt.shadowRoot?.querySelector('[contenteditable="true"]');
                    if (inner) return inner;
                }
                // Fallback: any visible contenteditable
                const ce = Array.from(document.querySelectorAll('[contenteditable="true"]'))
                    .find(el => el.offsetParent !== null && el.offsetWidth > 100);
                if (ce) return ce;
                // Last resort: textarea
                return document.querySelector('textarea');
            """)
        except Exception:
            pass

        if not input_el:
            raise Exception("Gemini input box not found")

        _status(f"{tag}  input found — injecting prompt")

        # ── Step 3: Inject prompt text ────────────────────────────────────
        # Use JavaScript execCommand for reliable text insertion into contenteditable
        driver.execute_script("arguments[0].focus();", input_el)
        time.sleep(0.3)

        # Try execCommand first (most reliable for contenteditable)
        injected = driver.execute_script("""
            arguments[0].focus();
            const success = document.execCommand('insertText', false, arguments[1]);
            if (!success) {
                // Fallback: dispatch input events manually
                arguments[0].textContent = arguments[1];
                arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
                arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
            }
            return arguments[0].textContent.length;
        """, input_el, prompt)
        _status(f"{tag}  prompt injected ({injected} chars)")
        time.sleep(0.5)

        # If execCommand failed (returned 0 length), try ActionChains
        if not injected:
            _status(f"{tag}  execCommand failed — using ActionChains")
            ActionChains(driver).move_to_element(input_el).click().send_keys(prompt).perform()
            time.sleep(0.5)

        # ── Step 4: Snapshot existing images before sending ───────────────
        try:
            _existing_srcs = set(driver.execute_script("""
                return Array.from(document.querySelectorAll('img'))
                    .map(i => i.src || i.currentSrc || '')
                    .filter(s => s.length > 0);
            """) or [])
        except Exception:
            _existing_srcs = set()

        # ── Step 5: Send the message ──────────────────────────────────────
        sent = driver.execute_script("""
            // Try send button by aria-label
            const byLabel = Array.from(document.querySelectorAll('button')).find(b => {
                const l = (b.getAttribute('aria-label') || b.title || '').toLowerCase();
                return l.includes('send') || l.includes('submit') || l === 'send message';
            });
            if (byLabel && !byLabel.disabled) { byLabel.click(); return 'aria-label'; }

            // Try send button by data-testid or mat-icon-button
            const matSend = document.querySelector('button[data-mat-icon-name="send"], button.send-button, button[jsname]');
            if (matSend && !matSend.disabled) { matSend.click(); return 'mat'; }

            return null;
        """)

        if not sent:
            _status(f"{tag}  no send button found — pressing Enter")
            input_el.send_keys(Keys.RETURN)
        else:
            _status(f"{tag}  sent via {sent}")

        _chat_pair_count += 1
        time.sleep(1)
        try:
            cur = driver.current_url
            if "/app/" in cur:
                _current_chat_url = cur
        except Exception:
            pass

    except Exception as e:
        _status(f"{tag}⚠️ Send error: {e}")

    # Snapshot after send for dedup
    try:
        _existing_srcs = set(driver.execute_script("""
            return Array.from(document.querySelectorAll('img'))
                .map(i => i.src || i.currentSrc || '')
                .filter(s => s.length > 0);
        """) or [])
    except Exception:
        _existing_srcs = set()

    # Push Chrome to background
    _chrome_to_background()
    _status(f"{tag}⏳ Prompt sent — Gemini generating")
    time.sleep(1)

    label = None

    def _quick_scan_for_image(timeout=15):
        """
        Fast-path scan: Gemini often completes in 3-8 seconds.
        Polls every second for a new image before falling back to stop-button watch.
        """
        for t in range(timeout):
            time.sleep(1)
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                all_imgs = driver.find_elements(By.TAG_NAME, "img")
                for el in all_imgs:
                    try:
                        s = el.get_attribute("src") or el.get_attribute("currentSrc") or ""
                        if not s or s in _existing_srcs:
                            continue
                        sz = el.size
                        w, h = sz.get("width", 0), sz.get("height", 0)
                        if w > 100 and h > 100:
                            _status(f"{tag}⚡ Fast image found at {t}s: {s[:80]}")
                            return s
                    except Exception:
                        pass
            except Exception:
                pass
        return None

    # Fast path — check if Gemini already finished (it's often done in <10s)
    fast_result = _quick_scan_for_image(timeout=12)
    if fast_result:
        img_src = fast_result
    else:
        # Full stop-button watch for slower responses
        gen_status = _wait_for_generation(driver, time.time() + 420, tag)
        if gen_status == "deadline":
            return {"label": label, "output": None, "error": "Gemini timed out"}
        img_src = None   # will be set in scan loop below

    # Check for error response
    time.sleep(2)
    try:
        page_text = (_safe_js(driver, "return document.body.innerText;") or "").lower()
        if any(p in page_text for p in ["can't help", "cannot help", "unable to", "i'm not able"]):
            _status(f"{tag}⚠️ Gemini refused — may need regenerate")
    except Exception:
        pass

    # Scan for new image (same approach as ChatGPT)
    if not img_src:
        _status(f"{tag}🔍 Scanning for generated image…")

    for tick in range(90):
        if img_src:
            break
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.3)

            # Log all new images on first tick for debugging
            if tick == 0:
                all_srcs = driver.execute_script("""
                    return Array.from(document.querySelectorAll('img'))
                        .map(i => ({src: (i.src||'').substring(0,100),
                                    w: i.offsetWidth, h: i.offsetHeight}));
                """) or []
                for info in all_srcs:
                    if info.get("src") and info.get("w", 0) > 50:
                        _status(f"{tag}   img {info['w']}x{info['h']}: {info['src']}")

            all_imgs = driver.find_elements(By.TAG_NAME, "img")
            new_imgs = []
            for el in all_imgs:
                try:
                    s = el.get_attribute("src") or el.get_attribute("currentSrc") or ""
                    if s and s not in _existing_srcs:
                        new_imgs.append((s, el))
                except Exception:
                    pass

            # Priority 1: Google-hosted generated image URLs
            GEMINI_CDN = ["googleusercontent.com", "lh3.google", "lh4.google",
                          "lh5.google", "lh6.google", "gstatic.com/images"]
            for s, el in new_imgs:
                if any(p in s for p in GEMINI_CDN):
                    try:
                        sz = el.size
                        if sz.get("width", 0) > 100 and sz.get("height", 0) > 100:
                            img_src = s
                            _status(f"{tag}🖼️ Google CDN image after {tick}s: {s[:100]}")
                            break
                    except Exception:
                        pass
            if img_src:
                break

            # Priority 2: blob: URL large on screen (Gemini sometimes uses blob)
            for s, el in new_imgs:
                if s.startswith("blob:"):
                    try:
                        sz = el.size
                        if sz.get("width", 0) > 200 and sz.get("height", 0) > 200:
                            img_src = s
                            _status(f"{tag}🖼️ Blob image after {tick}s ({sz['width']}x{sz['height']})")
                            break
                    except Exception:
                        pass
            if img_src:
                break

            # Priority 3: largest new img regardless of URL
            best_src, best_area = None, 0
            for s, el in new_imgs:
                if not s or "svg" in s or "favicon" in s or "avatar" in s:
                    continue
                try:
                    sz = el.size
                    w, h = sz.get("width", 0), sz.get("height", 0)
                    if w > 150 and h > 150 and w * h > best_area:
                        best_area = w * h
                        best_src = s
                except Exception:
                    pass
            if best_src:
                img_src = best_src
                _status(f"{tag}🖼️ Largest new img after {tick}s: {best_src[:100]}")
                break

        except Exception as e:
            _status(f"{tag}  scan {tick}: {e}")
        time.sleep(1)

    if not img_src:
        return {"label": label, "output": None, "error": "Gemini: image not found after 60s"}

    # Read label from response text
    try:
        msg_text = driver.execute_script("""
            const msgs = Array.from(document.querySelectorAll(
                '[class*="response"], [class*="message"], [class*="model-response"], message-content'));
            return msgs.length ? msgs[msgs.length-1].innerText : document.body.innerText;
        """) or ""
        m = re.search(r"LABEL[:\s]+([A-Z0-9][A-Z0-9/_-]{1,18})", msg_text, re.I)
        if m and " " not in m.group(1):
            label = m.group(1).strip().rstrip(".")
            _status(f"{tag}🏷️ Label: {label}")
    except Exception:
        pass

    # Download image
    import base64 as _b64
    safe = re.sub(r'[/\\:*?"<>|]', '_', label or "studio")
    out  = os.path.join(OUTPUT, f"{safe}_gemini.png")

    def _finish(lbl, path):
        if _current_chat_url:
            _delete_chat(driver, _current_chat_url)
        return {"label": lbl, "output": path, "error": None}

    # Method A: blob URL → canvas
    if img_src.startswith("blob:"):
        try:
            img_el = next((el for s, el in [(img_src, e) for _, e in
                          [(x, driver.find_element(By.XPATH, f'//img[@src="{img_src}"]'))
                           for x in [1]] if True] if True), None)
        except Exception:
            img_el = None
        b64 = _safe_js(driver, f"""
            return new Promise(resolve => {{
                const img = Array.from(document.querySelectorAll('img'))
                    .find(i => i.src === '{img_src}' || i.currentSrc === '{img_src}');
                if (!img) {{ resolve(null); return; }}
                const c = document.createElement('canvas');
                c.width = img.naturalWidth || 1024;
                c.height = img.naturalHeight || 1024;
                c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
                resolve(c.toDataURL('image/png').split(',')[1]);
            }});
        """, timeout=15)
        if b64:
            data = _b64.b64decode(b64)
            with open(out, "wb") as f: f.write(data)
            _status(f"{tag}✓ Saved {label} via canvas ({len(data)//1024}KB)")
            return _finish(label, out)

    # Method B: requests with cookies
    try:
        import requests as _req
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}
        resp = _req.get(img_src, cookies=cookies, headers=headers, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 10000:
            with open(out, "wb") as f: f.write(resp.content)
            _status(f"{tag}✓ Saved {label} via requests ({len(resp.content)//1024}KB)")
            return _finish(label, out)
    except Exception as e:
        _status(f"{tag}⚠️ requests: {e}")

    # Method C: browser fetch
    b64 = driver.execute_script("""
        return new Promise(resolve => {
            fetch(arguments[0], {credentials: 'include'})
                .then(r => r.blob())
                .then(b => { const fr = new FileReader();
                             fr.onload = () => resolve(fr.result);
                             fr.readAsDataURL(b); })
                .catch(e => resolve('ERR:' + e));
        });
    """, img_src)
    if b64 and b64.startswith("data:image"):
        data = _b64.b64decode(b64.split(",", 1)[1])
        with open(out, "wb") as f: f.write(data)
        _status(f"{tag}✓ Saved {label} via fetch ({len(data)//1024}KB)")
        return _finish(label, out)

    return {"label": label, "output": None, "error": "Gemini: all download methods failed"}
