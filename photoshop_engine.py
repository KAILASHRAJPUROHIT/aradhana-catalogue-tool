"""
Photoshop + Gemma 4 jewellery catalogue engine.
Pipeline:
  1. Gemma 4 reads the price tag label
  2. Photoshop: Select Subject AI → remove background
  3. Open background image → paste jewellery on top → flatten
  4. Save to output_aradhana\{category}\{label}.jpg
"""
import sys, os, io, time, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE            = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
OUTPUT          = os.path.join(BASE, "output_aradhana")
BACKGROUNDS_DIR = os.path.join(BASE, "backgrounds")

# ── Gemma 4 — read price tag ─────────────────────────────────────────────────

def read_tag_label(tag_path: str) -> str:
    try:
        from google import genai
        from google.genai import types as gt
        from PIL import Image
        from keys import GEMINI_API_KEY
        client = genai.Client(api_key=GEMINI_API_KEY)
        pil = Image.open(tag_path).convert("RGB")
        pil.thumbnail((512, 512))
        buf = io.BytesIO(); pil.save(buf, "JPEG", quality=90)
        resp = client.models.generate_content(
            model="gemma-4-31b-it",
            contents=[
                gt.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                "Read this price tag. What is the item code on the FIRST LINE? "
                "Reply with ONLY the code, nothing else. Example: JB617 or DL22/4 or TP22/157"
            ]
        )
        raw = resp.text.strip().split("\n")[0].strip()
        label = re.sub(r"[^\w/\-]", "", raw)[:20]
        print(f"  Label: {label}")
        return label
    except Exception as e:
        print(f"  Tag read failed: {e}")
        return ""


# ── Photoshop pipeline ───────────────────────────────────────────────────────

