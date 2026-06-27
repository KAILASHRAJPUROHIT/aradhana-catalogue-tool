import sys, time
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

# Known input thumbnail srcs to exclude
input_srcs = set()
try:
    for el in driver.find_elements(By.TAG_NAME, 'img'):
        s = el.get_attribute('src') or ''
        if s: input_srcs.add(s)
except: pass
print(f"Snapshotted {len(input_srcs)} existing imgs")

print("Waiting for generated image (>300px)...")
for t in range(120):
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    
    stop = driver.execute_script(
        "return !!document.querySelector('button[aria-label*=\"Stop\"]');")
    
    imgs = driver.find_elements(By.TAG_NAME, 'img')
    new_large = []
    for el in imgs:
        try:
            s = el.get_attribute('src') or ''
            if not s or s in input_srcs: continue
            sz = el.size
            w, h = sz.get('width',0), sz.get('height',0)
            if w > 200 and h > 200:
                new_large.append((s, w, h))
        except: pass
    
    if new_large:
        print(f"✅ GENERATED IMAGE FOUND at t={t}s!")
        for s, w, h in new_large:
            print(f"   {w}x{h}  {s[:100]}")
        break
    
    if t % 5 == 0:
        print(f"  t={t}s generating={stop} total_imgs={len(imgs)}")
    
    if not stop and t > 3:
        print(f"  Stop button gone at t={t}s — final scan")
        time.sleep(2)
        for el in driver.find_elements(By.TAG_NAME, 'img'):
            try:
                s = el.get_attribute('src') or ''
                if not s or s in input_srcs: continue
                sz = el.size
                if sz.get('width',0) > 100:
                    print(f"  img: {sz['width']}x{sz['height']} {s[:100]}")
            except: pass
        break
