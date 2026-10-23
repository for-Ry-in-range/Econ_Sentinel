"""
Triggered by a data file being uploaded to S3

Processes the data files uploaded to S3.
Calculates risk scores and saves them to DynamoDB.
"""

import json
import os
import boto3
from datetime import datetime, timezone
from typing import Dict, Any
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.risk_calculator import RiskCalculator
from shared.dynamodb_client import DynamoDBClient
from shared.data_parser import DataParser


s3_client = boto3.client('s3')
ses_client = boto3.client('ses')  # AWS Simple Email Service sends emails
dynamodb_client = DynamoDBClient()
data_parser = DataParser()
risk_calculator = RiskCalculator()

SENDER_EMAIL = os.environ.get('SES_SENDER_EMAIL', '')  # the 'from'

# Never alert on observations older than this
ALERT_MAX_AGE_DAYS = 10


def lambda_handler(event: Dict[str, Any], context: Any):
    """
    Lambda handler for S3 event triggers
    Event structure:
    {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket-name"},
                    "object": {"key": "path/to/file.json"}
                }
            }
        ]
    }
    """
    print(f"Received event: {json.dumps(event)}")
    processed_count = 0
    skipped_count = 0
    errors = []
    
    # Go through each S3 record
    for record in event.get('Records', []):
        try:
            bucket_name = record['s3']['bucket']['name']
            object_key = record['s3']['object']['key']
            
            print(f"Processing s3://{bucket_name}/{object_key}")
        
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            content_type = response.get('ContentType', 'application/json')
            file_content = response['Body'].read()
            
            parsed_data = data_parser.parse_s3_object(file_content, content_type)
            
            if not parsed_data:
                print(f"Failure parsing data from {object_key}")
                errors.append(f"Parse error: {object_key}")
                continue
            
            metrics_data = []

            # Backfill files hold history, so they must never send alerts
            backfill = parsed_data.get('backfill') is True
            if backfill:
                print(f"{object_key} is a backfill file, so alerts are off for it")

            # Check if it's FRED data
            if 'series_id' in parsed_data or ('metric' in parsed_data and 'fred' in parsed_data.get('source', '').lower()):
                fred_items = data_parser.parse_fred_data(parsed_data)
                metrics_data.extend(fred_items)
            
            # Check if it's port congestion data
            elif 'ports' in parsed_data or 'port' in parsed_data or 'congestion_count' in parsed_data:
                port_items = data_parser.parse_port_congestion_data(parsed_data)
                metrics_data.extend(port_items)

            # Last resort
            else:
                if 'metric' in parsed_data and 'value' in parsed_data:
                    metrics_data.append({
                        'metric': parsed_data['metric'],
                        'value': float(parsed_data['value']),
                        'timestamp': parsed_data.get('timestamp', parsed_data.get('date', '')),
                        'source': parsed_data.get('source', 'unknown')
                    })
            
            # Process each metric, in order (oldest first for backfill files)
            for metric_data in metrics_data:
                try:
                    scored = process_metric(
                        metric=metric_data['metric'],
                        value=metric_data['value'],
                        timestamp=metric_data.get('timestamp', ''),
                        source_object_key=object_key,
                        backfill=backfill
                    )
                    if scored:
                        processed_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    error_msg = f"Error processing metric {metric_data.get('metric', 'unknown')}: {str(e)}"
                    print(error_msg)
                    errors.append(error_msg)
        
        except Exception as e:
            error_msg = f"Error processing record: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
    
    result = {
        'statusCode': 200,
        'processed_count': processed_count,
        'skipped_count': skipped_count,
        'errors': errors
    }
    
    print(f"Processing complete: {result}")
    return result


