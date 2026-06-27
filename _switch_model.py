import sys, time, json
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

# Click model picker at calibrated coordinate (838, 407)
print("Clicking model picker...")
driver.execute_cdp_cmd("Input.dispatchMouseEvent",
    {"type":"mousePressed","x":838,"y":407,"button":"left","clickCount":1})
driver.execute_cdp_cmd("Input.dispatchMouseEvent",
    {"type":"mouseReleased","x":838,"y":407,"button":"left","clickCount":1})
time.sleep(1.5)

# What options appeared?
items = driver.execute_script("""
    const overlay = document.querySelector('.cdk-overlay-container');
    if (!overlay) return [];
    return Array.from(overlay.querySelectorAll('*'))
        .filter(e => e.children.length === 0 && e.textContent.trim().length > 0)
        .map(e => ({text: e.textContent.trim().substring(0,50), 
                    tag: e.tagName,
                    x: Math.round(e.getBoundingClientRect().left + e.getBoundingClientRect().width/2),
                    y: Math.round(e.getBoundingClientRect().top + e.getBoundingClientRect().height/2)}))
        .filter(e => e.text.length > 1 && e.text.length < 40);
""")
print("Model options:")
for i in items:
    print(f"  [{i['tag']}] ({i['x']},{i['y']}) {i['text']}")
