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

def cleanup_route53_record(instance_id: str, tags: Dict) -> None:
    """Clean up Route53 A record for an instance if it exists
    
    Args:
        instance_id: EC2 instance ID
        tags: Instance tags dictionary
    """
    if not HTTPS_HOSTED_ZONE_ID:
        return  # Route53 not configured, skip cleanup
    
    domain_to_delete = tags.get('HttpsDomain')
    if not domain_to_delete:
        return  # No domain configured for this instance
    
    try:
        route53 = boto3.client('route53', region_name=region)
        # Get the current record to ensure exact match for DELETE
        try:
            response = route53.list_resource_record_sets(
                HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                StartRecordName=domain_to_delete,
                StartRecordType='A',
                MaxItems=1
            )
            
            # Find the exact record to delete
            record_to_delete = None
            for record in response.get('ResourceRecordSets', []):
                if record['Name'] == domain_to_delete and record['Type'] == 'A':
                    record_to_delete = record
                    break
            
            if record_to_delete:
                # Delete the Route53 A record with exact match
                route53.change_resource_record_sets(
                    HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                    ChangeBatch={
                        'Changes': [{
                            'Action': 'DELETE',
                            'ResourceRecordSet': record_to_delete
                        }]
                    }
                )
                logger.info(f"Deleted Route53 record: {domain_to_delete} for instance {instance_id}")
            else:
                logger.debug(f"Route53 record {domain_to_delete} not found (may already be deleted)")
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchHostedZone':
                logger.warning(f"Hosted zone {HTTPS_HOSTED_ZONE_ID} not found")
            elif e.response['Error']['Code'] == 'InvalidChangeBatch':
                # Record might not exist or already deleted - this is OK
                logger.debug(f"Route53 record {domain_to_delete} may not exist or already deleted: {str(e)}")
            else:
                logger.warning(f"Failed to delete Route53 record {domain_to_delete} for {instance_id}: {str(e)}")
    except Exception as e:
        logger.warning(f"Error deleting Route53 record for {instance_id}: {str(e)}")

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
        
        # Check if instance is spot and reservation has expired (HIGH PRIORITY)
        if tags.get('PurchaseType') == 'spot':
            spot_end_time_str = tags.get('SpotReservationEndTime')
            if spot_end_time_str:
                try:
                    # Parse ISO 8601 timestamp
                    spot_end_time = datetime.fromisoformat(spot_end_time_str.replace('Z', '+00:00'))
                    # Add 5-minute buffer to account for time sync and processing delays
                    with_buffer = spot_end_time + timedelta(minutes=5)
                    
                    if now > with_buffer:
                        logger.info(f"Spot instance {instance_id}: reservation expired at {spot_end_time}, terminating immediately")
                        try:
                            # Clean up Route53 record before termination
                            cleanup_route53_record(instance_id, tags)
                            
                            # Terminate the spot instance immediately (MUST use terminate, not stop)
                            ec2_client.terminate_instances(InstanceIds=[instance_id])
                            logger.info(f"Terminated spot instance {instance_id} (reservation expired)")
                            
                            # Delete DynamoDB record if it exists
                            try:
                                table.delete_item(Key={'instance_id': instance_id})
                                logger.info(f"Deleted DynamoDB record for spot instance {instance_id}")
                            except Exception as e:
                                logger.warning(f"Failed to delete DynamoDB record for spot instance {instance_id}: {str(e)}")
                            
                            return {'instance_id': instance_id, 'status': 'terminated', 'reason': 'spot_reservation_expired'}
                        except Exception as e:
                            logger.error(f"Failed to terminate spot instance {instance_id}: {str(e)}")
                            return {'instance_id': instance_id, 'status': 'error', 'error': f'Failed to terminate spot instance: {str(e)}'}
                    else:
                        # Still within reservation window, skip from normal lifecycle (DO NOT STOP SPOT INSTANCES)
                        time_remaining = (with_buffer - now).total_seconds() / 60
                        logger.info(f"Spot instance {instance_id} within reservation ({time_remaining:.1f} minutes remaining), skipping normal lifecycle checks")
                        logger.info(f"  ⚠️ CRITICAL: Spot instances CANNOT be stopped, only terminated. Skipping stop lifecycle for {instance_id}")
                        return {'instance_id': instance_id, 'status': 'skipped', 'reason': f'spot_within_reservation ({time_remaining:.1f} min remaining)'}
                except ValueError as e:
                    logger.error(f"Failed to parse SpotReservationEndTime for {instance_id}: {str(e)}")
                    logger.error(f"  ⚠️ CRITICAL: Spot instance {instance_id} has malformed SpotReservationEndTime tag. Will treat as on-demand.")
                    logger.error(f"  ⚠️ RISK: Attempting to stop this instance may fail. Recommend manual review.")
                    # Fall through to normal lifecycle with warning (risky but allows manual intervention)
            else:
                # Spot instance without reservation end time is malformed
                logger.error(f"Spot instance {instance_id} missing SpotReservationEndTime tag")
                logger.error(f"  ⚠️ CRITICAL: Cannot determine when spot reservation expires. Skipping lifecycle to prevent accidental stop.")
                return {'instance_id': instance_id, 'status': 'error', 'reason': 'spot_instance_missing_reservation_tag', 'error': 'SpotReservationEndTime tag not found'}
        
        logger.info(f"Instance {instance_id} launched at {launch_time}, and now is {now}, so it has a remaining time of {now - launch_time}")
        # Check if instance has exceeded hard terminate timeout
        if now - launch_time > timedelta(minutes=HARD_TERMINATE_TIMEOUT_MINUTES):
            logger.info(f"Instance {instance_id} has exceeded hard terminate timeout of {HARD_TERMINATE_TIMEOUT_MINUTES} minutes")
            try:
                # Check if instance is assigned in DynamoDB
                response = table.get_item(Key={'instance_id': instance_id})
                is_assigned = 'Item' in response and 'student_name' in response['Item']
                
                if is_assigned:
                    logger.warning(f"Instance {instance_id} is assigned but has exceeded hard terminate timeout. Forcing termination.")
                    # Notify the student (you could add notification logic here)
                
                # Clean up Route53 record before termination
                cleanup_route53_record(instance_id, tags)
                
                # Terminate the instance regardless of state
                ec2_client.terminate_instances(InstanceIds=[instance_id])
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
            # SAFETY CHECK: Do not stop spot instances - they can only be terminated
            if tags.get('PurchaseType') == 'spot':
                logger.error(f"ERROR: Instance {instance_id} is marked as spot but reached stop logic!")
                logger.error(f"  Spot instances CANNOT be stopped, only terminated.")
                logger.error(f"  Recommendation: Check SpotReservationEndTime tag - should have returned earlier")
                logger.error(f"  Instance will not be stopped. Manual intervention required.")
                return {'instance_id': instance_id, 'status': 'error', 'reason': 'spot_instance_reached_stop_logic', 
                        'error': 'Spot instance should not reach stop logic. Check reservation end time.'}
            
            running_time = (now - launch_time).total_seconds() / 60
            if running_time < STOP_TIMEOUT_MINUTES:
                logger.info(f"Instance {instance_id} has been running for {running_time:.2f} minutes, which is less than STOP_TIMEOUT_MINUTES ({STOP_TIMEOUT_MINUTES}). Skipping stop.")
                return {'instance_id': instance_id, 'status': 'skipped', 'reason': f'running less than stop timeout ({running_time:.2f} < {STOP_TIMEOUT_MINUTES})'}
            logger.info(f"Stopping unassigned running instance {instance_id} (running for {running_time:.2f} minutes, exceeds STOP_TIMEOUT_MINUTES={STOP_TIMEOUT_MINUTES})")
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
                            
                            if now - last_stopped_at > timedelta(minutes=TERMINATE_TIMEOUT_MINUTES):
                                logger.info(f"Terminating stopped instance {instance_id} (stopped for more than {TERMINATE_TIMEOUT_MINUTES} minutes)")
                                try:
                                    # Clean up Route53 record before termination
                                    cleanup_route53_record(instance_id, tags)
                                    
                                    ec2_client.terminate_instances(InstanceIds=[instance_id])
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
                # Clean up Route53 record before termination
                cleanup_route53_record(instance_id, tags)
                
                # Terminate the instance
                ec2_client.terminate_instances(InstanceIds=[instance_id])
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