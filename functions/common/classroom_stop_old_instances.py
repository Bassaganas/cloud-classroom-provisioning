# Allow patching the route53 client for tests
def get_route53_client():
    return boto3.client('route53', region_name=region)
import boto3
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError, WaiterError
import concurrent.futures
from typing import List, Dict
from boto3.dynamodb.conditions import Attr
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients with region from environment
region = os.environ.get('CLASSROOM_REGION', 'eu-west-3')
WORKSHOP_NAME = os.environ.get('WORKSHOP_NAME', 'classroom')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
HTTPS_BASE_DOMAIN = os.environ.get('INSTANCE_MANAGER_BASE_DOMAIN', '')
HTTPS_HOSTED_ZONE_ID = os.environ.get('INSTANCE_MANAGER_HOSTED_ZONE_ID', '')
ssm = boto3.client('ssm', region_name=region)
dynamodb = boto3.resource('dynamodb', region_name=region)
table = dynamodb.Table(f'instance-assignments-{WORKSHOP_NAME}-{ENVIRONMENT}')

def get_timeout_parameters():
    """Get timeout parameters from Parameter Store"""
    try:
        parameter_prefix = os.environ.get('PARAMETER_PREFIX', f'/classroom/{WORKSHOP_NAME}/{ENVIRONMENT}')
        response = ssm.get_parameters(
            Names=[
                f"{parameter_prefix}/instance_stop_timeout_minutes",
                f"{parameter_prefix}/instance_terminate_timeout_minutes",
                f"{parameter_prefix}/instance_hard_terminate_timeout_minutes"
            ]
        )
        
        # Create a dictionary of parameters
        parameters = {param['Name'].split('/')[-1]: int(param['Value']) for param in response['Parameters']}
        
        # Set default values if any parameter is missing
        logger.info(f"Parameters: {parameters}")
        return {
            'stop_timeout': parameters.get('instance_stop_timeout_minutes', 10),
            'terminate_timeout': parameters.get('instance_terminate_timeout_minutes', 60),
            'hard_terminate_timeout': parameters.get('instance_hard_terminate_timeout_minutes', 240)
        }
    except Exception as e:
        logger.error(f"Error getting timeout parameters: {str(e)}")
        # Return default values if there's an error
        return {
            'stop_timeout': 10,
            'terminate_timeout': 60,
            'hard_terminate_timeout': 240
        }

def terminate_instance_properly(instance_id: str, ec2_client, instance_details: Dict = None) -> bool:
    """
    Properly terminate an instance, handling spot instances by canceling their spot requests first.
    
    For spot instances with 'persistent' type, terminating without canceling the spot request
    causes AWS to automatically launch replacement instances. This function:
    1. Cancels spot requests for spot instances (with TerminateInstances=True)
    2. Falls back to regular termination if spot request cancellation fails or instance is on-demand
    
    Args:
        instance_id: The EC2 instance ID to terminate
        ec2_client: The boto3 EC2 client
        instance_details: Optional cached instance details to avoid redundant API calls
    
    Returns:
        bool: True if termination was successful, False otherwise
    """
    try:
        # Get instance details if not provided
        if instance_details is None:
            response = ec2_client.describe_instances(InstanceIds=[instance_id])
            if not response['Reservations']:
                logger.warning(f"Instance {instance_id} not found for termination")
                return False
            instance_details = response['Reservations'][0]['Instances'][0]
        
        lifecycle = instance_details.get('InstanceLifecycle', 'on-demand')
        is_spot = lifecycle == 'spot'
        
        # For spot instances, cancel the spot request with TerminateInstances=True
        # This properly cleans up both the instance and prevents AWS from auto-launching replacements
        if is_spot:
            spot_request_id = instance_details.get('SpotInstanceRequestId')
            if spot_request_id:
                logger.info(f"Terminating spot instance {instance_id} by canceling spot request {spot_request_id}")
                try:
                    ec2_client.cancel_spot_instance_requests(
                        SpotInstanceRequestIds=[spot_request_id]
                    )
                    logger.info(f"Successfully canceled spot request {spot_request_id} for instance {instance_id}")
                except ClientError as e:
                    error_code = e.response['Error'].get('Code', 'Unknown')
                    if error_code == 'InvalidSpotInstanceRequestID.NotFound':
                        logger.warning(f"Spot request {spot_request_id} not found (may already be canceled), falling back to instance termination")
                    else:
                        logger.warning(f"Error canceling spot request {spot_request_id}: {str(e)}, falling back to instance termination")
                    # Fall through to regular termination
            else:
                logger.warning(f"Spot instance {instance_id} has no SpotInstanceRequestId, falling back to regular termination")
        
        # Regular termination for on-demand or as fallback for spot instances
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        logger.info(f"Terminated {'spot' if is_spot else 'on-demand'} instance {instance_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error terminating instance {instance_id}: {str(e)}")
        return False

