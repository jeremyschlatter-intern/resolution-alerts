#!/usr/bin/env python3
"""Generate an index.html page listing all alert files in the output directory."""

import os
import re
from datetime import datetime
from config import OUTPUT_DIR

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Congressional Resolution Alerts — Archive</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif;
    color: #1a1a2e;
    background: #f0f0f5;
    line-height: 1.6;
  }
  .container {
    max-width: 720px;
    margin: 0 auto;
    padding: 40px 20px;
  }
  header {
    background: #1a1a2e;
    color: #fff;
    padding: 36px 0;
    text-align: center;
  }
  header h1 {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.3px;
  }
  header p {
    color: #a0a0b8;
    font-size: 15px;
    margin-top: 6px;
  }
  .info-box {
    background: #fff;
    border: 1px solid #e8e8f0;
    border-radius: 8px;
    padding: 20px 24px;
    margin: 24px auto;
    max-width: 720px;
    font-size: 14px;
    color: #4a4a6a;
  }
  .info-box strong { color: #1a1a2e; }
  .alerts-list {
    list-style: none;
    margin: 24px auto;
    max-width: 720px;
  }
  .alerts-list li {
    background: #fff;
    border: 1px solid #e8e8f0;
    border-radius: 6px;
    margin-bottom: 8px;
    transition: border-color 0.15s;
  }
  .alerts-list li:hover {
    border-color: #2c3e8c;
  }
  .alerts-list a {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    text-decoration: none;
    color: #1a1a2e;
  }
  .alert-date {
    font-weight: 600;
    font-size: 15px;
  }
  .alert-meta {
    font-size: 13px;
    color: #7a7a9a;
  }
  .empty {
    text-align: center;
    padding: 48px 20px;
    color: #7a7a9a;
  }
  footer {
    text-align: center;
    padding: 32px 20px;
    font-size: 12px;
    color: #8a8aa8;
  }
  footer a { color: #2c3e8c; text-decoration: none; }
</style>
</head>
<body>
<header>
  <h1>Congressional Resolution Alerts</h1>
  <p>Daily digest of resolutions passed by Congress</p>
</header>

<div class="info-box">
  <strong>About this archive:</strong> Each day, this system checks for resolutions
  (simple, concurrent, and joint) that were passed or agreed to in the Senate and House.
  Resolutions often pass with little notice — many are agreed to by unanimous consent and
  may appear in the Congressional Record before they appear on congress.gov.
</div>

<ul class="alerts-list">
__ENTRIES__
</ul>

<footer>
  <p>Data sourced from the <a href="https://api.congress.gov/">Congress.gov API</a></p>
  <p>Congressional Resolution Alert System</p>
</footer>
</body>
</html>"""


def generate_index():
    """Scan the output directory and generate an index.html."""
    if not os.path.exists(OUTPUT_DIR):
        print("No output directory found.")
        return

    # Find all HTML alert files
    html_files = sorted(
        [f for f in os.listdir(OUTPUT_DIR) if f.startswith("alert-") and f.endswith(".html")],
        reverse=True,
    )

    if not html_files:
        entries_html = '<li class="empty">No alerts generated yet. Run main.py to generate your first alert.</li>'
    else:
        entries = []
        for fname in html_files:
            match = re.match(r"alert-(\d{4}-\d{2}-\d{2})\.html", fname)
            if not match:
                continue
            date_str = match.group(1)
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                display_date = dt.strftime("%A, %B %-d, %Y")
            except ValueError:
                display_date = date_str

            # Read the file to count resolutions (look for res-card divs)
            filepath = os.path.join(OUTPUT_DIR, fname)
            with open(filepath) as f:
                content = f.read()
            count = content.count('class="res-card"')
            meta = f"{count} resolution{'s' if count != 1 else ''}" if count > 0 else "No resolutions"

            entries.append(
                f'  <li><a href="{fname}">'
                f'<span class="alert-date">{display_date}</span>'
                f'<span class="alert-meta">{meta}</span>'
                f'</a></li>'
            )
        entries_html = "\n".join(entries)

    html = INDEX_TEMPLATE.replace("__ENTRIES__", entries_html)
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w") as f:
        f.write(html)
    print(f"Index written to {index_path}")


if __name__ == "__main__":
    generate_index()
