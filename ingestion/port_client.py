"""
Port and freight data client
"""

import logging
import xml.etree.ElementTree as ET
from datetime import date, timedelta
import requests
from .config import FREIGHT_FRED_SERIES

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

PORT_LA_VESSEL_QUEUE_URL = (
    "https://calumet.portoflosangeles.org/rss/ves_queue.xml"
)


class PortClient:
    def __init__(self, fred_api_key: str):
        self.fred_api_key = fred_api_key
        self.session = requests.Session()

    def fetch_freight_series(self, series_id: str) -> dict | None:
        observation_start = (date.today() - timedelta(days=90)).isoformat()
        params = {
            "series_id": series_id,
            "api_key": self.fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
            "observation_start": observation_start,
        }
        try:
            response = self.session.get(FRED_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            observations = response.json().get("observations", [])
            if not observations or observations[0].get("value") == ".":
                return None
            latest = observations[0]
            return {
                "date": latest["date"],
                "value": float(latest["value"])
            }
        except (requests.RequestException, ValueError) as e:
            logger.error("Failed to fetch freight FRED series %s: %s", series_id, e)
            return None

    def fetch_all_freight(self) -> list[dict]:
        """
        Return a dict for each metric type
        """
        results = []
        for metric_name, series_id in FREIGHT_FRED_SERIES.items():
            obs = self.fetch_freight_series(series_id)
            if obs:
                payload = {metric_name: obs["value"], "date": obs["date"]}
                results.append(payload)
                logger.info("Fetched freight series %s (%s)", series_id, metric_name)
            else:
                logger.warning("Skipping freight series %s (%s)", series_id, metric_name)
        return results
    

    def fetch_port_la_queue(self) -> dict | None:
        """
        Scrape Port of LA vessel-queue feed
        """
        try:
            response = self.session.get(PORT_LA_VESSEL_QUEUE_URL, timeout=10)
            response.raise_for_status()  # raise exception if HTTP response code is an error
            root = ET.fromstring(response.content)  # convert XML

            ports = []
            today = date.today().isoformat()

            for item in root.iter("item"):  # for each metric in root
                title = item.findtext("title", default="")
                pub_date = item.findtext("pubDate", default=today)

                # Title format: "Vessels Waiting: <count>"
                if "waiting" in title.lower() or "queue" in title.lower():
                    try:
                        count = int("".join(filter(str.isdigit, title)))
                        ports.append({
                            "port": "los_angeles",
                            "congestion_count": count,
                            "date": today,
                        })
                        logger.info("Port of LA vessel queue: %d vessels waiting", count)
                        break
                    except ValueError:
                        logger.warning("Could not parse vessel count from: %s", title)

            if ports:
                return {"ports": ports}
            return None

        except (requests.RequestException, ET.ParseError) as e:
            logger.warning("Could not fetch Port of LA vessel queue: %s", e)
            return None


    # Public interface:

    def fetch_all(self) -> list[dict]:
        """
        Fetch port AND freight data.
        Returns a list of dicts to upload to S3
        """
        results = []

        # Freight
        results.extend(self.fetch_all_freight())

        # Port vessel queue
        la_queue = self.fetch_port_la_queue()
        if la_queue:
            results.append(la_queue)
        else:
            logger.warning(
                "Port of LA vessel queue unavailable."
            )

        return results
