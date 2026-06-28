import sys, time, json
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
    if "chatgpt" in driver.current_url.lower():
        break

print(f"On: {driver.current_url}")
time.sleep(2)

# Use browser fetch (sends HTTPOnly cookies automatically)
result = driver.execute_script("""
    return fetch('/backend-api/conversations?offset=0&limit=100&order=updated', {
        credentials: 'include'
    }).then(r => r.json()).catch(e => ({error: String(e)}));
""")

if "error" in result:
    print("Error:", result["error"])
else:
    convs = result.get("items", [])
    print(f"Found {len(convs)} conversations")
    
    to_delete = [c for c in convs if 
                 c.get("title","").strip() in ("New chat","") or
                 "jewellery" in c.get("title","").lower() or
                 "extraction" in c.get("title","").lower()]
    print(f"To delete: {len(to_delete)}")
    
    deleted = 0
    for c in to_delete:
        cid = c["id"]
        r = driver.execute_script(f"""
            return fetch('/backend-api/conversation/{cid}', {{
                method: 'DELETE', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}}
            }}).then(r => r.status).catch(e => 0);
        """)
        if r in (200, 204):
            print(f"  ✓ {c.get('title','?')[:30]!r}")
            deleted += 1
        else:
            print(f"  ✗ {r} {c.get('title','?')[:30]!r}")
        time.sleep(0.4)
    
    print(f"\nDeleted {deleted}/{len(to_delete)}")
