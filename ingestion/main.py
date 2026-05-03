"""
Ingestion container entrypoint.

EventBridge triggers this file once a day.
Fetches economic and freight/port data then uploads raw JSON to S3.

Required env vars:
  RAW_DATA_BUCKET_NAME: S3 bucket for raw data
  FRED_API_KEY: FRED API key
"""

import logging
import os
import sys

from .fred_client import FREDClient
from .port_client import PortClient
from .storage import S3Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run():

    # os.environ is a dict that stores current env vars
    bucket_name = os.environ.get("RAW_DATA_BUCKET_NAME")
    fred_api_key = os.environ.get("FRED_API_KEY")

    if not bucket_name:
        logger.error("RAW_DATA_BUCKET_NAME environment variable is not set")
        sys.exit(1)

    if not fred_api_key:
        logger.error("FRED_API_KEY environment variable is not set")
        sys.exit(1)

    logger.info("Starting ingestion run — bucket: %s", bucket_name)

    storage = S3Storage(bucket_name=bucket_name)

    fred_client = FREDClient(api_key=fred_api_key)
    port_client = PortClient(fred_api_key=fred_api_key)

    upload_data: list[tuple[dict, str, str]] = []  # set up the types

    # FRED
    fred_results = fred_client.fetch_all()
    for result in fred_results:
        metric_name = result.get("metric_name", result.get("series_id", "unknown"))
        upload_data.append((result, "fred", metric_name))

    # Port and freight data
    port_results = port_client.fetch_all()
    logger.info("Fetched %d port/freight payloads", len(port_results))

    for result in port_results:
        # Get metric label from the payload
        if "ports" in result:
            metric_name = "port_congestion"
        elif "freight_cost_index" in result:
            metric_name = "freight_cost_index"
        elif "freight_cost_trucking" in result:
            metric_name = "freight_cost_trucking"
        else:
            metric_name = "port_data"
        upload_data.append((result, "port", metric_name))

    # Upload everything to S3
    uploaded_keys = storage.upload_many(upload_data)

    total = len(upload_data)
    succeeded = len(uploaded_keys)
    failed = total - succeeded
    logger.info(
        "Ingestion complete — %d/%d uploads succeeded, %d failed",
        succeeded, total, failed,
    )
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run()
