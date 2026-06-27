"""Diagnostic — connect to Gemini Chrome and dump the real DOM structure."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os

BASE = r"C:\Users\kaila\Desktop\JewelleryCatalogTool"
cd = os.path.join(BASE, "chromedriver.exe")
svc = Service(cd) if os.path.exists(cd) else None
opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=svc, options=opts) if svc else webdriver.Chrome(options=opts)

# Switch to gemini tab
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "gemini" in driver.current_url.lower():
        break

print("URL:", driver.current_url)
print("="*60)

# 1. Input element
info = driver.execute_script("""
    const out = {};
    const rt = document.querySelector('rich-textarea');
    out.has_rich_textarea = !!rt;
    if (rt) {
        const ce = rt.querySelector('[contenteditable="true"]');
        out.rt_inner_ce = !!ce;
        out.rt_inner_tag = ce ? ce.tagName : null;
    }
    // all contenteditable
    out.all_ce = Array.from(document.querySelectorAll('[contenteditable="true"]'))
        .map(e => ({tag: e.tagName, cls: (e.className||'').substring(0,40),
                    w: e.offsetWidth, visible: e.offsetParent !== null}));
    // file inputs
    out.file_inputs = document.querySelectorAll('input[type=file]').length;
    // send button candidates
    out.buttons_with_send = Array.from(document.querySelectorAll('button'))
        .filter(b => /send/i.test((b.getAttribute('aria-label')||'') + (b.title||'')))
        .map(b => ({label: b.getAttribute('aria-label'), disabled: b.disabled}));
    return out;
""")
import json
print(json.dumps(info, indent=2))
