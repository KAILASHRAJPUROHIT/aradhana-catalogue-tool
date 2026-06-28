"""
Auto Catalogue Tool — Aradhana Jewellers
Pipeline: input\ → ChatGPT (background) → output_aradhana\{category}\{label}.jpg
Server:   python app.py  →  http://127.0.0.1:9100
"""
import os, glob, re, shutil, threading, time, traceback
from flask import Flask, request, jsonify, send_from_directory, render_template
import chatgpt_bg
chatgpt_bg._JOB_DICT = None   # wired up after CGPT_JOB is defined below

BASE            = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
INPUT           = os.path.join(BASE, "input")
PROCESSING      = os.path.join(BASE, "processing")
OUTPUT          = os.path.join(BASE, "output_aradhana")
BACKGROUNDS_DIR = r"C:\Users\kaila\Desktop\Backgrounds\Watermarked"

for d in (INPUT, PROCESSING, OUTPUT, BACKGROUNDS_DIR):
    os.makedirs(d, exist_ok=True)

TYPES = [
    "earrings","ladies_rings","gents_rings",
    "ladies_chains","gents_chains",
    "ladies_bracelet","gents_bracelet",
    "ladies_kada","gents_kada",
    "locket","pendant","tops","wati",
    "mangalsutra_short","mangalsutra_long",
    "bangles","ladies_bali","mens_bali","necklace",
    "silver","diamond",
]
EXTS = ("*.jpg","*.jpeg","*.png")

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

# ── helpers ──────────────────────────────────────────────────────────────────

def _camera_key(path):
    """
    Sort by the LAST numeric sequence in the filename — matches camera roll order.
    IMG_5316.jpg, IMG_5317.jpg, DSC_0001.jpg, 20240626_120001.jpg all sort correctly.
    Files with no number sort by full name.
    """
    name = os.path.basename(path).lower()
    nums = re.findall(r"\d+", name)
    # Use the last (rightmost) number as primary sort key — that's the shot counter
    return (int(nums[-1]) if nums else 0, name)

def _list_imgs(folder):
    """
    List images sorted by camera sequence (shot order).
    Deduplicate .jpeg/.jpg pairs keeping one copy.
    Result: [shot1, shot2, shot3, shot4, ...] where
            odd positions (0,2,4...) = jewellery, even positions (1,3,5...) = tag
    """
    files = []
    for e in EXTS:
        files += glob.glob(os.path.join(folder, e))
    # Sort by camera shot number
    files.sort(key=_camera_key)
    # Deduplicate same base name (.jpeg vs .jpg)
    seen, unique = set(), []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0].lower()
        if base not in seen:
            seen.add(base)
            unique.append(f)
    return unique

# ── pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", types=TYPES)

# ── static assets ─────────────────────────────────────────────────────────────

@app.route("/img/<where>/<path:name>")
def img(where, name):
    folder = {
        "input":       INPUT,
        "processing":  PROCESSING,
        "output":      OUTPUT,
        "backgrounds": BACKGROUNDS_DIR,
    }.get(where)
    if not folder:
        return "Not found", 404
    return send_from_directory(folder, name)

# ── Step 1 — backgrounds list ─────────────────────────────────────────────────

@app.route("/api/backgrounds")
def api_backgrounds():
    bgs = sorted(f for f in os.listdir(BACKGROUNDS_DIR)
                 if f.lower().endswith((".png",".jpg",".jpeg",".webp"))
                 and not f.startswith("_"))
    return jsonify({"backgrounds": bgs})

# ── Step 2 — upload images to input\ ─────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def api_upload():
    saved = 0
    for f in request.files.getlist("files"):
        name = os.path.basename(f.filename or "")
        if not name:
            continue
        if os.path.splitext(name)[1].lower() not in (".jpg", ".jpeg", ".png"):
            continue
        f.save(os.path.join(INPUT, name))
        saved += 1
    return jsonify({"saved": saved})

# ── Step 3 — load pairs from input\ ──────────────────────────────────────────

@app.route("/api/load")
def api_load():
    files = [os.path.basename(f) for f in _list_imgs(INPUT)]
    pairs = []
    for i in range(0, len(files), 2):
        pairs.append({
            "pair":  i // 2 + 1,
            "jewel": files[i],
            "tag":   files[i + 1] if i + 1 < len(files) else None,
        })
    return jsonify({"count": len(files), "pairs": pairs, "note": "sorted by camera shot number"})

# ── Step 4 — rename & stage (optional) ───────────────────────────────────────

@app.route("/api/stage", methods=["POST"])
def api_stage():
    """
    Stage pairs instantly — just rename and move files.
    job_id = original camera filename base (e.g. IMG5316).
    Gemma 4 reads the tag label later during ChatGPT processing (not here).
    """
    files  = _list_imgs(INPUT)
    staged = []
    n      = 0
    for i in range(0, len(files), 2):
        n += 1
        jewel_path = files[i]
        tag_path   = files[i + 1] if i + 1 < len(files) else None

        # job_id from original filename — no API call, instant
        base   = re.sub(r"[^A-Za-z0-9]", "", os.path.splitext(os.path.basename(jewel_path))[0])[:15]
        job_id = base or f"{n:03d}"

        je = os.path.splitext(jewel_path)[1].lower()
        jn = f"{n:03d}_{job_id}_jewel{je}"
        shutil.move(jewel_path, os.path.join(PROCESSING, jn))

        tn = None
        if tag_path:
            te = os.path.splitext(tag_path)[1].lower()
            tn = f"{n:03d}_{job_id}_tag{te}"
            shutil.move(tag_path, os.path.join(PROCESSING, tn))

        staged.append({"pair": n, "jewel": jn, "tag": tn, "job_id": job_id, "staged": True})

    return jsonify({"staged": staged})

# ── Step 5 — ChatGPT + Gemini processing ──────────────────────────────────────

import gemini_bg

