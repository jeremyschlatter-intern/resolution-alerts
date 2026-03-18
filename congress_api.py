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
