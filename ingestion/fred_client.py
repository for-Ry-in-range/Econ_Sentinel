"""
Fetches FRED data
"""

import logging
from datetime import date, timedelta
import requests
from .config import FRED_SERIES

logger = logging.getLogger(__name__)  # For clean informative logging

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


class FREDClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()  # Create persistent session

    def fetch_series(self, series_id: str):
        """
        Fetch the most recent measurement for a FRED series
        """

        # Look back 90 days to get at least one data point (some series are published monthly)
        observation_start = (date.today() - timedelta(days=90)).isoformat()

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
            "observation_start": observation_start,
        }

        try:
            response = self.session.get(FRED_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            observations = response.json().get("observations", [])

            if not observations:
                logger.warning("No observations returned for series %s", series_id)
                return None

            latest = observations[0]

            # FRED uses "." for missing values
            if latest.get("value") == ".":
                logger.warning("Missing value for series %s on %s", series_id, latest["date"])
                return None

            return {
                "series_id": series_id,
                "data": [{"date": latest["date"], "value": latest["value"]}],
            }

        except requests.RequestException as e:
            logger.error("Failed to fetch FRED series %s: %s", series_id, e)
            return None

    def fetch_series_range(self, series_id: str, start: date, end: date):
        """
        Fetch every row for a FRED series in the range, oldest to latest
        """
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "asc",
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        }

        try:
            response = self.session.get(FRED_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            observations = response.json().get("observations", [])
        except requests.RequestException as e:
            logger.error("Failed to fetch FRED series %s range: %s", series_id, e)
            return None

        # Note: FRED uses "." for missing values
        data = []
        for obs in observations:
            if obs.get("value") != ".":
                data.append({"date": obs["date"], "value": obs["value"]})

        skipped = len(observations) - len(data)
        if skipped:
            logger.warning("Dropped %d missing values for series %s", skipped, series_id)

        if not data:
            logger.warning("No observations returned for series %s between %s and %s", series_id, start, end)
            return None

        return {
            "series_id": series_id,
            "data": data,
        }

    def fetch_all_range(self, start: date, end: date) -> list[dict]:
        """
        Return the full history between start and end for all FRED series in config
        """
        results = []
        for metric_name, series_id in FRED_SERIES.items():
            data = self.fetch_series_range(series_id, start, end)
            if data:
                data["metric_name"] = metric_name
                results.append(data)
                logger.info("Fetched %d observations of FRED series %s (%s)", len(data["data"]), series_id, metric_name)
            else:
                logger.warning("Skipping FRED series %s (%s)", series_id, metric_name)
        return results

    def fetch_all(self) -> list[dict]:
        """
        Return all selected FRED series.
        """
        results = []
        for metric_name, series_id in FRED_SERIES.items():
            data = self.fetch_series(series_id)
            if data:
                data["metric_name"] = metric_name
                results.append(data)
                logger.info("Fetched FRED series %s (%s)", series_id, metric_name)
            else:
                logger.warning("Skipping FRED series %s (%s)", series_id, metric_name)
        return results