CGPT_JOB = {
    "running": False, "total": 0, "done": 0,
    "current": "", "started": 0.0, "results": [], "error": None,
}
GEMINI_JOB = {
    "running": False, "total": 0, "done": 0,
    "current": "idle", "started": 0.0, "results": [], "error": None,
}
chatgpt_bg._JOB_DICT = CGPT_JOB
gemini_bg._JOB_DICT  = GEMINI_JOB

def _bg_for(category):
    path = os.path.join(BACKGROUNDS_DIR, f"{category}.png")
    return path if os.path.exists(path) else os.path.join(BACKGROUNDS_DIR, "earrings.png")

def _ensure_chrome():
    """Launch ChatGPT-dedicated Chrome on port 9222, then move it to catalogue desktop."""
    import socket as _s, subprocess
    try:
        c = _s.create_connection(("127.0.0.1", 9222), timeout=2)
        c.close()
        return True
    except OSError:
        pass
    CGPT_JOB["current"] = "🚀 Starting ChatGPT Chrome…"
    proc = subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--remote-debugging-port=9222",
        r"--user-data-dir=C:\Users\kaila\AppData\Local\AutoCatalogueChrome",
        "--no-first-run", "--no-default-browser-check",
        "--window-position=-32000,-32000",   # off every screen — never visible
        "--window-size=1280,900",
        "--homepage=https://chatgpt.com",
        "https://chatgpt.com",
    ])
    import time as _t; _t.sleep(6)
    # Tell chatgpt_bg which PID is ours so it never touches other Chrome instances
    chatgpt_bg._CATALOGUE_CHROME_PID = proc.pid
    return False

def _gemma_read_tag(tag_path):
    """Read tag label with Gemma. Returns label string or ''."""
    try:
        from keys import GEMINI_API_KEY
        from google import genai
        from google.genai import types as gt
        from PIL import Image
        import io
        client = genai.Client(api_key=GEMINI_API_KEY)
        pil = Image.open(tag_path).convert("RGB")
        buf = io.BytesIO(); pil.save(buf, "JPEG", quality=90)
        resp = client.models.generate_content(
            model="gemma-4-31b-it",
            contents=[gt.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                      "Read the item code on the FIRST LINE of this price tag. "
                      "Reply with ONLY the code, no spaces, no explanation. Example: TP22/157"]
        )
        raw = resp.text.strip().split()[0]
        return re.sub(r"[^\w/_-]", "", raw)[:20]
    except Exception:
        return ""


def _load_progress(category):
    """Load completed pair labels from progress file."""
    import json
    p = os.path.join(BASE, f"progress_{category}.json")
    if os.path.exists(p):
        try:
            return json.load(p.open())
        except Exception:
            pass
    return {}


def _save_progress(category, pair_key, label, output):
    """Save one completed pair to progress file."""
    import json
    p = os.path.join(BASE, f"progress_{category}.json")
    data = {}
    if os.path.exists(p):
        try: data = json.load(open(p))
        except Exception: pass
    data[pair_key] = {"label": label, "output": output}
    with open(p, "w") as f:
        json.dump(data, f, indent=2)


import catalogue_db

def _derive_pairs_from_disk():
    """
    Re-derive the processing queue directly from files on disk.
    Always sorted smallest file number → largest so no pair is ever missed.

    Staged files:   NNN_DSCxxxxx_jewel.jpg + NNN_DSCxxxxx_tag.jpg
    Unstaged files: DSCxxxxx.jpg DSCxxxxx+1.jpg (alternating jewel/tag by shot order)

    Returns list of pair dicts with keys: pair, jewel, tag, job_id, staged, folder
    """
    pairs = []

    # ── Staged pairs from processing\ (explicit _jewel / _tag suffixes) ──────
    jewel_files = sorted(
        [f for f in os.listdir(PROCESSING) if "_jewel." in f.lower()],
        key=_camera_key
    )
    for n, jf in enumerate(jewel_files, start=1):
        base = jf.lower().replace("_jewel", "_tag")
        # find matching tag (same base, any extension)
        tag_name = next(
            (f for f in os.listdir(PROCESSING)
             if "_tag." in f.lower() and
             f.lower().split("_tag.")[0] == jf.lower().split("_jewel.")[0]),
            None
        )
        job_id = re.sub(r"[^A-Za-z0-9]", "",
                        os.path.splitext(jf)[0].replace("_jewel",""))[:20]
        pairs.append({
            "pair":   n,
            "jewel":  jf,
            "tag":    tag_name,
            "job_id": job_id,
            "staged": True,
            "folder": PROCESSING,
        })

    # ── If nothing staged, fall back to input\ sorted by shot number ─────────
    if not pairs:
        files = [os.path.basename(f) for f in _list_imgs(INPUT)]
        for i in range(0, len(files), 2):
            n = i // 2 + 1
            jf = files[i]
            tf = files[i + 1] if i + 1 < len(files) else None
            job_id = re.sub(r"[^A-Za-z0-9]", "",
                            os.path.splitext(jf)[0])[:20]
            pairs.append({
                "pair":   n,
                "jewel":  jf,
                "tag":    tf,
                "job_id": job_id,
                "staged": False,
                "folder": INPUT,
            })

    return pairs


