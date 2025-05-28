import boto3
import json
import os
import requests  # Make sure this is packaged with your Lambda
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.resource('ec2', region_name='eu-west-3')

def lambda_handler(event, context):
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        # For Lambda Function URL, get user_name from query string
        user_name = None
        if event.get('queryStringParameters') and 'user_name' in event['queryStringParameters']:
            user_name = event['queryStringParameters']['user_name']
        # Optionally, fallback to pathParameters for API Gateway compatibility
        elif event.get('pathParameters') and 'user_name' in event['pathParameters']:
            user_name = event['pathParameters']['user_name']

        if not user_name:
            logger.warning("Missing user_name parameter in request")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing user_name parameter'})
            }

        filters = [
            {'Name': 'tag:Student', 'Values': [user_name]},
            {'Name': 'tag:Status', 'Values': ['assigned']},
            {'Name': 'instance-state-name', 'Values': ['pending', 'running']}
        ]
        logger.info(f"Using filters: {filters}")

        instances = list(ec2.instances.filter(Filters=filters))
        logger.info(f"Found {len(instances)} instances for user {user_name}")
        if not instances:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False})
            }

        instance = instances[0]
        instance.reload()
        logger.info(f"Instance {instance.id} public IP: {instance.public_ip_address}")

        if instance.public_ip_address:
            # Check if the Dify service is up
            try:
                resp = requests.get(f'http://{instance.public_ip_address}/v1/', timeout=2)
                logger.info(f"Checked Dify endpoint, status code: {resp.status_code}")
                if resp.status_code == 200:
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'ready': True,
                            'ip': instance.public_ip_address
                        })
                    }
                else:
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({'ready': False})
                    }
            except Exception as e:
                logger.error(f"Error checking Dify endpoint: {str(e)}")
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'ready': False})
                }
        else:
            logger.info("Instance does not have a public IP yet.")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False})
            }

    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }