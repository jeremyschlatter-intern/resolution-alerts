#!/usr/bin/env python3
"""
Congressional Resolution Alert System

Generates a daily email digest of resolutions that passed in Congress
on the prior legislative day. Tracks all resolution types (simple,
concurrent, and joint) from both chambers.

Usage:
    python main.py                  # Alert for yesterday's resolutions
    python main.py --date 2026-03-14  # Alert for a specific date
    python main.py --days-back 7    # Alert for each of the last 7 days
    python main.py --send           # Send via email (requires SMTP config)
"""

import argparse
import os
import sys
from datetime import date, timedelta

from fetch_resolutions import fetch_passed_resolutions
from render_email import render_email, render_plaintext
from send_email import send_alert_email
from config import OUTPUT_DIR


def run_alert(target_date: date, send: bool = False) -> int:
    """Run the alert for a single date. Returns count of resolutions found."""
    print(f"\nFetching resolutions passed on {target_date.strftime('%A, %B %-d, %Y')}...")

    resolutions = fetch_passed_resolutions(target_date)

    print(f"\n  Found {len(resolutions)} resolution(s) passed on {target_date}")

    # Render email
    html = render_email(resolutions, target_date)
    plaintext = render_plaintext(resolutions, target_date)

    # Save to output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = target_date.strftime("%Y-%m-%d")

    html_path = os.path.join(OUTPUT_DIR, f"alert-{date_str}.html")
    with open(html_path, "w") as f:
        f.write(html)
    print(f"  HTML saved to {html_path}")

    txt_path = os.path.join(OUTPUT_DIR, f"alert-{date_str}.txt")
    with open(txt_path, "w") as f:
        f.write(plaintext)
    print(f"  Text saved to {txt_path}")

    # Send email if requested
    if send:
        send_alert_email(html, plaintext, target_date, resolution_count=len(resolutions))

    return len(resolutions)


def main():
    parser = argparse.ArgumentParser(
        description="Congressional Resolution Alert System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--date", "-d",
        help="Target date (YYYY-MM-DD). Default: yesterday.",
    )
    parser.add_argument(
        "--days-back", "-n",
        type=int,
        help="Generate alerts for each of the last N days.",
    )
    parser.add_argument(
        "--send", "-s",
        action="store_true",
        help="Send the alert via email (requires SMTP configuration).",
    )

    args = parser.parse_args()

    if args.days_back:
        total = 0
        today = date.today()
        for i in range(args.days_back, 0, -1):
            d = today - timedelta(days=i)
            total += run_alert(d, send=args.send)
        print(f"\nTotal: {total} resolution(s) found across {args.days_back} day(s)")
    else:
        if args.date:
            target = date.fromisoformat(args.date)
        else:
            target = date.today() - timedelta(days=1)
        run_alert(target, send=args.send)


if __name__ == "__main__":
    main()