def _run_chatgpt_job(pairs, category, bg_name):
    CGPT_JOB["current"] = "🔍 Checking Chrome…"
    _ensure_chrome()
    CGPT_JOB["current"] = "🆕 Connecting to ChatGPT…"
    try:
        _d = chatgpt_bg.connect()
        chatgpt_bg.start_batch_chat(_d)
    except Exception as e:
        CGPT_JOB["current"] = f"⚠ Chrome connect failed: {e}"
        return

    # ── Always re-derive sequence from disk — smallest file number first ──────
    # Ignores whatever the UI sent; derives truth from what's actually on disk.
    pairs = _derive_pairs_from_disk()
    CGPT_JOB["total"] = len(pairs)
    CGPT_JOB["current"] = f"📂 {len(pairs)} pairs found on disk (sorted by file number)"

    # Resolve background
    if bg_name and not bg_name.endswith(".png"):
        bg_name += ".png"
    bg_path = os.path.join(BACKGROUNDS_DIR, bg_name) if bg_name else None
    if not bg_path or not os.path.exists(bg_path):
        bg_path = os.path.join(BACKGROUNDS_DIR, f"{category}.png")
    if not os.path.exists(bg_path):
        bgs = [f for f in os.listdir(BACKGROUNDS_DIR) if f.lower().endswith((".png",".jpg",".jpeg",".webp"))]
        bg_path = os.path.join(BACKGROUNDS_DIR, bgs[0]) if bgs else None

    out_dir = os.path.join(OUTPUT, category)
    os.makedirs(out_dir, exist_ok=True)

    # Load saved progress — skip already-completed pairs on resume
    progress = _load_progress(category)

    # In-run tag dedup — skip if same tag already saved in THIS batch
    seen_tags_this_run = set()

    results = list(CGPT_JOB.get("results") or [])
    for i, s in enumerate(pairs):
        pair_key = str(s["pair"])
        folder   = s.get("folder") or (PROCESSING if s.get("staged") else INPUT)
        jewel    = os.path.join(folder, s["jewel"])
        tag      = os.path.join(folder, s["tag"]) if s.get("tag") else None

        # ── Resume: skip already done ─────────────────────────────────
        if pair_key in progress and progress[pair_key].get("output"):
            saved = progress[pair_key]
            seen_tags_this_run.add((saved.get("label") or "").strip().upper())
            CGPT_JOB["current"] = f"⏭ Pair {s['pair']} already done — skipping"
            results.append({"pair": s["pair"], "sku": saved["label"],
                            "output": saved["output"], "error": None, "skipped": True})
            CGPT_JOB["done"]    = i + 1
            CGPT_JOB["results"] = results
            continue

        # ── Fire Gemma label read in background WHILE ChatGPT generates ──
        gemma_label = {"value": ""}
        def _bg_gemma(tp=tag, gl=gemma_label):
            if tp and os.path.exists(tp):
                gl["value"] = _gemma_read_tag(tp)
        gemma_thread = threading.Thread(target=_bg_gemma, daemon=True)
        gemma_thread.start()

        # ── Process with auto-retry + token exhaustion detection ──────
        result = {"error": "not started"}
        token_exhausted = False
        rate_limit_hits = 0
        for attempt in range(1, 6):   # up to 5 attempts (rate limits may need multiple retries)
            if attempt > 1:
                if token_exhausted:
                    CGPT_JOB["current"] = "⛔ ChatGPT out of tokens — waiting 60s"
                    time.sleep(60)
                    token_exhausted = False
                else:
                    CGPT_JOB["current"] = f"🔁 Retry {attempt}/5 · pair {s['pair']}"
                    time.sleep(5)

            CGPT_JOB["current"] = f"ChatGPT · pair {s['pair']} try{attempt}"
            result = chatgpt_bg.process(
                jewel_path=jewel,
                tag_path=tag or jewel,
                bg_path=bg_path,
                category=category,
                pair_num=f"{i+1}/{len(pairs)} try{attempt}",
                job_id=s.get("job_id") or f"{i+1:03d}",
            )

            # Rate limit → try Gemini as instant fallback instead of waiting
            err = (result.get("error") or "")
            if "RATE_LIMIT" in err or any(p in err.lower() for p in ["too many", "rate limit", "slow down"]):
                rate_limit_hits += 1
                CGPT_JOB["current"] = f"⏳ ChatGPT rate limited — switching to Gemini for pair {s['pair']}"
                try:
                    gem_result = gemini_bg.process(
                        jewel_path=jewel, tag_path=tag or jewel, bg_path=bg_path,
                        category=category,
                        pair_num=f"{i+1}/{len(pairs)} [Gemini fallback]",
                        job_id=s.get("job_id") or f"{i+1:03d}",
                    )
                    if gem_result.get("output") and os.path.exists(gem_result["output"]):
                        CGPT_JOB["current"] = f"✅ Pair {s['pair']} done via Gemini fallback"
                        result = gem_result
                        result["engine"] = "gemini_fallback"
                        break   # success via fallback — skip further ChatGPT retries
                    CGPT_JOB["current"] = f"⚠ Gemini fallback failed too — waiting for ChatGPT slot"
                except Exception as ge:
                    CGPT_JOB["current"] = f"⚠ Gemini fallback error: {ge} — waiting for ChatGPT slot"
                # Gemini also failed — wait for ChatGPT slot using slot scheduler
                chatgpt_bg.slot_wait_if_needed(
                    status_fn=lambda m: CGPT_JOB.update({"current": m})
                )
                continue
            if any(p in err.lower() for p in ["token", "quota", "usage", "exhausted"]):
                token_exhausted = True
                CGPT_JOB["current"] = f"⛔ Pair {s['pair']} — token limit hit, trying Gemini"
                try:
                    gem_result = gemini_bg.process(
                        jewel_path=jewel, tag_path=tag or jewel, bg_path=bg_path,
                        category=category,
                        pair_num=f"{i+1}/{len(pairs)} [Gemini fallback]",
                        job_id=s.get("job_id") or f"{i+1:03d}",
                    )
                    if gem_result.get("output") and os.path.exists(gem_result["output"]):
                        result = gem_result
                        result["engine"] = "gemini_fallback"
                        break
                except Exception:
                    pass
                continue

            if result.get("output") and os.path.exists(result["output"]):
                break

        # ── Resolve label: ChatGPT result → Gemma background → fallback ──
        gemma_thread.join(timeout=30)   # wait for Gemma if still running
        raw = (result.get("label") or "").strip()
        placeholders = ["first line", "price tag", "image 2", "tag in", "[", "]", " "]
        if raw and not any(p in raw.lower() for p in placeholders) and len(raw) >= 2:
            label = raw
        elif gemma_label["value"]:
            label = gemma_label["value"]
            CGPT_JOB["current"] = f"🏷 Gemma label: {label}"
        else:
            label = f"AJ-{s['pair']:03d}"

        safe     = re.sub(r'[/\\:*?"<>|]', '_', label)
        out_path = os.path.join(out_dir, f"{safe}.jpg")

        # ── In-run duplicate tag check — skip before even saving ──────
        clean_label = label.strip().upper()
        if clean_label and not clean_label.startswith("AJ-") and clean_label in seen_tags_this_run:
            CGPT_JOB["current"] = f"⏭ Pair {s['pair']} — tag {label} already saved this run, skipping"
            results.append({"pair": s["pair"], "sku": label, "output": None,
                            "error": f"Skipped — tag {label} already processed in this batch",
                            "skipped": True})
            CGPT_JOB["done"]    = i + 1
            CGPT_JOB["results"] = results
            continue

        if result.get("output") and os.path.exists(result["output"]):
            os.replace(result["output"], out_path)

            # ── Jewellery presence check — reject empty backgrounds ────────
            jcheck = catalogue_db.verify_jewellery_present(out_path)
            if not jcheck["ok"]:
                CGPT_JOB["current"] = f"⚠ Pair {s['pair']} — no jewellery in output ({jcheck['reason'][:60]}) — retrying"
                os.remove(out_path)
                # Force one more attempt on the next loop iteration
                result = {"error": f"no-jewellery: {jcheck['reason']}"}
                # Treat as failed so retry logic kicks in
                results.append({"pair": s["pair"], "sku": label, "output": None,
                                "error": f"Empty background — retrying: {jcheck['reason'][:80]}"})
                CGPT_JOB["done"]    = i + 1
                CGPT_JOB["results"] = results
                continue

            # ── Persistent 30-day duplicate / cross-check ─────────────────
            findings = catalogue_db.check_and_record(label, out_path, category)

            if findings:
                # Classify severity — exact duplicate is worst
                types   = [f["type"] for f in findings]
                worst   = (
                    "exact_duplicate"      if "exact_duplicate"      in types else
                    "same_tag_diff_design" if "same_tag_diff_design" in types else
                    "same_design_diff_tag"
                )
                msgs    = " | ".join(f["message"] for f in findings)
                suffix  = "_DUPLICATE" if worst == "exact_duplicate" else "_FLAGGED"
                flag_path = os.path.join(out_dir, f"{safe}{suffix}.jpg")
                os.replace(out_path, flag_path)
                CGPT_JOB["current"] = f"⚠️ {worst.upper()}: {msgs[:120]}"
                results.append({
                    "pair": s["pair"], "sku": label,
                    "output": f"{category}/{safe}{suffix}.jpg",
                    "error": None, "duplicate": True,
                    "duplicate_type":   worst,
                    "duplicate_reason": msgs,
                    "findings":         findings,
                })
            else:
                seen_tags_this_run.add(clean_label)   # mark tag as done this run
                results.append({"pair": s["pair"], "sku": label,
                                "output": f"{category}/{safe}.jpg", "error": None})

            _save_progress(category, pair_key, label, f"{category}/{safe}.jpg")

            # ── Soft warning cooldown — finish pair first, then wait 5 min ──
            if result.get("warn_cooldown"):
                CGPT_JOB["done"]    = i + 1
                CGPT_JOB["results"] = results
                cooldown = 300  # 5 minutes
                for remaining in range(cooldown, 0, -15):
                    CGPT_JOB["current"] = (
                        f"⚠️ ChatGPT warned — cooling {remaining}s before next pair"
                    )
                    time.sleep(min(15, remaining))
                CGPT_JOB["current"] = "✅ Cooldown done — resuming"
        else:
            results.append({"pair": s["pair"], "sku": label,
                            "output": None, "error": result.get("error", "failed")})

        CGPT_JOB["done"]    = i + 1
        CGPT_JOB["results"] = results

    CGPT_JOB["running"] = False
    CGPT_JOB["current"] = "done"


