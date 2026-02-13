"""
DynamoDB utilities
"""

import os
import boto3 # for talking to AWS
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Key


class DynamoDBClient:
    """For interacting with DynamoDB tables"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.risk_scores_table_name = os.environ.get('RISK_SCORES_TABLE_NAME', 'risk_scores')
        self.alert_rules_table_name = os.environ.get('ALERT_RULES_TABLE_NAME', 'user_alert_rules')
        
        self.risk_scores_table = self.dynamodb.Table(self.risk_scores_table_name)
        self.alert_rules_table = self.dynamodb.Table(self.alert_rules_table_name)
    
    def save_risk_score(
        self,
        metric: str,
        timestamp: str,
        value: float,
        moving_avg_30d: float,
        pct_change: float,
        risk_score: int,
        severity: str,
        source_object_key: str
    ):
        """
        Save a risk score to DynamoDB
        Args:
            metric: Metric name (ex: 'freight_cost_index')
            timestamp: timestamp string
            value: value today
            moving_avg_30d: 30 day moving average
            pct_change: percent change from the avg
            risk_score: Risk score
            severity: Severity level
            source_object_key: key of the S3 object that was scored
        """
        item = {
            'metric': metric,
            'timestamp': timestamp,
            'value': Decimal(str(value)),
            'moving_avg_30d': Decimal(str(moving_avg_30d)),
            'pct_change': Decimal(str(pct_change)),
            'risk_score': risk_score,
            'severity': severity,
            'source_object_key': source_object_key
        }
        self.risk_scores_table.put_item(Item=item)
    
    def get_latest_score(self, metric: str):
        """
        Get the latest risk score for a metric from DynamoDB
        Args:
            metric: Metric name
        Returns:
            Latest risk score item in DynamoDB or None
        """
        # Full response
        response = self.risk_scores_table.query(
            KeyConditionExpression=Key('metric').eq(metric),
            ScanIndexForward=False,  # descending, so it gets the latest item
            Limit=1
        )

        # Get only 'Items' part
        items = response.get('Items', [])
        if items:
            return self._convert_decimal_to_float(items[0]) # return the item found
        return None
    
    def get_scores_time_series(self, metric: str, start_date: str, end_date: str, limit: int = 1000):
        """
        Get risk scores for a metric for a range of dates.
        Args:
            metric: metric name
            start_date: Start date
            end_date: End date
            limit: Max amount of items to return
        Returns:
            List of risk score items
        """
        # Guarantee dates are in ISO format
        if len(start_date) == 10:  # If in YYYY-MM-DD format
            start_date = f"{start_date}T00:00:00Z"
        if len(end_date) == 10:  # If in YYYY-MM-DD format
            end_date = f"{end_date}T23:59:59Z"
        
        response = self.risk_scores_table.query(
            KeyConditionExpression=Key('metric').eq(metric) & 
                                  Key('timestamp').between(start_date, end_date),
            ScanIndexForward=False,  # descending for newest first
            Limit=limit
        )
        
        # Get only the 'Items' part of the dict
        items = response.get('Items', [])
        return [self._convert_decimal_to_float(item) for item in items]
    
    