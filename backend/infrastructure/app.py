"""
Prepares the AWS resources: Lambda functions, DynamoDB tables, S3 buckets, etc.
"""

#!/usr/bin/env python3
import os
import aws_cdk as cdk
from econ_sentinel_stack import EconSentinelStack  # Stack of AWS resources


app = cdk.App()

# Get environment variables
env = cdk.Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
    region=os.environ.get('CDK_DEFAULT_REGION', 'us-east-2')
)

# Create the stack
EconSentinelStack(
    app,
    "EconSentinelBackend",
    env=env,
    description="Econ Sentinel Backend Infrastructure - Analysis and API Layers"
)

app.synth()
