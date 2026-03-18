"""Core logic for identifying resolutions that passed on a given date."""

import re
import html as html_module
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field

from congress_api import CongressAPI
from config import (
    RESOLUTION_TYPES,
    PASSAGE_ACTION_CODES,
    VOTE_ACTION_CODES,
    FAILURE_ACTION_CODES,
    PASSAGE_KEYWORDS,
)


@dataclass
class PassedResolution:
    """A resolution that was passed/agreed to."""
    res_type: str           # e.g. "sres"
    type_label: str         # e.g. "Senate Simple Resolution"
    type_description: str   # e.g. "Simple resolutions address matters of one chamber"
    number: int
    title: str
    passage_date: str       # YYYY-MM-DD
    passage_text: str       # Description of the passage action
    passage_method: str     # "Unanimous Consent", "Roll Call Vote", etc.
    sponsor: str = ""
    congress_url: str = ""
    text_url: str = ""
    text_content: str = ""
    vote_result: str = ""
    chamber: str = ""
    category: str = ""      # "commemorative", "procedural", "substantive"
    cosponsor_count: int = 0
    cr_reference: str = ""  # Congressional Record page reference (e.g., "CR S1051")
    cr_html_url: str = ""   # Direct URL to Congressional Record HTML article
    cr_excerpt: str = ""    # Brief excerpt from Congressional Record text
    passage_time: str = ""  # Time of passage if available (e.g., "16:30")


# Patterns that identify commemorative resolutions
# These are "sense of" resolutions that don't have operative legal effect.
_COMMEMORATIVE_PATTERNS = [
    r"designating .* as ",
    r"recognizing the (importance|contributions|role|anniversary|birthday)",
    r"recognizing .* (day|week|month|year|anniversary)",
    r"recognizing .* on (its|his|her|their)",
    r"celebrating the",
    r"honoring the (life|memory|legacy|service|extraordinary)",
    r"expressing support for the designation",
    r"supporting the goals and ideals of",
    r"commemorat",
    r"expressing the sense of the (senate|house) (that|regarding|relating)",
    r"congratulat",
    r"acknowledging the",
    r"paying tribute",
    r"expressing condolences",
    r"expressing gratitude",
]

# Patterns that identify House Rules Committee procedural resolutions
_PROCEDURAL_PATTERNS = [
    r"providing for consideration of",
    r"waiving a requirement of clause",
    r"relating to consideration of",
]


def _classify_resolution(title: str, res_type: str) -> str:
    """Classify a resolution as commemorative, procedural, or substantive."""
    title_lower = title.lower()

    # Check procedural patterns (House rules)
    for pattern in _PROCEDURAL_PATTERNS:
        if re.search(pattern, title_lower):
            return "procedural"

    # Check commemorative patterns
    for pattern in _COMMEMORATIVE_PATTERNS:
        if re.search(pattern, title_lower):
            return "commemorative"

    return "substantive"


def _extract_cr_reference(action_text: str) -> str:
    """Extract Congressional Record page reference from action text."""
    # Patterns like "(consideration: CR S1051; text: CR S1051)" or "(text: CR S712)"
    match = re.search(r'\((?:consideration: )?(CR [SH]\d+)', action_text)
    if match:
        return match.group(1)
    return ""


def _detect_passage_method(action_text: str) -> str:
    """Extract how the resolution was passed from the action text."""
    text_lower = action_text.lower()
    if "unanimous consent" in text_lower:
        return "Unanimous Consent"
    if "yeas and nays" in text_lower or "yea-nay" in text_lower:
        # Try to extract the vote count
        match = re.search(r'(\d+)\s*-\s*(\d+)', action_text)
        if match:
            return f"Roll Call Vote ({match.group(1)}-{match.group(2)})"
        return "Roll Call Vote"
    if "voice vote" in text_lower:
        return "Voice Vote"
    if "without objection" in text_lower:
        return "Without Objection"
    return "Agreed To"


def _strip_html_tags(html_text: str) -> str:
    """Strip HTML tags and decode entities for plain-text excerpt."""
    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _extract_cr_excerpt(html_text: str, max_length: int = 500) -> str:
    """Extract a readable excerpt from Congressional Record HTML.

    Focuses on the resolution text (whereas clauses and resolved clauses).
    """
    # Try to find the resolution text section
    # Look for "Whereas" or "Resolved" sections
    text = _strip_html_tags(html_text)

    # Find the start of the resolution text
    for marker in ["Whereas", "Resolved,"]:
        idx = text.find(marker)
        if idx >= 0:
            excerpt = text[idx:]
            if len(excerpt) > max_length:
                # Cut at a sentence boundary
                cut_point = excerpt.rfind('. ', 0, max_length)
                if cut_point > 0:
                    excerpt = excerpt[:cut_point + 1]
                else:
                    excerpt = excerpt[:max_length] + "..."
            return excerpt

    # Fallback: return a portion of the text
    if len(text) > max_length:
        cut_point = text.rfind('. ', 0, max_length)
        if cut_point > 0:
            text = text[:cut_point + 1]
        else:
            text = text[:max_length] + "..."
    return text


