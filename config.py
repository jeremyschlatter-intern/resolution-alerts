"""Configuration for the Resolution Alert System."""

import os

# Congress.gov API
CONGRESS_API_KEY = os.environ.get("CONGRESS_API_KEY", "CONGRESS_API_KEY")
CONGRESS_API_BASE = "https://api.congress.gov/v3"
CURRENT_CONGRESS = 119

# Resolution types to track, ordered by significance
RESOLUTION_TYPES = [
    ("sjres", "Senate Joint Resolution", "Joint resolutions have the force of law"),
    ("hjres", "House Joint Resolution", "Joint resolutions have the force of law"),
    ("sconres", "Senate Concurrent Resolution", "Concurrent resolutions express the will of both chambers"),
    ("hconres", "House Concurrent Resolution", "Concurrent resolutions express the will of both chambers"),
    ("sres", "Senate Simple Resolution", "Simple resolutions address matters of one chamber"),
    ("hres", "House Simple Resolution", "Simple resolutions address matters of one chamber"),
]

# Action codes that indicate passage
PASSAGE_ACTION_CODES = {
    "17000",  # Passed/agreed to in Senate (Library of Congress)
    "8000",   # Passed/agreed to in House (Library of Congress)
    "H37100", # On agreeing to the resolution (House floor)
    "H37300", # On motion to suspend the rules and agree (House floor)
}

# Text patterns in latestAction that suggest passage (for quick filtering)
PASSAGE_KEYWORDS = [
    "agreed to",
    "passed senate",
    "passed house",
    "on passage passed",
    "resolution agreed to",
    "on agreeing to the resolution",
    "considered, and agreed to",
]

# Email configuration
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "resolution-alerts@example.com")
EMAIL_TO = os.environ.get("EMAIL_TO", "").split(",") if os.environ.get("EMAIL_TO") else []

# Output
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