# ── Gemini parallel runner ────────────────────────────────────────────────────

def _run_gemini_job(pairs, category, bg_name):
    """Mirror of _run_chatgpt_job but using gemini_bg."""
    if bg_name and not bg_name.endswith(".png"):
        bg_name += ".png"
    bg_path = os.path.join(BACKGROUNDS_DIR, bg_name) if bg_name else None
    if not bg_path or not os.path.exists(bg_path):
        bg_path = os.path.join(BACKGROUNDS_DIR, f"{category}.png")
    if not os.path.exists(bg_path):
        bgs = [f for f in os.listdir(BACKGROUNDS_DIR) if f.lower().endswith((".png",".jpg",".jpeg",".webp"))]
        bg_path = os.path.join(BACKGROUNDS_DIR, bgs[0]) if bgs else None

    out_dir = os.path.join(OUTPUT, category)
    os.makedirs(out_dir, exist_ok=True)
    progress = _load_progress(category)
    results  = list(GEMINI_JOB.get("results") or [])

    for i, s in enumerate(pairs):
        pair_key = str(s["pair"])
        folder   = s.get("folder") or (PROCESSING if s.get("staged") else INPUT)
        jewel    = os.path.join(folder, s["jewel"])
        tag      = os.path.join(folder, s["tag"]) if s.get("tag") else None

        if pair_key in progress and progress[pair_key].get("output"):
            saved = progress[pair_key]
            results.append({"pair": s["pair"], "sku": saved["label"],
                            "output": saved["output"], "error": None,
                            "engine": "gemini", "skipped": True})
            GEMINI_JOB["done"]    = i + 1
            GEMINI_JOB["results"] = results
            continue

        # Gemma label in background
        gemma_label = {"value": ""}
        def _bg_g(tp=tag, gl=gemma_label):
            if tp and os.path.exists(tp):
                gl["value"] = _gemma_read_tag(tp)
        gt = threading.Thread(target=_bg_g, daemon=True)
        gt.start()

        result = {"error": "not started"}
        for attempt in range(1, 4):
            if attempt > 1:
                GEMINI_JOB["current"] = f"🔁 Gemini retry {attempt}/3 · pair {s['pair']}"
                time.sleep(5)
            GEMINI_JOB["current"] = f"Gemini · pair {s['pair']} try{attempt}"
            result = gemini_bg.process(
                jewel_path=jewel, tag_path=tag or jewel,
                bg_path=bg_path, category=category,
                pair_num=f"{i+1}/{len(pairs)} try{attempt}",
                job_id=s.get("job_id") or f"{i+1:03d}",
            )
            if result.get("output") and os.path.exists(result["output"]):
                break

        gt.join(timeout=30)
        raw = (result.get("label") or "").strip()
        placeholders = ["first line", "price tag", "image 2", "[", " "]
        if raw and not any(p in raw.lower() for p in placeholders) and len(raw) >= 2:
            label = raw
        elif gemma_label["value"]:
            label = gemma_label["value"]
        else:
            label = f"AJ-{s['pair']:03d}"

        safe     = re.sub(r'[/\\:*?"<>|]', '_', label)
        out_path = os.path.join(out_dir, f"{safe}_gemini.jpg")

        if result.get("output") and os.path.exists(result["output"]):
            os.replace(result["output"], out_path)
            findings = catalogue_db.check_and_record(label, out_path, category)
            _save_progress(category, pair_key, label, f"{category}/{safe}_gemini.jpg")
            if findings:
                worst = findings[0]["type"]
                results.append({"pair": s["pair"], "sku": label,
                                "output": f"{category}/{safe}_gemini.jpg",
                                "error": None, "engine": "gemini",
                                "duplicate": True, "duplicate_type": worst,
                                "duplicate_reason": findings[0]["message"],
                                "findings": findings})
            else:
                results.append({"pair": s["pair"], "sku": label,
                                "output": f"{category}/{safe}_gemini.jpg",
                                "error": None, "engine": "gemini"})
        else:
            results.append({"pair": s["pair"], "sku": label, "output": None,
                            "error": result.get("error", "failed"), "engine": "gemini"})

        GEMINI_JOB["done"]    = i + 1
        GEMINI_JOB["results"] = results

    GEMINI_JOB["running"] = False
    GEMINI_JOB["current"] = "done"


