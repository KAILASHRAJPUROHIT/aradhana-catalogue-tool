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

# Click Upload & tools with Selenium
btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Upload & tools"]')
btn.click()
time.sleep(1.5)  # wait for Angular animation

# Deep inspection of the overlay
result = driver.execute_script("""
    // Look at mat-action-list items
    const list = document.querySelector('mat-action-list');
    if (!list) return {error: 'no mat-action-list'};
    
    const items = Array.from(list.querySelectorAll('*')).map(el => ({
        tag: el.tagName,
        text: el.textContent.trim().substring(0,50),
        cls: el.className.substring(0,40),
        visible: el.offsetParent !== null || el.offsetHeight > 0
    })).filter(e => e.text);
    
    // Also check for file input ANYWHERE in the document
    const fileInputs = Array.from(document.querySelectorAll('input[type=file]'))
        .map(i => ({accept: i.accept, multiple: i.multiple}));
    
    return {items, fileInputs, listHTML: list.innerHTML.substring(0, 500)};
""")
print(json.dumps(result, indent=2))
