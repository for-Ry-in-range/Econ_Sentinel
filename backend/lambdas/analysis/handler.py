"""
Triggered by S3 events

Processes the data files uploaded to S3.
Calculates risk scores and saves them to DynamoDB.
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.risk_calculator import RiskCalculator
from shared.dynamodb_client import DynamoDBClient
from shared.data_parser import DataParser


s3_client = boto3.client('s3')
dynamodb_client = DynamoDBClient()
data_parser = DataParser()
risk_calculator = RiskCalculator()


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
            
            # Check if it's FRED data
            if 'series_id' in parsed_data or ('metric' in parsed_data and 'fred' in parsed_data.get('source', '').lower()):
                fred_item = data_parser.parse_fred_data(parsed_data)
                if fred_item:
                    metrics_data.append(fred_item)
            
            # Check if it's port congestion data
            elif 'ports' in parsed_data or 'port' in parsed_data or 'congestion_count' in parsed_data:
                port_items = data_parser.parse_port_congestion_data(parsed_data)
                metrics_data.extend(port_items)
            
            # Check if it's freight cost index
            elif 'freight_cost_index' in parsed_data or 'freight_index' in parsed_data:
                freight_item = data_parser.parse_port_congestion_data(parsed_data)
                metrics_data.extend(freight_item)
            
            # Last resort
            else:
                if 'metric' in parsed_data and 'value' in parsed_data:
                    metrics_data.append({
                        'metric': parsed_data['metric'],
                        'value': float(parsed_data['value']),
                        'timestamp': parsed_data.get('timestamp', parsed_data.get('date', '')),
                        'source': parsed_data.get('source', 'unknown')
                    })
            
            # Process each metric
            for metric_data in metrics_data:
                try:
                    process_metric(
                        metric=metric_data['metric'],
                        value=metric_data['value'],
                        timestamp=metric_data.get('timestamp', ''),
                        source_object_key=object_key
                    )
                    processed_count += 1
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
        'errors': errors
    }
    
    print(f"Processing complete: {result}")
    return result


def process_metric(metric: str, value: float, timestamp: str, source_object_key: str):
    """
    Process one metric: calculate the risk and save to DynamoDB.
    Args:
        metric: Metric name
        value: Current value
        timestamp: Timestamp string
        source_object_key: S3 object key
    """
    # Normalize the timestamp
    normalized_timestamp = data_parser.normalize_timestamp(timestamp)
    if not normalized_timestamp:
        normalized_timestamp = datetime.utcnow().isoformat() + 'Z'
    
    # Get moving average
    moving_avg = dynamodb_client.calculate_moving_average(metric, days=30)
    
    # If no past data then use current value as the first data point
    if moving_avg is None:
        moving_avg = value
        print(f"No historical data for {metric}, so the current value will be used as the baseline")
    
    risk_assessment = risk_calculator.calculate_risk(value, moving_avg)
    
    # Save to DynamoDB
    dynamodb_client.save_risk_score(
        metric=metric,
        timestamp=normalized_timestamp,
        value=value,
        moving_avg_30d=moving_avg,
        pct_change=risk_assessment['pct_change'],
        risk_score=risk_assessment['risk_score'],
        severity=risk_assessment['severity'],
        source_object_key=source_object_key
    )
    
    print(f"Saved risk score for {metric}: {risk_assessment['severity']} (score: {risk_assessment['risk_score']})")
    
    # Check if alerts need to be triggered (if severity is warning or critical)
    if risk_assessment['severity'] in ['warning', 'critical']:
        trigger_alerts(metric, risk_assessment, value)


def trigger_alerts(metric: str, risk_assessment: Dict[str, Any], value: float) -> None:
    """
    Send alerts to users who have alert rules set for this metric.
    Args:
        metric: Metric name
        risk_assessment: Risk assessment dict
        value: Current value
    """
    # TODO: Get alert rules for this metric
    
    print(f"Alert check for {metric}: {risk_assessment['severity']} (pct_change: {risk_assessment['pct_change']}%)")
    
    # TODO: Send the actual alerts