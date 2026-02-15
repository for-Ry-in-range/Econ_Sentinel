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

    def get_recent_scores_for_average(self, metric: str, days: int = 30):
        """
        Get recent scores for calculating moving average
        Args:
            metric: Metric name
            days: Number of days to look back
        Returns:
            List of recent risk score items
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        start_iso = start_date.strftime('%Y-%m-%dT00:00:00Z')
        end_iso = end_date.strftime('%Y-%m-%dT23:59:59Z')
        return self.get_scores_time_series(metric, start_iso, end_iso, limit=1000)

    def calculate_moving_average(self, metric: str, days: int = 30):
        """
        Calculate moving average from recent scores
        Args:
            metric: Metric name
            days: Number of days for moving average
        Returns:
            Moving average value or None if not enough data
        """
        recent_scores = self.get_recent_scores_for_average(metric, days)

        if not recent_scores:
            return None

        values = [float(score['value']) for score in recent_scores]
        if values:
            return sum(values) / len(values)
        return None

    def get_all_metrics(self):
        """
        Get list of all unique metrics in the DynamoDB
        Returns:
            List of metric names
        """
        response = self.risk_scores_table.scan(
            ProjectionExpression='metric'
        )
        metrics = set()
        for item in response.get('Items', []):
            metrics.add(item['metric'])
        # Get the rest
        while 'LastEvaluatedKey' in response:
            response = self.risk_scores_table.scan(
                ProjectionExpression='metric',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            for item in response.get('Items', []):
                metrics.add(item['metric'])
        return sorted(list(metrics))

    def save_alert_rule(
        self,
        user_id: str,
        metric: str,
        threshold: float,
        enabled: bool = True
    ):
        """
        Save or update an alert rule
        Args:
            user_id: User id
            metric: Metric to monitor
            threshold: Threshold percentage for alert
            enabled: if the alert is enabled or not
        """
        item = {
            'user_id': user_id,
            'metric': metric,
            'threshold': Decimal(str(threshold)),
            'enabled': enabled,
            'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }

        self.alert_rules_table.put_item(Item=item)

    def get_user_alert_rules(self, user_id: str):
        """
        Get all alert rules for a user
        Args:
            user_id: User id
        Returns:
            List of alert rule items
        """
        response = self.alert_rules_table.query(
            KeyConditionExpression=Key('user_id').eq(user_id)
        )

        items = response.get('Items', [])
        return [self._convert_decimal_to_float(item) for item in items]

    def delete_alert_rule(self, user_id: str, metric: str):
        """
        Delete an alert rule
        Args:
            user_id: User id
            metric: Metric name
        """
        self.alert_rules_table.delete_item(
            Key={
                'user_id': user_id,
                'metric': metric
            }
        )

    def get_alert_rules_for_metric(self, metric: str):
        """
        Get all alert rules for a specific metric
        Args:
            metric: Metric name
        Returns:
            List of alert rule items
        """
        response = self.alert_rules_table.query(
            IndexName='metric-index',
            KeyConditionExpression=Key('metric').eq(metric)
        )
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = self.alert_rules_table.query(
                IndexName='metric-index',
                KeyConditionExpression=Key('metric').eq(metric),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        return [self._convert_decimal_to_float(item) for item in items]

    @staticmethod
    def _convert_decimal_to_float(item: Dict):
        """Convert Decimal types to float for JSON"""
        converted = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                converted[key] = float(value)
            elif isinstance(value, dict):
                converted[key] = DynamoDBClient._convert_decimal_to_float(value)
            elif isinstance(value, list):
                converted[key] = []
                for v in value:
                    if isinstance(v, dict):
                        converted[key].append(DynamoDBClient._convert_decimal_to_float(v))
                    elif isinstance(v, Decimal):
                        converted[key].append(float(v))
                    else:
                        converted[key].append(v)
            else:
                converted[key] = value
        return converted
