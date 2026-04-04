"""
Visual QA script using Playwright.
Run locally to capture screenshots at multiple viewports.
Requires: pip install playwright && playwright install
Usage:
  python tools/visual_qa_playwright.py
Outputs screenshots to tools/visual-screens/
"""
from playwright.sync_api import sync_playwright
import os

PAGES = [
    ("/", "home"),
    ("/shop", "shop"),
    ("/admin/refunds", "admin-refunds"),
]
VIEWPORTS = [ (375, 667, 'mobile-375'), (768, 1024, 'tablet-768'), (1280, 800, 'desktop-1280'), (1440, 900, 'wide-1440') ]
BASE = os.environ.get('EACIS_BASE','http://127.0.0.1:5000')
OUT = os.path.join(os.path.dirname(__file__), 'visual-screens')
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    for w,h,name in VIEWPORTS:
        context = browser.new_context(viewport={ 'width': w, 'height': h })
        page = context.new_page()
        for path,label in PAGES:
            url = BASE.rstrip('/') + path
            print(f'Capturing {url} at {w}x{h}')
            page.goto(url, wait_until='networkidle')
            # small delay for animations
            page.wait_for_timeout(500)
            fname = f"{label}--{name}.png"
            page.screenshot(path=os.path.join(OUT,fname), full_page=True)
        context.close()
    browser.close()
print('Screenshots saved to', OUT)