# ── Parallel dispatcher — splits queue between ChatGPT + Gemini ───────────────

def _run_parallel_job(pairs, category, bg_name):
    """
    Split pairs across ChatGPT and Gemini engines.
    Odd pairs → ChatGPT, Even pairs → Gemini.
    Both run simultaneously in separate threads.
    """
    cgpt_pairs   = [p for i, p in enumerate(pairs) if i % 2 == 0]
    gemini_pairs = [p for i, p in enumerate(pairs) if i % 2 == 1]

    CGPT_JOB.update({"running": True, "total": len(cgpt_pairs), "done": 0,
                     "results": [], "started": time.time(), "error": None})
    GEMINI_JOB.update({"running": True, "total": len(gemini_pairs), "done": 0,
                       "results": [], "started": time.time(), "error": None})

    t1 = threading.Thread(target=_run_chatgpt_job,
                          args=(cgpt_pairs, category, bg_name), daemon=True)
    t2 = threading.Thread(target=_run_gemini_job,
                          args=(gemini_pairs, category, bg_name), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


# ── Photoshop processing ──────────────────────────────────────────────────────

PS_JOB = {
    "running": False, "total": 0, "done": 0,
    "current": "", "started": 0.0, "results": [], "error": None,
}

def _run_ps_job(pairs, category, bg_name):
    import photoshop_engine
    if bg_name and not bg_name.endswith(".png"):
        bg_name += ".png"
    bg_path = os.path.join(BACKGROUNDS_DIR, bg_name) if bg_name else None
    if not bg_path or not os.path.exists(bg_path):
        bg_path = os.path.join(BACKGROUNDS_DIR, f"{category}.png")
    if not os.path.exists(bg_path):
        bgs = [f for f in os.listdir(BACKGROUNDS_DIR) if f.lower().endswith((".png",".jpg",".jpeg",".webp"))]
        bg_path = os.path.join(BACKGROUNDS_DIR, bgs[0]) if bgs else None

    out_dir = os.path.join(OUTPUT, category)
    os.makedirs(out_dir, exist_ok=True)
    results = []

    for i, s in enumerate(pairs):
        PS_JOB["current"] = f"Photoshop · pair {s['pair']}"
        folder = PROCESSING if s.get("staged") else INPUT
        jewel  = os.path.join(folder, s["jewel"])
        tag    = os.path.join(folder, s["tag"]) if s.get("tag") else jewel

        def _st(msg): PS_JOB["current"] = f"Pair {s['pair']} · {msg}"

        result = photoshop_engine.process_pair(
            jewel_path=jewel, tag_path=tag, bg_path=bg_path,
            category=category, pair_num=f"{i+1}/{len(pairs)}",
            status_fn=_st,
        )

        label = result.get("label") or f"AJ-{s['pair']:03d}"
        safe  = re.sub(r'[/\\:*?"<>|]', '_', label)
        out_path = os.path.join(out_dir, f"{safe}.jpg")

        if result.get("output") and os.path.exists(result["output"]):
            if result["output"] != out_path:
                os.replace(result["output"], out_path)
            results.append({"pair": s["pair"], "sku": label,
                            "output": f"{category}/{safe}.jpg", "error": None})
        else:
            results.append({"pair": s["pair"], "sku": label,
                            "output": None, "error": result.get("error", "failed")})

        PS_JOB["done"]    = i + 1
        PS_JOB["results"] = results

    PS_JOB["running"] = False
    PS_JOB["current"] = "done"


@app.route("/api/ps_run", methods=["POST"])
def api_ps_run():
    if PS_JOB["running"]:
        return jsonify({"error": "already running"}), 409
    data     = request.get_json(force=True)
    pairs    = data.get("pairs", [])
    category = (data.get("category") or "earrings").lower()
    bg_name  = data.get("bg") or ""
    if not pairs:
        return jsonify({"error": "no pairs"}), 400
    PS_JOB.update({
        "running": True, "total": len(pairs), "done": 0,
        "current": "Starting Photoshop…", "started": time.time(),
        "results": [], "error": None,
    })
    threading.Thread(target=_run_ps_job, args=(pairs, category, bg_name), daemon=True).start()
    return jsonify({"started": True, "total": len(pairs)})


@app.route("/api/ps_progress")
def api_ps_progress():
    j = PS_JOB
    elapsed = int(time.time() - j["started"]) if j["started"] else 0
    done, total = j["done"], j["total"]
    eta = int((elapsed / done) * (total - done)) if j["running"] and done > 0 and total > done else None
    return jsonify({"running": j["running"], "done": done, "total": total,
                    "current": j["current"], "elapsed": elapsed, "eta": eta,
                    "results": j["results"], "error": j["error"]})


ADMIN_PASSWORD = "Aradhana1992"   # change anytime in app.py

REPROCESS_QUEUE = []   # pairs queued for reprocessing after rejection

@app.route("/api/reject", methods=["POST"])
def api_reject():
    data     = request.json or {}
    pair_num = data.get("pair")
    sku      = data.get("sku", "")
    if pair_num is None:
        return jsonify({"ok": False, "error": "pair number required"}), 400

    # Find the pair on disk and add to reprocess queue
    pairs = _derive_pairs_from_disk()
    match = next((p for p in pairs if p["pair"] == pair_num), None)
    if not match:
        return jsonify({"ok": False, "error": f"Pair {pair_num} not found on disk"}), 404

    # Move its output to a _rejected folder so it doesn't count as done
    for cat in os.listdir(OUTPUT):
        cat_dir = os.path.join(OUTPUT, cat)
        if not os.path.isdir(cat_dir):
            continue
        for f in os.listdir(cat_dir):
            if sku and sku.replace("/", "_") in f:
                rej_dir = os.path.join(cat_dir, "_rejected")
                os.makedirs(rej_dir, exist_ok=True)
                os.rename(os.path.join(cat_dir, f), os.path.join(rej_dir, f))

    # Remove from progress cache so it reprocesses
    for cat in os.listdir(BASE):
        if cat.startswith("progress_") and cat.endswith(".json"):
            try:
                p = os.path.join(BASE, cat)
                data = json.load(open(p))
                data.pop(str(pair_num), None)
                json.dump(data, open(p, "w"), indent=2)
            except Exception:
                pass

    REPROCESS_QUEUE.append(match)
    return jsonify({"ok": True, "pair": pair_num, "queued": len(REPROCESS_QUEUE)})


@app.route("/api/reprocess_queue")
def api_reprocess_queue():
    return jsonify({"queue": REPROCESS_QUEUE, "count": len(REPROCESS_QUEUE)})


@app.route("/api/upload_bg", methods=["POST"])
def api_upload_bg():
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "no file"}), 400
    filename = re.sub(r"[^\w.\-]", "_", f.filename)
    dest = os.path.join(BACKGROUNDS_DIR, filename)
    f.save(dest)
    return jsonify({"ok": True, "filename": filename})


