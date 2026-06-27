import sys, json, time
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

# Navigate to fresh chat to get clean state
driver.get("https://gemini.google.com/app")
time.sleep(3)

# Click input and type something to reveal send button
driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
    "type": "mousePressed", "x": 640, "y": 734, "button": "left", "clickCount": 1})
driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
    "type": "mouseReleased", "x": 640, "y": 734, "button": "left", "clickCount": 1})
time.sleep(0.3)

# Type using CDP insertText
driver.execute_cdp_cmd("Input.insertText", {"text": "test"})
time.sleep(0.5)

# Now get ALL element coordinates
coords = driver.execute_script("""
    function rect(sel, label) {
        const el = document.querySelector(sel);
        if (!el) return {label, found: false};
        const r = el.getBoundingClientRect();
        return {label, found: true,
            x: Math.round(r.left + r.width/2),
            y: Math.round(r.top + r.height/2),
            top: Math.round(r.top), left: Math.round(r.left),
            w: Math.round(r.width), h: Math.round(r.height)};
    }
    return [
        rect('rich-textarea .ql-editor', 'input'),
        rect('rich-textarea', 'rich-textarea'),
        rect('button[aria-label="Upload & tools"]', 'upload'),
        rect('button[aria-label="Send message"]', 'send'),
        rect('button[aria-label*="Flash"]', 'model_picker'),
        rect('button[aria-label="Microphone"]', 'mic'),
        rect('button[aria-label="Open mode picker, currently Flash-Lite"]', 'flash_lite'),
    ];
""")
for c in coords:
    if c.get('found'):
        print(f"✓ {c['label']:20s} center=({c['x']},{c['y']}) size={c['w']}x{c['h']}")
    else:
        print(f"✗ {c['label']:20s} NOT FOUND")

# Save calibration screenshot
png = driver.get_screenshot_as_png()
with open(os.path.join(BASE, "_cal_with_text.png"), "wb") as f: f.write(png)
print("\nCalibration screenshot saved")

# Clear the test text
driver.execute_script("document.querySelector('rich-textarea .ql-editor').textContent='';")