def _normalize_record_name(record_name: str) -> str:
    if not record_name:
        return ''
    return record_name if record_name.endswith('.') else f"{record_name}."


def cleanup_route53_record(instance_id: str, tags: Dict, strict: bool = True, max_retries: int = 3, route53_client=None) -> Dict:
    """Clean up Route53 A record for an instance.

    Returns:
        dict: {success, deleted, skipped, reason, attempts}
    """
    if not HTTPS_HOSTED_ZONE_ID:
        return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'hosted-zone-not-configured', 'attempts': 0}

    domain_to_delete = tags.get('HttpsDomain')
    if not domain_to_delete:
        return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'no-domain', 'attempts': 0}

    route53 = route53_client if route53_client is not None else get_route53_client()
    normalized_domain = _normalize_record_name(domain_to_delete)

    for attempt in range(1, max_retries + 1):
        try:
            # BUGFIX: Use normalized domain (with trailing dot) for Route53 lookup
            response = route53.list_resource_record_sets(
                HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                StartRecordName=normalized_domain,
                StartRecordType='A',
                MaxItems='10'
            )

            record_to_delete = None
            for record in response.get('ResourceRecordSets', []):
                if record.get('Type') == 'A' and _normalize_record_name(record.get('Name')) == normalized_domain:
                    record_to_delete = record
                    break

            if not record_to_delete:
                logger.info(f"Route53 record {domain_to_delete} not found (already deleted)")
                return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'already-deleted', 'attempts': attempt}

            # BUGFIX: Construct ResourceRecordSet with only necessary fields for deletion
            delete_record_set = {
                'Name': record_to_delete['Name'],
                'Type': record_to_delete['Type']
            }
            # Include TTL if present (required for non-alias records)
            if 'TTL' in record_to_delete:
                delete_record_set['TTL'] = record_to_delete['TTL']
            # Include ResourceRecords if present (required for non-alias records)
            if 'ResourceRecords' in record_to_delete:
                delete_record_set['ResourceRecords'] = record_to_delete['ResourceRecords']
            
            route53.change_resource_record_sets(
                HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': delete_record_set
                    }]
                }
            )
            logger.info(f"Deleted Route53 record: {domain_to_delete} for instance {instance_id}")
            return {'success': True, 'deleted': True, 'skipped': False, 'reason': 'deleted', 'attempts': attempt}
        except ClientError as e:
            code = e.response['Error'].get('Code', 'Unknown')
            if code == 'InvalidChangeBatch':
                logger.info(f"Route53 record {domain_to_delete} already absent")
                return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'already-deleted', 'attempts': attempt}
            if code == 'NoSuchHostedZone':
                logger.error(f"Hosted zone {HTTPS_HOSTED_ZONE_ID} not found")
                return {'success': not strict, 'deleted': False, 'skipped': False, 'reason': 'hosted-zone-missing', 'attempts': attempt, 'error': str(e)}

            logger.warning(f"Route53 delete attempt {attempt}/{max_retries} failed for {domain_to_delete}: {str(e)}")
            if attempt < max_retries:
                time.sleep(attempt)
            else:
                return {'success': not strict, 'deleted': False, 'skipped': False, 'reason': 'delete-failed', 'attempts': attempt, 'error': str(e)}
        except Exception as e:
            logger.warning(f"Route53 delete unexpected error attempt {attempt}/{max_retries} for {domain_to_delete}: {str(e)}")
            if attempt < max_retries:
                time.sleep(attempt)
            else:
                return {'success': not strict, 'deleted': False, 'skipped': False, 'reason': 'delete-failed', 'attempts': attempt, 'error': str(e)}

    return {'success': not strict, 'deleted': False, 'skipped': False, 'reason': 'delete-failed', 'attempts': max_retries}

