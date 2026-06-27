import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import os, json, time

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
cd = os.path.join(BASE, "chromedriver.exe")
svc = Service(cd) if os.path.exists(cd) else None
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(service=svc, options=opts) if svc else webdriver.Chrome(options=opts)
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "chatgpt" in driver.current_url.lower():
        break

# Type test text into the input
inp = driver.find_element(By.ID, "prompt-textarea")
inp.click()
time.sleep(0.3)
inp.send_keys("test")
time.sleep(0.5)

# Now dump buttons again
btns = driver.execute_script("""
    return Array.from(document.querySelectorAll('button'))
        .filter(b => b.offsetParent !== null)
        .map(b => ({
            testid:   b.getAttribute('data-testid') || '',
            label:    b.getAttribute('aria-label') || '',
            disabled: b.disabled,
            cls:      (b.className||'').substring(0,50)
        }))
        .filter(b => b.label || b.testid);
""")
print(json.dumps(btns, indent=2))

# Clear it
inp.clear()
