"""
Run from the backend folder:  python -m pytest tests
"""

import os

# The analysis handler creates boto3 clients when it's imported, which needs a region.
# Nothing in these tests talks to AWS.
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-2')
