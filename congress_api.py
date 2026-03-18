"""Client for the Congress.gov API to fetch resolution data."""

import time
import requests
from typing import Optional
from config import CONGRESS_API_KEY, CONGRESS_API_BASE, CURRENT_CONGRESS


class CongressAPI:
    """Thin wrapper around the Congress.gov API with rate limiting."""

    def __init__(self, api_key: str = CONGRESS_API_KEY):
        self.api_key = api_key
        self.base_url = CONGRESS_API_BASE
        self.session = requests.Session()
        self._last_request_time = 0
        self._min_interval = 0.5  # seconds between requests

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make a rate-limited GET request to the API."""
        # Rate limit
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

        url = f"{self.base_url}{path}"
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        params.setdefault("format", "json")

        resp = self.session.get(url, params=params, timeout=30)
        self._last_request_time = time.time()

        if resp.status_code == 429:
            # Rate limited - wait and retry once
            time.sleep(5)
            resp = self.session.get(url, params=params, timeout=30)

        resp.raise_for_status()
        return resp.json()

    def list_resolutions(self, res_type: str, from_date: str, to_date: str,
                         limit: int = 250, offset: int = 0) -> list[dict]:
        """
        List resolutions of a given type updated within a date range.

        Args:
            res_type: e.g. "sres", "hres", "sjres", etc.
            from_date: ISO 8601 datetime string
            to_date: ISO 8601 datetime string
            limit: max results per page (max 250)
            offset: pagination offset
        """
        path = f"/bill/{CURRENT_CONGRESS}/{res_type}"
        params = {
            "fromDateTime": from_date,
            "toDateTime": to_date,
            "sort": "updateDate+desc",
            "limit": limit,
            "offset": offset,
        }
        data = self._get(path, params)
        return data.get("bills", [])

    def get_bill_detail(self, res_type: str, number: int) -> dict:
        """Get detailed information about a specific bill/resolution."""
        path = f"/bill/{CURRENT_CONGRESS}/{res_type}/{number}"
        data = self._get(path)
        return data.get("bill", {})

    def get_bill_actions(self, res_type: str, number: int) -> list[dict]:
        """Get all actions for a specific bill/resolution."""
        path = f"/bill/{CURRENT_CONGRESS}/{res_type}/{number}/actions"
        data = self._get(path)
        return data.get("actions", [])

    def get_bill_text_versions(self, res_type: str, number: int) -> list[dict]:
        """Get text versions for a specific bill/resolution."""
        path = f"/bill/{CURRENT_CONGRESS}/{res_type}/{number}/text"
        data = self._get(path)
        return data.get("textVersions", [])

    def get_bill_cosponsors(self, res_type: str, number: int) -> dict:
        """Get cosponsor information for a specific bill/resolution."""
        path = f"/bill/{CURRENT_CONGRESS}/{res_type}/{number}/cosponsors"
        data = self._get(path)
        return data

    def get_bill_subjects(self, res_type: str, number: int) -> dict:
        """Get subjects/policy area for a specific bill/resolution."""
        path = f"/bill/{CURRENT_CONGRESS}/{res_type}/{number}/subjects"
        data = self._get(path)
        return data

    # --- Congressional Record ---

    def get_daily_cr_issues(self, limit: int = 20) -> list[dict]:
        """Get recent Daily Congressional Record issues."""
        path = "/daily-congressional-record"
        data = self._get(path, {"limit": limit})
        return data.get("dailyCongressionalRecord", [])

    def get_cr_articles(self, volume: int, issue: int, section: str = None) -> list[dict]:
        """Get articles for a specific Congressional Record issue.

        The API returns sections, each containing sectionArticles.
        This flattens them into a single list, optionally filtered by section name.
        """
        path = f"/daily-congressional-record/{volume}/{issue}/articles"
        data = self._get(path, {"limit": 250})
        sections = data.get("articles", [])

        all_articles = []
        for sec in sections:
            sec_name = sec.get("name", "")
            if section and section.lower() not in sec_name.lower():
                continue
            for article in sec.get("sectionArticles", []):
                article["_section"] = sec_name
                all_articles.append(article)
        return all_articles

    def fetch_cr_article_html(self, url: str) -> str:
        """Fetch the HTML content of a Congressional Record article."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

        resp = self.session.get(url, timeout=30)
        self._last_request_time = time.time()
        resp.raise_for_status()
        return resp.text
