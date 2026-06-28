"""Bulk delete all ChatGPT conversations via API using browser cookies."""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os, requests

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(service=Service(os.path.join(BASE,"chromedriver.exe")), options=opts)
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "chatgpt" in driver.current_url.lower():
        break

cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
ua = driver.execute_script("return navigator.userAgent;")
headers = {"User-Agent": ua, "Content-Type": "application/json",
           "Origin": "https://chatgpt.com", "Referer": "https://chatgpt.com/"}

deleted = 0
offset = 0
while True:
    # Get conversations page by page
    r = requests.get(
        f"https://chatgpt.com/backend-api/conversations?offset={offset}&limit=50&order=updated",
        headers=headers, cookies=cookies, timeout=15)
    
    if r.status_code != 200:
        print(f"List failed: {r.status_code}")
        break
    
    data = r.json()
    convs = data.get("items", [])
    if not convs:
        break
    
    for c in convs:
        title = c.get("title", "").strip()
        cid   = c.get("id", "")
        # Delete "New chat" and "Jewellery Extraction" test chats
        if title in ("New chat", "") or "jewellery" in title.lower() or "extraction" in title.lower():
            dr = requests.delete(
                f"https://chatgpt.com/backend-api/conversation/{cid}",
                headers=headers, cookies=cookies, timeout=10)
            status = "✓" if dr.status_code in (200, 204) else f"✗{dr.status_code}"
            print(f"{status} {title[:40]!r} ({cid[-8:]})")
            if dr.status_code in (200, 204):
                deleted += 1
            time.sleep(0.3)   # be gentle with the API
        else:
            print(f"  skip: {title[:50]!r}")
    
    if not data.get("has_missing_conversations") and len(convs) < 50:
        break
    offset += 50

print(f"\nDeleted {deleted} conversations")
