"""
Port congestion data client
"""

import logging
import xml.etree.ElementTree as ET
from datetime import date
import requests

logger = logging.getLogger(__name__)

PORT_LA_VESSEL_QUEUE_URL = (
    "https://calumet.portoflosangeles.org/rss/ves_queue.xml"
)


class PortClient:
    def __init__(self):
        self.session = requests.Session()

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
        Fetch port congestion data.
        Returns a list of dicts to upload to S3
        """
        results = []

        la_queue = self.fetch_port_la_queue()
        if la_queue:
            results.append(la_queue)
        else:
            logger.warning(
                "Port of LA vessel queue unavailable."
            )

        return results
