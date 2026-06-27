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
BACKGROUNDS_DIR = os.path.join(BASE, "backgrounds")

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
                 if f.lower().endswith(".png") and not f.startswith("_"))
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

# ── Step 5 — ChatGPT processing ───────────────────────────────────────────────

CGPT_JOB = {
    "running": False, "total": 0, "done": 0,
    "current": "", "started": 0.0, "results": [], "error": None,
}
chatgpt_bg._JOB_DICT = CGPT_JOB   # wire status updates into live progress bar

def _bg_for(category):
    path = os.path.join(BACKGROUNDS_DIR, f"{category}.png")
    return path if os.path.exists(path) else os.path.join(BACKGROUNDS_DIR, "earrings.png")

def _ensure_chrome():
    """Launch Chrome with remote debugging if port 9222 is not open."""
    import socket as _s, subprocess
    try:
        c = _s.create_connection(("127.0.0.1", 9222), timeout=2)
        c.close()
        return True   # already running
    except OSError:
        pass
    CGPT_JOB["current"] = "🚀 Starting Chrome…"
    subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--remote-debugging-port=9222",
        r"--user-data-dir=C:\Users\kaila\AppData\Local\AutoCatalogueChrome",
        "--no-first-run", "--no-default-browser-check"
    ])
    import time as _t; _t.sleep(6)
    return False   # we just launched it

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
        bgs = [f for f in os.listdir(BACKGROUNDS_DIR) if f.endswith(".png")]
        bg_path = os.path.join(BACKGROUNDS_DIR, bgs[0]) if bgs else None

    out_dir = os.path.join(OUTPUT, category)
    os.makedirs(out_dir, exist_ok=True)

    # Load saved progress — skip already-completed pairs on resume
    progress = _load_progress(category)

    results = list(CGPT_JOB.get("results") or [])
    for i, s in enumerate(pairs):
        pair_key = str(s["pair"])
        folder   = s.get("folder") or (PROCESSING if s.get("staged") else INPUT)
        jewel    = os.path.join(folder, s["jewel"])
        tag      = os.path.join(folder, s["tag"]) if s.get("tag") else None

        # ── Resume: skip already done ─────────────────────────────────
        if pair_key in progress and progress[pair_key].get("output"):
            saved = progress[pair_key]
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

            # Rate limit or token exhaustion — pause and retry same pair
            err = (result.get("error") or "")
            if "RATE_LIMIT" in err or any(p in err.lower() for p in ["too many", "rate limit", "slow down"]):
                rate_limit_hits += 1
                CGPT_JOB["current"] = f"⏳ Rate limited (hit #{rate_limit_hits}) — slot scheduler waiting"
                # Use slot scheduler — sleeps exactly until oldest slot's 3hr window expires
                chatgpt_bg.slot_wait_if_needed(
                    status_fn=lambda m: CGPT_JOB.update({"current": m})
                )
                continue
            if any(p in err.lower() for p in ["token", "quota", "usage", "exhausted"]):
                token_exhausted = True
                CGPT_JOB["current"] = f"⛔ Pair {s['pair']} — token limit hit"
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

        if result.get("output") and os.path.exists(result["output"]):
            os.replace(result["output"], out_path)

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
        bgs = [f for f in os.listdir(BACKGROUNDS_DIR) if f.endswith(".png")]
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
    return jsonify({
        "running": j["running"], "done": done, "total": total,
        "current": j["current"], "elapsed": elapsed, "eta": eta,
        "results": j["results"], "error": j["error"],
        "slots": chatgpt_bg.slot_status(),
    })


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












