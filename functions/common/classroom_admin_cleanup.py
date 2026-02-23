import boto3
import json
import logging
from datetime import datetime, timezone
from botocore.exceptions import ClientError
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients with region from environment
region = os.environ.get('CLASSROOM_REGION', 'eu-west-3')
ec2_client = boto3.client('ec2', region_name=region)
environment = os.environ.get('ENVIRONMENT', 'dev')
HTTPS_BASE_DOMAIN = os.environ.get('INSTANCE_MANAGER_BASE_DOMAIN', '')
HTTPS_HOSTED_ZONE_ID = os.environ.get('INSTANCE_MANAGER_HOSTED_ZONE_ID', '')

def lambda_handler(event, context):
    """
    Lambda function to clean up admin instances based on age.
    Admin instances are deleted periodically (weekly or monthly) based on configuration.
    """
    try:
        # Get cleanup configuration from environment variables
        # ADMIN_CLEANUP_INTERVAL_DAYS: Number of days after which admin instances should be deleted
        # Default: 7 days (weekly) if not specified
        cleanup_interval_days = int(os.environ.get('ADMIN_CLEANUP_INTERVAL_DAYS', '7'))
        
        logger.info(f"Starting admin instance cleanup. Interval: {cleanup_interval_days} days")
        
        # Get all admin instances (both running and stopped)
        response = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Project', 'Values': ['classroom']},
                {'Name': 'tag:Type', 'Values': ['admin']},
                {'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'pending', 'stopping']}
            ]
        )
        
        instance_ids = []
        instances_to_delete = []
        now = datetime.now(timezone.utc)
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                launch_time = instance['LaunchTime']
                
                # Calculate age of instance
                age_days = (now - launch_time).days
                
                # Get tags
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                instance_name = tags.get('Name', instance_id)
                
                # Get cleanup days from tag (per-instance setting, fallback to environment variable)
                instance_cleanup_days = int(tags.get('CleanupDays', str(cleanup_interval_days)))
                
                logger.info(f"Admin instance {instance_id} ({instance_name}): age={age_days} days, cleanup_days={instance_cleanup_days}, state={instance['State']['Name']}")
                
                # Check if instance is older than its cleanup interval
                if age_days >= instance_cleanup_days:
                    instances_to_delete.append({
                        'instance_id': instance_id,
                        'name': instance_name,
                        'age_days': age_days,
                        'cleanup_days': instance_cleanup_days,
                        'state': instance['State']['Name'],
                        'launch_time': launch_time.isoformat()
                    })
                    instance_ids.append(instance_id)
        
        if not instance_ids:
            logger.info("No admin instances found that need cleanup")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No admin instances to clean up',
                    'cleanup_interval_days': cleanup_interval_days
                })
            }
        
        logger.info(f"Found {len(instance_ids)} admin instance(s) to delete (age >= {cleanup_interval_days} days)")
        
        deleted = []
        errors = []
        
        # Delete each admin instance
        for instance_info in instances_to_delete:
            instance_id = instance_info['instance_id']
            try:
                # Get instance tags to retrieve domain information for Route53 cleanup
                instance_tags = {}
                try:
                    instance_response = ec2_client.describe_instances(InstanceIds=[instance_id])
                    if instance_response.get('Reservations') and instance_response['Reservations'][0].get('Instances'):
                        instance = instance_response['Reservations'][0]['Instances'][0]
                        instance_tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                except Exception as e:
                    logger.warning(f"Error getting instance tags for {instance_id}: {str(e)}")
                
                # Clean up Route53 record if domain exists
                domain_to_delete = instance_tags.get('HttpsDomain')
                if domain_to_delete and HTTPS_HOSTED_ZONE_ID:
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
                                logger.info(f"Deleted Route53 record: {domain_to_delete} for admin instance {instance_id}")
                            else:
                                logger.debug(f"Route53 record {domain_to_delete} not found (may already be deleted)")
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'NoSuchHostedZone':
                                logger.warning(f"Hosted zone {HTTPS_HOSTED_ZONE_ID} not found")
                            elif e.response['Error']['Code'] == 'InvalidChangeBatch':
                                logger.debug(f"Route53 record {domain_to_delete} may not exist or already deleted: {str(e)}")
                            else:
                                logger.warning(f"Failed to delete Route53 record {domain_to_delete} for {instance_id}: {str(e)}")
                    except Exception as e:
                        logger.warning(f"Error deleting Route53 record for {instance_id}: {str(e)}")
                
                # Terminate the instance (EC2 can terminate running instances directly)
                ec2_client.terminate_instances(InstanceIds=[instance_id])
                deleted.append(instance_info)
                logger.info(f"Initiated termination for admin instance {instance_id} ({instance_info['name']}) - age: {instance_info['age_days']} days")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'InvalidInstanceID.NotFound':
                    logger.warning(f"Admin instance {instance_id} not found (may already be terminated)")
                    deleted.append(instance_info)  # Consider it deleted
                else:
                    error_msg = f"{instance_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Error terminating admin instance {instance_id}: {str(e)}")
            except Exception as e:
                error_msg = f"{instance_id}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Error processing admin instance {instance_id}: {str(e)}")
        
        result = {
            'statusCode': 200 if len(errors) == 0 else 207,  # 207 = Multi-Status (some succeeded, some failed)
            'body': json.dumps({
                'message': f'Processed {len(instances_to_delete)} admin instance(s)',
                'cleanup_interval_days': cleanup_interval_days,
                'deleted': len(deleted),
                'errors': len(errors),
                'deleted_instances': [
                    {
                        'instance_id': inst['instance_id'],
                        'name': inst['name'],
                        'age_days': inst['age_days']
                    }
                    for inst in deleted
                ],
                'error_details': errors
            }, indent=2)
        }
        
        logger.info(f"Admin cleanup completed: {len(deleted)} deleted, {len(errors)} errors")
        return result
        
    except Exception as e:
        logger.error(f"Error in admin cleanup lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to process admin instance cleanup'
            })
        }

