"""AWS utility functions for EC2, Route53, and Lambda operations."""
from botocore.exceptions import ClientError
import os
from .aws_boto3_client import (
    get_ec2_client, get_route53_client, get_lambda_client, get_dynamodb_client
)
import logging

logger = logging.getLogger(__name__)


def get_dynamodb_resource(region=None):
    """Get DynamoDB resource client."""
    import boto3
    import os
    resolved_region = region or os.getenv('AWS_REGION', 'eu-west-3')
    return boto3.resource('dynamodb', region_name=resolved_region)

# ============================================================================
# EC2 Utilities
# ============================================================================

def get_instance_by_id(instance_id, region=None):
    """Get EC2 instance details by ID."""
    try:
        import boto3
        if region:
            ec2 = boto3.client('ec2', region_name=region)
        else:
            ec2 = get_ec2_client()
        response = ec2.describe_instances(InstanceIds=[instance_id])
        if response['Reservations']:
            return response['Reservations'][0]['Instances'][0]
        return None
    except ClientError as e:
        logger.error(f"Error getting instance {instance_id}: {e}")
        return None

def instance_exists(instance_id, region=None):
    """Check if EC2 instance exists."""
    return get_instance_by_id(instance_id, region=region) is not None

def instance_is_terminated(instance_id, region=None):
    """Check if instance is terminated."""
    instance = get_instance_by_id(instance_id, region=region)
    if instance:
        return instance['State']['Name'] in ['terminated', 'terminating']
    return False

def get_instance_tags(instance_id, region=None):
    """Get all tags for an instance."""
    instance = get_instance_by_id(instance_id, region=region)
    if instance:
        return {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
    return {}

def get_instances_by_tag(key, value, region=None):
    """Get instances filtered by tag."""
    try:
        import boto3
        if region:
            ec2 = boto3.client('ec2', region_name=region)
        else:
            ec2 = get_ec2_client()
        response = ec2.describe_instances(
            Filters=[
                {'Name': f'tag:{key}', 'Values': [value]},
                {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
            ]
        )
        instances = []
        for reservation in response['Reservations']:
            instances.extend(reservation['Instances'])
        return instances
    except ClientError as e:
        logger.error(f"Error getting instances by tag {key}={value}: {e}")
        return []


def get_instances_by_filters(filters, region=None, include_terminated=False):
    """Get instances using arbitrary EC2 filters."""
    try:
        import boto3
        if region:
            ec2 = boto3.client('ec2', region_name=region)
        else:
            ec2 = get_ec2_client()

        query_filters = list(filters or [])
        if not include_terminated:
            query_filters.append(
                {
                    'Name': 'instance-state-name',
                    'Values': ['pending', 'running', 'stopping', 'stopped', 'starting']
                }
            )

        response = ec2.describe_instances(Filters=query_filters)
        instances = []
        for reservation in response.get('Reservations', []):
            instances.extend(reservation.get('Instances', []))
        return instances
    except ClientError as e:
        logger.error(f"Error getting instances by filters {filters}: {e}")
        return []


def get_instances_for_session(workshop_name, session_id, region=None):
    """Get active classroom instances for a specific workshop/session."""
    return get_instances_by_filters(
        [
            {'Name': 'tag:Project', 'Values': ['classroom']},
            {'Name': 'tag:WorkshopID', 'Values': [workshop_name]},
            {'Name': 'tag:TutorialSessionID', 'Values': [session_id]}
        ],
        region=region,
        include_terminated=False
    )


def count_instances_for_session(workshop_name, session_id, region=None):
    """Count active classroom instances for a specific workshop/session."""
    return len(get_instances_for_session(workshop_name, session_id, region=region))


def get_unnamed_classroom_instances(workshop_name=None, region=None):
    """Return classroom instances missing a non-empty Name tag."""
    filters = [{'Name': 'tag:Project', 'Values': ['classroom']}]
    if workshop_name:
        filters.append({'Name': 'tag:WorkshopID', 'Values': [workshop_name]})

    instances = get_instances_by_filters(filters, region=region, include_terminated=False)
    unnamed = []
    for instance in instances:
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        if not tags.get('Name', '').strip():
            unnamed.append(instance)
    return unnamed

def count_instances_by_tag(key, value, region=None):
    """Count instances by tag."""
    return len(get_instances_by_tag(key, value, region=region))

# ============================================================================
# Route53 Utilities
# ============================================================================

def get_route53_hosted_zone_id():
    """Get the Route53 hosted zone ID from environment."""
    import os
    return os.getenv('INSTANCE_MANAGER_HOSTED_ZONE_ID')

def get_route53_base_domain():
    """Get the Route53 base domain from environment."""
    import os
    return os.getenv('INSTANCE_MANAGER_BASE_DOMAIN')

def route53_record_exists(domain):
    """Check if a Route53 A record exists."""
    try:
        route53 = get_route53_client()
        zone_id = get_route53_hosted_zone_id()
        if not zone_id:
            logger.warning("Route53 hosted zone ID not configured")
            return False
        
        # Normalize domain name (add trailing dot if not present)
        if not domain.endswith('.'):
            domain = f"{domain}."
        
        response = route53.list_resource_record_sets(
            HostedZoneId=zone_id,
            StartRecordName=domain,
            StartRecordType='A'
        )
        
        # Check if the domain exists in the records
        for record in response.get('ResourceRecordSets', []):
            if record.get('Type') == 'A' and record.get('Name') == domain:
                return True
        return False
    except ClientError as e:
        logger.error(f"Error checking Route53 record {domain}: {e}")
        return False

def delete_route53_record(domain):
    """Delete a Route53 A record."""
    try:
        route53 = get_route53_client()
        zone_id = get_route53_hosted_zone_id()
        if not zone_id:
            logger.warning("Route53 hosted zone ID not configured")
            return False
        
        if not domain.endswith('.'):
            domain = f"{domain}."
        
        # Get the record first
        response = route53.list_resource_record_sets(
            HostedZoneId=zone_id,
            StartRecordName=domain,
            StartRecordType='A'
        )
        
        record_to_delete = None
        for record in response.get('ResourceRecordSets', []):
            if record.get('Type') == 'A' and record.get('Name') == domain:
                record_to_delete = record
                break
        
        if not record_to_delete:
            logger.info(f"Route53 record {domain} not found (already deleted)")
            return True
        
        # Delete the record
        route53.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Changes': [{
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'Name': record_to_delete['Name'],
                        'Type': record_to_delete['Type'],
                        'TTL': record_to_delete.get('TTL'),
                        'ResourceRecords': record_to_delete.get('ResourceRecords', [])
                    }
                }]
            }
        )
        logger.info(f"Deleted Route53 record {domain}")
        return True
    except ClientError as e:
        logger.error(f"Error deleting Route53 record {domain}: {e}")
        return False

