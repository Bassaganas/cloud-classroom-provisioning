import boto3
import json
import logging
from datetime import datetime, timezone
from botocore.exceptions import ClientError
import time
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients with region from environment
region = os.environ.get('CLASSROOM_REGION', 'eu-west-3')
ec2_client = boto3.client('ec2', region_name=region)
environment = os.environ.get('ENVIRONMENT', 'dev')
HTTPS_BASE_DOMAIN = os.environ.get('INSTANCE_MANAGER_BASE_DOMAIN', '')
HTTPS_HOSTED_ZONE_ID = os.environ.get('INSTANCE_MANAGER_HOSTED_ZONE_ID', '')


def _normalize_record_name(record_name: str) -> str:
    if not record_name:
        return ''
    return record_name if record_name.endswith('.') else f"{record_name}."


def cleanup_route53_record(instance_id: str, tags: dict, strict: bool = True, max_retries: int = 3) -> dict:
    if not HTTPS_HOSTED_ZONE_ID:
        return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'hosted-zone-not-configured', 'attempts': 0}

    domain_to_delete = tags.get('HttpsDomain')
    if not domain_to_delete:
        return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'no-domain', 'attempts': 0}

    route53 = boto3.client('route53', region_name=region)
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
            logger.info(f"Deleted Route53 record: {domain_to_delete} for admin instance {instance_id}")
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
                
                # BUGFIX: Non-blocking Route53 cleanup - failure doesn't prevent deletion
                # Log Route53 cleanup issues but continue with instance termination
                dns_cleanup = cleanup_route53_record(instance_id, instance_tags, strict=False)
                if not dns_cleanup.get('success'):
                    logger.warning(
                        f"Route53 cleanup incomplete for {instance_id}: "
                        f"reason={dns_cleanup.get('reason')}, attempts={dns_cleanup.get('attempts')}"
                    )

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
        
        # BUGFIX: Always return 200 (success) to prevent EventBridge from retrying
        # Errors are logged but tracked separately
        result = {
            'statusCode': 200,  # Always return 200 for Lambda to be considered successful
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