def process_pair(jewel_path: str, tag_path: str, bg_path: str,
                 category: str = "earrings", pair_num: str = "",
                 status_fn=None) -> dict:
    """
    Full pipeline. Returns {"label": str, "output": str|None, "error": str|None}
    """
    def _st(msg):
        print(f"  [{pair_num}] {msg}")
        if status_fn:
            status_fn(msg)

    t0 = time.time()

    # Step 1 — read tag label
    _st("Reading tag label…")
    label = read_tag_label(tag_path) or f"AJ-{pair_num or '000'}"

    # Step 2 — open Photoshop and process
    _st("Opening Photoshop…")
    try:
        import photoshop.api as ps
    except ImportError:
        return {"label": label, "output": None,
                "error": "photoshop package not installed (pip install photoshop-python-api)"}

    app = ps.Application()
    tmp_png = os.path.join(BASE, "processing", "_tmp_jewel_nobg.png")

    # ── Step 2: Open jewellery, remove background, save as transparent PNG ──
    _st("Opening jewellery image…")
    jewel_doc = app.open(os.path.abspath(jewel_path))
    time.sleep(1)

    _st("Removing background (Select Subject AI)…")
    result_js = app.doJavaScript("""
        var doc = app.activeDocument;

        // Convert to RGB with alpha if needed
        if (doc.mode !== DocumentMode.RGB) {
            doc.changeMode(ChangeMode.RGB);
        }

        // Unlock background layer so we can edit it
        try { doc.activeLayer.isBackgroundLayer = false; } catch(e) {}

        // Method 1: autoCutout (PS 2021+) — removes BG directly
        var method = "none";
        try {
            executeAction(stringIDToTypeID("autoCutout"),
                          new ActionDescriptor(), DialogModes.NO);
            method = "autoCutout";
        } catch(e1) {
            // Method 2: Select Subject → invert → delete
            try {
                var sd = new ActionDescriptor();
                sd.putBoolean(stringIDToTypeID("sampleAllLayers"), false);
                executeAction(stringIDToTypeID("selectSubject"), sd, DialogModes.NO);
                // Invert to select background
                executeAction(charIDToTypeID("Invr"), new ActionDescriptor(), DialogModes.NO);
                // Delete background pixels
                executeAction(charIDToTypeID("Dlt "), new ActionDescriptor(), DialogModes.NO);
                // Deselect all
                executeAction(charIDToTypeID("Dsel"), new ActionDescriptor(), DialogModes.NO);
                method = "selectSubject";
            } catch(e2) {
                method = "failed:" + e2.toString();
            }
        }
        method;
    """)
    _st(f"BG removal: {result_js} ({time.time()-t0:.1f}s)")

    if str(result_js).startswith("failed"):
        jewel_doc.close(ps.SaveOptions.DoNotSaveChanges)
        return {"label": label, "output": None, "error": f"BG removal failed: {result_js}"}

    # Save jewellery as transparent PNG (no clipboard needed)
    _st("Saving transparent jewellery PNG…")
    try:
        png_opts = ps.PNGSaveOptions()
        jewel_doc.saveAs(os.path.abspath(tmp_png), png_opts, asCopy=True)
        jewel_doc.close(ps.SaveOptions.DoNotSaveChanges)
    except Exception as e:
        try: jewel_doc.close(ps.SaveOptions.DoNotSaveChanges)
        except: pass
        return {"label": label, "output": None, "error": f"PNG save failed: {e}"}

    # ── Step 3: Open background, place jewellery PNG on top ─────────────────
    _st("Opening background…")
    bg_doc = app.open(os.path.abspath(bg_path))
    time.sleep(1)

    _st("Placing jewellery on background…")
    abs_tmp = os.path.abspath(tmp_png).replace("\\", "\\\\")
    app.doJavaScript(f"""
        var doc = app.activeDocument;
        var tmpFile = new File("{abs_tmp}");

        // Place jewellery PNG as an embedded smart object
        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), tmpFile);
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"),
                           charIDToTypeID("Qcsa"));
        executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);

        // Commit the placement (same as pressing Enter) BEFORE touching the layer
        executeAction(charIDToTypeID("Cmmt"), new ActionDescriptor(), DialogModes.NO);

        // Rasterize the placed smart object layer
        executeAction(stringIDToTypeID("rasterizeLayer"),
                      new ActionDescriptor(), DialogModes.NO);

        // Scale to fit within 85% of canvas, centred
        var layer = doc.activeLayer;
        var bounds = layer.bounds;
        var lw = bounds[2].value - bounds[0].value;
        var lh = bounds[3].value - bounds[1].value;
        var cw = doc.width.value;
        var ch = doc.height.value;
        var scale = Math.min((cw * 0.85) / lw, (ch * 0.85) / lh, 1.0) * 100;
        if (scale < 99) {{
            layer.resize(scale, scale, AnchorPosition.MIDDLECENTER);
        }}
        // Centre
        var b2 = layer.bounds;
        layer.translate(
            (cw - (b2[2].value - b2[0].value)) / 2 - b2[0].value,
            (ch - (b2[3].value - b2[1].value)) / 2 - b2[1].value
        );
        "placed";
    """)

    # ── Step 4: Flatten and save as JPEG ────────────────────────────────────
    safe    = re.sub(r'[/\\:*?"<>|]', "_", label)
    out_dir = os.path.join(OUTPUT, category)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{safe}.jpg")

    _st("Flattening and saving JPEG…")
    try:
        bg_doc.flatten()
        opts = ps.JPEGSaveOptions(quality=12)
        bg_doc.saveAs(os.path.abspath(out_path), opts, asCopy=True)
        bg_doc.close(ps.SaveOptions.DoNotSaveChanges)
        # Clean up temp file
        try: os.remove(tmp_png)
        except: pass
        sz = os.path.getsize(out_path)
        _st(f"✓ Saved {label} ({sz//1024}KB) in {time.time()-t0:.1f}s")
        return {"label": label, "output": out_path, "error": None}
    except Exception as e:
        try: bg_doc.close(ps.SaveOptions.DoNotSaveChanges)
        except: pass
        return {"label": label, "output": None, "error": str(e)}


# ── Quick test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import glob
    proc_files = sorted(glob.glob(os.path.join(BASE, "processing", "*.jp*g")))
    jewel = next((f for f in proc_files if "_jewel" in f), None)
    tag   = next((f for f in proc_files if "_tag" in f), None)
    bg    = os.path.join(BACKGROUNDS_DIR, "earrings.png")

    if not jewel:
        print("No files in processing\\ — put staged pairs there first.")
        sys.exit(1)

    print(f"Jewel: {jewel}")
    print(f"Tag:   {tag}")
    print(f"BG:    {bg}")
    print()
    result = process_pair(jewel, tag or jewel, bg, category="earrings", pair_num="test")
    print("\nResult:", result)
