import sys, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import os

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
cd   = os.path.join(BASE, "chromedriver.exe")
svc  = Service(cd) if os.path.exists(cd) else None
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=svc, options=opts) if svc else webdriver.Chrome(options=opts)

for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower():
        break

# 1. Click Upload & tools button, see what file input appears
print("=== Clicking Upload & tools ===")
driver.execute_script("""
    const btn = Array.from(document.querySelectorAll('button'))
        .find(b => b.getAttribute('aria-label') === 'Upload & tools');
    if (btn) btn.click();
""")
time.sleep(1)

after_click = driver.execute_script("""
    return {
        file_inputs: document.querySelectorAll('input[type=file]').length,
        menu_items: Array.from(document.querySelectorAll('[role=menuitem],[role=option],button'))
            .filter(e => e.offsetParent)
            .map(e => e.textContent.trim().substring(0,30))
            .filter(t => t)
    };
""")
print("After click:", json.dumps(after_click, indent=2))

# Press Escape to close menu
driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
time.sleep(0.5)

# 2. Type in the Quill editor and find send button
print("\n=== Typing in input ===")
inp = driver.execute_script("""
    const rt = document.querySelector('rich-textarea');
    return rt ? rt.querySelector('.ql-editor') : null;
""")
if inp:
    inp.click()
    time.sleep(0.2)
    # Use execCommand
    result = driver.execute_script("""
        arguments[0].focus();
        return document.execCommand('insertText', false, 'test');
    """, inp)
    print("execCommand result:", result)
    time.sleep(0.5)
    
    # Find send button now
    send_info = driver.execute_script("""
        const btns = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent);
        return btns.filter(b => {
            const l = (b.getAttribute('aria-label')||b.getAttribute('mattooltip')||b.title||'').toLowerCase();
            return l.includes('send') || b.querySelector('[data-mat-icon-name="send"]') ||
                   b.querySelector('mat-icon')?.textContent?.trim() === 'send';
        }).map(b => ({
            label: b.getAttribute('aria-label')||b.getAttribute('mattooltip')||'',
            cls: b.className.substring(0,50),
            disabled: b.disabled,
            icon: b.querySelector('mat-icon')?.textContent?.trim()||''
        }));
    """)
    print("Send buttons after typing:", json.dumps(send_info, indent=2))
    
    # Clear input
    driver.execute_script("""
        const rt = document.querySelector('rich-textarea .ql-editor');
        if (rt) { rt.innerHTML = '<p><br></p>'; rt.dispatchEvent(new Event('input',{bubbles:true})); }
    """)
else:
    print("Input not found!")
