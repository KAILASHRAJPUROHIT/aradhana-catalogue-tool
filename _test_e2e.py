"""Full end-to-end Gemini test — upload images, send prompt, detect + download result."""
import sys, os, time, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\kaila\Desktop\JewelleryCatalogTool")

import gemini_bg

# Find first staged pair
PROC = r"C:\Users\kaila\Desktop\JewelleryCatalogTool\processing"
jewels = sorted([f for f in os.listdir(PROC) if "_jewel" in f.lower()])
tags   = sorted([f for f in os.listdir(PROC) if "_tag"   in f.lower()])
bgs    = [f for f in os.listdir(r"C:\Users\kaila\Desktop\JewelleryCatalogTool\backgrounds") if f.endswith(".png")]

if not jewels:
    print("No staged pairs found")
    sys.exit(1)

jewel = os.path.join(PROC, jewels[0])
tag   = os.path.join(PROC, tags[0]) if tags else jewel
bg    = os.path.join(r"C:\Users\kaila\Desktop\JewelleryCatalogTool\backgrounds", bgs[0])

print(f"Jewel: {jewels[0]}")
print(f"Tag:   {tags[0] if tags else 'none'}")
print(f"BG:    {bgs[0]}")
print()

start = time.time()
result = gemini_bg.process(
    jewel_path=jewel, tag_path=tag, bg_path=bg,
    category="earrings", pair_num="e2e_test", job_id="E2ETEST"
)
elapsed = time.time() - start

print(f"\n{'='*50}")
print(f"Result:  {result}")
print(f"Time:    {elapsed:.1f}s")
if result.get("output"):
    sz = os.path.getsize(result["output"])
    print(f"File:    {result['output']} ({sz//1024}KB)")
