"""
Aradhana Jewellers — Professional Catalogue Model Engine
Generates lifestyle/model images using the Codex engine.
Full template library, model roster, camera specs, and lighting language.
"""

# ── MODEL LIBRARY ─────────────────────────────────────────────────────────────

MODELS = {
    # Women
    "F1": "A beautiful contemporary Indian woman in her late 20s, refined luxury aesthetic, "
          "subtle Western-fusion styling, flawless natural skin, minimal makeup, confident expression",
    "F2": "A beautiful Indian woman in her late 20s to early 30s, traditional festive styling, "
          "silk saree or salwar kameez, warm expressive features, traditional grace",
    "F3": "A stunning Indian bride, early to mid 20s, full bridal makeup and styling, "
          "bridal red or pastel lehenga, glowing skin, wedding-ready look",
    "F4": "An elegant mature Indian woman in her early 40s, sophisticated presence, "
          "premium saree or formal attire, graceful and distinguished",

    # Men
    "M1": "A handsome contemporary Indian man in his early 30s, luxury lifestyle aesthetic, "
          "smart-casual or formal Western attire, clean grooming, confident",
    "M2": "A handsome Indian man in his early 30s, traditional festive styling, "
          "kurta or sherwani, warm expressive features",
    "M3": "A distinguished mature Indian man in his mid 40s, premium business or formal attire, "
          "authoritative and polished presence",

    # Kids
    "KG": "An adorable Indian girl aged 6-8, bright natural smile, "
          "traditional or festive dress, playful yet graceful",
    "KB": "An adorable Indian boy aged 6-8, bright natural smile, "
          "kurta or smart casual wear, lively natural expression",
}

# ── LIGHTING LANGUAGE (consistent across all shots) ───────────────────────────

LIGHTING = (
    "Soft diffused luxury studio lighting. Neutral cream or warm grey background. "
    "High-end editorial retouching. Natural skin texture. Minimal clean makeup. "
    "The jewellery must be the brightest, sharpest, most detailed element in the frame — "
    "it is the absolute hero of the shot."
)

# ── CAMERA SPECS BY BODY ZONE ─────────────────────────────────────────────────

CAMERA = {
    "face":   "85–135mm portrait lens, shallow depth of field, face and jewellery in sharp focus",
    "neck":   "70–100mm, chest-up framing, neck and jewellery as focal point",
    "hand":   "100mm macro-style framing, crisp detail on fingers and jewellery",
    "wrist":  "100mm macro-style framing, wrist detail, jewellery in sharp focus",
    "waist":  "mid-body crop emphasizing the waistline and jewellery",
    "feet":   "lower-leg close-up, elegant foot positioning, jewellery as focal point",
    "bridal": "85mm portrait, face and full jewellery visible, soft bokeh background",
}

# ── CATEGORY TEMPLATE LIBRARY ─────────────────────────────────────────────────
# Each category has: model, zone, and 3 templates

