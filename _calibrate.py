import sys, os, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=Service(os.path.join(BASE,"chromedriver.exe")), options=opts)
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower(): break

# Get viewport size
size = driver.execute_script("return {w: window.innerWidth, h: window.innerHeight};")
print(f"Viewport: {size['w']} x {size['h']}")

# Save screenshot
png = driver.get_screenshot_as_png()
out = os.path.join(BASE, "_gemini_calibration.png")
with open(out, "wb") as f: f.write(png)
print(f"Screenshot saved: {out}")

# Get exact positions of key elements
coords = driver.execute_script("""
    function rect(sel) {
        const el = document.querySelector(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2),
                w: Math.round(r.width), h: Math.round(r.height), found: true};
    }
    return {
        input:    rect('rich-textarea .ql-editor') || rect('rich-textarea'),
        upload:   rect('button[aria-label="Upload & tools"]'),
        send:     rect('button[aria-label="Send message"]') || rect('button[aria-label*="Send"]'),
        rt:       rect('rich-textarea'),
        body_h:   document.body.scrollHeight
    };
""")
import json
print("Element coordinates:")
print(json.dumps(coords, indent=2))
