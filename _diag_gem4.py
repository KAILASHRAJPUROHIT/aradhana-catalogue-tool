import sys, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=Service(os.path.join(BASE,"chromedriver.exe")), options=opts)

for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower(): break

# Overlay is open — dump everything inside it
result = driver.execute_script("""
    // Find the overlay/panel
    const overlays = document.querySelectorAll('[role=menu],[class*="overlay"],[class*="panel"],[class*="menu"]');
    const out = [];
    overlays.forEach(o => {
        if (o.offsetParent || o.offsetHeight > 0) {
            out.push({
                tag: o.tagName,
                cls: o.className.substring(0,60),
                role: o.getAttribute('role')||'',
                children: Array.from(o.querySelectorAll('button,a,[role=menuitem],[role=option]'))
                    .filter(e => e.offsetParent || e.offsetHeight > 0)
                    .map(e => ({
                        tag: e.tagName,
                        text: e.textContent.trim().substring(0,50),
                        label: e.getAttribute('aria-label')||'',
                        role: e.getAttribute('role')||''
                    }))
            });
        }
    });
    return out;
""")
print("Overlay contents:", json.dumps(result, indent=2))
