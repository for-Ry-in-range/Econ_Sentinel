# Econ Sentinel

## Overview

Econ Sentinel combines global economic data with supply chain data to form a macroeconomic monitoring system. Econ Sentinel will help stock investors and business leaders better predict the future of the economy. The system uses a containerized architecture on AWS, automating the detection of "market stress" signals that could cause inventory shortages or price increases. Users can sign in on the Econ Sentinel website to view numerous economic status scores and configure email alerts when critical risks are detected based on real-time economic data analysis.


## Architecture

Econ Sentinel is a four-stage automated pipeline: Ingestion, Storage/Analysis, Alerting, and Frontend.

### 1. The Ingestion Layer (Docker, AWS ECS)

Econ Sentinel uses a containerized worker instead of a script that has to be run manually.

The Tech:
- A Python scraper and an API client packaged into a Docker image
- Stored in AWS ECR
- Ran with AWS ECS (Fargate) once every day

Data Sources:
- FRED API (Federal Reserve) for inflation data
- Port congestion data at major US hubs

### 2. Storage and Data Lake (AWS S3)

Raw Data Storage:
- Every container execution saves raw JSON/CSV output into an S3 bucket

Partitioning:
- Organize data by date

### 3. Analysis and Intelligence Layer (AWS Lambda)

Event-Driven Processing:
- S3 Event Trigger automatically starts an AWS Lambda function when a new data file is uploaded
- Allows for real-time risk detection

Risk Logic:
- Compares the new data with the 30-day moving average
- Example: If the freight cost index increases by more than 15% in one week, the Lambda function will flag this as a critical risk

Database Record:
- The risk score is saved into AWS DynamoDB
- Provides the data for the web dashboard and alert system

### 4. The Frontend and User Interface Layer

This is where users interact with Econ Sentinel and choose their alert preferences.

Website:
- User authentication system for secure account access
- Dashboard displaying economic status scores for different economic measurements
- Real-time visualization of the risk scores stored in DynamoDB

User Features:
- Sign in to account
- View current economic status scores (e.g., freight cost index, port congestion, inflation)
- Choose email alert preferences and thresholds

## Tech Stack

- Containerization: Docker
- Container registry: AWS ECR
- Application hosting: AWS ECS
- Storage: AWS S3
- Serverless functions: AWS Lambda
- Database: AWS DynamoDB
- Backend language: Python
- Frontend languages: JavaScript, HTML, CSS

## Features

- Economic data automatically ingested every day
- Real-time risk detection using moving averages
- User authentication and account management
- Web dashboard displaying economic status scores
- Customizable email alerts for critical economic risks
- Scalable, event-driven architecture