import json
import boto3
import os
import sys
import logging
import time
from botocore.exceptions import ClientError
from datetime import datetime, timezone
import base64
import hashlib
import hmac
import urllib.parse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Log module initialization
logger.info("=" * 60)
logger.info("Module testus_patronus_instance_manager.py loaded")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"File location: {__file__}")

# Get region from environment variable (Lambda automatically sets AWS_REGION)
REGION = os.environ.get('CLASSROOM_REGION', os.environ.get('AWS_REGION', 'eu-west-3'))
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

logger.info(f"REGION: {REGION}")
logger.info(f"ENVIRONMENT: {ENVIRONMENT}")
logger.info("=" * 60)

# Initialize AWS clients
try:
    logger.info("Initializing AWS clients...")
    ec2 = boto3.client('ec2', region_name=REGION)
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(f"instance-assignments-{ENVIRONMENT}")
    logger.info(f"AWS clients initialized. Table: instance-assignments-{ENVIRONMENT}")
except Exception as e:
    logger.error(f"Error initializing AWS clients: {str(e)}", exc_info=True)
    raise

# Get configuration from environment variables
INSTANCE_TYPE = os.environ.get('EC2_INSTANCE_TYPE', 't3.medium')
SUBNET_ID = os.environ.get('EC2_SUBNET_ID')
SECURITY_GROUP_IDS = os.environ.get('EC2_SECURITY_GROUP_IDS', '').split(',') if os.environ.get('EC2_SECURITY_GROUP_IDS') else []
IAM_INSTANCE_PROFILE = os.environ.get('EC2_IAM_INSTANCE_PROFILE', f'ec2-ssm-profile-{ENVIRONMENT}')

# Initialize Secrets Manager client for password authentication
secretsmanager = boto3.client('secretsmanager', region_name=REGION)
PASSWORD_SECRET_NAME = os.environ.get('INSTANCE_MANAGER_PASSWORD_SECRET', '')

# Cache for password (to avoid repeated Secrets Manager calls)
_password_cache = None

def get_password_from_secret():
    """Get the instance manager password from AWS Secrets Manager"""
    global _password_cache
    
    if _password_cache is not None:
        return _password_cache
    
    if not PASSWORD_SECRET_NAME:
        logger.warning("INSTANCE_MANAGER_PASSWORD_SECRET not set, authentication disabled")
        return None
    
    try:
        response = secretsmanager.get_secret_value(SecretId=PASSWORD_SECRET_NAME)
        _password_cache = response['SecretString']
        logger.info("Successfully retrieved password from Secrets Manager")
        return _password_cache
    except ClientError as e:
        logger.error(f"Error retrieving password from Secrets Manager: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving password: {str(e)}")
        return None

def parse_cookies(headers):
    """Parse cookies from HTTP headers"""
    cookies = {}
    cookie_header = headers.get('cookie') or headers.get('Cookie') or ''
    
    for cookie in cookie_header.split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookies[key.strip()] = urllib.parse.unquote(value.strip())
    
    return cookies

def check_authentication(event):
    """Check if the request is authenticated"""
    headers = event.get('headers', {}) or {}
    cookies = parse_cookies(headers)
    
    # Check for authentication cookie
    auth_token = cookies.get('instance_manager_auth')
    if not auth_token:
        return False
    
    # Get password from secret
    password = get_password_from_secret()
    if not password:
        # If no password is configured, allow access (backward compatibility)
        return True
    
    # Create expected token (simple hash of password)
    expected_token = hashlib.sha256(f"instance_manager_{password}".encode()).hexdigest()
    
    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(auth_token, expected_token)

def create_auth_response(password):
    """Create authentication cookie response"""
    auth_token = hashlib.sha256(f"instance_manager_{password}".encode()).hexdigest()
    
    # Cookie expires in 7 days
    max_age = 7 * 24 * 60 * 60
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Set-Cookie': f'instance_manager_auth={auth_token}; Path=/; Max-Age={max_age}; HttpOnly; Secure; SameSite=Lax'
        },
        'body': json.dumps({
            'success': True,
            'message': 'Authentication successful'
        })
    }

