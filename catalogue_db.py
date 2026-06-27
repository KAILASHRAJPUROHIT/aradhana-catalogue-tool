"""
Aradhana Catalogue — persistent duplicate & cross-check database.

Stores every processed item for 30 days. On each new item checks:
  1. Same hash  + same tag  → exact duplicate (already processed on DATE)
  2. Same hash  + diff tag  → same design, different tag number (possible mislabel)
  3. Same tag   + diff hash → same tag reused on a different design (data integrity issue)

DB file: catalogue_db.json  (stays small — ~1KB/entry, 2000 items ≈ 2MB)
"""

import os, json, time, datetime

DB_PATH   = os.path.join(os.path.dirname(__file__), "catalogue_db.json")
KEEP_DAYS = 30
HASH_DIST_THRESHOLD = 12  # phash pre-filter only — Gemma does final confirm

# ── Internal helpers ──────────────────────────────────────────────────────────

def _load():
    if os.path.exists(DB_PATH):
        try:
            return json.load(open(DB_PATH, encoding="utf-8"))
        except Exception:
            pass
    return {"entries": []}


def _save(db):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


def _prune(db):
    """Remove entries older than KEEP_DAYS."""
    cutoff = time.time() - (KEEP_DAYS * 86400)
    db["entries"] = [e for e in db["entries"] if e.get("ts", 0) >= cutoff]
    return db


def _phash(path):
    try:
        import imagehash
        from PIL import Image
        return str(imagehash.phash(Image.open(path).convert("RGB")))
    except Exception:
        return None


def _gemma_same_design(path_a: str, path_b: str) -> dict:
    """
    Use Gemma 4 VLM to compare the actual jewellery design in two catalogue images.
    Ignores background — focuses entirely on the jewellery pieces themselves.
    Returns {"same": bool, "confidence": "high"|"medium"|"low", "reason": str}
    """
    try:
        from google import genai
        from google.genai import types as gt
        from PIL import Image
        import io, sys
        sys.path.insert(0, os.path.dirname(__file__))
        from keys import GEMINI_API_KEY

        client = genai.Client(api_key=GEMINI_API_KEY)

        def _img_part(p):
            img = Image.open(p).convert("RGB")
            img.thumbnail((768, 768))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=90)
            return gt.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")

        resp = client.models.generate_content(
            model="gemma-4-31b-it",
            contents=[
                _img_part(path_a),
                _img_part(path_b),
                """You are a jewellery expert comparing two catalogue product images.

TASK: Determine if Image A and Image B show THE EXACT SAME jewellery design.

FOCUS ONLY ON the jewellery pieces themselves — ignore:
- The background (satin, velvet, studio backdrop)
- Lighting differences
- Slight angle differences
- Image quality differences

EXAMINE CLOSELY:
- Shape and silhouette of each piece
- Stone placement, colour and cut
- Metal pattern, texture and finish
- Dangles, drops or pendants
- Overall construction details

Answer in this exact format:
SAME_DESIGN: YES or NO
CONFIDENCE: HIGH or MEDIUM or LOW
REASON: [one sentence explaining what matches or differs in the jewellery design itself]"""
            ]
        )

        text = resp.text.strip()
        same       = "SAME_DESIGN: YES" in text.upper()
        confidence = "high" if "CONFIDENCE: HIGH" in text.upper() else \
                     "medium" if "CONFIDENCE: MEDIUM" in text.upper() else "low"
        reason     = ""
        for line in text.split("\n"):
            if line.upper().startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()
                break

        return {"same": same, "confidence": confidence, "reason": reason}

    except Exception as e:
        # Gemma unavailable — fall back to hash-only decision
        return {"same": None, "confidence": "low", "reason": f"Gemma unavailable: {e}"}


def _hash_dist(h1_str, h2_str):
    try:
        import imagehash
        return imagehash.hex_to_hash(h1_str) - imagehash.hex_to_hash(h2_str)
    except Exception:
        return 999


