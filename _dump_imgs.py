import sys, json
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

driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
import time; time.sleep(1)

# Dump ALL images with ALL attributes
result = driver.execute_script("""
    return Array.from(document.querySelectorAll('img')).map(img => ({
        src: (img.src||'').substring(0,100),
        currentSrc: (img.currentSrc||'').substring(0,100),
        naturalW: img.naturalWidth,
        naturalH: img.naturalHeight,
        offsetW: img.offsetWidth,
        offsetH: img.offsetHeight,
        srcset: (img.srcset||'').substring(0,60),
        dataSrc: img.getAttribute('data-src')||'',
        loading: img.loading,
        complete: img.complete
    }));
""")
print(f"Total imgs: {len(result)}")
for i, img in enumerate(result):
    print(f"[{i}] nat={img['naturalW']}x{img['naturalH']} off={img['offsetW']}x{img['offsetH']} complete={img['complete']}")
    print(f"     src={img['src']}")
    if img['srcset']: print(f"     srcset={img['srcset']}")

# Also check for canvas elements (Gemini might render image there)
canvases = driver.execute_script("""
    return Array.from(document.querySelectorAll('canvas')).map(c => ({
        w: c.width, h: c.height, offsetW: c.offsetWidth, offsetH: c.offsetHeight
    }));
""")
print(f"\nCanvas elements: {json.dumps(canvases)}")

# Check response area text for clues
resp = driver.execute_script("""
    const msgs = Array.from(document.querySelectorAll('model-response, [class*="response"], [data-message-author-role=assistant]'));
    return msgs.length ? msgs[msgs.length-1].textContent.substring(0,200) : document.body.innerText.substring(0,500);
""")
print(f"\nResponse text: {resp}")
