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

print("Watching generation... polling every second")
for t in range(120):
    state = driver.execute_script("""
        const stop = !!document.querySelector('button[aria-label*="Stop"], button[aria-label*="stop"]');
        const dots = !!document.querySelector('[class*="loading"], [class*="spinner"], .dots');
        const allImgs = Array.from(document.querySelectorAll('img'))
            .map(i => ({src: (i.src||'').substring(0,100), w: i.offsetWidth, h: i.offsetHeight}))
            .filter(i => i.w > 100 && i.h > 100);
        return {stop, dots, t: arguments[0], imgs: allImgs};
    """, t)
    
    print(f"t={t}s stop={state['stop']} imgs={len(state['imgs'])}")
    if state['imgs']:
        for img in state['imgs']:
            print(f"  IMG: {img['w']}x{img['h']} {img['src']}")
        break
    if not state['stop'] and t > 5:
        print("Stop button gone — generation complete, scanning...")
        time.sleep(2)
        # Final scan
        imgs = driver.find_elements(By.TAG_NAME, 'img')
        for el in imgs:
            try:
                w = el.size.get('width', 0)
                h = el.size.get('height', 0)
                s = el.get_attribute('src') or ''
                if w > 100 and h > 100:
                    print(f"FOUND: {w}x{h} {s[:100]}")
            except: pass
        break
    time.sleep(1)
