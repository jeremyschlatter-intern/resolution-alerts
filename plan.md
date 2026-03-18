# Resolution Alert System - Implementation Plan

## Problem
The Senate and House pass resolutions that often fly under the radar. The text appears in the Congressional Record but may not appear on congress.gov for some time. DC staffers and policy watchers need timely alerts about these resolutions.

## Solution
A Python-based system that:
1. Queries the Congress.gov API daily for all resolution types (SRES, HRES, SJRES, HJRES, SCONRES, HCONRES)
2. Identifies resolutions that passed/were agreed to on the prior day
3. Fetches the full text and details of each resolution
4. Generates a polished HTML email digest
5. Can be run as a daily cron job or GitHub Actions workflow

## Architecture

### Core Components
- `fetch_resolutions.py` - Main script that queries APIs and identifies passed resolutions
- `email_template.html` - Jinja2 template for the email digest
- `config.py` - Configuration (API keys, email settings, etc.)
- `send_alert.py` - Email sending logic
- `main.py` - Entry point that orchestrates everything

### Data Sources
- **Congress.gov API** (`/v3/bill/{congress}/{type}`) - Lists resolutions with latest actions
- **Congress.gov Actions endpoint** - Confirms passage with action codes 17000 (Senate) and 8000 (House)
- **Congress.gov Text endpoint** - Gets full text of resolutions when available
- **Congressional Record links** - Deep links into the Congressional Record for the day

### Resolution Types Tracked
| Type | Code | Description |
|------|------|-------------|
| Simple Senate | SRES | Senate-only matters (appointments, rules, commemorations) |
| Simple House | HRES | House-only matters |
| Joint Senate | SJRES | Force of law if both chambers pass + president signs |
| Joint House | HJRES | Force of law |
| Concurrent Senate | SCONRES | Both chambers, no force of law |
| Concurrent House | HCONRES | Both chambers, no force of law |

### Email Format
- Date and summary count at top
- Resolutions grouped by type (Joint > Concurrent > Simple)
- Each resolution shows: number, title, sponsor, how it passed (UC/roll call), and link to full text
- Congressional Record reference when available
- Clean, professional HTML that works in all email clients

## Implementation Steps
1. Set up project structure with requirements
2. Build the Congress.gov API client
3. Build resolution passage detection logic
4. Build email template
5. Build email sending capability
6. Create a sample/demo output
7. Add GitHub Actions workflow for daily automation
8. Polish and iterate with DC agent feedback
