"""
AWS CDK Stack for Econ Sentinel Backend.
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_s3_notifications as s3_notifications,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
)
from constructs import Construct
import os


class EconSentinelStack(Stack):
    """Main CDK Stack for Econ Sentinel Backend."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get S3 bucket name from environment or use default
        raw_data_bucket_name = os.environ.get(
            'RAW_DATA_BUCKET_NAME',
            f'econ-sentinel-raw-{self.account}-{self.region}'
        )

        # ========== S3 Bucket for Raw Data ==========
        raw_data_bucket = s3.Bucket(
            self,
            "RawDataBucket",
            bucket_name=raw_data_bucket_name,
            versioned=False,
            removal_policy=RemovalPolicy.RETAIN,  # Keep data on stack deletion
            auto_delete_objects=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # ========== DynamoDB Tables ==========
        
        # Risk Scores Table
        risk_scores_table = dynamodb.Table(
            self,
            "RiskScoresTable",
            table_name="risk_scores",
            partition_key=dynamodb.Attribute(
                name="metric",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,  # Keep data on stack deletion
            point_in_time_recovery=True,
        )

        # Add GSI for querying by timestamp (optional, for time-range queries)
        risk_scores_table.add_global_secondary_index(
            index_name="timestamp-index",
            partition_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="risk_score",
                type=dynamodb.AttributeType.NUMBER
            )
        )

        # User Alert Rules Table
        alert_rules_table = dynamodb.Table(
            self,
            "AlertRulesTable",
            table_name="user_alert_rules",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="metric",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Add GSI for querying alerts by metric (for alert dispatch)
        alert_rules_table.add_global_secondary_index(
            index_name="metric-index",
            partition_key=dynamodb.Attribute(
                name="metric",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING
            )
        )

        # ========== Lambda Functions ==========

        # Shared Lambda layer for common dependencies (optional optimization)
        # For now, we'll bundle dependencies directly in each Lambda

        # Analysis Lambda (triggered by S3 events)
        analysis_lambda = _lambda.Function(
            self,
            "AnalysisLambda",
            function_name="econ-sentinel-analysis",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("../lambdas/analysis"),
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "RISK_SCORES_TABLE_NAME": risk_scores_table.table_name,
                "ALERT_RULES_TABLE_NAME": alert_rules_table.table_name,
                "RAW_DATA_BUCKET_NAME": raw_data_bucket.bucket_name,
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant permissions
        raw_data_bucket.grant_read(analysis_lambda)
        risk_scores_table.grant_read_write_data(analysis_lambda)
        alert_rules_table.grant_read_data(analysis_lambda)

        # S3 Event Notification to trigger Analysis Lambda
        raw_data_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3_notifications.LambdaDestination(analysis_lambda),
            s3.NotificationKeyFilter(suffix=".json")  # Only trigger on JSON files
        )

        # API Lambda (handles HTTP requests)
        api_lambda = _lambda.Function(
            self,
            "ApiLambda",
            function_name="econ-sentinel-api",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("../lambdas/api"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "RISK_SCORES_TABLE_NAME": risk_scores_table.table_name,
                "ALERT_RULES_TABLE_NAME": alert_rules_table.table_name,
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant permissions
        risk_scores_table.grant_read_data(api_lambda)
        alert_rules_table.grant_read_write_data(api_lambda)

        # ========== API Gateway ==========
        
        # Create REST API
        api = apigateway.RestApi(
            self,
            "EconSentinelApi",
            rest_api_name="Econ Sentinel API",
            description="API for Econ Sentinel dashboard and alert management",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,  # Configure properly in production
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization", "x-user-id"],
            ),
        )

        # Create Lambda integration
        api_lambda_integration = apigateway.LambdaIntegration(
            api_lambda,
            request_templates={"application/json": '{"statusCode": "200"}'},
        )

        # Define API routes
        # GET /scores/latest?metric={metric}
        scores_latest = api.root.add_resource("scores").add_resource("latest")
        scores_latest.add_method("GET", api_lambda_integration)

        # GET /scores?metric={metric}&start={date}&end={date}
        scores = api.root.add_resource("scores")
        scores.add_method("GET", api_lambda_integration)

        # GET /metrics
        metrics = api.root.add_resource("metrics")
        metrics.add_method("GET", api_lambda_integration)

        # GET /alerts
        alerts = api.root.add_resource("alerts")
        alerts.add_method("GET", api_lambda_integration)

        # PUT /alerts
        alerts.add_method("PUT", api_lambda_integration)

        # DELETE /alerts/{metric}
        alert_metric = alerts.add_resource("{metric}")
        alert_metric.add_method("DELETE", api_lambda_integration)

        # OPTIONS for CORS
        for resource in [scores_latest, scores, metrics, alerts, alert_metric]:
            resource.add_method("OPTIONS", api_lambda_integration)

        # ========== Outputs ==========
        CfnOutput(
            self,
            "ApiEndpoint",
            value=api.url,
            description="API Gateway endpoint URL"
        )

        CfnOutput(
            self,
            "RawDataBucketName",
            value=raw_data_bucket.bucket_name,
            description="S3 bucket for raw data storage"
        )

        CfnOutput(
            self,
            "RiskScoresTableName",
            value=risk_scores_table.table_name,
            description="DynamoDB table for risk scores"
        )

        CfnOutput(
            self,
            "AlertRulesTableName",
            value=alert_rules_table.table_name,
            description="DynamoDB table for user alert rules"
        )
