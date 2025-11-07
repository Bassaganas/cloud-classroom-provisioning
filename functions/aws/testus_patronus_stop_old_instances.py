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
ssm = boto3.client('ssm', region_name=region)
dynamodb = boto3.resource('dynamodb', region_name=region)
environment = os.environ.get('ENVIRONMENT', 'testus-patronus')
table = dynamodb.Table(f'instance-assignments-{environment}')

def get_timeout_parameters():
    """Get timeout parameters from Parameter Store"""
    try:
        parameter_prefix = os.environ.get('PARAMETER_PREFIX', '/classroom/dev')
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
        # Get timeout parameters
        timeouts = get_timeout_parameters()
        STOP_TIMEOUT_MINUTES = timeouts['stop_timeout']
        TERMINATE_TIMEOUT_MINUTES = timeouts['terminate_timeout']
        HARD_TERMINATE_TIMEOUT_MINUTES = timeouts['hard_terminate_timeout']
        
        # Get instance state and launch time
        instance = ec2_client.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
        current_state = instance['State']['Name']
        launch_time = instance['LaunchTime']
        now = datetime.now(timezone.utc)
        
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
                        {'Key': 'Student', 'Value': ''}
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
                                    ec2_client.terminate_instances(InstanceIds=[instance_id])
                                    logger.info(f"Terminating instance {instance_id}")
                                    waiter = ec2_client.get_waiter('instance_terminated')
                                    waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 5, 'MaxAttempts': 12})
                                    ec2_client.create_tags(
                                        Resources=[instance_id],
                                        Tags=[
                                            {'Key': 'Status', 'Value': 'available'},
                                            {'Key': 'Student', 'Value': ''}
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
    environment = os.environ.get('ENVIRONMENT', 'testus-patronus')
    table = dynamodb.Table(f'instance-assignments-{environment}')
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