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

# Click the model picker
print("Clicking model picker...")
try:
    btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="mode picker"]')
    btn.click()
    time.sleep(1.5)
except Exception as e:
    print("Picker error:", e)

# Dump what appeared
result = driver.execute_script("""
    // Get ALL text elements that appeared
    const all = Array.from(document.querySelectorAll('*'))
        .filter(e => e.offsetParent !== null && e.children.length === 0)
        .map(e => e.textContent.trim())
        .filter(t => t.length > 0 && t.length < 50);
    return [...new Set(all)];
""")
print("All text nodes visible:", json.dumps(result[:50], indent=2))