def _fmt_date(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M")


# ── Public API ────────────────────────────────────────────────────────────────

def check_and_record(label: str, output_path: str, category: str = "") -> list:
    """
    Check the new entry against the 30-day database, then record it.

    Returns a list of findings (may be empty):
    Each finding is a dict:
      {
        "type":    "exact_duplicate" | "same_design_diff_tag" | "same_tag_diff_design",
        "label":   label of the matching DB entry,
        "date":    human-readable date of prior processing,
        "output":  prior output file path,
        "message": human-readable explanation
      }
    """
    db      = _prune(_load())
    entries = db["entries"]
    findings = []

    clean_label = label.strip().upper() if label else ""
    new_hash    = _phash(output_path) if output_path and os.path.exists(output_path) else None

    for e in entries:
        e_label = (e.get("label") or "").strip().upper()
        e_hash  = e.get("phash")
        e_date  = _fmt_date(e.get("ts", 0))
        e_out   = e.get("output", "")

        label_match = bool(clean_label and e_label and clean_label == e_label)
        hash_close  = False
        if new_hash and e_hash:
            dist = _hash_dist(new_hash, e_hash)
            hash_close = dist <= HASH_DIST_THRESHOLD

        # ── For any hash-based suspicion, confirm with Gemma before flagging ──
        gemma_confirmed_same = None
        gemma_reason = ""
        if hash_close and output_path and os.path.exists(output_path) and \
                e_out and os.path.exists(e_out):
            g = _gemma_same_design(output_path, e_out)
            gemma_confirmed_same = g["same"]
            gemma_reason = g["reason"]
            # If Gemma says different design and is confident → not a match
            if g["same"] is False and g["confidence"] in ("high", "medium"):
                hash_close = False  # override hash match — Gemma wins

        hash_match = hash_close  # final decision after Gemma

        if hash_match and label_match:
            findings.append({
                "type":    "exact_duplicate",
                "label":   e.get("label"),
                "date":    e_date,
                "output":  e_out,
                "message": f"Exact duplicate — same design & tag {label} processed on {e_date}. "
                           f"Gemma: {gemma_reason}"
            })

        elif hash_match and not label_match:
            findings.append({
                "type":    "same_design_diff_tag",
                "label":   e.get("label"),
                "date":    e_date,
                "output":  e_out,
                "message": (
                    f"Same design but different tag — "
                    f"saved as '{e.get('label')}' on {e_date}, now tagged '{label}'. "
                    f"Gemma: {gemma_reason}"
                )
            })

        elif label_match and not hash_match:
            # Same tag, different hash — still run Gemma to check if design really differs
            if output_path and os.path.exists(output_path) and e_out and os.path.exists(e_out) \
                    and gemma_confirmed_same is None:
                g = _gemma_same_design(output_path, e_out)
                gemma_confirmed_same = g["same"]
                gemma_reason = g["reason"]
            # Only flag if Gemma also confirms designs differ (or Gemma unavailable)
            if gemma_confirmed_same is not True:
                findings.append({
                    "type":    "same_tag_diff_design",
                    "label":   e.get("label"),
                    "date":    e_date,
                    "output":  e_out,
                    "message": (
                        f"Same tag '{label}' but different design — "
                        f"previously processed on {e_date}. "
                        f"Gemma: {gemma_reason or 'designs appear visually different'}"
                    )
                })

    # Record this entry
    entry = {
        "label":    label,
        "phash":    new_hash,
        "output":   output_path,
        "category": category,
        "ts":       time.time(),
        "date":     _fmt_date(time.time()),
    }
    db["entries"].append(entry)
    _save(db)

    return findings


def db_stats() -> dict:
    """Return summary stats for the UI."""
    db    = _prune(_load())
    total = len(db["entries"])
    if not total:
        return {"total": 0, "oldest": None, "newest": None}
    ts_list = [e.get("ts", 0) for e in db["entries"]]
    return {
        "total":  total,
        "oldest": _fmt_date(min(ts_list)),
        "newest": _fmt_date(max(ts_list)),
    }
