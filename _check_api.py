import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(service=Service(os.path.join(BASE,"chromedriver.exe")), options=opts)
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "chatgpt" in driver.current_url.lower(): break

for url in ['/backend-api/conversations?limit=5&offset=0', '/backend-api/me']:
    r = driver.execute_script(f"""
        return fetch("{url}", {{credentials:"include"}})
            .then(r => r.status + ' ' + r.url.split('/').slice(-1)[0])
            .catch(e => 'ERR:' + e);
    """)
    print(f"{url}: {r}")
