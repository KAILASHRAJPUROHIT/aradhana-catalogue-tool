"""
Model Version Generator — Aradhana Jewellers
Generates 3 lifestyle/model images per jewellery item using ChatGPT.
Each image shows the jewellery being worn by a model with the Aradhana watermark.
"""
import os, re, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE   = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
OUTPUT = os.path.join(BASE, "output_aradhana")

# ── Category → Shoot config ───────────────────────────────────────────────────

CATEGORY_SHOTS = {
    # Earrings / tops
    "earrings":      {"body": "ear",    "gender": "female", "scene": "close-up of a woman's ear and side of face"},
    "tops":          {"body": "ear",    "gender": "female", "scene": "extreme close-up of a woman's ear"},
    "ladies_bali":   {"body": "ear",    "gender": "female", "scene": "close-up of a woman's ear and jawline"},
    "mens_bali":     {"body": "ear",    "gender": "male",   "scene": "close-up of a man's ear"},

    # Neck / chest
    "necklace":             {"body": "neck", "gender": "female", "scene": "close-up of a woman's neck and upper chest"},
    "pendant":              {"body": "neck", "gender": "female", "scene": "close-up of a woman's neck and décolletage"},
    "locket":               {"body": "neck", "gender": "female", "scene": "close-up of a woman's neck"},
    "ladies_chains":        {"body": "neck", "gender": "female", "scene": "close-up of a woman's neck and collarbone"},
    "gents_chains":         {"body": "neck", "gender": "male",   "scene": "close-up of a man's neck and upper chest"},
    "mangalsutra_short":    {"body": "neck", "gender": "female", "scene": "close-up of a bride's neck with mangalsutra"},
    "mangalsutra_long":     {"body": "neck", "gender": "female", "scene": "bridal portrait showing neck and chest with mangalsutra"},

    # Rings
    "ladies_rings": {"body": "hand",   "gender": "female", "scene": "close-up of elegant female fingers"},
    "gents_rings":  {"body": "hand",   "gender": "male",   "scene": "close-up of a man's hand and fingers"},

    # Bangles / bracelets / kada
    "bangles":          {"body": "wrist", "gender": "female", "scene": "close-up of a woman's wrist and hand with bangles"},
    "ladies_bracelet":  {"body": "wrist", "gender": "female", "scene": "close-up of a woman's wrist"},
    "gents_bracelet":   {"body": "wrist", "gender": "male",   "scene": "close-up of a man's wrist"},
    "ladies_kada":      {"body": "wrist", "gender": "female", "scene": "close-up of a woman's wrist"},
    "gents_kada":       {"body": "wrist", "gender": "male",   "scene": "close-up of a man's wrist"},

    # Feet / anklets
    "payal": {"body": "feet", "gender": "female", "scene": "close-up of a woman's feet and ankles"},
    "wati":  {"body": "feet", "gender": "female", "scene": "close-up of elegant female feet"},

    # Diamond (usually earrings)
    "diamond": {"body": "ear", "gender": "female", "scene": "glamorous close-up of a woman's ear and face profile"},

    # Silver (generic)
    "silver": {"body": "neck", "gender": "female", "scene": "close-up of a woman's neck and collarbone"},
}

DEFAULT_SHOT = {"body": "neck", "gender": "female", "scene": "close-up of a woman's neck and collarbone"}


def get_shot_config(category: str, body_override: str = None) -> dict:
    cfg = CATEGORY_SHOTS.get(category, DEFAULT_SHOT).copy()
    if body_override and body_override != "auto":
        # Map body override to scene description
        overrides = {
            "ear":   {"body": "ear",   "scene": "close-up of the model's ear and face profile"},
            "neck":  {"body": "neck",  "scene": "close-up of the model's neck and collarbone"},
            "hand":  {"body": "hand",  "scene": "close-up of the model's elegant fingers"},
            "wrist": {"body": "wrist", "scene": "close-up of the model's wrist"},
            "feet":  {"body": "feet",  "scene": "close-up of the model's feet and ankles"},
            "nose":  {"body": "nose",  "scene": "extreme close-up of the model's nose and face"},
            "chest": {"body": "chest", "scene": "close-up of the model's neck and upper chest"},
        }
        if body_override in overrides:
            cfg.update(overrides[body_override])
    return cfg


def build_model_prompt(category: str, job_id: str, cfg: dict, variant: int) -> str:
    """Build a ChatGPT prompt for generating a model wearing the jewellery."""
    cat_label = category.replace("_", " ").title()
    gender    = cfg["gender"]
    scene     = cfg["scene"]

    # Variation styles for 3 variants
    styles = [
        "natural daylight, minimal makeup, clean white/cream background, editorial style",
        "warm golden studio lighting, traditional Indian jewellery editorial aesthetic, soft background",
        "lifestyle setting, soft bokeh background, professional commercial photography look",
    ]
    style = styles[(variant - 1) % 3]

    return (
        f"{job_id} | Model shoot variant {variant}/3 for {cat_label} jewellery.\n\n"
        f"Create a professional jewellery catalogue photograph showing the {cat_label} "
        f"from image 1 being worn by a model.\n\n"

        f"SHOOT SPECIFICATION:\n"
        f"- Shot: {scene}\n"
        f"- Model: Beautiful Indian {'woman' if gender == 'female' else 'man'}, "
        f"{'20-30 years old, elegant and graceful' if gender == 'female' else '25-35 years old, refined and distinguished'}\n"
        f"- The jewellery from image 1 must be VISIBLY and CLEARLY worn — it is the HERO of the shot\n"
        f"- Style: {style}\n\n"

        f"JEWELLERY ACCURACY — CRITICAL:\n"
        f"- The jewellery in the model photo must look IDENTICAL to image 1\n"
        f"- Same design, same stones, same gold colour — do NOT alter or simplify the design\n"
        f"- The piece must be the focal point — sharp, detailed and prominent\n\n"

        f"WATERMARK — MANDATORY:\n"
        f"- Place the ARADHANA JEWELLERS logo watermark (the 'A' motif with text) "
        f"subtly in the bottom-right corner of the image\n"
        f"- Watermark opacity: 30–40% — visible but not distracting\n\n"

        f"OUTPUT: A single high-quality square catalogue image (1:1 ratio).\n"
        f"NO text overlays, NO borders, NO frames other than the Aradhana watermark.\n\n"

        f"Reply: MODEL_VARIANT: {variant}"
    )