def process_metric(metric: str, value: float, timestamp: str, source_object_key: str, backfill: bool = False) -> bool:
    """
    Process one observation: calculate the risk and save to DynamoDB.
    Args:
        metric: Metric name
        value: Observed value
        timestamp: Observation timestamp string
        source_object_key: S3 object key
        backfill: True if this came from a backfill file (always rescore, never alert)
    Returns:
        True if the observation was scored, False if it was skipped
    """
    # Normalize the timestamp
    normalized_timestamp = data_parser.normalize_timestamp(timestamp)
    if not normalized_timestamp:
        normalized_timestamp = datetime.utcnow().isoformat() + 'Z'

    # If there's already a score for this metric on a specific date
    existing = dynamodb_client.get_score(metric, normalized_timestamp)

    # The daily job re-fetches the latest value of a weekly series about 5 times.
    # Scoring it again would change the score and send the same alert again, so skip it.
    # Backfill always rescores, to fix rows the daily job scored before there was history.
    if existing and not backfill and float(existing['value']) == value:
        print(f"{metric} at {normalized_timestamp} is already scored with the same value, so skipping")
        return False

    # Values from the 30 days before this observation
    baseline_values = dynamodb_client.get_values_before(metric, normalized_timestamp, days=30)

    # Risk score
    risk_assessment = risk_calculator.assess(value, baseline_values)

    # Save to DynamoDB
    dynamodb_client.save_risk_score(
        metric=metric,
        timestamp=normalized_timestamp,
        value=value,
        moving_avg_30d=risk_assessment['moving_avg'],
        pct_change=risk_assessment['pct_change'],
        risk_score=risk_assessment['risk_score'],
        severity=risk_assessment['severity'],
        source_object_key=source_object_key
    )

    print(f"Saved risk score for {metric} at {normalized_timestamp}: {risk_assessment['severity']} "
          f"(score: {risk_assessment['risk_score']}, baseline points: {len(baseline_values)})")

    # Check if alerts need to be triggered (if severity is warning or critical)
    if risk_assessment['severity'] in ['warning', 'critical']:
        if should_send_alerts(metric, normalized_timestamp, backfill, is_revision=existing is not None):
            trigger_alerts(metric, risk_assessment, value)

    return True


def should_send_alerts(metric: str, timestamp: str, backfill: bool, is_revision: bool) -> bool:
    """
    Decide whether a warning/critical score should email subscribers.
    Args:
        metric: Metric name
        timestamp: Observation timestamp string
        backfill: True if this came from a backfill file
        is_revision: True if this observation was already scored once (FRED revised the value)
    Returns:
        True if alerts should be sent
    """
    if backfill:
        print(f"Not alerting for {metric} at {timestamp}: backfill file")
        return False

    if is_revision:
        print(f"Not alerting for {metric} at {timestamp}: revised value of an observation that was already scored")
        return False

    # Safety net in case a historical file ever shows up without the backfill flag
    if not is_recent_observation(timestamp):
        print(f"Not alerting for {metric} at {timestamp}: older than {ALERT_MAX_AGE_DAYS} days")
        return False

    return True


# Only allow recent data to trigger alerts
def is_recent_observation(timestamp: str) -> bool:
    """True if the observation is within ALERT_MAX_AGE_DAYS. Unreadable timestamps count as old."""
    try:
        observed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError:
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    # Compare calendar dates, since FRED observations are date-only
    age_days = (datetime.now(timezone.utc).date() - observed.astimezone(timezone.utc).date()).days
    return age_days <= ALERT_MAX_AGE_DAYS


def trigger_alerts(metric: str, risk_assessment: Dict[str, Any], value: float):
    """
    Send alerts to users who have alert rules set for this metric.
    Args:
        metric: Metric name
        risk_assessment: Risk assessment dict
        value: Current value
    """
    print(f"Alert check for {metric}: {risk_assessment['severity']} (pct_change: {risk_assessment['pct_change']}%)")

    alert_rules = dynamodb_client.get_alert_rules_for_metric(metric)
    triggered_count = 0

    for rule in alert_rules:
        if not rule.get('enabled', True):
            continue
        threshold = float(rule.get('threshold', 0))
        if abs(risk_assessment['pct_change']) >= threshold:
            email = rule.get('email')
            if email and SENDER_EMAIL:
                _send_alert_email(email, metric, risk_assessment, value, rule)
                triggered_count += 1

    print(f"Triggered {triggered_count} alert(s) for {metric}")


def _send_alert_email(recipient: str, metric: str, risk_assessment: Dict[str, Any], value: float, rule: Dict[str, Any]):
    """Send an alert email using SES"""
    severity = risk_assessment['severity'].upper()
    pct_change = risk_assessment['pct_change']
    risk_score = risk_assessment['risk_score']

    subject = f"Econ Sentinel - {severity} Alert: {metric}"
    body = (
        f"Econ Sentinel Alert\n\n"
        f"Metric:            {metric}\n"
        f"Severity:          {severity}\n"
        f"Current Value:     {value}\n"
        f"Change (30d avg):  {pct_change:+.2f}%\n"
        f"Risk Score:        {risk_score}/100\n"
        f"Your Threshold:    {rule.get('threshold')}%\n\n"
        f"Log in to Econ Sentinel to view the full dashboard."
    )

    try:
        ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        print(f"Alert email sent to {recipient} for {metric}")
    except Exception as e:
        print(f"Failed to send alert email; {e}")