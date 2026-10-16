"""
One-shot historical backfill.

Run once after a fresh deploy so the 30-day moving averages have real history
instead of starting from nothing:

  python -m ingestion.backfill --days 400

Writes ONE S3 file per FRED series containing the full history, under
backfill/fred/YYYY/MM/DD/. Each file triggers one analysis Lambda run, which
scores the observations oldest first. One file per series (instead of one
file per day) keeps the scoring in order, since day N's moving average
depends on the days before it already being saved.

Every payload is marked "backfill": true so the analysis Lambda never sends
alert emails for it.

Port of LA data is not backfilled: the RSS feed only has the current value.

Required env vars:
  RAW_DATA_BUCKET_NAME: S3 bucket for raw data
  FRED_API_KEY: FRED API key
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
        logger.error("Nothing fetched, so nothing to backfill")
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
