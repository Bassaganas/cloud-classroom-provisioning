"""
Fellowship Status Lambda Function

Checks if a fellowship student's assigned instance is ready for use by:
1. Verifying the EC2 instance is running
2. Checking instance status checks pass
3. Verifying the SUT service is healthy

This follows the same pattern as testus_patronus_status.py but adapted for fellowship.
"""

import boto3
import json
import os
import requests
import logging
import time
from botocore.exceptions import WaiterError, ClientError
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get region from environment variable with multiple fallbacks
REGION = os.environ.get('CLASSROOM_REGION') or os.environ.get('AWS_REGION') or 'eu-west-3'

# Initialize AWS clients with environment-based region
ec2 = boto3.resource('ec2', region_name=REGION)
ec2_client = boto3.client('ec2', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
WORKSHOP_NAME = os.environ.get('WORKSHOP_NAME', 'fellowship')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
table = dynamodb.Table(f'instance-assignments-{WORKSHOP_NAME}-{ENVIRONMENT}')

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
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'UnauthorizedOperation':
            logger.warning(f"UnauthorizedOperation for DescribeInstanceStatus - permission may be missing, skipping status check")
            return None  # Return None to indicate we can't check, but don't fail
        logger.error(f"Error checking instance status: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error checking instance status: {str(e)}")
        return False

def check_sut_service(public_ip, max_retries=2, delay=1):
    """Check if Fellowship SUT service is up with retries"""
    endpoints = ["/api/health", "/"]
    for endpoint in endpoints:
        for attempt in range(max_retries):
            try:
                logger.info(f"Checking Fellowship SUT service at http://{public_ip}{endpoint}")
                resp = requests.get(f'http://{public_ip}{endpoint}', timeout=1)
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
        student_name = None
        
        # Safely get queryStringParameters
        query_params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}
        
        if isinstance(query_params, dict) and 'student_name' in query_params:
            student_name = query_params['student_name']
        elif isinstance(path_params, dict) and 'student_name' in path_params:
            student_name = path_params['student_name']
        
        if not student_name:
            logger.warning("Missing student_name parameter in request")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing student_name parameter'})
            }
        
        # Query DynamoDB for assignment using student_name-index GSI
        try:
            response = table.query(
                IndexName='student_name-index',
                KeyConditionExpression=Key('student_name').eq(student_name)
            )
        except Exception as query_error:
            logger.error(f"Error querying DynamoDB for student {student_name}: {str(query_error)}")
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
            # No assignment found - student needs a new instance
            logger.info(f"No assignment found for {student_name} - reassignment needed")
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
            logger.warning(f"Assignment found for {student_name} but no instance_id - reassignment needed")
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
        # ── NEW: Check provisioning status (must be complete before returning links)
        provisioning_status = item.get('provisioning_status', 'unknown')
        logger.info(f"Found assignment for {student_name}: {instance_id} with status {status}, provisioning_status: {provisioning_status}")

        # If provisioning is not yet complete, return provisioning_in_progress flag
        if provisioning_status not in ['success', 'completed']:
            logger.info(f"Provisioning not complete for {student_name} (status: {provisioning_status})")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'ready': False,
                    'provisioning_in_progress': True,
                    'provisioning_status': provisioning_status,
                    'reason': 'provisioning_in_progress',
                    'message': 'Jenkins folder and Gitea repository are being created. Please wait...'
                })
            }

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

        # Check instance status (may return None if permission is missing)
        status_check_result = check_instance_status(instance_id)
        if status_check_result is False:
            logger.info(f"Instance {instance_id} status checks not passed yet")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False})
            }
        # If status_check_result is None, we couldn't check but continue anyway
        if status_check_result is None:
            logger.info(f"Instance {instance_id} status check unavailable (permission issue), continuing with other checks")

        # Check for public IP
        if not instance.public_ip_address:
            logger.info("Instance does not have a public IP yet.")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ready': False})
            }

        # Check SUT service
        endpoint_ready = check_sut_service(instance.public_ip_address)
        if endpoint_ready in ["/", "/api/health"]:
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
            
            # ─── CHECK PROVISIONING STATUS ────────────────────────────────────────────
            # Only return links (jenkins_url, gitea_url) if provisioning has completed
            provisioning_status = item.get('provisioning_status', 'unknown')
            logger.info(f"Provisioning status for {student_name}: {provisioning_status}")
            
            if provisioning_status not in ['success', 'completed']:
                # Provisioning still in progress or failed; return provisioning_in_progress flag
                logger.info(f"Provisioning not complete for {student_name} (status: {provisioning_status})")
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'ready': False,
                        'provisioning_in_progress': True,
                        'provisioning_status': provisioning_status,
                        'reason': 'provisioning_in_progress',
                        'message': 'Jenkins folder and Git repository are being created. Please wait...'
                    })
                }
            
            # Provisioning complete; return all URLs
            # Get SUT URL from assignment or construct it
            sut_url = item.get('sut_url', f"https://sut-{student_name}.testingfantasy.com")
            jenkins_url = item.get('jenkins_url', f"https://jenkins.fellowship.testingfantasy.com/job/{student_name}/")
            gitea_url = item.get('gitea_url', f"https://gitea.fellowship.testingfantasy.com/fellowship-org/fellowship-sut-{student_name}")
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'ready': True,
                    'ip': instance.public_ip_address,
                    'sut_url': sut_url,
                    'jenkins_url': jenkins_url,
                    'gitea_url': gitea_url,
                    'provisioning_status': provisioning_status
                })
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
                    logger.info(f"Updated status to 'starting' for {instance_id} as SUT service is not ready")
                except Exception as e:
                    logger.error(f"Failed to update status to 'starting' for {instance_id}: {str(e)}")
            logger.info("SUT service is not ready yet")
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