@app.route("/api/admin/reset_db", methods=["POST"])
def api_reset_db():
    pwd = (request.json or {}).get("password", "")
    if pwd != ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "Wrong password"}), 403
    db_path = os.path.join(BASE, "catalogue_db.json")
    if os.path.exists(db_path):
        os.remove(db_path)
    return jsonify({"ok": True, "message": "Duplicate history cleared"})


@app.route("/api/chrome_preview")
def api_chrome_preview():
    """Live screenshot from any connected Chrome debug port."""
    from flask import Response
    import base64
    port = request.args.get("port", "9222")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service as _Svc
        _cd = os.path.join(BASE, "chromedriver.exe")
        _svc = _Svc(_cd) if os.path.exists(_cd) else None
        opts = Options()
        opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        drv = webdriver.Chrome(service=_svc, options=opts) if _svc else webdriver.Chrome(options=opts)
        png = drv.get_screenshot_as_png()
        return Response(png, mimetype="image/png",
                        headers={"Cache-Control": "no-store"})
    except Exception as e:
        # Return a 1×1 grey PNG on error
        import struct, zlib
        def _make_grey():
            raw = b'\x00\x80\x80\x80'
            compressed = zlib.compress(raw)
            def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
            return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')
        return Response(_make_grey(), mimetype="image/png",
                        headers={"Cache-Control": "no-store", "X-Error": str(e)})


@app.route("/api/chrome_click", methods=["POST"])
def api_chrome_click():
    """Click at x,y coordinates in the Chrome tab using CDP."""
    data = request.json or {}
    port = data.get("port", "9222")
    x, y = data.get("x", 0), data.get("y", 0)
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service as _Svc
        _cd = os.path.join(BASE, "chromedriver.exe")
        _svc = _Svc(_cd) if os.path.exists(_cd) else None
        opts = Options()
        opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        drv = webdriver.Chrome(service=_svc, options=opts) if _svc else webdriver.Chrome(options=opts)
        drv.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        drv.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    CGPT_JOB["running"]   = False
    CGPT_JOB["current"]   = "⏹ Stopped by user"
    GEMINI_JOB["running"] = False
    GEMINI_JOB["current"] = "idle"
    return jsonify({"ok": True})


