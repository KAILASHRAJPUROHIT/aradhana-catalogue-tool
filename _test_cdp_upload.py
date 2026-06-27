"""Test CDP DOM.setFileInputFiles — sets files directly without OS dialog."""
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=Service(os.path.join(BASE,"chromedriver.exe")), options=opts)
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower(): break

driver.get("https://gemini.google.com/app")
time.sleep(2.5)

# Click + button to trigger the menu and reveal the file input in DOM
print("Clicking + button...")
driver.execute_cdp_cmd("Input.dispatchMouseEvent",
    {"type":"mousePressed","x":366,"y":407,"button":"left","clickCount":1})
driver.execute_cdp_cmd("Input.dispatchMouseEvent",
    {"type":"mouseReleased","x":366,"y":407,"button":"left","clickCount":1})
time.sleep(1.5)

# Get document root nodeId
root = driver.execute_cdp_cmd("DOM.getDocument", {"depth": 1})["root"]["nodeId"]

# Find ALL file inputs via CDP (searches everywhere including shadow DOM)
try:
    result = driver.execute_cdp_cmd("DOM.querySelectorAll", {
        "nodeId": root, "selector": "input[type='file']"
    })
    nodeIds = result.get("nodeIds", [])
    print(f"File inputs found via CDP: {len(nodeIds)}")
    
    if nodeIds:
        # Test files
        proc = r"C:\Users\kaila\Desktop\JewelleryCatalogTool\processing"
        files = [os.path.join(proc, f) for f in os.listdir(proc) 
                 if "_jewel" in f.lower() or "_tag" in f.lower()][:2]
        bg = r"C:\Users\kaila\Desktop\JewelleryCatalogTool\backgrounds\earrings.png"
        if os.path.exists(bg): files.append(bg)
        
        print(f"Setting files: {[os.path.basename(f) for f in files]}")
        driver.execute_cdp_cmd("DOM.setFileInputFiles", {
            "files": files,
            "nodeId": nodeIds[0]
        })
        time.sleep(2)
        
        # Check if thumbnails appeared
        thumbs = driver.execute_script(
            "return document.querySelectorAll('rich-textarea img').length")
        print(f"Thumbnails after CDP upload: {thumbs}")
        
        # Save screenshot to verify
        png = driver.get_screenshot_as_png()
        with open(os.path.join(BASE, "_cdp_upload_test.png"), "wb") as f: f.write(png)
        print("Screenshot saved")
    else:
        print("No file inputs — need to click menu item first")
        # Check what's in the overlay
        items = driver.execute_script("""
            const ov = document.querySelector('.cdk-overlay-container');
            return ov ? ov.innerText.substring(0,200) : 'no overlay';
        """)
        print("Overlay text:", items)
except Exception as e:
    print(f"Error: {e}")
