"""
Storing the raw ingestion data in S3


Makes it easy to query by date in S3.
"""

import json
import logging
import uuid
from datetime import date

import boto3

logger = logging.getLogger(__name__)


class S3Storage:
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.s3 = boto3.client("s3")

    def _build_key(self, source: str, metric: str, run_date: date) -> str:
        """
        Make S3 key (unique name in S3) based on date.
        Example: fred/2024/01/15/inflation_rate_cpi_a3f2.json
        """
        short_id = uuid.uuid4().hex[:8]  # random unique ID
        return (
            f"{source}/"
            f"{run_date.year:04d}/{run_date.month:02d}/{run_date.day:02d}/"
            f"{metric}_{short_id}.json"
        )

    def upload(self, payload: dict, source: str, metric: str, run_date: date | None = None) -> str:
        """
        Serialize payload to JSON and upload it to S3.

        Args:
            payload:   Dict to upload
            source:    e.g. "fred" or "port"
            metric:    e.g. "inflation_rate_cpi"
            run_date:  Date used for partitioning

        Returns:
            S3 key of the uploaded object
        """
        if run_date is None:
            run_date = date.today()

        key = self._build_key(source, metric, run_date)
        body = json.dumps(payload, default=str).encode("utf-8")

        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
        logger.info("Uploaded s3://%s/%s (%d bytes)", self.bucket_name, key, len(body))
        return key

    def upload_many(self, payloads: list[tuple[dict, str, str]]) -> list[str]:
        """
        Upload multiple payloads.
        Args:
            payloads: List of (payload, source, metric) tuples.
        Returns:
            List of uploaded S3 keys.
        """
        today = date.today()
        keys = []
        for payload, source, metric in payloads:
            try:
                key = self.upload(payload, source, metric, run_date=today)
                keys.append(key)
            except Exception as e:
                logger.error("Failed to upload %s/%s: %s", source, metric, e)
        return keys
