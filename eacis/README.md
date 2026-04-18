# E-ACIS (Frontend + Flask scaffold)

This folder contains the initial scaffold for the E-ACIS project.

Structure created:
- `eacis/app.py` — minimal Flask app factory
- `eacis/config.py` — loads .env values
- `eacis/templates/base.html` — base Jinja2 template
- `eacis/static/css/tokens.css` — design tokens
- `eacis/static/css/base.css` — base styles
- `eacis/static/js/main.js` — minimal JS setup
- `eacis/static/assets/placeholder-manifest.json` — product image manifest (starter)

Next recommended steps:
1. Copy product images into `eacis/static/assets/products/` (I can do this and normalize filenames for you).
2. Implement models and blueprints under `eacis/` (I can scaffold those next).
3. Install requirements:

```bash
python -m pip install -r eacis/requirements.txt
```

To run the minimal app (dev):

```bash
python eacis/app.py
```

If you want me to continue, tell me which tasks to run next (copy images, scaffold models, seed DB, or implement UI improvements).