def get_user_data_script():
    """Get the user_data.sh script content"""
    user_data_path = os.path.join(os.path.dirname(__file__), '..', '..', 'iac', 'aws', 'user_data.sh')
    try:
        with open(user_data_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        # Fallback to inline script if file not found
        return """#!/bin/bash
set -e

# Function to wait for yum lock
wait_for_yum() {
    while sudo fuser /var/run/yum.pid >/dev/null 2>&1; do
        echo "Waiting for other yum process to finish..."
        sleep 5
    done
}

wait_for_yum
yum update -y
wait_for_yum
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

mkdir -p /home/ec2-user/.docker/cli-plugins/
curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 -o /home/ec2-user/.docker/cli-plugins/docker-compose
chmod +x /home/ec2-user/.docker/cli-plugins/docker-compose
chown -R ec2-user:ec2-user /home/ec2-user/.docker

su - ec2-user -c "git clone https://github.com/langgenius/dify.git ~/dify"
su - ec2-user -c "cd ~/dify && git checkout 1.9.1"
su - ec2-user -c "cp ~/dify/docker/.env.example ~/dify/docker/.env"

cat >> /home/ec2-user/dify/docker/.env << 'EOF'
LANG=en_US.UTF-8
NEXT_PUBLIC_API_PREFIX=/console/api
NEXT_PUBLIC_PUBLIC_API_PREFIX=/v1
DIFY_API_VERSION=1.9.1
DIFY_WEB_VERSION=1.9.1
DIFY_WORKER_VERSION=1.9.1
DIFY_WORKER_BEAT_VERSION=1.9.1
POSTGRES_VERSION=15-alpine
REDIS_VERSION=6-alpine
WEAVIATE_VERSION=1.27.0
EOF

su - ec2-user -c "cd ~/dify/docker && docker compose pull"
su - ec2-user -c "cd ~/dify/docker && docker compose up -d"
"""

def get_latest_ami():
    """Get the latest Amazon Linux 2 AMI"""
    try:
        response = ec2.describe_images(
            Owners=['amazon'],
            Filters=[
                {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
                {'Name': 'virtualization-type', 'Values': ['hvm']}
            ],
            MostRecent=True
        )
        if response['Images']:
            return response['Images'][0]['ImageId']
        else:
            logger.warning("No AMI found, using default")
            return 'ami-0746ed6b6c0683e67'  # Fallback AMI for eu-west-3
    except Exception as e:
        logger.error(f"Error getting AMI: {str(e)}")
        return 'ami-0746ed6b6c0683e67'  # Fallback AMI

def create_instance(count=1, instance_type='pool', cleanup_days=None):
    """Create EC2 instance(s) with Dify
    
    Args:
        count: Number of instances to create
        instance_type: 'pool' for pool instances or 'admin' for admin instances
        cleanup_days: Number of days before admin instances are deleted (only for admin instances, default: 7)
    """
    try:
        ami_id = get_latest_ami()
        user_data = get_user_data_script()
        
        instances = []
        for i in range(count):
            # Determine naming and tags based on type
            if instance_type == 'admin':
                name = f'classroom-admin-{i}'
                # Default cleanup days to 7 if not specified
                cleanup_days_value = str(cleanup_days if cleanup_days is not None else 7)
                tags = [
                    {'Key': 'Name', 'Value': name},
                    {'Key': 'Status', 'Value': 'available'},
                    {'Key': 'Project', 'Value': 'classroom'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Type', 'Value': 'admin'},  # Different tag for admin
                    {'Key': 'Isolated', 'Value': 'true'},
                    {'Key': 'CreatedBy', 'Value': 'lambda-manager'},
                    {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()},
                    {'Key': 'CleanupDays', 'Value': cleanup_days_value}  # Days until cleanup
                ]
            else:  # pool
                name = f'classroom-pool-{i}'
                tags = [
                    {'Key': 'Name', 'Value': name},
                    {'Key': 'Status', 'Value': 'available'},
                    {'Key': 'Project', 'Value': 'classroom'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Type', 'Value': 'pool'},
                    {'Key': 'CreatedBy', 'Value': 'lambda-manager'},
                    {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
                ]
            
            response = ec2.run_instances(
                ImageId=ami_id,
                InstanceType=INSTANCE_TYPE,
                MinCount=1,
                MaxCount=1,
                UserData=user_data,
                IamInstanceProfile={'Name': IAM_INSTANCE_PROFILE},
                SubnetId=SUBNET_ID if SUBNET_ID else None,
                SecurityGroupIds=SECURITY_GROUP_IDS if SECURITY_GROUP_IDS else None,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': tags
                    }
                ],
                MetadataOptions={
                    'HttpTokens': 'required',
                    'HttpEndpoint': 'enabled'
                },
                BlockDeviceMappings=[
                    {
                        'DeviceName': '/dev/xvda',
                        'Ebs': {
                            'VolumeSize': 40,
                            'VolumeType': 'gp3',
                            'DeleteOnTermination': True
                        }
                    }
                ]
            )
            
            instance_id = response['Instances'][0]['InstanceId']
            initial_state = response['Instances'][0]['State']['Name']
            
            # Launch instances asynchronously - don't wait for them to be running
            # They will be stopped by a background process once they're running
            # This makes the API response much faster (no waiting for instance_running waiter)
            logger.info(f"Launched {instance_type} instance {instance_id} ({i+1}/{count}) - state: {initial_state}")
            
            # Note: We don't stop pending instances here - they need to be running first
            # A background process (or the stop_old_instances Lambda) will stop them once running
            # This makes creation much faster - we just launch and return
            
            instances.append({
                'instance_id': instance_id,
                'state': initial_state,  # Current state (pending -> running -> stopping -> stopped)
                'launch_time': response['Instances'][0]['LaunchTime'].isoformat(),
                'type': instance_type
            })
            
            logger.info(f"Created {instance_type} instance {instance_id} ({i+1}/{count}) - will be stopped automatically once running")
        
        return {
            'success': True,
            'instances': instances,
            'count': len(instances),
            'type': instance_type
        }
    except Exception as e:
        logger.error(f"Error creating instances: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def list_instances(include_terminated=False):
    """List all EC2 instances with their assignments and IPs
    
    Args:
        include_terminated: If True, include terminated instances in the results
    """
    try:
        # Get all instances (both pool and admin)
        # Note: terminated instances are automatically excluded by default
        filters = [
            {'Name': 'tag:Project', 'Values': ['classroom']}
        ]
        
        # If we want to include terminated, we need to get all states
        # Otherwise, exclude terminated and shutting-down
        if not include_terminated:
            filters.append({'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped', 'starting']})
        
        response = ec2.describe_instances(Filters=filters)
        
        instances = []
        
        # Get all DynamoDB assignments
        assignments = {}
        try:
            scan_response = table.scan()
            for item in scan_response.get('Items', []):
                instance_id = item.get('instance_id')
                if instance_id:
                    assignments[instance_id] = {
                        'student_name': item.get('student_name'),
                        'status': item.get('status', 'unknown'),
                        'assigned_at': item.get('assigned_at')
                    }
        except Exception as e:
            logger.warning(f"Error scanning DynamoDB: {str(e)}")
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                state = instance['State']['Name']
                
                # Get tags
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                instance_type = tags.get('Type', 'unknown')
                
                # Get assignment info from DynamoDB (only for pool instances)
                assignment = assignments.get(instance_id, {}) if instance_type == 'pool' else {}
                
                # Calculate days remaining for admin instances
                cleanup_days_remaining = None
                cleanup_days = None
                if instance_type == 'admin' and instance.get('LaunchTime'):
                    launch_time = instance['LaunchTime']
                    # EC2 LaunchTime is already timezone-aware
                    now = datetime.now(timezone.utc)
                    age_days = (now - launch_time).days
                    
                    # Get cleanup days from tag (default to 7 if not set)
                    cleanup_days = int(tags.get('CleanupDays', '7'))
                    cleanup_days_remaining = max(0, cleanup_days - age_days)
                
                instance_info = {
                    'instance_id': instance_id,
                    'state': state,
                    'public_ip': instance.get('PublicIpAddress'),
                    'private_ip': instance.get('PrivateIpAddress'),
                    'instance_type': instance.get('InstanceType'),
                    'launch_time': instance.get('LaunchTime').isoformat() if instance.get('LaunchTime') else None,
                    'tags': tags,
                    'type': instance_type,
                    'assigned_to': assignment.get('student_name'),
                    'assignment_status': assignment.get('status'),
                    'assigned_at': assignment.get('assigned_at'),
                    'cleanup_days': cleanup_days,  # Total cleanup days configured
                    'cleanup_days_remaining': cleanup_days_remaining  # Days remaining before deletion
                }
                
                instances.append(instance_info)
        
        # Sort by launch time (newest first)
        instances.sort(key=lambda x: x['launch_time'] or '', reverse=True)
        
        # ALWAYS filter out terminated instances for summary (regardless of include_terminated flag)
        # Summary should only show active instances (running, stopped, pending, starting, stopping)
        active_instances = [i for i in instances if i['state'] not in ['terminated', 'shutting-down']]
        
        # Calculate summary (only for active instances: running, stopped, pending, starting, stopping)
        pool_instances = [i for i in active_instances if i['type'] == 'pool']
        admin_instances = [i for i in active_instances if i['type'] == 'admin']
        
        # Count instances by state for summary
        pool_running = len([i for i in pool_instances if i['state'] == 'running'])
        pool_stopped = len([i for i in pool_instances if i['state'] == 'stopped'])
        pool_assigned = len([i for i in pool_instances if i.get('assigned_to')])
        
        admin_running = len([i for i in admin_instances if i['state'] == 'running'])
        admin_stopped = len([i for i in admin_instances if i['state'] == 'stopped'])
        
        return {
            'success': True,
            'instances': instances,  # Return all instances (may include terminated if include_terminated=True)
            'count': len(instances),
            'summary': {
                'total': len(active_instances),  # Only active instances (excluding terminated)
                'pool': {
                    'total': len(pool_instances),
                    'running': pool_running,
                    'stopped': pool_stopped,
                    'assigned': pool_assigned,
                    'available': len([i for i in pool_instances if not i.get('assigned_to') and i['state'] in ['running', 'stopped']])
                },
                'admin': {
                    'total': len(admin_instances),
                    'running': admin_running,
                    'stopped': admin_stopped
                }
            }
        }
    except Exception as e:
        logger.error(f"Error listing instances: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def stop_instances(instance_ids):
    """
    Stop EC2 instances (does not terminate them)
    
    Args:
        instance_ids: List of instance IDs to stop
    """
    try:
        if not instance_ids:
            return {
                'success': False,
                'error': 'instance_ids is required'
            }
        
        stopped = []
        errors = []
        
        for instance_id in instance_ids:
            try:
                # Check instance state first
                response = ec2.describe_instances(InstanceIds=[instance_id])
                if not response.get('Reservations') or not response['Reservations'][0].get('Instances'):
                    errors.append(f'{instance_id}: not found')
                    continue
                
                instance = response['Reservations'][0]['Instances'][0]
                state = instance['State']['Name']
                
                if state == 'stopped':
                    stopped.append(instance_id)
                    logger.info(f"Instance {instance_id} is already stopped")
                elif state == 'stopping':
                    stopped.append(instance_id)
                    logger.info(f"Instance {instance_id} is already stopping")
                elif state in ['running', 'pending']:
                    # Stop the instance
                    ec2.stop_instances(InstanceIds=[instance_id])
                    stopped.append(instance_id)
                    logger.info(f"Initiated stop for instance {instance_id} (state: {state})")
                elif state in ['terminated', 'shutting-down']:
                    errors.append(f'{instance_id}: cannot stop {state} instance')
                else:
                    errors.append(f'{instance_id}: invalid state {state}')
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
                    errors.append(f'{instance_id}: not found')
                else:
                    errors.append(f'{instance_id}: {str(e)}')
                    logger.error(f"Error stopping instance {instance_id}: {str(e)}")
            except Exception as e:
                errors.append(f'{instance_id}: {str(e)}')
                logger.error(f"Error processing stop for {instance_id}: {str(e)}")
        
        return {
            'success': len(errors) == 0,
            'stopped': stopped,
            'errors': errors,
            'count': len(stopped)
        }
    except Exception as e:
        logger.error(f"Error stopping instances: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def delete_instances(instance_ids=None, delete_type='individual'):
    """Delete EC2 instance(s)
    
    Args:
        instance_ids: List of instance IDs to delete, or None
        delete_type: 'individual', 'pool', 'admin', or 'all'
    """
    try:
        if delete_type == 'all':
            # Get all instances
            response = ec2.describe_instances(
                Filters=[{'Name': 'tag:Project', 'Values': ['classroom']}]
            )
            instance_ids = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_ids.append(instance['InstanceId'])
        elif delete_type == 'pool':
            # Get all pool instances
            response = ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:Project', 'Values': ['classroom']},
                    {'Name': 'tag:Type', 'Values': ['pool']}
                ]
            )
            instance_ids = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_ids.append(instance['InstanceId'])
        elif delete_type == 'admin':
            # Get all admin instances
            response = ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:Project', 'Values': ['classroom']},
                    {'Name': 'tag:Type', 'Values': ['admin']}
                ]
            )
            instance_ids = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_ids.append(instance['InstanceId'])
        elif not instance_ids:
            return {
                'success': False,
                'error': 'No instance IDs provided'
            }
        
        if not instance_ids:
            return {
                'success': True,
                'message': f'No {delete_type} instances found to delete',
                'deleted': []
            }
        
        deleted = []
        errors = []
        
        # Process deletions asynchronously - don't wait for completion
        for instance_id in instance_ids:
            try:
                # Clean up DynamoDB assignment (non-blocking)
                try:
                    response = table.get_item(Key={'instance_id': instance_id})
                    if 'Item' in response:
                        student_name = response['Item'].get('student_name')
                        if student_name:
                            logger.warning(f"Instance {instance_id} is assigned to {student_name}. Cleaning up assignment.")
                            # Delete the assignment record
                            table.delete_item(Key={'instance_id': instance_id})
                except Exception as e:
                    logger.warning(f"Error cleaning up assignment: {str(e)}")
                
                # Terminate instance directly - EC2 can terminate running instances without stopping first
                # This is much faster than stopping then terminating
                try:
                    ec2.terminate_instances(InstanceIds=[instance_id])
                    deleted.append(instance_id)
                    logger.info(f"Initiated termination for instance {instance_id} (async)")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
                        errors.append(f'{instance_id}: not found')
                    else:
                        errors.append(f'{instance_id}: {str(e)}')
                
            except Exception as e:
                errors.append(f'{instance_id}: {str(e)}')
                logger.error(f"Error processing deletion for {instance_id}: {str(e)}")
        
        return {
            'success': len(errors) == 0,
            'deleted': deleted,
            'errors': errors,
            'count': len(deleted)
        }
    except Exception as e:
        logger.error(f"Error deleting instances: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def lambda_handler(event, context):
    """Lambda handler for EC2 instance pool management"""
    logger.info("=" * 50)
    logger.info("Lambda handler invoked")
    logger.info(f"Event type: {type(event)}")
    logger.info(f"Event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}")
    logger.info(f"Context: {context}")
    
    try:
        # Get HTTP method and path
        http_method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
        path = event.get('requestContext', {}).get('http', {}).get('path', '/')
        logger.info(f"HTTP Method: {http_method}, Path: {path}")
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        body = {}
        
        # Parse body if it exists
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except:
                body = {}
        
        # Handle login endpoint (no authentication required)
        if path == '/login' and http_method == 'POST':
            password = get_password_from_secret()
            if not password:
                # No password configured, allow access
                return create_auth_response('')
            
            provided_password = body.get('password') or query_params.get('password', '')
            if provided_password == password:
                return create_auth_response(password)
            else:
                return {
                    'statusCode': 401,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'Invalid password'
                    })
                }
        
        # Check authentication for all other endpoints
        if not check_authentication(event):
            # If no password is configured, allow access (backward compatibility)
            password = get_password_from_secret()
            if not password:
                # No password configured, continue without authentication
                pass
            else:
                # Password is configured but user is not authenticated
                # Return login page for UI, 401 for API endpoints
                if path == '/ui' or path == '/':
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'text/html'},
                        'body': get_login_html()
                    }
                else:
                    return {
                        'statusCode': 401,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'Authentication required',
                            'requires_auth': True
                        })
                    }
        
        # Serve frontend HTML
        if path == '/ui' or path == '/':
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html'},
                'body': get_frontend_html()
            }
        
        # Route based on method and path
        if path == '/create' and http_method == 'POST':
            count = int(body.get('count', query_params.get('count', 1)))
            instance_type = body.get('type', query_params.get('type', 'pool'))
            cleanup_days = body.get('cleanup_days') or query_params.get('cleanup_days')
            if cleanup_days is not None:
                cleanup_days = int(cleanup_days)
            
            if count < 1 or count > 120:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'Count must be between 1 and 120'
                    })
                }
            
            if instance_type not in ['pool', 'admin']:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'Type must be "pool" or "admin"'
                    })
                }
            
            if instance_type == 'admin' and cleanup_days is not None:
                if cleanup_days < 1 or cleanup_days > 365:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'Cleanup days must be between 1 and 365'
                        })
                    }
            
            result = create_instance(count=count, instance_type=instance_type, cleanup_days=cleanup_days)
            # Add a message indicating the operation is async
            if result['success']:
                result['message'] = f"✅ Initiated creation of {result['count']} {instance_type} instance(s). They will be stopped automatically once running. Refresh to see updates."
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        elif path == '/list' and http_method == 'GET':
            # Check if include_terminated parameter is set
            include_terminated = query_params.get('include_terminated', 'false').lower() == 'true'
            result = list_instances(include_terminated=include_terminated)
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result, indent=2)
            }
        
        elif path == '/update_cleanup_days' and http_method == 'POST':
            # Update cleanup days for an admin instance
            instance_id = body.get('instance_id') or query_params.get('instance_id')
            new_cleanup_days = body.get('cleanup_days') or query_params.get('cleanup_days')
            
            if not instance_id:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'instance_id is required'
                    })
                }
            
            if new_cleanup_days is None:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'cleanup_days is required'
                    })
                }
            
            try:
                new_cleanup_days = int(new_cleanup_days)
                if new_cleanup_days < 1 or new_cleanup_days > 365:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'Cleanup days must be between 1 and 365'
                        })
                    }
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'cleanup_days must be a number'
                    })
                }
            
            try:
                # Verify instance exists and is an admin instance
                response = ec2.describe_instances(InstanceIds=[instance_id])
                if not response.get('Reservations') or not response['Reservations'][0].get('Instances'):
                    return {
                        'statusCode': 404,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'Instance not found'
                        })
                    }
                
                instance = response['Reservations'][0]['Instances'][0]
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                
                if tags.get('Type') != 'admin':
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'Only admin instances can have cleanup days updated'
                        })
                    }
                
                # Update the CleanupDays tag
                ec2.create_tags(
                    Resources=[instance_id],
                    Tags=[
                        {'Key': 'CleanupDays', 'Value': str(new_cleanup_days)}
                    ]
                )
                
                logger.info(f"Updated cleanup days for instance {instance_id} to {new_cleanup_days}")
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': True,
                        'message': f'Updated cleanup days to {new_cleanup_days} for instance {instance_id}',
                        'instance_id': instance_id,
                        'cleanup_days': new_cleanup_days
                    })
                }
            except ClientError as e:
                logger.error(f"Error updating cleanup days: {str(e)}")
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': str(e)
                    })
                }
        
        elif path == '/assign' and http_method == 'POST':
            # Manual assignment endpoint
            instance_id = body.get('instance_id') or query_params.get('instance_id')
            student_name = body.get('student_name') or query_params.get('student_name')
            
            if not instance_id:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'instance_id is required'
                    })
                }
            
            if not student_name:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': 'student_name is required'
                    })
                }
            
            try:
                # Verify instance exists and is a pool instance
                response = ec2.describe_instances(InstanceIds=[instance_id])
                if not response.get('Reservations') or not response['Reservations'][0].get('Instances'):
                    return {
                        'statusCode': 404,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'Instance not found'
                        })
                    }
                
                instance = response['Reservations'][0]['Instances'][0]
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                
                if tags.get('Type') != 'pool':
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'Only pool instances can be manually assigned'
                        })
                    }
                
                # Check if instance is already assigned
                existing = None
                try:
                    existing = table.get_item(Key={'instance_id': instance_id})
                    if 'Item' in existing and existing['Item'].get('student_name'):
                        return {
                            'statusCode': 400,
                            'headers': {'Content-Type': 'application/json'},
                            'body': json.dumps({
                                'success': False,
                                'error': f"Instance is already assigned to {existing['Item'].get('student_name')}"
                            })
                        }
                except Exception as e:
                    logger.warning(f"Error checking existing assignment: {str(e)}")
                
                # Create assignment in DynamoDB
                assignment_ttl = 600  # 10 minutes
                item = {
                    'instance_id': instance_id,
                    'student_name': student_name,
                    'assigned_at': datetime.now(timezone.utc).isoformat(),
                    'status': 'assigning',
                    'expires_at': int(time.time()) + assignment_ttl
                }
                
                # Preserve last_stopped_at if it exists
                if existing and 'Item' in existing and 'last_stopped_at' in existing['Item']:
                    item['last_stopped_at'] = existing['Item']['last_stopped_at']
                
                table.put_item(
                    Item=item,
                    ConditionExpression='attribute_not_exists(instance_id) OR attribute_not_exists(student_name)'
                )
                
                # Update EC2 tags
                instance_state = instance['State']['Name']
                ec2.create_tags(
                    Resources=[instance_id],
                    Tags=[
                        {'Key': 'Status', 'Value': 'starting'},
                        {'Key': 'Student', 'Value': student_name}
                    ]
                )
                
                # Start instance if stopped
                if instance_state == 'stopped':
                    ec2.start_instances(InstanceIds=[instance_id])
                
                # Update DynamoDB status
                table.update_item(
                    Key={'instance_id': instance_id},
                    UpdateExpression='SET #status = :status REMOVE expires_at',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={':status': 'starting'}
                )
                
                # Update EC2 tags to assigned
                ec2.create_tags(
                    Resources=[instance_id],
                    Tags=[
                        {'Key': 'Status', 'Value': 'assigned'},
                        {'Key': 'Student', 'Value': student_name}
                    ]
                )
                
                logger.info(f"Manually assigned instance {instance_id} to {student_name}")
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': True,
                        'message': f'Successfully assigned instance {instance_id} to {student_name}',
                        'instance_id': instance_id,
                        'student_name': student_name
                    })
                }
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    return {
                        'statusCode': 409,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'Instance is already assigned or assignment in progress'
                        })
                    }
                logger.error(f"Error assigning instance: {str(e)}")
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': str(e)
                    })
                }
            except Exception as e:
                logger.error(f"Error assigning instance: {str(e)}", exc_info=True)
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': str(e)
                    })
                }
        
        elif path == '/stop' and http_method == 'POST':
            instance_ids = body.get('instance_ids') or (query_params.get('instance_ids', '').split(',') if query_params.get('instance_ids') else None)
            
            if not instance_ids:
                instance_id = body.get('instance_id') or query_params.get('instance_id')
                if instance_id:
                    instance_ids = [instance_id]
                else:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'instance_id or instance_ids is required'
                        })
                    }
            
            result = stop_instances(instance_ids=instance_ids)
            # Add a message indicating the operation is async
            if result['success']:
                result['message'] = f"✅ Initiated stop for {result['count']} instance(s). Instances are stopping. Refresh to see updates."
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        elif path == '/delete' and http_method == 'DELETE':
            instance_ids = body.get('instance_ids') or (query_params.get('instance_ids', '').split(',') if query_params.get('instance_ids') else None)
            delete_type = body.get('delete_type', query_params.get('delete_type', 'individual'))
            
            if delete_type == 'individual' and not instance_ids:
                instance_id = body.get('instance_id') or query_params.get('instance_id')
                if instance_id:
                    instance_ids = [instance_id]
                else:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'success': False,
                            'error': 'instance_id or instance_ids is required for individual delete'
                        })
                    }
            
            result = delete_instances(instance_ids=instance_ids, delete_type=delete_type)
            # Add a message indicating the operation is async
            if result['success']:
                result['message'] = f"✅ Initiated deletion of {result['count']} instance(s). Termination is in progress. Refresh to see updates."
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'error': 'Not found',
                    'available_endpoints': {
                        'GET /ui': 'Frontend interface',
                        'POST /create': 'Create instances (body: {"count": 1, "type": "pool", "cleanup_days": 7})',
                        'GET /list': 'List all instances',
                        'POST /update_cleanup_days': 'Update cleanup days for admin instance (body: {"instance_id": "...", "cleanup_days": 7})',
                        'POST /assign': 'Manually assign instance to student (body: {"instance_id": "...", "student_name": "..."})',
                        'POST /stop': 'Stop instances (body: {"instance_id": "..."} or query: ?instance_id=...)',
                        'DELETE /delete': 'Delete instances'
                    }
                })
            }
    
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }

