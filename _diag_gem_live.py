import sys, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import os

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
cd = os.path.join(BASE, "chromedriver.exe")
svc = Service(cd) if os.path.exists(cd) else None
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=svc, options=opts) if svc else webdriver.Chrome(options=opts)

for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower():
        break

print("URL:", driver.current_url)

info = driver.execute_script("""
    const out = {};

    // 1. Input box
    const rt = document.querySelector('rich-textarea');
    out.has_rich_textarea = !!rt;
    if (rt) {
        const ce = rt.querySelector('[contenteditable="true"]');
        out.input_class = ce ? ce.className.substring(0,60) : null;
        out.input_found = !!ce;
    }

    // 2. The + button
    const plus = document.querySelector('button[data-testid="composer-plus-btn"]') ||
                 Array.from(document.querySelectorAll('button')).find(b =>
                     (b.getAttribute('aria-label')||'').toLowerCase().includes('upload') ||
                     (b.getAttribute('aria-label')||'') === 'Upload & tools' ||
                     b.textContent.trim() === '+');
    out.plus_btn_label = plus ? (plus.getAttribute('aria-label') || plus.textContent.trim()) : null;
    out.plus_btn_testid = plus ? plus.getAttribute('data-testid') : null;

    // 3. File input
    out.file_inputs = document.querySelectorAll('input[type="file"]').length;

    // 4. Send button
    const send = Array.from(document.querySelectorAll('button')).find(b =>
        /send/i.test(b.getAttribute('aria-label')||'') ||
        /send/i.test(b.getAttribute('data-testid')||'') ||
        b.getAttribute('mattooltip') === 'Send message');
    out.send_btn_label = send ? (send.getAttribute('aria-label')||send.getAttribute('mattooltip')||'') : null;
    out.send_btn_testid = send ? send.getAttribute('data-testid') : null;
    out.send_btn_disabled = send ? send.disabled : null;

    // 5. All visible buttons
    out.buttons = Array.from(document.querySelectorAll('button'))
        .filter(b => b.offsetParent !== null)
        .map(b => ({
            label: b.getAttribute('aria-label') || b.getAttribute('mattooltip') || '',
            testid: b.getAttribute('data-testid') || '',
            icon: (b.querySelector('mat-icon')||{textContent:''}).textContent.trim(),
            text: b.textContent.trim().substring(0,20)
        }))
        .filter(b => b.label || b.testid || b.icon);

    return out;
""")
print(json.dumps(info, indent=2))