def wait_for_command(ssm_client, command_id: str, instance_id: str, timeout: int = 60) -> Dict:
    """Wait for an SSM command to complete with timeout"""
    start_time = time.time()
    
    # Add initial delay to allow command to be registered
    time.sleep(2)
    
    while time.time() - start_time < timeout:
        try:
            output = ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id
            )
            if output['Status'] in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
                return output
            time.sleep(2)
        except ssm_client.exceptions.InvocationDoesNotExist:
            # Command might not be registered yet, wait and retry
            time.sleep(2)
            continue
        except Exception as e:
            logger.error(f"Error checking command status: {str(e)}")
            raise
    
    raise TimeoutError(f"Command {command_id} timed out after {timeout} seconds")

def process_instance(instance_id, ec2_client, ssm_client, table):
    """Process a single instance based on its state and assignment status"""
    try:
        # Get instance state and launch time first (need tags from instance)
        instance = ec2_client.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        
        # Get SSM default timeout parameters (fallback if instance tags not set)
        ssm_defaults = get_timeout_parameters()
        
        # Check instance tags first, then fall back to SSM defaults
        STOP_TIMEOUT_MINUTES = int(tags.get('StopTimeout')) if tags.get('StopTimeout') else ssm_defaults['stop_timeout']
        TERMINATE_TIMEOUT_MINUTES = int(tags.get('TerminateTimeout')) if tags.get('TerminateTimeout') else ssm_defaults['terminate_timeout']
        HARD_TERMINATE_TIMEOUT_MINUTES = int(tags.get('HardTerminateTimeout')) if tags.get('HardTerminateTimeout') else ssm_defaults['hard_terminate_timeout']
        
        timeout_source = 'tags' if tags.get('StopTimeout') else 'SSM defaults'
        logger.info(f"Instance {instance_id} timeouts - Stop: {STOP_TIMEOUT_MINUTES}min, Terminate: {TERMINATE_TIMEOUT_MINUTES}min, Hard: {HARD_TERMINATE_TIMEOUT_MINUTES}min (from {timeout_source})")
        
        current_state = instance['State']['Name']
        launch_time = instance['LaunchTime']
        now = datetime.now(timezone.utc)
        
        logger.info(f"Instance {instance_id} launched at {launch_time}, and now is {now}, so it has a remaining time of {now - launch_time}")
        # Check if instance has exceeded hard terminate timeout
        is_spot = instance.get('InstanceLifecycle') == 'spot'
        logger.info(f"Instance {instance_id} lifecycle: {'spot' if is_spot else 'on-demand'}")
        if now - launch_time > timedelta(minutes=HARD_TERMINATE_TIMEOUT_MINUTES):
            logger.info(f"Instance {instance_id} has exceeded hard terminate timeout of {HARD_TERMINATE_TIMEOUT_MINUTES} minutes")
            try:
                # Check if instance is assigned in DynamoDB
                response = table.get_item(Key={'instance_id': instance_id})
                is_assigned = 'Item' in response and 'student_name' in response['Item']
                
                if is_assigned:
                    logger.warning(f"Instance {instance_id} is assigned but has exceeded hard terminate timeout. Forcing termination.")
                    # Notify the student (you could add notification logic here)
                
                    # BUGFIX: Non-blocking Route53 cleanup - don't block hard termination
                    dns_cleanup = cleanup_route53_record(instance_id, tags, strict=False)
                    if not dns_cleanup.get('success'):
                        logger.warning(f"Route53 cleanup incomplete for hard termination of {instance_id}: {dns_cleanup}")

                    # Terminate the instance regardless of state and Route53 cleanup outcome
                terminate_instance_properly(instance_id, ec2_client, instance)
                logger.info(f"Hard terminating instance {instance_id}")
                waiter = ec2_client.get_waiter('instance_terminated')
                waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 5, 'MaxAttempts': 12})
                
                # Reset tags
                ec2_client.create_tags(
                    Resources=[instance_id],
                    Tags=[
                        {'Key': 'Status', 'Value': 'available'},
                        {'Key': 'Student', 'Value': ''},
                        {'Key': 'Company', 'Value': 'TestingFantasy'}
                    ]
                )
                
                # Delete DynamoDB record if it exists
                try:
                    table.delete_item(Key={'instance_id': instance_id})
                    logger.info(f"Deleted DynamoDB record for instance {instance_id}")
                except Exception as e:
                    logger.error(f"Failed to delete DynamoDB record for instance {instance_id}: {str(e)}")
                
                return {'instance_id': instance_id, 'status': 'hard_terminated', 'reason': 'exceeded hard terminate timeout'}
                
            except Exception as e:
                logger.error(f"Failed to hard terminate instance {instance_id}: {str(e)}")
                return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}
        
        # Check if instance is assigned in DynamoDB
        try:
            response = table.get_item(Key={'instance_id': instance_id})
            is_assigned = 'Item' in response
        except Exception as e:
            logger.error(f"Error checking DynamoDB for instance {instance_id}: {str(e)}")
            return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}
        
        # Case 1: Running instance without assignment
        if current_state == 'running' and not is_assigned:
            running_time = (now - launch_time).total_seconds() / 60
            if running_time < STOP_TIMEOUT_MINUTES:
                logger.info(f"Instance {instance_id} has been running for {running_time:.2f} minutes, which is less than STOP_TIMEOUT_MINUTES ({STOP_TIMEOUT_MINUTES}). Skipping stop.")
                return {'instance_id': instance_id, 'status': 'skipped', 'reason': f'running less than stop timeout ({running_time:.2f} < {STOP_TIMEOUT_MINUTES})'}
            logger.info(f"Stopping unassigned running instance {instance_id} (running for {running_time:.2f} minutes, exceeds STOP_TIMEOUT_MINUTES={STOP_TIMEOUT_MINUTES})")
            # For spot instances, terminate immediately instead of stopping
            # Spot instances should be terminated when they exceed stop timeout, not stopped
            if is_spot:
                logger.info(f"Terminating spot instance {instance_id} (exceeds STOP_TIMEOUT_MINUTES={STOP_TIMEOUT_MINUTES})")
                try:
                    # BUGFIX: Non-blocking Route53 cleanup - don't block instance termination
                    dns_cleanup = cleanup_route53_record(instance_id, tags, strict=False)
                    if not dns_cleanup.get('success'):
                        logger.warning(f"Route53 cleanup incomplete for spot instance {instance_id}: {dns_cleanup}")

                    # Properly terminate spot instance by canceling spot request first
                    terminate_instance_properly(instance_id, ec2_client, instance)
                    logger.info(f"Initiated termination for spot instance {instance_id}")
                    
                    # Delete DynamoDB record if it exists
                    try:
                        table.delete_item(Key={'instance_id': instance_id})
                        logger.info(f"Deleted DynamoDB record for instance {instance_id}")
                    except Exception as e:
                        logger.warning(f"Failed to delete DynamoDB record for instance {instance_id}: {str(e)}")
                    
                    return {'instance_id': instance_id, 'status': 'terminated', 'reason': 'spot instance exceeded stop timeout'}
                except Exception as e:
                    logger.error(f"Failed to terminate spot instance {instance_id}: {str(e)}")
                    return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}
            
            # For on-demand instances, stop them or cleanup before stopping
            try:
                # Run cleanup commands before stopping
                try:
                    # First check if SSM agent is running
                    try:
                        ssm_client.describe_instance_information(
                            Filters=[{'Key': 'InstanceIds', 'Values': [instance_id]}]
                        )
                    except ClientError as e:
                        logger.warning(f"SSM agent not available for instance {instance_id}: {str(e)}")
                        raise Exception("SSM agent not available")

                    # Check if Docker is running
                    docker_check_cmd = "systemctl is-active docker"
                    response = ssm_client.send_command(
                        InstanceIds=[instance_id],
                        DocumentName="AWS-RunShellScript",
                        Parameters={'commands': [docker_check_cmd]}
                    )
                    command_id = response['Command']['CommandId']
                    time.sleep(2)
                    output = ssm_client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
                    if output['Status'] != 'Success' or output['StandardOutputContent'].strip() != 'active':
                        logger.warning(f"Docker not running on instance {instance_id}")
                        raise Exception("Docker not running")

                    # Find Redis container
                    redis_cmd = "docker ps --filter 'name=redis' --format '{{.Names}}'"
                    response = ssm_client.send_command(
                        InstanceIds=[instance_id],
                        DocumentName="AWS-RunShellScript",
                        Parameters={'commands': [redis_cmd]}
                    )
                    command_id = response['Command']['CommandId']
                    time.sleep(2)
                    output = ssm_client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
                    
                    if output['Status'] != 'Success':
                        logger.warning(f"Error finding Redis container for instance {instance_id}: {output['StandardErrorContent']}")
                        raise Exception(f"Failed to find Redis container: {output['StandardErrorContent']}")
                        
                    redis_container = output['StandardOutputContent'].strip()
                    if not redis_container:
                        logger.warning(f"No Redis container found for instance {instance_id}")
                        raise Exception("No Redis container found")

                    # Run cleanup commands
                    cleanup_cmd = f"""
                    docker exec docker-api-1 flask reset-password
                    docker exec {redis_container} redis-cli FLUSHALL
                    """
                    response = ssm_client.send_command(
                        InstanceIds=[instance_id],
                        DocumentName="AWS-RunShellScript",
                        Parameters={'commands': [cleanup_cmd]}
                    )
                    command_id = response['Command']['CommandId']
                    time.sleep(2)
                    output = ssm_client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
                    
                    if output['Status'] != 'Success':
                        logger.warning(f"Cleanup failed for instance {instance_id}: {output['StandardErrorContent']}")
                        raise Exception(f"Cleanup failed: {output['StandardErrorContent']}")
                        
                    logger.info(f"Cleanup successful for instance {instance_id}: {output['StandardOutputContent']}")
                    
                except Exception as e:
                    logger.warning(f"Cleanup failed for instance {instance_id}: {str(e)}")
                    # Continue with instance stop even if cleanup fails
                
                # Stop the instance
                ec2_client.stop_instances(InstanceIds=[instance_id])
                logger.info(f"Stopping instance {instance_id}")
                
                # Update DynamoDB with stop time
                try:
                    # Check if there's an existing record
                    existing_record = table.get_item(Key={'instance_id': instance_id})
                    if 'Item' in existing_record:
                        # Update existing record
                        table.update_item(
                            Key={'instance_id': instance_id},
                            UpdateExpression='SET #status = :status, last_stopped_at = :time',
                            ExpressionAttributeNames={'#status': 'status'},
                            ExpressionAttributeValues={
                                ':status': 'stopped',
                                ':time': datetime.now(timezone.utc).isoformat()
                            },
                            ConditionExpression='attribute_not_exists(student_name)'
                        )
                    else:
                        # Create new record
                        table.put_item(
                            Item={
                                'instance_id': instance_id,
                                'last_stopped_at': datetime.now(timezone.utc).isoformat(),
                                'status': 'stopped'
                            }
                        )
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                        logger.info(f"Instance {instance_id} was assigned while we were stopping it")
                        return {'instance_id': instance_id, 'status': 'skipped', 'reason': 'instance was assigned'}
                    else:
                        raise
                
                return {'instance_id': instance_id, 'status': 'stopped'}
                
            except Exception as e:
                logger.error(f"Failed to stop instance {instance_id}: {str(e)}")
                return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}
        
        # Case 2: Stopped instance
        elif current_state == 'stopped':
            # Get the last stopped time from DynamoDB
            try:
                response = table.get_item(Key={'instance_id': instance_id})
                if 'Item' in response:
                    # Only proceed if the instance is not assigned to a student
                    if 'student_name' not in response['Item']:
                        if 'last_stopped_at' in response['Item']:
                            last_stopped_at = datetime.fromisoformat(response['Item']['last_stopped_at']).replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                            # For spot instances, use a shorter threshold to avoid lingering costs.
                            # For on-demand instances, use configured terminate timeout.
                            terminate_threshold = timedelta(
                                minutes=(max(5, STOP_TIMEOUT_MINUTES) if is_spot else TERMINATE_TIMEOUT_MINUTES)
                            )

                            if now - last_stopped_at > terminate_threshold:
                                logger.info(
                                    f"Terminating stopped instance {instance_id} "
                                    f"(stopped for more than {terminate_threshold.total_seconds() / 60:.0f} minutes)"
                                )
                                try:
                                    # BUG FIX: Non-blocking Route53 cleanup - don't block instance termination
                                    dns_cleanup = cleanup_route53_record(instance_id, tags, strict=False)
                                    if not dns_cleanup.get('success'):
                                        logger.warning(f"Route53 cleanup incomplete for stopped instance {instance_id}: {dns_cleanup}")

                                    # Properly terminate by handling spot instances
                                    terminate_instance_properly(instance_id, ec2_client, instance)
                                    logger.info(f"Terminating instance {instance_id}")
                                    waiter = ec2_client.get_waiter('instance_terminated')
                                    waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 5, 'MaxAttempts': 12})
                                    ec2_client.create_tags(
                                        Resources=[instance_id],
                                        Tags=[
                                            {'Key': 'Status', 'Value': 'available'},
                                            {'Key': 'Student', 'Value': ''},
                                            {'Key': 'Company', 'Value': 'TestingFantasy'}
                                        ]
                                    )
                                    logger.info(f"Tags reset for instance {instance_id}")
                                    logger.info(f"Instance {instance_id} terminated")
                                    
                                    # Delete DynamoDB record
                                    try:
                                        table.delete_item(Key={'instance_id': instance_id})
                                        logger.info(f"Deleted DynamoDB record for instance {instance_id}")
                                    except Exception as e:
                                        logger.error(f"Failed to delete DynamoDB record for instance {instance_id}: {str(e)}")
                                        
                                    return {'instance_id': instance_id, 'status': 'terminated'}
                                    
                                except Exception as e:
                                    logger.error(f"Failed to terminate instance {instance_id}: {str(e)}")
                                    return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}
                    else:
                        logger.info(f"Skipping instance {instance_id} as it is assigned to a student")
                        return {'instance_id': instance_id, 'status': 'skipped', 'reason': 'assigned to student'}
                else:
                    # If no record exists, create one
                    table.put_item(
                        Item={
                            'instance_id': instance_id,
                            'last_stopped_at': datetime.now(timezone.utc).isoformat(),
                            'status': 'stopped'
                        }
                    )
                    logger.info(f"Created stop time record for instance {instance_id}")
                    return {'instance_id': instance_id, 'status': 'skipped', 'reason': 'created stop time record'}
                    
            except Exception as e:
                logger.error(f"Error processing stopped instance {instance_id}: {str(e)}")
                return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}
        
        else:
            logger.info(f"Skipping instance {instance_id} (state: {current_state}, assigned: {is_assigned})")
            return {'instance_id': instance_id, 'status': 'skipped', 'reason': 'no action needed'}
            
    except Exception as e:
        logger.error(f"Unexpected error processing instance {instance_id}: {str(e)}")
        return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}

