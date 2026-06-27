import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
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
print("Title:", driver.title)

# What's in the input right now?
info = driver.execute_script("""
    const inp = document.querySelector('#prompt-textarea');
    const composer = inp ? (inp.closest('form') || inp.parentElement?.parentElement) : null;
    const thumbnails = composer ? composer.querySelectorAll('img').length : 0;
    const text = inp ? inp.textContent.trim().substring(0, 100) : 'NOT FOUND';
    // Send button state
    const sendBtn = document.querySelector('button[data-testid="send-button"]');
    // File input
    const fileInput = document.querySelector('input[type="file"]');
    // Any dialogs/modals
    const modal = document.querySelector('[role="dialog"], [class*="modal"], [class*="dialog"]');
    return {
        input_found: !!inp,
        input_text: text,
        thumbnails: thumbnails,
        send_btn_exists: !!sendBtn,
        send_btn_disabled: sendBtn ? sendBtn.disabled : null,
        file_input_exists: !!fileInput,
        modal: modal ? modal.textContent.substring(0,100) : null
    };
""")
print(json.dumps(info, indent=2))

# Close the Share modal
closed = driver.execute_script("""
    // Try Escape key first
    document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
    // Then try clicking close/cancel buttons inside the dialog
    const modal = document.querySelector('[role="dialog"]');
    if (modal) {
        const close = modal.querySelector('button[aria-label*="Close"], button[aria-label*="close"], button:last-child');
        if (close) { close.click(); return 'clicked close'; }
    }
    return 'escape sent';
""")
import time; time.sleep(0.5)
print("Closed dialog:", closed)
print("Modal now:", driver.execute_script("""
    const m = document.querySelector('[role="dialog"]');
    return m ? m.textContent.substring(0,50) : 'none';
"""))
