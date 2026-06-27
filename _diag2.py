import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os, json, time

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
cd = os.path.join(BASE, "chromedriver.exe")
svc = Service(cd) if os.path.exists(cd) else None
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=svc, options=opts) if svc else webdriver.Chrome(options=opts)
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower():
        break

# Dump ALL buttons with their aria-labels and icon names
btns = driver.execute_script("""
    return Array.from(document.querySelectorAll('button')).map(b => ({
        label: b.getAttribute('aria-label') || '',
        testid: b.getAttribute('data-test-id') || b.getAttribute('data-testid') || '',
        mat: b.getAttribute('mattooltip') || b.getAttribute('matTooltip') || '',
        icon: (b.querySelector('mat-icon') || {}).getAttribute ? (b.querySelector('mat-icon').getAttribute('data-mat-icon-name') || b.querySelector('mat-icon').textContent || '') : '',
        cls: (b.className||'').substring(0,50),
        visible: b.offsetParent !== null
    })).filter(b => b.visible && (b.label || b.icon || b.testid || b.mat));
""")
print("BUTTONS:")
print(json.dumps(btns, indent=1))
