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
HASH_DIST_THRESHOLD = 8   # phash Hamming distance — ≤8 = same design

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
        hash_match  = False
        if new_hash and e_hash:
            dist = _hash_dist(new_hash, e_hash)
            hash_match = dist <= HASH_DIST_THRESHOLD

        if hash_match and label_match:
            findings.append({
                "type":    "exact_duplicate",
                "label":   e.get("label"),
                "date":    e_date,
                "output":  e_out,
                "message": f"Exact duplicate — same design & tag {label} was processed on {e_date}"
            })

        elif hash_match and not label_match:
            findings.append({
                "type":    "same_design_diff_tag",
                "label":   e.get("label"),
                "date":    e_date,
                "output":  e_out,
                "message": (
                    f"Same design but different tag — "
                    f"this design was saved as '{e.get('label')}' on {e_date}. "
                    f"Current tag is '{label}'. Possible mislabel?"
                )
            })

        elif label_match and not hash_match:
            findings.append({
                "type":    "same_tag_diff_design",
                "label":   e.get("label"),
                "date":    e_date,
                "output":  e_out,
                "message": (
                    f"Same tag but different design — "
                    f"tag '{label}' was used for a visually different item on {e_date}. "
                    f"Possible tag reuse or data entry error?"
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