def process_admin_instance(instance_id, ec2_client, table):
    """Process an admin instance - delete if expired based on CleanupDays tag"""
    try:
        # Get instance details
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        if not response.get('Reservations') or not response['Reservations'][0].get('Instances'):
            return {'instance_id': instance_id, 'status': 'error', 'error': 'Instance not found'}
        
        instance = response['Reservations'][0]['Instances'][0]
        launch_time = instance['LaunchTime']
        now = datetime.now(timezone.utc)
        
        # Get tags
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        instance_type = tags.get('Type', 'unknown')
        
        # Only process admin instances
        if instance_type != 'admin':
            return {'instance_id': instance_id, 'status': 'skipped', 'reason': 'not an admin instance'}
        
        # Get cleanup days from tag (default to 7 if not set)
        cleanup_days = int(tags.get('CleanupDays', '7'))
        age_days = (now - launch_time).days
        
        logger.info(f"Admin instance {instance_id}: age={age_days} days, cleanup_days={cleanup_days}")
        
        # Check if instance has expired
        if age_days >= cleanup_days:
            logger.info(f"Admin instance {instance_id} has expired (age={age_days} >= cleanup_days={cleanup_days}). Deleting...")
            try:
                # BUG FIX: Non-blocking Route53 cleanup - don't block admin instance deletion
                dns_cleanup = cleanup_route53_record(instance_id, tags, strict=False)
                if not dns_cleanup.get('success'):
                    logger.warning(f"Route53 cleanup incomplete for expired admin instance {instance_id}: {dns_cleanup}")

                # Properly terminate by handling spot instances
                terminate_instance_properly(instance_id, ec2_client, instance)
                logger.info(f"Terminated expired admin instance {instance_id}")
                
                # Wait for termination (with timeout)
                try:
                    waiter = ec2_client.get_waiter('instance_terminated')
                    waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 5, 'MaxAttempts': 12})
                except WaiterError:
                    logger.warning(f"Timeout waiting for instance {instance_id} to terminate, but termination was initiated")
                
                # Clean up any DynamoDB records (though admin instances shouldn't have assignments)
                try:
                    table.delete_item(Key={'instance_id': instance_id})
                    logger.info(f"Deleted DynamoDB record for admin instance {instance_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete DynamoDB record for admin instance {instance_id}: {str(e)}")
                
                return {
                    'instance_id': instance_id,
                    'status': 'deleted',
                    'reason': f'expired (age={age_days} days >= cleanup_days={cleanup_days})'
                }
            except Exception as e:
                logger.error(f"Failed to delete expired admin instance {instance_id}: {str(e)}")
                return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}
        else:
            days_remaining = cleanup_days - age_days
            logger.info(f"Admin instance {instance_id} has {days_remaining} days remaining")
            return {
                'instance_id': instance_id,
                'status': 'skipped',
                'reason': f'not expired (age={age_days} days < cleanup_days={cleanup_days}, {days_remaining} days remaining)'
            }
    except Exception as e:
        logger.error(f"Error processing admin instance {instance_id}: {str(e)}")
        return {'instance_id': instance_id, 'status': 'error', 'error': str(e)}

