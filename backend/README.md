# Econ Sentinel Backend

Backend infrastructure and Lambda functions for Econ Sentinel.

## Architecture

- **Analysis Lambda**: Triggered by S3 events when raw data is uploaded. Calculates risk scores and saves to DynamoDB.
- **API Lambda**: Handles HTTP requests for dashboard data and alert preferences.
- **DynamoDB Tables**: 
  - `risk_scores`: Stores calculated risk scores
  - `user_alert_rules`: Stores user alert preferences
- **API Gateway**: REST API endpoint for frontend

## Project Structure

```
backend/
├── infrastructure/          # AWS CDK infrastructure code
│   ├── app.py              # CDK app entry point
│   ├── econ_sentinel_stack.py  # Main stack definition
│   ├── requirements.txt    # CDK dependencies
│   └── cdk.json            # CDK configuration
├── lambdas/
│   ├── analysis/           # Analysis Lambda function
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── api/                # API Lambda function
│       ├── handler.py
│       └── requirements.txt
└── shared/                 # Shared utilities
    ├── risk_calculator.py   # Risk calculation logic
    ├── dynamodb_client.py   # DynamoDB operations
    └── data_parser.py       # Data parsing utilities
```

## Setup

### Prerequisites

- Python 3.12+
- AWS CLI configured
- AWS CDK CLI installed: `npm install -g aws-cdk`

### Installation

1. Install CDK dependencies:
```bash
cd infrastructure
pip install -r requirements.txt
```

2. Install Lambda dependencies:
```bash
cd ../lambdas/analysis
pip install -r requirements.txt -t .

cd ../api
pip install -r requirements.txt -t .
```

### Deployment

1. Bootstrap CDK (first time only):
```bash
cd infrastructure
cdk bootstrap
```

2. Deploy the stack:
```bash
cdk deploy
```

3. Note the API endpoint URL from the stack outputs.

## API Endpoints

### Dashboard Endpoints

- `GET /scores/latest?metric={metric}` - Get latest risk score for a metric
- `GET /scores?metric={metric}&start={date}&end={date}` - Get time series of scores
- `GET /metrics` - Get list of all available metrics

### Alert Endpoints

- `GET /alerts` - Get user's alert rules (requires `x-user-id` header)
- `PUT /alerts` - Create/update alert rule (requires `x-user-id` header)
  ```json
  {
    "metric": "freight_cost_index",
    "threshold": 15.0,
    "enabled": true
  }
  ```
- `DELETE /alerts/{metric}` - Delete alert rule (requires `x-user-id` header)

## Risk Calculation

Risk scores are calculated based on percent change from 30-day moving average:

- **Normal**: < 5% change (risk score: 0-30)
- **Warning**: 5% to 15% change (risk score: 31-70)
- **Critical**: > 15% change (risk score: 71-100)

## Environment Variables

Lambda functions use these environment variables (set automatically by CDK):

- `RISK_SCORES_TABLE_NAME`: DynamoDB table for risk scores
- `ALERT_RULES_TABLE_NAME`: DynamoDB table for alert rules
- `RAW_DATA_BUCKET_NAME`: S3 bucket for raw data

## Adding Authentication

The code is structured to support authentication later. To add Cognito:

1. Add Cognito User Pool to CDK stack
2. Add Cognito authorizer to API Gateway routes
3. Update API Lambda to extract `user_id` from JWT claims in `requestContext.authorizer.claims.sub`

## Development

### Local Testing

For local Lambda testing, you can use AWS SAM or test directly:

```python
# Test analysis Lambda
from lambdas.analysis.handler import lambda_handler
event = {
    "Records": [{
        "s3": {
            "bucket": {"name": "test-bucket"},
            "object": {"key": "test/data.json"}
        }
    }]
}
lambda_handler(event, None)
```

### Testing API Lambda

Use a local API Gateway simulator or test directly:

```python
from lambdas.api.handler import lambda_handler
event = {
    "httpMethod": "GET",
    "path": "/scores/latest",
    "queryStringParameters": {"metric": "freight_cost_index"},
    "headers": {}
}
lambda_handler(event, None)
```

## Next Steps

- [ ] Implement alert dispatch logic (SES/SNS integration)
- [ ] Add Cognito authentication
- [ ] Add CloudWatch alarms for error monitoring
- [ ] Optimize DynamoDB queries with caching
- [ ] Add unit tests