@app.route("/api/new_chat", methods=["POST"])
def api_new_chat():
    cfg = os.path.join(BASE, "chatgpt_config.json")
    try:
        os.remove(cfg)
    except FileNotFoundError:
        pass
    chatgpt_bg._BATCH_CHAT_URL = ""
    chatgpt_bg.SAVED_CHAT_URL  = ""
    return jsonify({"ok": True})


@app.route("/api/chatgpt_run", methods=["POST"])
def api_chatgpt_run():
    if CGPT_JOB["running"]:
        return jsonify({"error": "already running"}), 409
    data     = request.get_json(force=True)
    pairs    = data.get("pairs", [])
    category = (data.get("category") or data.get("type") or "earrings").lower()
    bg_name  = data.get("bg") or data.get("background") or ""
    if not pairs:
        return jsonify({"error": "no pairs"}), 400
    CGPT_JOB.update({
        "running": True, "total": len(pairs), "done": 0,
        "current": "Starting…", "started": time.time(),
        "results": [], "error": None,
    })
    threading.Thread(
        target=_run_chatgpt_job, args=(pairs, category, bg_name), daemon=True
    ).start()
    return jsonify({"started": True, "total": len(pairs)})


@app.route("/api/chatgpt_progress")
def api_chatgpt_progress():
    j       = CGPT_JOB
    elapsed = int(time.time() - j["started"]) if j["started"] else 0
    done    = j["done"]
    total   = j["total"]
    eta     = None
    if j["running"] and done > 0 and total > done:
        eta = int((elapsed / done) * (total - done))
    # Merge Gemini results in when running parallel
    all_results = list(j["results"] or [])
    if GEMINI_JOB["running"] or GEMINI_JOB.get("results"):
        all_results = sorted(
            all_results + list(GEMINI_JOB.get("results") or []),
            key=lambda r: r.get("pair", 0)
        )
        done  = len([r for r in all_results if r.get("output") or r.get("error")])
        total = CGPT_JOB["total"] + GEMINI_JOB["total"]
    return jsonify({
        "running": j["running"] or GEMINI_JOB["running"],
        "done": done, "total": total,
        "current": j["current"],
        "gemini_current": GEMINI_JOB.get("current", ""),
        "elapsed": elapsed, "eta": eta,
        "results": all_results, "error": j["error"],
        "slots": chatgpt_bg.slot_status(),
    })


@app.route("/api/codex_run", methods=["POST"])
def api_codex_run():
    if CGPT_JOB["running"]:
        return jsonify({"error": "Already running"}), 400
    data     = request.json or {}
    category = data.get("category", "earrings")
    bg_name  = data.get("bg", "")
    pairs    = _derive_pairs_from_disk()

    if bg_name and not bg_name.endswith(".png"):
        bg_name += ".png"
    bg_path = os.path.join(BACKGROUNDS_DIR, bg_name) if bg_name else None
    if not bg_path or not os.path.exists(bg_path):
        bg_path = os.path.join(BACKGROUNDS_DIR, f"{category}.png")
    if not os.path.exists(bg_path):
        bgs = [f for f in os.listdir(BACKGROUNDS_DIR) if f.lower().endswith((".png",".jpg",".jpeg",".webp"))]
        bg_path = os.path.join(BACKGROUNDS_DIR, bgs[0]) if bgs else None

    CGPT_JOB.update({"running": True, "total": len(pairs), "done": 0,
                     "results": [], "started": time.time(), "error": None,
                     "current": f"🟢 Codex engine — {len(pairs)} pairs"})

    def _run():
        import codex_img, catalogue_db
        progress = _load_progress(category)
        out_dir  = os.path.join(OUTPUT, category)
        os.makedirs(out_dir, exist_ok=True)
        results  = []

        for i, s in enumerate(pairs):
            pair_key = str(s["pair"])
            folder   = s.get("folder") or (PROCESSING if s.get("staged") else INPUT)
            jewel    = os.path.join(folder, s["jewel"])
            tag      = os.path.join(folder, s["tag"]) if s.get("tag") else jewel

            if pair_key in progress and progress[pair_key].get("output"):
                saved = progress[pair_key]
                results.append({"pair": s["pair"], "sku": saved["label"],
                                "output": saved["output"], "error": None,
                                "skipped": True, "engine": "codex"})
                CGPT_JOB["done"]    = i + 1
                CGPT_JOB["results"] = results
                continue

            CGPT_JOB["current"] = f"Codex · pair {s['pair']}"
            r = codex_img.generate(
                jewel_path=jewel, tag_path=tag, bg_path=bg_path,
                category=category, label=f"AJ-{s['pair']:03d}",
                status_fn=lambda m: CGPT_JOB.update({"current": m})
            )

            label = r.get("label") or f"AJ-{s['pair']:03d}"
            safe  = re.sub(r'[/\\:*?"<>|]', '_', label)
            out_path = os.path.join(out_dir, f"{safe}_codex.png")

            if r.get("output") and os.path.exists(r["output"]):
                os.replace(r["output"], out_path)
                jcheck = catalogue_db.verify_jewellery_present(out_path)
                if not jcheck["ok"]:
                    CGPT_JOB["current"] = f"⚠ No jewellery detected — skipping pair {s['pair']}"
                    results.append({"pair": s["pair"], "sku": label, "output": None,
                                   "error": f"Empty output: {jcheck['reason'][:60]}",
                                   "engine": "codex"})
                else:
                    findings = catalogue_db.check_and_record(label, out_path, category)
                    _save_progress(category, pair_key, label, f"{category}/{safe}_codex.png")
                    results.append({"pair": s["pair"], "sku": label,
                                   "output": f"{category}/{safe}_codex.png",
                                   "error": None, "engine": "codex",
                                   "duplicate": bool(findings),
                                   "findings": findings})
            else:
                results.append({"pair": s["pair"], "sku": label, "output": None,
                               "error": r.get("error", "failed"), "engine": "codex"})

            CGPT_JOB["done"]    = i + 1
            CGPT_JOB["results"] = results

        CGPT_JOB["running"] = False
        CGPT_JOB["current"] = "done"

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"started": True, "pairs": len(pairs)})