CATEGORY_TEMPLATES = {

    "necklace": {
        "models": ["F1", "F2"],
        "zone": "neck",
        "templates": [
            "front portrait, model facing camera directly, necklace centred on chest, full neck and collarbone visible",
            "45-degree portrait, model turned slightly to one side, necklace falling naturally, elegant three-quarter angle",
            "half-body editorial, model in composed pose, necklace as centrepiece, upper body styling visible",
        ]
    },

    "mangalsutra_long": {
        "models": ["F2", "F3", "F4"],
        "zone": "neck",
        "templates": [
            "waist-up traditional pose, married woman, mangalsutra draping naturally, graceful dignified expression",
            "three-quarter portrait, mangalsutra visible from neckline, authentic traditional styling",
            "walking pose, candid editorial feel, mangalsutra in motion, beautiful lifestyle moment",
        ]
    },

    "ladies_chains": {
        "models": ["F1", "F2"],
        "zone": "neck",
        "templates": [
            "female neckline close-up, chain resting elegantly on collarbone, soft focus background",
            "half-body portrait, chain layered naturally, contemporary styling",
            "lifestyle portrait, model in natural setting, chain as subtle statement piece",
        ]
    },

    "gents_chains": {
        "models": ["M1", "M2"],
        "zone": "neck",
        "templates": [
            "male neckline, open collar shirt or kurta, chain visible on chest, masculine and confident",
            "three-quarter portrait, chain as style accent, smart casual or formal styling",
            "lifestyle hand/chest pose, chain as premium detail, editorial masculine aesthetic",
        ]
    },

    "mangalsutra_short": {
        "models": ["F3", "F4"],
        "zone": "neck",
        "templates": [
            "married woman portrait, front-facing, mangalsutra at neckline, warm and graceful expression",
            "half-body, saree or lehenga styling, mangalsutra visible and prominent",
            "close neckline crop, mangalsutra as focal point, soft bokeh",
        ]
    },

    "necklace": {
        "models": ["F1", "F2"],
        "zone": "neck",
        "templates": [
            "front portrait, necklace centred and prominent, model looking directly at camera",
            "45-degree portrait, necklace draped elegantly at angle",
            "half-body editorial, full styling visible, necklace as hero piece",
        ]
    },

    "pendant": {
        "models": ["F1", "F2"],
        "zone": "neck",
        "templates": [
            "neck crop close-up, pendant centred on collarbone, delicate and precise",
            "half-body, pendant visible as accent piece, contemporary styling",
            "layered styling, pendant worn with chain, lifestyle editorial look",
        ]
    },

    "locket": {
        "models": ["F1", "F2", "F4"],
        "zone": "neck",
        "templates": [
            "neck crop, locket as focal point, elegant and meaningful",
            "half-body, locket resting on chest, traditional or contemporary styling",
            "lifestyle portrait, locket as personal statement piece",
        ]
    },

    "choker": {
        "models": ["F1", "F2", "F3"],
        "zone": "neck",
        "templates": [
            "tight neck close-up, choker sitting perfectly on neck, ultra-sharp detail",
            "side portrait, choker visible at neck, elegant profile",
            "elegant seated pose, choker as statement piece, composed editorial",
        ]
    },

    "earrings": {
        "models": ["F1", "F2", "F3"],
        "zone": "face",
        "templates": [
            "front face portrait, both earrings visible, model facing camera, 85mm shallow depth of field",
            "45-degree profile, near earring in sharp focus, face turned gracefully",
            "side profile with hair tucked back, earring fully revealed, clean elegant composition",
        ]
    },

    "tops": {
        "models": ["F1", "F2"],
        "zone": "face",
        "templates": [
            "front face close-up, ear and top visible, minimal jewellery detail crisp",
            "45-degree face, earring delicate and precise in frame",
            "side profile, hair swept back, earring as sole focal point",
        ]
    },

    "ladies_bali": {
        "models": ["F1", "F2", "F3"],
        "zone": "face",
        "templates": [
            "front face, bali earrings on both ears, warm expressive face",
            "45-degree portrait, one bali in sharp focus, graceful profile",
            "side profile with hair tucked, bali earring as hero, elegant neck line visible",
        ]
    },

    "mens_bali": {
        "models": ["M1", "M2"],
        "zone": "face",
        "templates": [
            "front masculine portrait, bali earring visible, confident styling",
            "45-degree profile, earring in sharp focus, masculine and refined",
            "side profile, bali as subtle statement, contemporary male editorial",
        ]
    },

    "maang_tika": {
        "models": ["F3", "F2"],
        "zone": "bridal",
        "templates": [
            "front bridal portrait, maang tika centred on forehead, full bridal makeup and styling visible",
            "head slightly lowered, maang tika falling naturally, soft and beautiful angle",
            "45-degree bridal profile, maang tika visible, face turned gracefully, full jewellery styling",
        ]
    },

    "nath": {
        "models": ["F3", "F2"],
        "zone": "face",
        "templates": [
            "front close-up face, nath (nose ring) as focal point, bridal or festive styling",
            "45-degree face turn, nath profile visible, soft depth of field",
            "side profile, nath visible from the side, elegant bridal pose",
        ]
    },

    "ladies_rings": {
        "models": ["F1", "F2"],
        "zone": "hand",
        "templates": [
            "single elegant female hand, ring prominently displayed on finger, soft focus background",
            "both hands together, rings on complementary fingers, graceful feminine pose",
            "ring close-up on fingers, macro detail, beautiful manicured hand",
        ]
    },

    "gents_rings": {
        "models": ["M1", "M2", "M3"],
        "zone": "hand",
        "templates": [
            "masculine hand, ring on finger, confident masculine styling, strong hand pose",
            "hand with shirt or suit cuff visible, ring as power accessory",
            "lifestyle hand pose, ring as part of refined grooming, premium aesthetic",
        ]
    },

    "bangles": {
        "models": ["F1", "F2", "F3"],
        "zone": "wrist",
        "templates": [
            "single wrist raised elegantly, bangles stacked beautifully, warm skin tone contrast",
            "both hands together, bangles on both wrists, traditional festive pose",
            "raised wrist pose, bangles catching light, beautiful movement and detail",
        ]
    },

    "ladies_bracelet": {
        "models": ["F1", "F2"],
        "zone": "wrist",
        "templates": [
            "female wrist close-up, bracelet as elegant accent, clean composition",
            "hand and wrist in natural pose, bracelet draping beautifully",
            "crossed arms or wrist detail, bracelet as statement piece",
        ]
    },

    "gents_bracelet": {
        "models": ["M1", "M3"],
        "zone": "wrist",
        "templates": [
            "male wrist, bracelet on masculine forearm, confident styling",
            "wrist with watch or cuff, bracelet as complementary piece",
            "crossed arms lifestyle pose, bracelet as subtle luxury detail",
        ]
    },

    "ladies_kada": {
        "models": ["F1", "F2", "F4"],
        "zone": "wrist",
        "templates": [
            "wrist close-up, kada as bold statement piece, feminine wrist",
            "both wrists visible, kada styling, traditional elegance",
            "raised wrist pose, kada catching studio light",
        ]
    },

    "gents_kada": {
        "models": ["M1", "M2", "M3"],
        "zone": "wrist",
        "templates": [
            "wrist close-up, kada on masculine wrist, powerful and premium",
            "folded arms pose, kada visible on forearm, confident stance",
            "lifestyle wrist pose, kada as signature piece, editorial masculine look",
        ]
    },

    "waist_belt": {
        "models": ["F2", "F3"],
        "zone": "waist",
        "templates": [
            "waist crop, kamarbandh/waist belt as centrepiece, saree or lehenga styling",
            "three-quarter body, full waist jewellery visible in context of bridal/festive outfit",
            "bridal pose, waist belt as part of complete bridal ensemble",
        ]
    },

    "payal": {
        "models": ["F1", "F2", "F3"],
        "zone": "feet",
        "templates": [
            "standing feet close-up, anklets on both feet, elegant foot positioning on marble or wooden floor",
            "walking pose, anklets in gentle motion, lifestyle candid feel",
            "seated feet detail, anklets draped beautifully, soft floral or fabric background",
        ]
    },

    "wati": {
        "models": ["F2", "F3"],
        "zone": "feet",
        "templates": [
            "feet close-up, toe rings prominently visible, bridal or traditional styling",
            "walking feet, toe rings captured in motion, candid and beautiful",
            "bridal foot pose, henna and toe rings, traditional styling",
        ]
    },

    "diamond": {
        "models": ["F1"],
        "zone": "face",
        "templates": [
            "glamorous front portrait, diamond jewellery as ultimate luxury statement, high-fashion editorial",
            "45-degree glamour pose, diamond catching light, sophisticated and striking",
            "side profile, diamond jewellery in cinematic close-up, luxury lifestyle aesthetic",
        ]
    },

    "silver": {
        "models": ["F1", "F2"],
        "zone": "neck",
        "templates": [
            "contemporary styling, silver jewellery as clean modern statement",
            "traditional festive look, silver complementing ethnic outfit",
            "lifestyle portrait, silver jewellery in natural setting",
        ]
    },
}

