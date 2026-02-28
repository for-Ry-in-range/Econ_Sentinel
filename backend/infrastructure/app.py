"""
AWS CDK App for Econ Sentinel Backend Infrastructure.
"""

#!/usr/bin/env python3
import os
import aws_cdk as cdk
from econ_sentinel_stack import EconSentinelStack


app = cdk.App()

# Get environment variables or use defaults
env = cdk.Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
    region=os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')
)

# Create the stack
EconSentinelStack(
    app,
    "EconSentinelBackend",
    env=env,
    description="Econ Sentinel Backend Infrastructure - Analysis and API Layers"
)

app.synth()
