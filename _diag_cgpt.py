import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os, json

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

print("URL:", driver.current_url)

info = driver.execute_script("""
    const out = {};
    // input box
    const inp = document.querySelector('#prompt-textarea, div[contenteditable="true"]');
    out.input_tag  = inp ? inp.tagName : null;
    out.input_id   = inp ? inp.id : null;
    out.input_text = inp ? inp.textContent.substring(0,50) : null;

    // ALL buttons visible
    out.buttons = Array.from(document.querySelectorAll('button'))
        .filter(b => b.offsetParent !== null)
        .map(b => ({
            testid:   b.getAttribute('data-testid') || '',
            label:    b.getAttribute('aria-label') || '',
            disabled: b.disabled,
            cls:      (b.className||'').substring(0,40)
        }));
    return out;
""")
print(json.dumps(info, indent=2))
