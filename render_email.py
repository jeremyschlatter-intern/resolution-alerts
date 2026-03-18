"""Render the email digest from fetched resolution data."""

import os
from datetime import date
from jinja2 import Environment, FileSystemLoader

from fetch_resolutions import PassedResolution


def _group_resolutions(resolutions: list[PassedResolution]) -> list[dict]:
    """Group resolutions by type category for display."""
    categories = [
        {
            "key": "joint",
            "label": "Joint Resolutions",
            "description": "Joint resolutions have the force of law when passed by both chambers and signed by the President.",
            "types": {"sjres", "hjres"},
        },
        {
            "key": "concurrent",
            "label": "Concurrent Resolutions",
            "description": "Concurrent resolutions express the will of both chambers but do not have the force of law.",
            "types": {"sconres", "hconres"},
        },
        {
            "key": "simple_senate",
            "label": "Senate Simple Resolutions",
            "description": "Senate resolutions address internal Senate matters — rules, procedures, appointments, and commemorations.",
            "types": {"sres"},
        },
        {
            "key": "simple_house",
            "label": "House Simple Resolutions",
            "description": "House resolutions address internal House matters — rules, procedures, and commemorations.",
            "types": {"hres"},
        },
    ]

    groups = []
    for cat in categories:
        group_res = [r for r in resolutions if r.res_type in cat["types"]]
        if group_res:
            groups.append({
                "key": cat["key"],
                "label": cat["label"],
                "description": cat["description"],
                "resolutions": group_res,
            })
    return groups


def render_email(resolutions: list[PassedResolution], target_date: date) -> str:
    """Render the HTML email from resolution data."""
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template("email_template.html")

    senate_count = sum(1 for r in resolutions if r.chamber == "Senate")
    house_count = sum(1 for r in resolutions if r.chamber == "House")
    joint_count = sum(1 for r in resolutions if r.res_type in ("sjres", "hjres"))
    grouped = _group_resolutions(resolutions)

    return template.render(
        resolutions=resolutions,
        grouped_resolutions=grouped,
        date_formatted=target_date.strftime("%A, %B %-d, %Y"),
        senate_count=senate_count,
        house_count=house_count,
        joint_count=joint_count,
    )


def render_plaintext(resolutions: list[PassedResolution], target_date: date) -> str:
    """Render a plain-text version of the email for non-HTML clients."""
    lines = []
    lines.append(f"CONGRESSIONAL RESOLUTION ALERT")
    lines.append(f"Resolutions passed on {target_date.strftime('%A, %B %-d, %Y')}")
    lines.append("=" * 60)
    lines.append("")

    if not resolutions:
        lines.append("No resolutions were passed on this date.")
        lines.append("This could mean Congress was not in session.")
        return "\n".join(lines)

    lines.append(f"{len(resolutions)} resolution(s) passed")
    lines.append("")

    grouped = _group_resolutions(resolutions)
    for group in grouped:
        lines.append(f"--- {group['label']} ({len(group['resolutions'])}) ---")
        lines.append(f"    {group['description']}")
        lines.append("")

        for res in group["resolutions"]:
            lines.append(f"  {res.res_type.upper()} {res.number}")
            lines.append(f"  {res.title}")
            if res.sponsor:
                lines.append(f"  Sponsor: {res.sponsor}")
            lines.append(f"  Passed: {res.passage_method}")
            lines.append(f"  Link: {res.congress_url}")
            if res.text_url:
                lines.append(f"  Full Text: {res.text_url}")
            lines.append("")

    lines.append("=" * 60)
    lines.append("Data sourced from the Congress.gov API")
    lines.append("Resolution text may appear in the Congressional Record")
    lines.append("before it appears on individual congress.gov bill pages.")

    return "\n".join(lines)
