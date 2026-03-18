# After Action Report: Congressional Resolution Alert System

## Project Summary

I built a system that generates daily email alerts for Congressional resolutions that passed the prior day. The system queries the Congress.gov API for all six resolution types (Senate/House simple, concurrent, and joint), classifies them by significance, fetches the actual text from the Congressional Record, and delivers a polished HTML digest.

The project addresses a real problem in DC: resolutions frequently pass with little notice — especially in the Senate via unanimous consent — and their text appears in the Congressional Record before it shows up on congress.gov bill pages. This system closes that gap.

## What It Does

- Detects resolutions passed on any given date across both chambers
- Classifies each as **substantive**, **procedural** (House Rules), or **commemorative**
- Shows the passage method (unanimous consent, roll call with tally, voice vote)
- Displays sponsor and cosponsor count
- Links directly to the Congressional Record HTML article for each resolution
- Includes an excerpt of the resolution text from the Congressional Record (whereas clauses, resolved clauses)
- Generates Outlook-compatible HTML email and plaintext versions
- Includes a GitHub Actions workflow for daily automated runs

## Process and Obstacles

### 1. Understanding the API Landscape

**Challenge:** The Congress.gov API has multiple endpoints with different behaviors, and the documentation doesn't always make the relationships clear.

**What I did:** Systematically queried each relevant endpoint to understand the data model. I discovered that:
- The `/bill` endpoint's `type` query parameter is ignored on the generic path; you must use the congress-specific path (`/bill/119/sres`)
- The `fromDateTime`/`toDateTime` parameters filter on `updateDate`, not `actionDate`
- The Library of Congress wraps chamber actions with its own codes (17000 for Senate passage, 8000 for House)

### 2. The updateDate Lag Bug

**Challenge:** Initially, the system only searched a 2-day window around the target date. But the Congress.gov API filters by `updateDate`, which can lag the actual `actionDate` by days or even weeks. SRES 642 passed on March 12 but its `updateDate` was March 18 — completely outside my initial search window.

**Impact:** The system was silently missing resolutions.

**Fix:** Widened the search window to 14 days (or to today, whichever is sooner). For daily production use, this window is naturally tight. The actual passage date verification happens at the action level, so false positives aren't possible.

### 3. The False Positive on Failed Votes

**Challenge:** House action code `H37100` ("On agreeing to the resolution") fires for both successful and failed votes. My initial implementation included this as a passage code, which caused HCONRES 38 — the War Powers Resolution regarding Iran, which *failed* 212-219 — to appear as "passed."

**How I found it:** The DC feedback agent flagged the 212-219 vote count as suspicious. I verified by querying the actions endpoint and discovered the Library of Congress uses code `9000` for failure vs. `8000` for success.

**Fix:** Removed ambiguous House floor codes from the definitive passage list. Now only Library of Congress codes (17000, 8000) are treated as definitive. For fallback text matching, the system explicitly checks for the word "failed" in the action text. A separate `FAILURE_ACTION_CODES` set (`9000`, `10000`) catches explicit failure markers.

### 4. Congressional Record Integration

**Challenge:** This was the core value proposition — getting the actual CR text that may not yet be on congress.gov. The Congressional Record API has a nested response structure (sections containing articles) that wasn't immediately apparent.

**What I did:**
- Discovered the `/v3/daily-congressional-record/{volume}/{issue}/articles` endpoint returns sections, not flat articles
- Built a three-tier matching strategy: exact resolution number in article title, fuzzy keyword matching from the bill title, and page reference fallback
- Had to fix a date comparison bug (`issueDate` is a timestamp like "2026-03-16T04:00:00Z", not a bare date)
- Also discovered that the Library of Congress passage action sometimes omits the CR page reference that the Senate/House floor action includes — fixed by scanning all actions on the target date

**Result:** The system now pulls in actual CR article HTML with direct links and text excerpts showing the Whereas/Resolved clauses.

### 5. Resolution Classification

**Challenge:** The project description emphasizes "sneaky resolutions" — the substantive ones that pass without notice alongside commemoratives. Mixing them together defeats the purpose.

**What I did:** Built a regex-based classifier with three categories:
- **Substantive**: Resolutions that make policy statements, authorize actions, or have operational significance
- **Procedural**: House Rules Committee resolutions ("Providing for consideration of...")
- **Commemorative**: Designations, recognitions, celebrations, memorials

**Iteration:** The initial patterns were too narrow — "celebrating Black History Month" and "supporting the US Olympic Team" slipped through as substantive. Refined through multiple rounds of testing against real data, adding patterns for "celebrating", "supporting the...teams/olympic", "recognizing...game", etc.

### 6. CR Reference Extraction

**Challenge:** The Congressional Record page reference (e.g., "CR S1058") is embedded in parenthetical text at the end of action descriptions, and the Library of Congress version of the action sometimes omits it while the Senate floor version includes it.

**Fix:** Instead of only checking the passage action text, the system now scans all actions on the target date for CR references.

## Agent Team

I used three types of agent teammates:

- **API Researcher**: Systematically explored the Congress.gov API endpoints, discovering the correct path structures, query parameters, and response formats. Made 47 API calls to map the data model.

- **DC Agent (Daniel Schuman)**: Provided three rounds of feedback from the perspective of the project originator. Key contributions:
  - Identified the false positive on failed votes (critical bug)
  - Pushed for the commemorative/substantive classification
  - Flagged the missing Congressional Record integration as the core value proposition
  - Caught classification errors ("CTE educators" resolution misclassified)
  - Recommended Outlook-compatible HTML, cosponsor counts, vote tallies

- **CR Researcher**: Investigated the Congressional Record API structure, discovered the nested sections/articles format, and identified the correct URL patterns for direct article links.

## Technical Architecture

```
main.py                  # CLI entry point (--date, --days-back, --send)
congress_api.py          # API client with rate limiting
fetch_resolutions.py     # Detection, classification, CR lookup
render_email.py          # HTML and plaintext rendering
send_email.py            # SMTP email delivery
email_template.html      # Jinja2 HTML template (Outlook-compatible)
config.py                # Configuration and constants
generate_index.py        # Archive index page generator
shell.nix                # Reproducible Python environment
.github/workflows/       # Daily automation via GitHub Actions
```

## Files Delivered

- Working Python application that generates daily resolution alerts
- 30+ days of sample output (HTML and plaintext) in the `output/` directory
- GitHub Actions workflow for daily automated runs
- Browsable archive index page
- This report

## What a Production Deployment Would Need

1. **Email service**: Hook up SMTP (SendGrid, Amazon SES, etc.) via the environment variables already defined
2. **Hosting**: Deploy on any server with Python 3.12+ and cron, or use GitHub Actions (workflow included)
3. **Congress number**: Update `CURRENT_CONGRESS` in config.py when the 120th Congress convenes
4. **Subscriber management**: Currently delivers to a static email list; a production version would want a subscription mechanism
