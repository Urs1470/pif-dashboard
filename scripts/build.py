#!/usr/bin/env python3
"""Minify JS and CSS files for production.

Usage:  python scripts/build.py
Requires: pip install rjsmin rcssmin

Reads static/*.js and static/*.css, writes minified versions to
static/dist/. Templates reference dist/ versions via a build flag.
"""
import os
import sys
import hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, 'static')
DIST = os.path.join(STATIC, 'dist')

JS_FILES = ['core.js', 'app.js', 'mobile.js', 'pv-modal.js']
CSS_FILES = ['style.css', 'login.css', 'mobile-app.css']
BUDGET_JS = ['budget/budget-tracker.js']
BUDGET_CSS = ['budget/budget.css']


def ensure_deps():
    try:
        import rjsmin
        import rcssmin
        return rjsmin, rcssmin
    except ImportError:
        print("Installing rjsmin and rcssmin...")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'rjsmin', 'rcssmin', '-q'])
        import rjsmin
        import rcssmin
        return rjsmin, rcssmin


def minify_file(src_path, dest_path, minifier):
    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()
    minified = minifier(content)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(minified)
    orig = len(content.encode('utf-8'))
    mini = len(minified.encode('utf-8'))
    pct = (1 - mini / orig) * 100 if orig else 0
    print(f"  {os.path.relpath(src_path, STATIC):30s} {orig:>8,} -> {mini:>8,}  ({pct:.0f}% smaller)")


def file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]


def main():
    rjsmin_mod, rcssmin_mod = ensure_deps()

    print("Minifying JS...")
    for name in JS_FILES + BUDGET_JS:
        src = os.path.join(STATIC, name)
        if not os.path.exists(src):
            print(f"  SKIP {name} (not found)")
            continue
        dest = os.path.join(DIST, name)
        minify_file(src, dest, rjsmin_mod.jsmin)

    print("\nMinifying CSS...")
    for name in CSS_FILES + BUDGET_CSS:
        src = os.path.join(STATIC, name)
        if not os.path.exists(src):
            print(f"  SKIP {name} (not found)")
            continue
        dest = os.path.join(DIST, name)
        minify_file(src, dest, rcssmin_mod.cssmin)

    print("\nDone. Minified files in static/dist/")
    print("To use: set FLASK_ENV=production or PIF_USE_DIST=1")


if __name__ == '__main__':
    main()