# Default for unknown categories
DEFAULT_TEMPLATE = {
    "models": ["F1", "F2"],
    "zone": "neck",
    "templates": [
        "front portrait, jewellery prominently displayed, elegant model",
        "45-degree portrait, jewellery as focal point, graceful angle",
        "half-body editorial, jewellery styled as hero piece",
    ]
}


def get_templates(category: str) -> dict:
    """Get the full template config for a category."""
    # Normalize category name
    cat = category.lower().strip()
    # Try direct match, then partial match
    if cat in CATEGORY_TEMPLATES:
        return CATEGORY_TEMPLATES[cat]
    for key in CATEGORY_TEMPLATES:
        if key in cat or cat in key:
            return CATEGORY_TEMPLATES[key]
    return DEFAULT_TEMPLATE


def build_model_prompt(category: str, job_id: str, variant: int,
                       model_override: str = None) -> str:
    """
    Build a complete Codex prompt for a model/lifestyle shot.
    variant: 1, 2, or 3
    """
    cfg       = get_templates(category)
    cat_label = category.replace("_", " ").title()
    zone      = cfg["zone"]
    template  = cfg["templates"][(variant - 1) % len(cfg["templates"])]

    # Pick model
    model_key = model_override or cfg["models"][0]
    model_desc = MODELS.get(model_key, MODELS["F1"])
    camera_spec = CAMERA.get(zone, CAMERA["neck"])

    return (
        f"{job_id}_MODEL_V{variant} | {cat_label} lifestyle catalogue image — variant {variant}/3\n\n"

        f"TASK: Create a professional jewellery catalogue lifestyle photograph showing "
        f"the {cat_label} from image 1 being worn by a model.\n\n"

        f"MODEL: {model_desc}\n\n"

        f"SHOT SPECIFICATION:\n"
        f"- Composition: {template}\n"
        f"- Camera: {camera_spec}\n\n"

        f"LIGHTING & ENVIRONMENT:\n"
        f"{LIGHTING}\n\n"

        f"JEWELLERY ACCURACY — CRITICAL:\n"
        f"- The jewellery in the lifestyle image must look IDENTICAL to image 1\n"
        f"- Same design, same stones, same gold colour, same every detail\n"
        f"- The piece must be SHARPER and more DETAILED than anything else in the frame\n"
        f"- The jewellery is the undisputed HERO of this photograph\n"
        f"- Do NOT simplify, alter, or recreate the design — exact reproduction only\n\n"

        f"BRAND WATERMARK — MANDATORY:\n"
        f"- Place the ARADHANA JEWELLERS logo (A monogram + text) at bottom-right corner\n"
        f"- Watermark opacity: 35% — clearly visible but non-intrusive\n\n"

        f"FINAL OUTPUT: Square (1:1) high-resolution lifestyle catalogue image.\n"
        f"Professional, luxury, ready for print and digital catalogue use.\n"
        f"No extra text, borders, or graphics beyond the Aradhana watermark.\n\n"

        f"Reply on the last line only: MODEL_DONE: {variant}"
    )


def get_model_for_category(category: str, index: int = 0) -> str:
    """Return the preferred model key for a category."""
    cfg    = get_templates(category)
    models = cfg["models"]
    return models[index % len(models)]