def lookup_cr_text(api, target_date: date, cr_page_ref: str, res_type: str, number: int, bill_title: str = "") -> tuple[str, str]:
    """
    Look up the Congressional Record text for a resolution.

    Args:
        api: CongressAPI instance
        target_date: The date the resolution was discussed
        cr_page_ref: Page reference like "S1051" extracted from action text
        res_type: Resolution type code (e.g., "sres")
        number: Resolution number
        bill_title: The resolution's title (for fuzzy matching)

    Returns:
        Tuple of (html_url, excerpt) or ("", "") if not found.
    """
    try:
        # Get recent CR issues and find the one matching our date
        issues = api.get_daily_cr_issues(limit=30)
        target_str = target_date.strftime("%Y-%m-%d")

        matching_issue = None
        for issue in issues:
            issue_date = issue.get("issueDate", "")
            # issueDate can be a timestamp like "2026-03-16T04:00:00Z"
            if issue_date.startswith(target_str):
                matching_issue = issue
                break

        if not matching_issue:
            return "", ""

        vol = matching_issue.get("volumeNumber")
        iss = matching_issue.get("issueNumber")
        if not vol or not iss:
            return "", ""

        # Get articles for this issue, filtering to relevant chamber section
        section_filter = "Senate" if res_type.startswith("s") else "House"
        articles = api.get_cr_articles(vol, iss, section=section_filter)

        # Try to match by page reference or by resolution number in title
        res_label = f"{res_type.upper()} {number}"  # e.g., "SRES 629"
        # Also try formats like "SENATE RESOLUTION 629" or "S. RES. 629"
        alt_labels = []
        if res_type == "sres":
            alt_labels = [f"SENATE RESOLUTION {number}", f"S. RES. {number}", f"S.RES. {number}"]
        elif res_type == "hres":
            alt_labels = [f"HOUSE RESOLUTION {number}", f"H. RES. {number}", f"H.RES. {number}"]
        elif res_type == "sjres":
            alt_labels = [f"SENATE JOINT RESOLUTION {number}", f"S.J. RES. {number}"]
        elif res_type == "hjres":
            alt_labels = [f"HOUSE JOINT RESOLUTION {number}", f"H.J. RES. {number}"]
        elif res_type == "sconres":
            alt_labels = [f"SENATE CONCURRENT RESOLUTION {number}", f"S. CON. RES. {number}"]
        elif res_type == "hconres":
            alt_labels = [f"HOUSE CONCURRENT RESOLUTION {number}", f"H. CON. RES. {number}"]

        best_article = None
        page_matches = []  # All page-matching articles

        for article in articles:
            article_title = article.get("title", "").upper()
            start_page = article.get("startPage", "")

            # Prefer exact resolution number match in title
            for label in [res_label] + alt_labels:
                if label.upper() in article_title:
                    best_article = article
                    break
            if best_article:
                break

            # Track page matches for fallback
            if cr_page_ref and start_page == cr_page_ref:
                if not any(w in article_title for w in ["ADJOURNMENT", "ORDERS FOR", "EXECUTIVE SESSION"]):
                    page_matches.append(article)

        if not best_article and page_matches:
            if len(page_matches) == 1:
                best_article = page_matches[0]
            else:
                # Try matching by resolution number in article title
                str_number = str(number)
                for pm in page_matches:
                    if str_number in pm.get("title", ""):
                        best_article = pm
                        break

                # Try matching by keywords from the bill title
                if not best_article and bill_title:
                    # Extract significant words (>4 chars, not common words)
                    skip = {"resolution", "senate", "house", "congress", "united", "states", "america"}
                    keywords = [w.upper() for w in re.findall(r'\b\w{5,}\b', bill_title) if w.lower() not in skip]
                    best_score = 0
                    for pm in page_matches:
                        at = pm.get("title", "").upper()
                        score = sum(1 for kw in keywords if kw in at)
                        if score > best_score:
                            best_score = score
                            best_article = pm

                if not best_article:
                    best_article = page_matches[0]

        if not best_article:
            return "", ""

        # Get the HTML URL
        html_url = ""
        text_formats = best_article.get("text", [])
        for fmt in text_formats:
            fmt_type = fmt.get("type", "").lower()
            fmt_url = fmt.get("url", "")
            if "formatted text" in fmt_type or "html" in fmt_type or ".htm" in fmt_url.lower():
                html_url = fmt_url
                break
        # Fallback to PDF if no HTML
        if not html_url:
            for fmt in text_formats:
                if "pdf" in fmt.get("type", "").lower():
                    html_url = fmt.get("url", "")
                    break

        # Fetch the HTML and extract an excerpt
        excerpt = ""
        if html_url:
            try:
                raw_html = api.fetch_cr_article_html(html_url)
                excerpt = _extract_cr_excerpt(raw_html)
            except Exception:
                pass

        return html_url, excerpt

    except Exception as e:
        print(f"    Note: Could not look up Congressional Record text: {e}")
        return "", ""