@app.route("/api/gemini_run", methods=["POST"])
def api_gemini_run():
    if GEMINI_JOB["running"]:
        return jsonify({"error": "Gemini already running"}), 400
    data     = request.json or {}
    category = data.get("category", "earrings")
    bg_name  = data.get("bg", "")
    pairs    = _derive_pairs_from_disk()
    GEMINI_JOB.update({"running": True, "total": len(pairs), "done": 0,
                       "results": [], "started": time.time(), "error": None})
    threading.Thread(target=_run_gemini_job,
                     args=(pairs, category, bg_name), daemon=True).start()
    return jsonify({"started": True, "pairs": len(pairs)})


@app.route("/api/parallel_run", methods=["POST"])
def api_parallel_run():
    if CGPT_JOB["running"] or GEMINI_JOB["running"]:
        return jsonify({"error": "Already running"}), 400
    data     = request.json or {}
    category = data.get("category", "earrings")
    bg_name  = data.get("bg", "")
    pairs    = _derive_pairs_from_disk()
    CGPT_JOB.update({"running": True, "total": 0, "done": 0,
                     "results": [], "started": time.time(), "error": None})
    GEMINI_JOB.update({"running": True, "total": 0, "done": 0,
                       "results": [], "started": time.time(), "error": None})
    threading.Thread(target=_run_parallel_job,
                     args=(pairs, category, bg_name), daemon=True).start()
    return jsonify({"started": True, "pairs": len(pairs)})


# ── Quality comparison test ───────────────────────────────────────────────────

COMPARE_RESULT = {"running": False, "chatgpt": None, "gemini": None, "error": None}

@app.route("/api/compare_test", methods=["POST"])
def api_compare_test():
    """Run the SAME first pair through both engines simultaneously."""
    if COMPARE_RESULT["running"]:
        return jsonify({"error": "Already running"}), 400

    data     = request.json or {}
    category = data.get("category", "earrings")
    bg_name  = data.get("bg", "")

    pairs = _derive_pairs_from_disk()
    if not pairs:
        return jsonify({"error": "No pairs found — stage a pair first"}), 400

    pair = pairs[0]   # always test the first pair
    folder = pair.get("folder") or (PROCESSING if pair.get("staged") else INPUT)
    jewel  = os.path.join(folder, pair["jewel"])
    tag    = os.path.join(folder, pair["tag"]) if pair.get("tag") else jewel

    if bg_name and not bg_name.endswith(".png"):
        bg_name += ".png"
    bg_path = os.path.join(BACKGROUNDS_DIR, bg_name) if bg_name else None
    if not bg_path or not os.path.exists(bg_path):
        bg_path = os.path.join(BACKGROUNDS_DIR, f"{category}.png")
    if not os.path.exists(bg_path):
        bgs = [f for f in os.listdir(BACKGROUNDS_DIR) if f.lower().endswith((".png",".jpg",".jpeg",".webp"))]
        bg_path = os.path.join(BACKGROUNDS_DIR, bgs[0]) if bgs else None

    COMPARE_RESULT.update({"running": True, "chatgpt": None, "gemini": None, "error": None})

    def _run_cgpt():
        r = chatgpt_bg.process(
            jewel_path=jewel, tag_path=tag, bg_path=bg_path,
            category=category, pair_num="test/cgpt", job_id="COMPARE_TEST"
        )
        COMPARE_RESULT["chatgpt"] = r
        _check_done()

    def _run_gem():
        r = gemini_bg.process(
            jewel_path=jewel, tag_path=tag, bg_path=bg_path,
            category=category, pair_num="test/gem", job_id="COMPARE_TEST"
        )
        COMPARE_RESULT["gemini"] = r
        _check_done()

    def _check_done():
        if COMPARE_RESULT["chatgpt"] is not None and COMPARE_RESULT["gemini"] is not None:
            COMPARE_RESULT["running"] = False

    threading.Thread(target=_run_cgpt, daemon=True).start()
    threading.Thread(target=_run_gem,  daemon=True).start()

    return jsonify({"started": True, "pair": pair["jewel"]})


@app.route("/api/compare_progress")
def api_compare_progress():
    c = COMPARE_RESULT
    cgpt_out = c["chatgpt"].get("output") if c["chatgpt"] else None
    gem_out  = c["gemini"].get("output")  if c["gemini"]  else None
    return jsonify({
        "running":        c["running"],
        "chatgpt_done":   c["chatgpt"] is not None,
        "gemini_done":    c["gemini"]  is not None,
        "chatgpt_output": cgpt_out,
        "chatgpt_error":  c["chatgpt"].get("error") if c["chatgpt"] else None,
        "gemini_output":  gem_out,
        "gemini_error":   c["gemini"].get("error")  if c["gemini"]  else None,
    })


@app.route("/img/compare/<path:filename>")
def serve_compare_img(filename):
    from flask import send_file
    # serve directly from output folder
    full = os.path.join(OUTPUT, filename)
    if os.path.exists(full):
        return send_file(full)
    return "not found", 404


# ── launch ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import socket as _sock

    # Find a free port — NO SO_REUSEADDR so zombie sockets block the port
    # and we move to the next one, guaranteeing a clean bind.
    def _free_port(preferred=7654):
        for p in range(preferred, preferred + 50):
            try:
                s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                s.bind(("0.0.0.0", p))   # no SO_REUSEADDR — must be truly free
                s.close()
                return p
            except OSError:
                continue
        return preferred

    port = _free_port(7654)

    # Write port to file so BAT can open the browser on the right URL
    with open(os.path.join(BASE, "port.txt"), "w") as _pf:
        _pf.write(str(port))

    print(f"\n  Auto Catalogue Tool  →  http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)