# ============================================================================
# Lambda Utilities
# ============================================================================

def invoke_lambda(function_name, payload=None, async_invoke=False):
    """Invoke a Lambda function."""
    try:
        lambda_func = get_lambda_client()
        invocation_type = 'Event' if async_invoke else 'RequestResponse'
        
        response = lambda_func.invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            Payload=payload or '{}'
        )
        
        logger.info(f"Invoked Lambda {function_name} with status {response.get('StatusCode')}")
        return response
    except ClientError as e:
        logger.error(f"Error invoking Lambda {function_name}: {e}")
        return None

# ============================================================================
# DynamoDB Utilities
# ============================================================================

def get_dynamodb_table(table_name):
    """Get DynamoDB table resource."""
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='eu-west-3')
    return dynamodb.Table(table_name)

def get_instance_assignment(instance_id, table_name):
    """Get instance assignment from DynamoDB."""
    try:
        table = get_dynamodb_table(table_name)
        response = table.get_item(Key={'instance_id': instance_id})
        return response.get('Item')
    except ClientError as e:
        logger.error(f"Error getting instance assignment {instance_id}: {e}")
        return None

# ============================================================================
# Cleanup Utilities
# ============================================================================

def cleanup_e2e_resources(prefix='e2e-tests-'):
    """Clean up all E2E test resources with the given prefix."""
    logger.info(f"Starting cleanup of resources with prefix: {prefix}")
    
    # Cleanup tutorial sessions from DynamoDB
    cleanup_e2e_tutorial_sessions(prefix)
    
    # Cleanup EC2 instances
    cleanup_e2e_instances(prefix)
    
    # Cleanup Route53 records
    cleanup_e2e_route53_records(prefix)
    
    # Cleanup instance assignments from DynamoDB
    cleanup_e2e_instance_assignments(prefix)
    
    logger.info("Cleanup completed")

def cleanup_e2e_tutorial_sessions(prefix='e2e-tests-'):
    """Clean up E2E test tutorial sessions from DynamoDB."""
    try:
        dynamodb = get_dynamodb_resource()
        workshop_name = os.getenv('WORKSHOP_NAME', 'fellowship')
        environment = os.getenv('ENVIRONMENT', 'dev')
        
        table_name = f'tutorial-sessions-{workshop_name}-{environment}'
        
        try:
            table = dynamodb.Table(table_name)
            # Scan for sessions with the e2e prefix
            response = table.scan(
                FilterExpression='begins_with(session_id, :prefix)',
                ExpressionAttributeValues={':prefix': prefix}
            )
            
            sessions_to_delete = response.get('Items', [])
            
            if sessions_to_delete:
                logger.info(f"Deleting {len(sessions_to_delete)} E2E tutorial sessions from {table_name}")
                with table.batch_writer(batch_size=25) as batch:
                    for session in sessions_to_delete:
                        batch.delete_item(Key={'session_id': session['session_id']})
                        logger.info(f"  Deleted session: {session['session_id']}")
            else:
                logger.info(f"No E2E tutorial sessions to cleanup in {table_name}")
        except Exception as e:
            logger.warning(f"Could not cleanup tutorial sessions table {table_name}: {e}")
            
    except Exception as e:
        logger.error(f"Error cleaning up E2E tutorial sessions: {e}")