def get_login_html():
    """Return the login page HTML"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EC2 Instance Manager - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            max-width: 400px;
            width: 100%;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            text-align: center;
        }
        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
        }
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            width: 100%;
            transition: background 0.3s;
        }
        button:hover {
            background: #5568d3;
        }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: none;
        }
        .error.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🚀 EC2 Instance Manager</h1>
        <p class="subtitle">Please enter your password to continue</p>
        <div id="error" class="error"></div>
        <form id="loginForm">
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required autofocus>
            </div>
            <button type="submit">Login</button>
        </form>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('error');
            
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({password: password})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Redirect to main UI
                    window.location.href = '/ui';
                } else {
                    errorDiv.textContent = data.error || 'Invalid password';
                    errorDiv.classList.add('show');
                    document.getElementById('password').value = '';
                }
            } catch (error) {
                errorDiv.textContent = 'Error: ' + error.message;
                errorDiv.classList.add('show');
            }
        });
    </script>
</body>
</html>"""

def get_frontend_html():
    """Return the HTML frontend interface"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EC2 Instance Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
        }
        .actions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .card h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.3em;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }
        input, select {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.3s;
            width: 100%;
        }
        button:hover {
            background: #5568d3;
        }
        button.delete {
            background: #e74c3c;
        }
        button.delete:hover {
            background: #c0392b;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }
        .summary-card h3 {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
        }
        .summary-card .number {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        .instances-table {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background: #f8f9fa;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #333;
            border-bottom: 2px solid #e0e0e0;
        }
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }
        .badge.pool {
            background: #e3f2fd;
            color: #1976d2;
        }
        .badge.admin {
            background: #fff3e0;
            color: #f57c00;
        }
        .badge.running {
            background: #e8f5e9;
            color: #388e3c;
        }
        .badge.stopped {
            background: #ffebee;
            color: #d32f2f;
        }
        .badge.terminated {
            background: #eceff1;
            color: #546e7a;
        }
        .badge.assigned {
            background: #f3e5f5;
            color: #7b1fa2;
        }
        a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        a:hover {
            text-decoration: underline;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .success {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .actions-buttons {
            display: flex;
            gap: 10px;
        }
        .btn-small {
            padding: 6px 12px;
            font-size: 12px;
            width: auto;
        }
        code {
            font-family: 'Fira Mono', 'Consolas', monospace;
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .table-header {
            padding: 20px;
            border-bottom: 2px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .table-header h2 {
            margin: 0;
            color: #333;
        }
        .refresh-btn {
            width: auto;
            padding: 8px 16px;
        }
        small {
            display: block;
            margin-top: 4px;
        }
        .days-remaining {
            font-weight: 500;
        }
        .days-remaining.expired {
            color: #c62828;
            font-weight: bold;
        }
        .days-remaining.critical {
            color: #f57c00;
            font-weight: bold;
        }
        .days-remaining.warning {
            color: #ff9800;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 EC2 Instance Manager</h1>
            <p class="subtitle">Manage your Dify classroom instances</p>
        </div>

        <div id="message"></div>

        <div class="actions">
            <div class="card">
                <h2>Create Pool Instances</h2>
                <form id="createPoolForm">
                    <div class="form-group">
                        <label>Number of instances:</label>
                        <input type="number" id="poolCount" min="1" max="120" value="4" required>
                    </div>
                    <button type="submit">Create Pool</button>
                </form>
            </div>

            <div class="card">
                <h2>Create Admin Instance</h2>
                <form id="createAdminForm">
                    <div class="form-group">
                        <label>Number of instances:</label>
                        <input type="number" id="adminCount" min="1" max="5" value="1" required>
                    </div>
                    <div class="form-group">
                        <label>Cleanup after (days):</label>
                        <input type="number" id="adminCleanupDays" min="1" max="365" value="7" required>
                        <small style="color: #666; font-size: 0.85em;">Instances will be automatically deleted after this many days (default: 7)</small>
                    </div>
                    <button type="submit">Create Admin</button>
                </form>
            </div>

            <div class="card">
                <h2>Bulk Delete</h2>
                <div class="form-group">
                    <label>Delete type:</label>
                    <select id="deleteType">
                        <option value="pool">All Pool Instances</option>
                        <option value="admin">All Admin Instances</option>
                        <option value="all">All Instances</option>
                    </select>
                </div>
                <button class="delete" onclick="bulkDelete()">Delete Selected</button>
            </div>
        </div>

        <div id="summary" class="summary"></div>

        <div class="instances-table">
            <div class="table-header">
                <h2>Instances</h2>
                <div style="display: flex; gap: 15px; align-items: center;">
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="showTerminated" onchange="refreshList()" style="width: auto; cursor: pointer;">
                        <span>Show terminated instances</span>
                    </label>
                    <button class="refresh-btn" onclick="refreshList()">🔄 Refresh</button>
                </div>
            </div>
            <div id="instancesList" class="loading">Loading instances...</div>
        </div>
    </div>

    <script>
        const API_URL = window.location.origin;

        function showMessage(text, type = 'success') {
            const messageDiv = document.getElementById('message');
            messageDiv.className = type;
            messageDiv.textContent = text;
            messageDiv.style.display = 'block';
            setTimeout(() => {
                messageDiv.style.display = 'none';
            }, 5000);
        }

        async function createInstances(count, type, cleanupDays = null) {
            try {
                showMessage('Creating instances...', 'success');
                const payload = {count, type};
                if (type === 'admin' && cleanupDays !== null) {
                    payload.cleanup_days = cleanupDays;
                }
                const response = await fetch(`${API_URL}/create`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (data.success) {
                    const message = data.message || `✅ Created ${data.count} ${type} instance(s)`;
                    showMessage(message, 'success');
                    // Refresh immediately to show the new instances
                    refreshList();
                    // Auto-refresh after a few seconds to show updated states
                    setTimeout(refreshList, 5000);
                } else {
                    showMessage(`❌ Error: ${data.error}`, 'error');
                }
            } catch (error) {
                showMessage(`❌ Error: ${error.message}`, 'error');
            }
        }

        async function deleteInstance(instanceId) {
            if (!confirm(`Delete instance ${instanceId}?`)) return;
            try {
                const response = await fetch(`${API_URL}/delete?instance_id=${instanceId}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                if (data.success) {
                    const message = data.message || `✅ Deleted instance ${instanceId}`;
                    showMessage(message, 'success');
                    // Refresh immediately
                    refreshList();
                    // Auto-refresh after a few seconds to show updated states
                    setTimeout(refreshList, 3000);
                } else {
                    showMessage(`❌ Error: ${data.error}`, 'error');
                }
            } catch (error) {
                showMessage(`❌ Error: ${error.message}`, 'error');
            }
        }

        async function bulkDelete() {
            const deleteType = document.getElementById('deleteType').value;
            const typeName = deleteType === 'all' ? 'all instances' : `all ${deleteType} instances`;
            if (!confirm(`Delete ${typeName}? This action cannot be undone.`)) return;
            
            try {
                showMessage('Deleting instances...', 'success');
                const response = await fetch(`${API_URL}/delete?delete_type=${deleteType}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                if (data.success) {
                    const message = data.message || `✅ Deleted ${data.count} instance(s)`;
                    showMessage(message, 'success');
                    // Refresh immediately
                    refreshList();
                    // Auto-refresh after a few seconds to show updated states
                    setTimeout(refreshList, 3000);
                } else {
                    showMessage(`❌ Error: ${data.error || 'Unknown error'}`, 'error');
                }
            } catch (error) {
                showMessage(`❌ Error: ${error.message}`, 'error');
            }
        }

        async function refreshList() {
            const listDiv = document.getElementById('instancesList');
            listDiv.innerHTML = '<div class="loading">Loading instances...</div>';
            
            // Get the show terminated checkbox value
            const showTerminated = document.getElementById('showTerminated').checked;
            // Add timestamp to prevent caching
            const timestamp = new Date().getTime();
            const baseUrl = `${API_URL}/list`;
            const params = new URLSearchParams();
            if (showTerminated) {
                params.append('include_terminated', 'true');
            }
            params.append('_t', timestamp.toString());
            const url = `${baseUrl}?${params.toString()}`;
            
            try {
                const response = await fetch(url, {
                    cache: 'no-cache',
                    headers: {
                        'Cache-Control': 'no-cache'
                    }
                });
                const data = await response.json();
                
                if (!data.success) {
                    listDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                    return;
                }

                // Update summary (only active instances: running and stopped)
                const summaryDiv = document.getElementById('summary');
                const summary = data.summary;
                
                // Debug logging
                console.log('[Instance Manager] Summary data:', summary);
                console.log('[Instance Manager] Total instances in response:', data.instances.length);
                console.log('[Instance Manager] Active instances (summary.total):', summary.total);
                
                summaryDiv.innerHTML = `
                    <div class="summary-card">
                        <h3>Active Instances<br><small style="font-size: 0.7em; font-weight: normal;">(Running & Stopped)</small></h3>
                        <div class="number">${summary.total}</div>
                    </div>
                    <div class="summary-card">
                        <h3>Pool Instances<br><small style="font-size: 0.7em; font-weight: normal;">(Running & Stopped)</small></h3>
                        <div class="number">${summary.pool.total}</div>
                        <small>Running: ${summary.pool.running} | Stopped: ${summary.pool.stopped} | Assigned: ${summary.pool.assigned}</small>
                    </div>
                    <div class="summary-card">
                        <h3>Admin Instances<br><small style="font-size: 0.7em; font-weight: normal;">(Running & Stopped)</small></h3>
                        <div class="number">${summary.admin.total}</div>
                        <small>Running: ${summary.admin.running} | Stopped: ${summary.admin.stopped}</small>
                    </div>
                `;

                // Build table
                if (data.instances.length === 0) {
                    listDiv.innerHTML = '<div class="loading">No instances found</div>';
                    return;
                }

                let tableHTML = '<table><thead><tr><th>Instance ID</th><th>Type</th><th>State</th><th>Public IP</th><th>Assigned To</th><th>Days Remaining</th><th>Actions</th></tr></thead><tbody>';
                
                data.instances.forEach(instance => {
                    const typeBadge = `<span class="badge ${instance.type}">${instance.type}</span>`;
                    const stateBadge = `<span class="badge ${instance.state}">${instance.state}</span>`;
                    
                    // Assigned To column: show badge if assigned, or button if unassigned pool instance
                    let assignedBadge;
                    if (instance.assigned_to) {
                        assignedBadge = `<span class="badge assigned">${instance.assigned_to}</span>`;
                    } else if (instance.type === 'pool' && instance.state !== 'terminated') {
                        // Show assignment button for unassigned pool instances
                        assignedBadge = `<button class="btn-small" style="background: #4caf50; padding: 4px 8px; font-size: 11px;" onclick="assignInstance('${instance.instance_id}')">Assign</button>`;
                    } else {
                        assignedBadge = '<span>-</span>';
                    }
                    
                    // Make public IP a clickable link if available
                    let publicIpCell;
                    if (instance.public_ip) {
                        publicIpCell = `<a href="http://${instance.public_ip}" target="_blank">${instance.public_ip}</a>`;
                    } else {
                        publicIpCell = '-';
                    }
                    
                    // Only show delete button if instance is not terminated
                    const deleteButton = instance.state === 'terminated' 
                        ? '<span style="color: #999;">-</span>'
                        : `<button class="delete btn-small" onclick="deleteInstance('${instance.instance_id}')">Delete</button>`;
                    
                    // Days remaining display for admin instances
                    let daysRemainingCell = '-';
                    if (instance.type === 'admin' && instance.cleanup_days_remaining !== null && instance.cleanup_days_remaining !== undefined) {
                        const daysRemaining = instance.cleanup_days_remaining;
                        const daysTotal = instance.cleanup_days || 7;
                        let daysClass = 'days-remaining';
                        let daysStyle = '';
                        
                        if (daysRemaining <= 0) {
                            daysClass += ' expired';
                            daysRemainingCell = `<span class="${daysClass}" style="color: #c62828; font-weight: bold;">Expired</span>`;
                        } else if (daysRemaining <= 2) {
                            daysClass += ' critical';
                            daysRemainingCell = `<span class="${daysClass}" style="color: #f57c00; font-weight: bold;">${daysRemaining} day${daysRemaining !== 1 ? 's' : ''}</span>`;
                        } else if (daysRemaining <= 7) {
                            daysClass += ' warning';
                            daysRemainingCell = `<span class="${daysClass}" style="color: #ff9800;">${daysRemaining} day${daysRemaining !== 1 ? 's' : ''}</span>`;
                        } else {
                            daysRemainingCell = `<span class="${daysClass}" style="color: #388e3c;">${daysRemaining} day${daysRemaining !== 1 ? 's' : ''}</span>`;
                        }
                        
                        // Add extend button for admin instances
                        if (instance.state !== 'terminated') {
                            daysRemainingCell += `<br><button class="btn-small" style="background: #4caf50; margin-top: 4px; padding: 4px 8px; font-size: 11px;" onclick="extendCleanupDays('${instance.instance_id}', ${daysTotal})">Extend</button>`;
                        }
                    }
                    
                    tableHTML += `
                        <tr>
                            <td><code>${instance.instance_id}</code></td>
                            <td>${typeBadge}</td>
                            <td>${stateBadge}</td>
                            <td>${publicIpCell}</td>
                            <td>${assignedBadge}</td>
                            <td>${daysRemainingCell}</td>
                            <td>${deleteButton}</td>
                        </tr>
                    `;
                });
                
                tableHTML += '</tbody></table>';
                listDiv.innerHTML = tableHTML;
            } catch (error) {
                listDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            }
        }

        // Form handlers
        document.getElementById('createPoolForm').addEventListener('submit', (e) => {
            e.preventDefault();
            const count = parseInt(document.getElementById('poolCount').value);
            createInstances(count, 'pool');
        });

        document.getElementById('createAdminForm').addEventListener('submit', (e) => {
            e.preventDefault();
            const count = parseInt(document.getElementById('adminCount').value);
            const cleanupDays = parseInt(document.getElementById('adminCleanupDays').value);
            createInstances(count, 'admin', cleanupDays);
        });
        
        async function extendCleanupDays(instanceId, currentDays) {
            const newDays = prompt(`Current cleanup days: ${currentDays}\nEnter new number of days (1-365):`, currentDays + 7);
            if (!newDays) return;
            
            const days = parseInt(newDays);
            if (isNaN(days) || days < 1 || days > 365) {
                showMessage('Invalid number of days. Must be between 1 and 365.', 'error');
                return;
            }
            
            try {
                showMessage('Updating cleanup days...', 'success');
                const response = await fetch(`${API_URL}/update_cleanup_days`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({instance_id: instanceId, cleanup_days: days})
                });
                const data = await response.json();
                if (data.success) {
                    showMessage(data.message || `✅ Updated cleanup days to ${days}`, 'success');
                    refreshList();
                    setTimeout(refreshList, 2000);
                } else {
                    showMessage(`❌ Error: ${data.error}`, 'error');
                }
            } catch (error) {
                showMessage(`❌ Error: ${error.message}`, 'error');
            }
        }

        async function assignInstance(instanceId) {
            const studentName = prompt(`Enter student name to assign instance ${instanceId}:`);
            if (!studentName || !studentName.trim()) {
                return;
            }
            
            try {
                showMessage('Assigning instance...', 'success');
                const response = await fetch(`${API_URL}/assign`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({instance_id: instanceId, student_name: studentName.trim()})
                });
                const data = await response.json();
                if (data.success) {
                    showMessage(data.message || `✅ Assigned instance to ${studentName}`, 'success');
                    refreshList();
                    setTimeout(refreshList, 2000);
                } else {
                    showMessage(`❌ Error: ${data.error}`, 'error');
                }
            } catch (error) {
                showMessage(`❌ Error: ${error.message}`, 'error');
            }
        }

        // Initial load
        refreshList();
        setInterval(refreshList, 30000); // Auto-refresh every 30 seconds
    </script>
</body>
</html>"""
