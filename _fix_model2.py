import sys, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import os

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=Service(os.path.join(BASE,"chromedriver.exe")), options=opts)
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower(): break

# Click the Flash-Lite button to open model dropdown
print("Clicking Flash-Lite picker...")
driver.execute_script("""
    const btn = Array.from(document.querySelectorAll('button'))
        .find(b => b.textContent.includes('Flash-Lite') || 
              (b.getAttribute('aria-label')||'').includes('mode picker'));
    if (btn) btn.click();
""")
time.sleep(2)

# Get everything in overlays / menus
result = driver.execute_script("""
    const overlay = document.querySelector('.cdk-overlay-container');
    if (!overlay) return {error: 'no overlay'};
    const items = Array.from(overlay.querySelectorAll('*'))
        .filter(e => e.children.length === 0 && e.textContent.trim().length > 0)
        .map(e => ({text: e.textContent.trim(), tag: e.tagName, cls: e.className.substring(0,30)}))
        .filter(e => e.text.length < 60);
    return items;
""")
print("Overlay items:", json.dumps(result, indent=2))

# Also check for stop button / current generation state  
state = driver.execute_script("""
    const stop = document.querySelector('button[aria-label*="Stop"]');
    const imgs = Array.from(document.querySelectorAll('img'))
        .filter(i => i.offsetWidth > 150)
        .map(i => ({src: i.src.substring(0,80), w: i.offsetWidth, h: i.offsetHeight}));
    return {generating: !!stop, new_imgs: imgs};
""")
print("Generation state:", json.dumps(state, indent=2))