def cleanup_e2e_instance_assignments(prefix='e2e-tests-'):
    """Clean up E2E test instance assignments from DynamoDB."""
    try:
        dynamodb = get_dynamodb_resource()
        workshop_name = os.getenv('WORKSHOP_NAME', 'fellowship')
        environment = os.getenv('ENVIRONMENT', 'dev')
        
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        
        try:
            table = dynamodb.Table(table_name)
            # Scan for assignments related to e2e sessions
            # Since instance_id is the partition key, we can't use begins_with on it directly for scan
            # Instead, we'll scan and filter by the session ID (if present)
            response = table.scan()
            
            assignments_to_delete = []
            for item in response.get('Items', []):
                # Delete if it's an e2e session tracking item (key prefixes with e2e-tests-)
                if prefix in str(item.get('instance_id', '')):
                    assignments_to_delete.append(item)
            
            if assignments_to_delete:
                logger.info(f"Deleting {len(assignments_to_delete)} E2E instance assignments from {table_name}")
                with table.batch_writer(batch_size=25) as batch:
                    for assignment in assignments_to_delete:
                        batch.delete_item(Key={'instance_id': assignment['instance_id']})
                        logger.info(f"  Deleted assignment: {assignment['instance_id']}")
            else:
                logger.info(f"No E2E instance assignments to cleanup in {table_name}")
        except Exception as e:
            logger.warning(f"Could not cleanup instance assignments table {table_name}: {e}")
            
    except Exception as e:
        logger.error(f"Error cleaning up E2E instance assignments: {e}")

def cleanup_e2e_instances(prefix='e2e-tests-'):
    """Clean up E2E test EC2 instances, properly handling spot instances."""
    try:
        instances_by_name = get_instances_by_filters(
            [{'Name': 'tag:Name', 'Values': [f"*{prefix}*"]}],
            include_terminated=False
        )
        instances_by_session = get_instances_by_filters(
            [{'Name': 'tag:TutorialSessionID', 'Values': [f"{prefix}*"]}],
            include_terminated=False
        )

        instance_map = {}
        for instance in instances_by_name + instances_by_session:
            instance_map[instance['InstanceId']] = instance

        instances = list(instance_map.values())
        if instances:
            ec2 = get_ec2_client()
            instance_ids = [i['InstanceId'] for i in instances]
            logger.info(f"Terminating {len(instance_ids)} E2E instances: {instance_ids}")
            
            # Properly handle spot instances by canceling spot requests first
            spot_request_ids = []
            for instance in instances:
                instance_id = instance['InstanceId']
                lifecycle = instance.get('InstanceLifecycle', 'on-demand')
                
                if lifecycle == 'spot':
                    # Get spot instance request ID to cancel it properly
                    spot_request_id = instance.get('SpotInstanceRequestId')
                    if spot_request_id:
                        spot_request_ids.append(spot_request_id)
                        logger.info(f"Found spot request {spot_request_id} for instance {instance_id}")
            
            # Cancel spot requests with TerminateInstances=True to properly clean up
            if spot_request_ids:
                logger.info(f"Canceling {len(spot_request_ids)} spot instance requests: {spot_request_ids}")
                try:
                    ec2.cancel_spot_instance_requests(
                        SpotInstanceRequestIds=spot_request_ids,
                        TerminateInstances=True  # This terminates the instances and cancels the request
                    )
                    logger.info(f"Canceled {len(spot_request_ids)} spot requests")
                except Exception as e:
                    logger.warning(f"Error canceling spot requests, will continue with regular termination: {e}")
                    # Fall back to regular termination if spot request cancellation fails
                    ec2.terminate_instances(InstanceIds=instance_ids)
            else:
                # No spot instances found, use regular termination for on-demand
                ec2.terminate_instances(InstanceIds=instance_ids)
    except Exception as e:
        logger.error(f"Error cleaning up E2E instances: {e}")

def cleanup_e2e_route53_records(prefix='e2e-tests-'):
    """Clean up E2E test Route53 records."""
    try:
        route53 = get_route53_client()
        zone_id = get_route53_hosted_zone_id()
        if not zone_id:
            logger.warning("Route53 hosted zone ID not configured for cleanup")
            return
        
        response = route53.list_resource_record_sets(HostedZoneId=zone_id)
        records_to_delete = []
        
        for record in response.get('ResourceRecordSets', []):
            if prefix in record.get('Name', '') and record.get('Type') == 'A':
                records_to_delete.append(record)
        
        if records_to_delete:
            changes = []
            for record in records_to_delete:
                changes.append({
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'Name': record['Name'],
                        'Type': record['Type'],
                        'TTL': record.get('TTL'),
                        'ResourceRecords': record.get('ResourceRecords', [])
                    }
                })
            
            if changes:
                logger.info(f"Deleting {len(changes)} E2E Route53 records")
                route53.change_resource_record_sets(
                    HostedZoneId=zone_id,
                    ChangeBatch={'Changes': changes}
                )
    except Exception as e:
        logger.error(f"Error cleaning up E2E Route53 records: {e}")
