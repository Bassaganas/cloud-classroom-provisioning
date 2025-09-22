import boto3
import json
import os
import requests
import logging
import time
from botocore.exceptions import WaiterError
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.resource('ec2', region_name='eu-west-1')
ec2_client = boto3.client('ec2', region_name='eu-west-1')
dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
table = dynamodb.Table('instance-assignments-dev')

def check_instance_status(instance_id):
    """Check if instance has passed both system and instance status checks"""
    try:
        response = ec2_client.describe_instance_status(
            InstanceIds=[instance_id],
            IncludeAllInstances=True
        )
        
        if not response['InstanceStatuses']:
            return False
            
        status = response['InstanceStatuses'][0]
        system_status = status['SystemStatus']['Status']
        instance_status = status['InstanceStatus']['Status']
        
        return system_status == 'ok' and instance_status == 'ok'
    except Exception as e:
        logger.error(f"Error checking instance status: {str(e)}")
        return False

def check_dify_service(ip_address, max_retries=2, delay=1):
    """Check if Dify service is up with retries"""
    endpoints = ["/v1/", "/install", "/"]
    for endpoint in endpoints:
        for attempt in range(max_retries):
            try:
                resp = requests.get(f'http://{ip_address}{endpoint}', timeout=1)
                if resp.status_code == 200:
                    return endpoint  # Return the endpoint that is ready
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(delay)
    return None

def lambda_handler(event, context):
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        user_name = None
        if event.get('queryStringParameters') and 'user_name' in event['queryStringParameters']:
            user_name = event['queryStringParameters']['user_name']
        elif event.get('pathParameters') and 'user_name' in event['pathParameters']:
            user_name = event['pathParameters']['user_name']
        if not user_name:
            logger.warning("Missing user_name parameter in request")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing user_name parameter'})
            }
        # Query DynamoDB for assignment
        response = table.query(
            IndexName='student_name-index',
            KeyConditionExpression=Key('student_name').eq(user_name)
        )
        if not response['Items']:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False})
            }
        item = response['Items'][0]
        instance_id = item['instance_id']
        status = item.get('status', 'unknown')
        logger.info(f"Found assignment for {user_name}: {instance_id} with status {status}")

        # Check EC2 instance state
        try:
            instance = ec2.Instance(instance_id)
            instance.load()
        except Exception as e:
            logger.error(f"Error loading instance {instance_id}: {str(e)}")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False})
            }

        # Always check instance state first
        if instance.state['Name'] != 'running':
            logger.info(f"Instance {instance_id} is not running")
            if instance.state['Name'] == 'stopped':
                try:
                    # Start the instance if it's stopped
                    logger.info(f"Starting stopped instance {instance_id}")
                    ec2_client.start_instances(InstanceIds=[instance_id])
                    # Update DynamoDB status
                    table.update_item(
                        Key={'instance_id': instance_id},
                        UpdateExpression='SET #status = :status',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={':status': 'starting'}
                    )
                except Exception as e:
                    logger.error(f"Failed to start instance {instance_id}: {str(e)}")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False, 'reason': 'not_running'})
            }

        # Check instance status
        if not check_instance_status(instance_id):
            logger.info(f"Instance {instance_id} status checks not passed yet")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False})
            }

        # Check for public IP
        if not instance.public_ip_address:
            logger.info("Instance does not have a public IP yet.")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False})
            }

        # Check Dify service
        endpoint_ready = check_dify_service(instance.public_ip_address)
        if endpoint_ready in ["/install", "/", "/v1/"]:
            # Update DynamoDB status to 'ready' if not already
            if status != 'ready':
                try:
                    table.update_item(
                        Key={'instance_id': instance_id},
                        UpdateExpression='SET #status = :ready',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={':ready': 'ready'}
                    )
                    logger.info(f"Updated status to 'ready' for {instance_id}")
                except Exception as e:
                    logger.error(f"Failed to update status to 'ready' for {instance_id}: {str(e)}")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': True, 'ip': instance.public_ip_address})
            }
        else:
            # If instance is not ready but was previously marked as ready, update status
            if status == 'ready':
                try:
                    table.update_item(
                        Key={'instance_id': instance_id},
                        UpdateExpression='SET #status = :starting',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={':starting': 'starting'}
                    )
                    logger.info(f"Updated status to 'starting' for {instance_id} as Dify is not ready")
                except Exception as e:
                    logger.error(f"Failed to update status to 'starting' for {instance_id}: {str(e)}")
            logger.info("Dify service is not ready yet")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False, 'reason': 'service_unavailable'})
            }

    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }