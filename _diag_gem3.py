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
cd = os.path.join(BASE, "chromedriver.exe")
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=Service(cd), options=opts)
wait = WebDriverWait(driver, 10)

for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower(): break

# Real Selenium click on Upload & tools
print("Clicking Upload & tools with Selenium...")
try:
    btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, 'button[aria-label="Upload & tools"]')))
    btn.click()
    time.sleep(1.5)
except Exception as e:
    print("Button click error:", e)

# What appeared?
result = driver.execute_script("""
    return {
        file_inputs: Array.from(document.querySelectorAll('input[type=file]'))
            .map(i => ({accept: i.accept, multiple: i.multiple, visible: i.offsetParent !== null})),
        new_buttons: Array.from(document.querySelectorAll('[role=menuitem],[role=option]'))
            .filter(e => e.offsetParent)
            .map(e => e.textContent.trim().substring(0,40)),
        overlay: !!document.querySelector('[role=menu],[class*="overlay"],[class*="panel"]')
    };
""")
print("After real click:", json.dumps(result, indent=2))
