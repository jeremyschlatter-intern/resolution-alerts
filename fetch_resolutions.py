"""Core logic for identifying resolutions that passed on a given date."""

import re
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field

from congress_api import CongressAPI
from config import (
    RESOLUTION_TYPES,
    PASSAGE_ACTION_CODES,
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

                passage_action = None
                for action in actions:
                    code = action.get("actionCode", "")
                    action_dt = action.get("actionDate", "")
                    action_text = action.get("text", "")

                    # Check if this is a passage action on our target date
                    if action_dt == target_str:
                        if code in PASSAGE_ACTION_CODES:
                            # Prefer Library of Congress codes (17000, 8000) over
                            # chamber-specific codes to avoid double-counting
                            if code in ("17000", "8000"):
                                passage_action = action
                                break
                            elif passage_action is None:
                                passage_action = action
                                # Don't break — keep looking for a LoC code
                        # Also check text patterns for codes we might have missed
                        elif passage_action is None:
                            text_lower = action_text.lower()
                            if any(kw in text_lower for kw in [
                                "passed/agreed to",
                                "agreed to in senate",
                                "agreed to in house",
                                "considered, and agreed to",
                            ]):
                                passage_action = action

                if passage_action is None:
                    continue

                # Found a passed resolution! Get more details.
                passage_text = passage_action.get("text", "")
                passage_method = _detect_passage_method(passage_text)

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

                congress_url = f"https://www.congress.gov/bill/119th-congress/{_type_to_url_segment(res_code)}/{number}"

                results.append(PassedResolution(
                    res_type=res_code,
                    type_label=type_label,
                    type_description=type_desc,
                    number=number,
                    title=bill.get("title", ""),
                    passage_date=target_str,
                    passage_text=passage_text,
                    passage_method=passage_method,
                    sponsor=sponsor,
                    congress_url=congress_url,
                    text_url=text_url,
                    chamber=chamber,
                    vote_result=vote_result,
                ))

                print(f"    Found: {res_code.upper()} {number} - {bill.get('title', '')[:60]}...")

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
