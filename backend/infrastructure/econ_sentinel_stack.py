"""
AWS CDK Stack

Sets up S3 bucket, 2 DynamoDB tables, 2 Lambda functions,
API Gateway, ECR repo, ECS Fargate cluster, and daily ingestion schedule
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
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_events as events,
    aws_events_targets as events_targets,
    CfnOutput,
)
from constructs import Construct
import os


class EconSentinelStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get S3 bucket name
        raw_data_bucket_name = os.environ.get(
            'RAW_DATA_BUCKET_NAME',
            f'econ-sentinel-raw-{self.account}-{self.region}'
        )

        # S3 Bucket for Raw Data
        raw_data_bucket = s3.Bucket(
            self,
            "RawDataBucket",
            bucket_name=raw_data_bucket_name,
            versioned=False,
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # DynamoDB Tables:

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
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
        )

        # Add global secondary index for querying by timestamp
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

        # Add global secondary index for querying alerts by metric
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

        # Lambda functions:

        # Analysis Lambda
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
                "SES_SENDER_EMAIL": os.environ.get("SES_SENDER_EMAIL", "alerts@econ-sentinel.com"),
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        raw_data_bucket.grant_read(analysis_lambda)
        risk_scores_table.grant_read_write_data(analysis_lambda)
        alert_rules_table.grant_read_data(analysis_lambda)

        # Allow analysis lambda to send SES emails
        analysis_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        # S3 Event Notification to trigger Analysis Lambda
        raw_data_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3_notifications.LambdaDestination(analysis_lambda),
            s3.NotificationKeyFilter(suffix=".json")  # Only trigger on JSON files
        )

        # API Lambda
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

        risk_scores_table.grant_read_data(api_lambda)
        alert_rules_table.grant_read_write_data(api_lambda)

        # API Gateway:

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

        api_lambda_integration = apigateway.LambdaIntegration(
            api_lambda,
            request_templates={"application/json": '{"statusCode": "200"}'},
        )

        # GET /scores/latest?metric={metric}
        # GET /scores?metric={metric}&start={date}&end={date}
        scores = api.root.add_resource("scores")
        scores.add_method("GET", api_lambda_integration)
        scores_latest = scores.add_resource("latest")
        scores_latest.add_method("GET", api_lambda_integration)

        # GET /metrics
        metrics = api.root.add_resource("metrics")
        metrics.add_method("GET", api_lambda_integration)

        # GET/PUT /alerts
        # DELETE /alerts/{metric}
        alerts = api.root.add_resource("alerts")
        alerts.add_method("GET", api_lambda_integration)
        alerts.add_method("PUT", api_lambda_integration)
        alert_metric = alerts.add_resource("{metric}")
        alert_metric.add_method("DELETE", api_lambda_integration)

        # Add options for CORS (security)
        for resource in [scores_latest, scores, metrics, alerts, alert_metric]:
            resource.add_method("OPTIONS", api_lambda_integration)


        # Ingestion Layer: ECR, ECS Fargate, daily schedule

        # ECR repository for ingestion Docker image
        ingestion_repo = ecr.Repository(
            self,
            "IngestionRepository",
            repository_name="econ-sentinel-ingestion",
            removal_policy=RemovalPolicy.RETAIN,
        )

        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)

        cluster = ecs.Cluster(
            self,
            "EconSentinelCluster",
            cluster_name="econ-sentinel",
            vpc=vpc,
        )

        # Set up Fargate task definition for ingestion container
        ingestion_task = ecs.FargateTaskDefinition(
            self,
            "IngestionTaskDef",
            memory_limit_mib=512,
            cpu=256,
        )

        # Give ingestion_task write access to s3 so it can upload data
        raw_data_bucket.grant_write(ingestion_task.task_role)

        ingestion_task.add_container(
            "IngestionContainer",
            image=ecs.ContainerImage.from_ecr_repository(ingestion_repo),
            environment={
                "RAW_DATA_BUCKET_NAME": raw_data_bucket.bucket_name,
                
                # Set FRED_API_KEY as env var before deploying
                "FRED_API_KEY": os.environ.get("FRED_API_KEY", ""),
            },
            logging=ecs.LogDrivers.aws_logs(  # CloudWatch
                stream_prefix="ingestion",
                log_retention=logs.RetentionDays.ONE_WEEK,
            ),
        )

        # EventBridge - creates scheduled event to run ingestion once a day
        daily_schedule = events.Rule(
            self,
            "DailyIngestionRule",
            rule_name="econ-sentinel-daily-ingestion",
            description="Triggers ECS ingestion every day at 6 AM UTC",
            schedule=events.Schedule.cron(hour="6", minute="0"),
        )
        daily_schedule.add_target(
            events_targets.EcsTask(
                cluster=cluster,
                task_definition=ingestion_task,
                launch_type=ecs.LaunchType.FARGATE,
                platform_version=ecs.FargatePlatformVersion.LATEST,
                subnet_selection=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PUBLIC
                ),
                assign_public_ip=True,
            )
        )


        # Print values to terminal after CDK deploy finishes:

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

        CfnOutput(
            self,
            "IngestionRepositoryUri",
            value=ingestion_repo.repository_uri,
            description="ECR URI for the ingestion Docker image"
        )

        CfnOutput(
            self,
            "EcsClusterName",
            value=cluster.cluster_name,
            description="ECS cluster name"
        )
