"""AWS Boto3 client initialization and configuration."""
import boto3
import os

# Configuration from environment or defaults
AWS_REGION = os.getenv('AWS_REGION', 'eu-west-3')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

# Initialize AWS clients
ec2_client = boto3.client(
    'ec2',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

route53_client = boto3.client(
    'route53',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

lambda_client = boto3.client(
    'lambda',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

dynamodb_client = boto3.client(
    'dynamodb',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def get_ec2_client():
    """Return EC2 client."""
    return ec2_client

def get_route53_client():
    """Return Route53 client."""
    return route53_client

def get_lambda_client():
    """Return Lambda client."""
    return lambda_client

def get_dynamodb_client():
    """Return DynamoDB client."""
    return dynamodb_client
