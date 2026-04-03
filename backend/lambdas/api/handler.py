"""
Handles HTTP requests for dashboard and alert preferences.
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.dynamodb_client import DynamoDBClient


dynamodb_client = DynamoDBClient()


def lambda_handler(event: Dict[str, Any], context: Any):
    """
    Lambda handler for API Gateway requests.
    """
    print(f"Received API request: {json.dumps(event)}")
    
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    query_params = event.get('queryStringParameters') or {}
    
    # Extract user_id from authorizer
    user_id = None
    if 'requestContext' in event and 'authorizer' in event['requestContext']:
        claims = event['requestContext']['authorizer'].get('claims', {})
        user_id = claims.get('sub')
    
    # Fallback
    if not user_id:
        headers = event.get('headers', {})
        user_id = headers.get('x-user-id') or query_params.get('user_id')
    
    try:
        # Call the correct function
        if path == '/scores/latest' and http_method == 'GET':
            return get_latest_score(query_params)
        elif path == '/scores' and http_method == 'GET':
            return get_scores_time_series(query_params)
        elif path == '/metrics' and http_method == 'GET':
            return get_all_metrics()
        elif path == '/alerts' and http_method == 'GET':
            return get_user_alerts(user_id)
        elif path == '/alerts' and http_method == 'PUT':
            body = json.loads(event.get('body', '{}'))
            return create_or_update_alert(user_id, body)
        elif path.startswith('/alerts/') and http_method == 'DELETE':
            metric = path.split('/')[-1]
            return delete_alert(user_id, metric)
        else:
            return create_response(404, {'error': 'Not found'})
    
    except Exception as e:
        print(f"Error handling request: {str(e)}")
        return create_response(500, {'error': str(e)})


def get_latest_score(query_params: Dict[str, str]):
    """Get latest risk score for a metric"""
    metric = query_params.get('metric')
    
    if not metric:
        return create_response(400, {'error': 'metric parameter is required'})
    
    score = dynamodb_client.get_latest_score(metric)
    
    if not score:
        return create_response(404, {'error': f'No scores found for metric: {metric}'})
    
    return create_response(200, score)


def get_scores_time_series(query_params: Dict[str, str]):
    """Get time series of risk scores for a metric"""
    metric = query_params.get('metric')
    start_date = query_params.get('start')
    end_date = query_params.get('end')
    
    if not metric:
        return create_response(400, {'error': 'metric parameter is required'})
    
    # Default to last 30 days if dates not provided
    if not start_date or not end_date:
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    scores = dynamodb_client.get_scores_time_series(metric, start_date, end_date)
    
    return create_response(200, {
        'metric': metric,
        'start_date': start_date,
        'end_date': end_date,
        'count': len(scores),
        'scores': scores
    })


def get_all_metrics() -> Dict[str, Any]:
    """Get list of all available metrics"""
    metrics = dynamodb_client.get_all_metrics()
    
    return create_response(200, {
        'metrics': metrics,
        'count': len(metrics)
    })


def get_user_alerts(user_id: Optional[str]):
    """Get all alert rules for a user."""
    if not user_id:
        return create_response(401, {'error': 'Authentication required'})
    
    alerts = dynamodb_client.get_user_alert_rules(user_id)
    
    return create_response(200, {
        'user_id': user_id,
        'alerts': alerts,
        'count': len(alerts)
    })


def create_or_update_alert(user_id: Optional[str], body: Dict[str, Any]):
    """Create or update an alert rule"""
    if not user_id:
        return create_response(401, {'error': 'Authentication required'})
    
    metric = body.get('metric')
    threshold = body.get('threshold')
    enabled = body.get('enabled', True)
    email = body.get('email')

    if not metric:
        return create_response(400, {'error': 'metric is required'})

    if threshold is None:
        return create_response(400, {'error': 'threshold is required'})

    try:
        threshold_float = float(threshold)
    except (ValueError, TypeError):
        return create_response(400, {'error': 'threshold must be a number'})

    dynamodb_client.save_alert_rule(user_id, metric, threshold_float, enabled, email)

    return create_response(200, {
        'message': 'Alert rule created/updated',
        'user_id': user_id,
        'metric': metric,
        'threshold': threshold_float,
        'enabled': enabled,
        'email': email
    })


def delete_alert(user_id: Optional[str], metric: str):
    """Delete an alert rule"""
    if not user_id:
        return create_response(401, {'error': 'Authentication required'})
    
    if not metric:
        return create_response(400, {'error': 'metric is required'})
    
    dynamodb_client.delete_alert_rule(user_id, metric)
    
    return create_response(200, {
        'message': 'Alert rule deleted',
        'user_id': user_id,
        'metric': metric
    })


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """API Gateway response template"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',  # Edit CORS during production
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,x-user-id',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body)
    }
