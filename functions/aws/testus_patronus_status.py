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

# Get region from environment variable with multiple fallbacks
REGION = os.environ.get('CLASSROOM_REGION') or os.environ.get('AWS_REGION') or 'eu-west-3'

# Initialize AWS clients with environment-based region
ec2 = boto3.resource('ec2', region_name=REGION)
ec2_client = boto3.client('ec2', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
table = dynamodb.Table(f'instance-assignments-{ENVIRONMENT}')

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
                logger.info(f"Checking Dify service at http://{ip_address}{endpoint}")
                resp = requests.get(f'http://{ip_address}{endpoint}', timeout=1)
                logger.info(f"Response: {resp.status_code}")
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
        
        # Safely get queryStringParameters
        query_params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}
        
        if isinstance(query_params, dict) and 'user_name' in query_params:
            user_name = query_params['user_name']
        elif isinstance(path_params, dict) and 'user_name' in path_params:
            user_name = path_params['user_name']
        
        if not user_name:
            logger.warning("Missing user_name parameter in request")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing user_name parameter'})
            }
        # Query DynamoDB for assignment
        try:
            response = table.query(
                IndexName='student_name-index',
                KeyConditionExpression=Key('student_name').eq(user_name)
            )
        except Exception as query_error:
            logger.error(f"Error querying DynamoDB for user {user_name}: {str(query_error)}")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'ready': False,
                    'reassign_needed': True,
                    'reason': 'dynamodb_error'
                })
            }
        
        if not response['Items']:
            # No assignment found - user needs a new instance
            logger.info(f"No assignment found for {user_name} - reassignment needed")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'ready': False,
                    'reassign_needed': True,
                    'reason': 'no_assignment'
                })
            }
        
        item = response['Items'][0]
        instance_id = item.get('instance_id')
        if not instance_id:
            # Assignment exists but no instance_id - needs reassignment
            logger.warning(f"Assignment found for {user_name} but no instance_id - reassignment needed")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'ready': False,
                    'reassign_needed': True,
                    'reason': 'no_instance_id'
                })
            }
        
        status = item.get('status', 'unknown')
        logger.info(f"Found assignment for {user_name}: {instance_id} with status {status}")

        # Check EC2 instance state
        instance = None
        instance_state = None
        try:
            instance = ec2.Instance(instance_id)
            instance.load()
            instance_state = instance.state['Name']
        except Exception as e:
            logger.error(f"Error loading instance {instance_id}: {str(e)}")
            # Instance might be terminated or not exist - check with describe_instances
            try:
                response = ec2_client.describe_instances(InstanceIds=[instance_id])
                if not response.get('Reservations') or not response['Reservations'][0].get('Instances'):
                    # Instance doesn't exist - clean up and trigger reassignment
                    logger.warning(f"Instance {instance_id} not found - cleaning up and triggering reassignment")
                    try:
                        # Delete the DynamoDB record
                        table.delete_item(Key={'instance_id': instance_id})
                        logger.info(f"Deleted DynamoDB record for missing instance {instance_id}")
                    except Exception as delete_error:
                        logger.error(f"Failed to delete DynamoDB record: {str(delete_error)}")
                    
                    # Return a special flag to indicate reassignment needed
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'ready': False,
                            'reassign_needed': True,
                            'reason': 'instance_not_found'
                        })
                    }
                else:
                    # Instance exists, get its state
                    instance_state = response['Reservations'][0]['Instances'][0]['State']['Name']
                    instance = ec2.Instance(instance_id)
                    instance.load()
            except Exception as describe_error:
                logger.error(f"Error describing instance {instance_id}: {str(describe_error)}")
                # If we can't describe it, assume it's gone
                try:
                    table.delete_item(Key={'instance_id': instance_id})
                    logger.info(f"Deleted DynamoDB record after describe error for {instance_id}")
                except:
                    pass
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'ready': False,
                        'reassign_needed': True,
                        'reason': 'instance_error'
                    })
                }
        
        # Check if instance is terminated
        if instance_state == 'terminated':
            logger.warning(f"Instance {instance_id} is terminated - cleaning up and triggering reassignment")
            try:
                # Delete the DynamoDB record
                table.delete_item(Key={'instance_id': instance_id})
                logger.info(f"Deleted DynamoDB record for terminated instance {instance_id}")
            except Exception as delete_error:
                logger.error(f"Failed to delete DynamoDB record: {str(delete_error)}")
            
            # Return a special flag to indicate reassignment needed
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'ready': False,
                    'reassign_needed': True,
                    'reason': 'instance_terminated'
                })
            }

        # Always check instance state first
        if instance_state != 'running':
            logger.info(f"Instance {instance_id} is not running (state: {instance_state})")
            if instance_state == 'stopped':
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
            elif instance_state in ['terminated', 'shutting-down']:
                # Instance is being terminated - clean up and trigger reassignment
                logger.warning(f"Instance {instance_id} is {instance_state} - cleaning up")
                try:
                    table.delete_item(Key={'instance_id': instance_id})
                    logger.info(f"Deleted DynamoDB record for {instance_state} instance {instance_id}")
                except Exception as delete_error:
                    logger.error(f"Failed to delete DynamoDB record: {str(delete_error)}")
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'ready': False,
                        'reassign_needed': True,
                        'reason': f'instance_{instance_state}'
                    })
                }
            
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