def lambda_handler(event, context):
    """
    Lambda handler for managing instance lifecycle.
    - Processes pool instances (Type: pool): stops unassigned running instances, terminates stopped instances
    - Processes admin instances (Type: admin): deletes expired instances based on CleanupDays tag
    """
    region = os.environ.get('CLASSROOM_REGION', 'eu-west-3')
    ec2_client = boto3.client('ec2', region_name=region)
    ssm_client = boto3.client('ssm', region_name=region)
    dynamodb = boto3.resource('dynamodb', region_name=region)
    workshop_name = os.environ.get('WORKSHOP_NAME', 'classroom')
    environment = os.environ.get('ENVIRONMENT', 'dev')
    table = dynamodb.Table(f'instance-assignments-{workshop_name}-{environment}')
    try:
        # Get all pool instances
        pool_response = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Project', 'Values': ['classroom']},
                {'Name': 'tag:Type', 'Values': ['pool']},
                {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
            ]
        )
        
        pool_instance_ids = []
        for reservation in pool_response['Reservations']:
            for instance in reservation['Instances']:
                pool_instance_ids.append(instance['InstanceId'])
        
        # Get all admin instances
        admin_response = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Project', 'Values': ['classroom']},
                {'Name': 'tag:Type', 'Values': ['admin']},
                {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
            ]
        )
        
        admin_instance_ids = []
        for reservation in admin_response['Reservations']:
            for instance in reservation['Instances']:
                admin_instance_ids.append(instance['InstanceId'])
        
        if not pool_instance_ids and not admin_instance_ids:
            logger.info("No instances to process")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No instances to process'})
            }
            
        results = []
        
        # Process pool instances
        if pool_instance_ids:
            logger.info(f"Found {len(pool_instance_ids)} pool instances to process")
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_instance = {
                    executor.submit(process_instance, instance_id, ec2_client, ssm_client, table): instance_id
                    for instance_id in pool_instance_ids
                }
                for future in concurrent.futures.as_completed(future_to_instance):
                    instance_id = future_to_instance[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing pool instance {instance_id}: {str(e)}")
                        results.append({'instance_id': instance_id, 'status': 'error', 'error': str(e)})
        
        # Process admin instances
        if admin_instance_ids:
            logger.info(f"Found {len(admin_instance_ids)} admin instances to process")
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_instance = {
                    executor.submit(process_admin_instance, instance_id, ec2_client, table): instance_id
                    for instance_id in admin_instance_ids
                }
                for future in concurrent.futures.as_completed(future_to_instance):
                    instance_id = future_to_instance[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing admin instance {instance_id}: {str(e)}")
                        results.append({'instance_id': instance_id, 'status': 'error', 'error': str(e)})
                    
        successful = sum(1 for r in results if r['status'] in ['stopped', 'terminated', 'hard_terminated', 'deleted'])
        failed = len(results) - successful
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(results)} instances',
                'successful': successful,
                'failed': failed,
                'results': results
            })
        }
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        } 