"""Render the email digest from fetched resolution data."""

import os
from datetime import date
from jinja2 import Environment, FileSystemLoader

from fetch_resolutions import PassedResolution


def render_email(resolutions: list[PassedResolution], target_date: date) -> str:
    """Render the HTML email from resolution data."""
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template("email_template.html")

    senate_count = sum(1 for r in resolutions if r.chamber == "Senate")
    house_count = sum(1 for r in resolutions if r.chamber == "House")
    joint_count = sum(1 for r in resolutions if r.res_type in ("sjres", "hjres"))

    # Categorize resolutions
    substantive = [r for r in resolutions if r.category == "substantive"]
    procedural = [r for r in resolutions if r.category == "procedural"]
    commemorative = [r for r in resolutions if r.category == "commemorative"]

    return template.render(
        resolutions=resolutions,
        substantive_resolutions=substantive,
        procedural_resolutions=procedural,
        commemorative_resolutions=commemorative,
        substantive_count=len(substantive),
        date_formatted=target_date.strftime("%A, %B %-d, %Y"),
        senate_count=senate_count,
        house_count=house_count,
        joint_count=joint_count,
    )


def render_plaintext(resolutions: list[PassedResolution], target_date: date) -> str:
    """Render a plain-text version of the email for non-HTML clients."""
    lines = []
    lines.append("CONGRESSIONAL RESOLUTION ALERT")
    lines.append(f"Resolutions passed on {target_date.strftime('%A, %B %-d, %Y')}")
    lines.append("=" * 60)
    lines.append("")

    if not resolutions:
        lines.append("No resolutions were agreed to on this date.")
        return "\n".join(lines)

    lines.append(f"{len(resolutions)} resolution(s) passed")
    lines.append("")

    # Group by category for display
    categories = [
        ("SUBSTANTIVE", [r for r in resolutions if r.category == "substantive"]),
        ("PROCEDURAL", [r for r in resolutions if r.category == "procedural"]),
        ("COMMEMORATIVE", [r for r in resolutions if r.category == "commemorative"]),
    ]

    for cat_name, cat_resolutions in categories:
        if not cat_resolutions:
            continue

        lines.append(f"--- {cat_name} ({len(cat_resolutions)}) ---")
        lines.append("")

        for res in cat_resolutions:
            lines.append(f"  {res.res_type.upper()} {res.number} [{res.chamber}]")
            lines.append(f"  {res.title}")
            if res.sponsor:
                sponsor_line = f"  Sponsor: {res.sponsor}"
                if res.cosponsor_count:
                    sponsor_line += f" + {res.cosponsor_count} cosponsor(s)"
                lines.append(sponsor_line)
            lines.append(f"  Passed: {res.passage_method}")
            if res.vote_result:
                lines.append(f"  Vote: {res.vote_result}")
            lines.append(f"  Link: {res.congress_url}")
            if res.text_url:
                lines.append(f"  Full Text: {res.text_url}")
            if res.cr_reference:
                lines.append(f"  Congressional Record: {res.cr_reference}")
            lines.append("")

    lines.append("=" * 60)
    lines.append("Data sourced from the Congress.gov API")
    lines.append("Resolution text may appear in the Congressional Record")
    lines.append("before it appears on individual congress.gov bill pages.")

    return "\n".join(lines)