def _might_have_passed(bill: dict) -> bool:
    """Quick check based on latestAction text to avoid unnecessary API calls."""
    latest = bill.get("latestAction", {})
    text = latest.get("text", "").lower()
    return any(kw in text for kw in PASSAGE_KEYWORDS)


def _extract_text_url(text_versions: list[dict]) -> str:
    """Find the best text URL (prefer HTML) from text versions."""
    for version in text_versions:
        formats = version.get("formats", [])
        # Prefer HTML
        for fmt in formats:
            if fmt.get("type") == "Formatted Text (HTML)":
                return fmt.get("url", "")
        # Fall back to PDF
        for fmt in formats:
            if fmt.get("type") == "PDF":
                return fmt.get("url", "")
    return ""


def fetch_passed_resolutions(target_date: date, api: CongressAPI = None) -> list[PassedResolution]:
    """
    Fetch all resolutions that passed on the given date.

    Uses a two-pass approach:
    1. List all recently-updated resolutions (quick filter by latestAction text)
    2. For candidates, fetch full actions to confirm passage on the target date
    """
    if api is None:
        api = CongressAPI()

    # The API filters by updateDate, which can lag actionDate by days or weeks.
    # Use a generous window: target_date to min(target_date + 14 days, tomorrow).
    today = date.today()
    window_end = min(target_date + timedelta(days=14), today + timedelta(days=1))
    from_dt = datetime.combine(target_date, datetime.min.time()).strftime("%Y-%m-%dT00:00:00Z")
    to_dt = datetime.combine(window_end, datetime.min.time()).strftime("%Y-%m-%dT00:00:00Z")

    target_str = target_date.strftime("%Y-%m-%d")
    results = []

    for res_code, type_label, type_desc in RESOLUTION_TYPES:
        print(f"  Checking {type_label}s ({res_code})...")

        # Paginate through all updated resolutions
        offset = 0
        while True:
            bills = api.list_resolutions(res_code, from_dt, to_dt, limit=250, offset=offset)
            if not bills:
                break

            for bill in bills:
                # Quick filter: does the latest action look like passage?
                if not _might_have_passed(bill):
                    continue

                # Also check if the latestAction date matches our target
                action_date = bill.get("latestAction", {}).get("actionDate", "")
                if action_date != target_str:
                    # The latestAction might not be the passage action, or the date
                    # might not match. We still need to check the full actions list
                    # if the updateDate is in range.
                    pass

                number = int(bill["number"])

                # Fetch full actions to confirm passage on target date
                try:
                    actions = api.get_bill_actions(res_code, number)
                except Exception as e:
                    print(f"    Warning: could not fetch actions for {res_code.upper()} {number}: {e}")
                    continue

                # First, check if any action explicitly marks this as FAILED
                failed_on_target = False
                passage_action = None

                for action in actions:
                    code = action.get("actionCode", "")
                    action_dt = action.get("actionDate", "")
                    action_text = action.get("text", "")

                    if action_dt != target_str:
                        continue

                    # Explicit failure codes — skip this resolution entirely
                    if code in FAILURE_ACTION_CODES:
                        failed_on_target = True
                        break

                    # Check text for failure language
                    text_lower = action_text.lower()
                    if "failed" in text_lower and ("passage" in text_lower or "agreeing" in text_lower):
                        failed_on_target = True
                        break

                    # Definitive passage codes from Library of Congress
                    if code in PASSAGE_ACTION_CODES:
                        passage_action = action
                        break

                    # Ambiguous vote codes — check text to confirm passage
                    if code in VOTE_ACTION_CODES:
                        if "failed" not in text_lower:
                            passage_action = action
                            # Don't break — keep looking for a definitive LoC code

                    # Text-based detection as fallback
                    if passage_action is None:
                        if any(kw in text_lower for kw in [
                            "passed/agreed to",
                            "agreed to in senate",
                            "agreed to in house",
                            "considered, and agreed to",
                        ]) and "failed" not in text_lower:
                            passage_action = action

                if failed_on_target or passage_action is None:
                    continue

                # Found a passed resolution! Get more details.
                passage_text = passage_action.get("text", "")
                passage_method = _detect_passage_method(passage_text)

                # Look for CR reference across ALL floor actions on target date
                # (the LoC action may omit it, but the chamber floor action has it)
                all_cr_refs = []
                for action in actions:
                    if action.get("actionDate") == target_str:
                        ref = _extract_cr_reference(action.get("text", ""))
                        if ref:
                            all_cr_refs.append(ref)

                # Extract vote result if available
                vote_result = ""
                recorded_votes = passage_action.get("recordedVotes", [])
                if recorded_votes:
                    rv = recorded_votes[0]
                    vote_result = f"Roll no. {rv.get('rollNumber', '?')}"

                # Determine chamber
                if res_code.startswith("s"):
                    chamber = "Senate"
                else:
                    chamber = "House"

                # Get sponsor info
                sponsor = ""
                try:
                    detail = api.get_bill_detail(res_code, number)
                    sponsors = detail.get("sponsors", [])
                    if sponsors:
                        s = sponsors[0]
                        full_name = s.get("fullName", "")
                        # fullName often includes [party-state] already
                        if "[" in full_name:
                            sponsor = full_name
                        else:
                            first = s.get("firstName", "")
                            last = s.get("lastName", "")
                            party = s.get("party", "")
                            state = s.get("state", "")
                            sponsor = f"{first} {last}".strip()
                            if party and state:
                                sponsor += f" [{party}-{state}]"
                except Exception:
                    pass

                # Get text URL
                text_url = ""
                try:
                    text_versions = api.get_bill_text_versions(res_code, number)
                    text_url = _extract_text_url(text_versions)
                except Exception:
                    pass

                # Get cosponsor count
                cosponsor_count = 0
                try:
                    cosponsors_data = api.get_bill_cosponsors(res_code, number)
                    # Count is in the pagination section
                    pagination = cosponsors_data.get("pagination", {})
                    cosponsor_count = pagination.get("count", 0)
                    if not cosponsor_count:
                        # Fallback: count the list directly
                        cosponsor_count = len(cosponsors_data.get("cosponsors", []))
                except Exception:
                    pass

                # Classify the resolution
                title = bill.get("title", "")
                category = _classify_resolution(title, res_code)

                # Extract Congressional Record reference from any floor action
                cr_reference = ""
                if all_cr_refs:
                    cr_reference = all_cr_refs[0]
                if not cr_reference:
                    cr_reference = _extract_cr_reference(passage_text)

                # Extract passage time if available
                passage_time = passage_action.get("actionTime", "")
                if passage_time and passage_time != "00:00:00":
                    # Format as HH:MM
                    try:
                        h, m, s = passage_time.split(":")
                        passage_time = f"{h}:{m}"
                    except ValueError:
                        pass

                # Look up Congressional Record text
                cr_html_url = ""
                cr_excerpt = ""
                if cr_reference:
                    page_ref = cr_reference.replace("CR ", "")  # "S1051"
                    cr_html_url, cr_excerpt = lookup_cr_text(api, target_date, page_ref, res_code, number, title)

                congress_url = f"https://www.congress.gov/bill/119th-congress/{_type_to_url_segment(res_code)}/{number}"

                results.append(PassedResolution(
                    res_type=res_code,
                    type_label=type_label,
                    type_description=type_desc,
                    number=number,
                    title=title,
                    passage_date=target_str,
                    passage_text=passage_text,
                    passage_method=passage_method,
                    sponsor=sponsor,
                    congress_url=congress_url,
                    text_url=text_url,
                    chamber=chamber,
                    vote_result=vote_result,
                    category=category,
                    cosponsor_count=cosponsor_count,
                    cr_reference=cr_reference,
                    cr_html_url=cr_html_url,
                    cr_excerpt=cr_excerpt,
                    passage_time=passage_time,
                ))

                cat_label = f" [{category}]" if category != "substantive" else ""
                print(f"    Found: {res_code.upper()} {number}{cat_label} - {title[:60]}...")

            if len(bills) < 250:
                break
            offset += 250

    # Sort: joint resolutions first, then concurrent, then simple
    type_order = {"sjres": 0, "hjres": 1, "sconres": 2, "hconres": 3, "sres": 4, "hres": 5}
    results.sort(key=lambda r: (type_order.get(r.res_type, 99), r.number))

    return results


def _type_to_url_segment(res_type: str) -> str:
    """Convert resolution type code to congress.gov URL segment."""
    mapping = {
        "sres": "senate-resolution",
        "hres": "house-resolution",
        "sjres": "senate-joint-resolution",
        "hjres": "house-joint-resolution",
        "sconres": "senate-concurrent-resolution",
        "hconres": "house-concurrent-resolution",
    }
    return mapping.get(res_type, res_type)
