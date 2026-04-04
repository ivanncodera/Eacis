"""
Run Playwright + axe-core accessibility checks across key pages and save results.
Usage: python tools/playwright_axe_run.py
Requires: playwright installed and the app running at EACIS_BASE (default http://127.0.0.1:5000)
Outputs: tools/axe-results.new.json
"""
from playwright.sync_api import sync_playwright
import os, json

PAGES = [
    ("/", "home"),
    ("/shop", "shop"),
    ("/admin/refunds", "admin-refunds"),
]
BASE = os.environ.get('EACIS_BASE','http://127.0.0.1:5000')
OUT = os.path.join(os.path.dirname(__file__), 'axe-results.new.json')

results = {
    'tool': 'axe-playwright-run',
    'base': BASE,
    'pages': []
}

AXE_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.6.3/axe.min.js'

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context()
    page = context.new_page()
    # inject axe
    page.goto('about:blank')
    page.add_script_tag(url=AXE_CDN)

    for path,label in PAGES:
        url = BASE.rstrip('/') + path
        print('Auditing', url)
        try:
            page.goto(url, wait_until='networkidle')
            # ensure axe is available on page
            page.add_script_tag(url=AXE_CDN)
            page.wait_for_timeout(500)
            res = page.evaluate("async () => { return await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2aa'] } }); }")
            results['pages'].append({
                'path': path,
                'label': label,
                'url': url,
                'result': res
            })
        except Exception as e:
            print('Error auditing', url, e)
            results['pages'].append({ 'path': path, 'label': label, 'url': url, 'error': str(e) })

    context.close()
    browser.close()

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print('Wrote axe results to', OUT)
