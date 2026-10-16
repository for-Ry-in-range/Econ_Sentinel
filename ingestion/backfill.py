"""
One time historical backfill

Run once after deploy: python -m ingestion.backfill --days 400

Writes 1 S3 file per FRED series containing the full history. The payloads are marked
as backfill so the analysis Lambda doesn't send alert emails for it. Port of LA is
not backfilled because the RSS feed only has the current value.
"""

import argparse
import logging
import os
import sys
from datetime import date, timedelta

from .fred_client import FREDClient
from .storage import S3Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Get the amount of days to backfill
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Backfill historical FRED data into S3")
    parser.add_argument(
        "--days",
        type=int,
        default=400,
        help="How many days of history to fetch (default: 400)",
    )
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be at least 1")
    return args


def run(argv=None):
    args = parse_args(argv)

    bucket_name = os.environ.get("RAW_DATA_BUCKET_NAME")
    fred_api_key = os.environ.get("FRED_API_KEY")

    if not bucket_name:
        logger.error("RAW_DATA_BUCKET_NAME environment variable is not set")
        sys.exit(1)

    if not fred_api_key:
        logger.error("FRED_API_KEY environment variable is not set")
        sys.exit(1)

    end = date.today()
    start = end - timedelta(days=args.days)
    logger.info("Starting backfill — bucket: %s, range: %s to %s", bucket_name, start, end)

    storage = S3Storage(bucket_name=bucket_name)
    fred_client = FREDClient(api_key=fred_api_key)

    upload_data: list[tuple[dict, str, str]] = []

    for result in fred_client.fetch_all_range(start, end):
        metric_name = result.get("metric_name", result.get("series_id", "unknown"))
        result["backfill"] = True  # tells the analysis Lambda not to send alerts
        upload_data.append((result, "backfill/fred", metric_name))

    if not upload_data:
        logger.error("Nothing fetched so there is nothing to backfill")
        sys.exit(1)

    uploaded_keys = storage.upload_many(upload_data)

    total = len(upload_data)
    succeeded = len(uploaded_keys)
    failed = total - succeeded
    logger.info(
        "Backfill complete — %d/%d uploads succeeded, %d failed",
        succeeded, total, failed,
    )
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run()
