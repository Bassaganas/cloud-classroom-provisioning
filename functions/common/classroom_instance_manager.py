import json
import boto3
import os
import sys
import logging
import time
import urllib.request
import urllib.error
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import base64

# Initialize test mode BEFORE boto3 clients are created
# This allows moto mocks to intercept all boto3 calls during testing
try:
    from common import test_mode as test_mode_module
    test_mode_module.init_test_mode()
except ImportError:
    # test_mode module not available (production Lambda) - continue normally
    pass

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Log module initialization
logger.info("=" * 60)
logger.info("Module classroom_instance_manager.py loaded")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"File location: {__file__}")

# Get region from environment variable (Lambda automatically sets AWS_REGION)
REGION = os.environ.get('CLASSROOM_REGION', os.environ.get('AWS_REGION', 'eu-west-3'))
WORKSHOP_NAME = os.environ.get('WORKSHOP_NAME', 'classroom')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

logger.info(f"REGION: {REGION}")
logger.info(f"WORKSHOP_NAME: {WORKSHOP_NAME}")
logger.info(f"ENVIRONMENT: {ENVIRONMENT}")
logger.info("=" * 60)

# Initialize AWS clients
try:
    logger.info("Initializing AWS clients...")
    ec2 = boto3.client('ec2', region_name=REGION)
    elbv2 = boto3.client('elbv2', region_name=REGION)
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    dynamodb_client = boto3.client('dynamodb', region_name=REGION)
    table = dynamodb.Table(f"instance-assignments-{WORKSHOP_NAME}-{ENVIRONMENT}")
    # Tutorial sessions table - note: table name will be determined per workshop
    logger.info(f"AWS clients initialized. Table: instance-assignments-{WORKSHOP_NAME}-{ENVIRONMENT}")
except Exception as e:
    logger.error(f"Error initializing AWS clients: {str(e)}", exc_info=True)
    raise

def get_tutorial_sessions_table(workshop_name=None):
    """Get the tutorial sessions DynamoDB table for a workshop"""
    workshop = workshop_name or WORKSHOP_NAME
    return dynamodb.Table(f"tutorial-sessions-{workshop}-{ENVIRONMENT}")

def convert_decimal(obj):
    """Convert Decimal objects to int or float for JSON serialization"""
    if isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(item) for item in obj]
    return obj

def parse_bool(value):
    """Parse a value into boolean, returning None when ambiguous."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, Decimal)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ['true', '1', 'yes', 'y', 'on']:
            return True
        if normalized in ['false', '0', 'no', 'n', 'off']:
            return False
    return None

# Get configuration from environment variables
INSTANCE_TYPE = os.environ.get('EC2_INSTANCE_TYPE', 't3.medium')
SUBNET_ID = os.environ.get('EC2_SUBNET_ID')
SECURITY_GROUP_IDS = os.environ.get('EC2_SECURITY_GROUP_IDS', '').split(',') if os.environ.get('EC2_SECURITY_GROUP_IDS') else []
IAM_INSTANCE_PROFILE = os.environ.get('EC2_IAM_INSTANCE_PROFILE', f'ec2-ssm-profile-{WORKSHOP_NAME}-{ENVIRONMENT}')

# Initialize Secrets Manager client for password authentication
secretsmanager = boto3.client('secretsmanager', region_name=REGION)
ssm = boto3.client('ssm', region_name=REGION)
PASSWORD_SECRET_NAME = os.environ.get('INSTANCE_MANAGER_PASSWORD_SECRET', '')
TEMPLATE_MAP_PARAMETER = os.environ.get(
    'INSTANCE_MANAGER_TEMPLATE_MAP_PARAMETER',
    f'/classroom/templates/{ENVIRONMENT}'
)
HTTPS_BASE_DOMAIN = os.environ.get('INSTANCE_MANAGER_BASE_DOMAIN', '')
HTTPS_HOSTED_ZONE_ID = os.environ.get('INSTANCE_MANAGER_HOSTED_ZONE_ID', '')
HTTPS_CERT_ARN = os.environ.get('INSTANCE_MANAGER_HTTPS_CERT_ARN', '')
HTTPS_ALB_NAME = f"classroom-https-{ENVIRONMENT}"
HTTPS_ALB_SG_NAME = f"classroom-https-sg-{ENVIRONMENT}"

# Cache for password (to avoid repeated Secrets Manager calls)
_password_cache = None
_template_map_cache = None
_template_map_cache_time = None
# Cache TTL: Reduced to 60 seconds for faster template updates during development
# Can be overridden via TEMPLATE_MAP_CACHE_TTL environment variable
TEMPLATE_MAP_CACHE_TTL = int(os.environ.get('TEMPLATE_MAP_CACHE_TTL', '60'))

HEALTH_CHECK_CONFIG = {
    'fellowship': {'endpoint': '/api/health', 'port': 5000, 'timeout': 2.0},
    'testus_patronus': {'endpoint': '/health', 'port': 5000, 'timeout': 2.0},
}

def get_health_check_config(workshop_name):
    """Get health check config for workshop. Returns None if not configured."""
    if not workshop_name:
        return None
    normalized = str(workshop_name).strip().lower().replace('-', '_')
    if normalized in ['fellowship_of_the_build']:
        normalized = 'fellowship'
    return HEALTH_CHECK_CONFIG.get(normalized)

def check_instance_health(public_ip, workshop_name):
    """Check instance health endpoint. Returns (status, checked_at_iso, error_message)."""
    checked_at = datetime.now(timezone.utc).isoformat()
    config = get_health_check_config(workshop_name)

    if not config:
        return None, checked_at, 'Health check not configured for workshop'

    if not public_ip:
        return 'unreachable', checked_at, 'Instance has no public IP'

    url = f"http://{public_ip}:{config['port']}{config['endpoint']}"
    request = urllib.request.Request(url, method='GET')

    try:
        with urllib.request.urlopen(request, timeout=config['timeout']) as response:
            status_code = response.getcode()
            if 200 <= status_code < 300:
                return 'healthy', checked_at, None
            return 'unhealthy', checked_at, f'HTTP {status_code}'
    except urllib.error.HTTPError as error:
        return 'unhealthy', checked_at, f'HTTP {error.code}'
    except Exception as error:
        return 'unreachable', checked_at, str(error)

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

def get_timeout_parameters(workshop_name=None):
    """Get timeout parameters from SSM Parameter Store for a workshop, with defaults as fallback
    
    Args:
        workshop_name: Workshop identifier (defaults to WORKSHOP_NAME)
    
    Returns:
        dict with keys: stop_timeout, terminate_timeout, hard_terminate_timeout, admin_cleanup_days
    """
    workshop_name = workshop_name or WORKSHOP_NAME
    parameter_prefix = f'/classroom/{workshop_name}/{ENVIRONMENT}'
    
    defaults = {
        'stop_timeout': 4,  # minutes
        'terminate_timeout': 20,  # minutes
        'hard_terminate_timeout': 45,  # minutes
        'admin_cleanup_days': 7  # days
    }
    
    try:
        response = ssm.get_parameters(
            Names=[
                f"{parameter_prefix}/instance_stop_timeout_minutes",
                f"{parameter_prefix}/instance_terminate_timeout_minutes",
                f"{parameter_prefix}/instance_hard_terminate_timeout_minutes",
                f"{parameter_prefix}/admin_cleanup_interval_days"
            ],
            WithDecryption=False
        )
        
        # Create a dictionary of parameters
        parameters = {}
        for param in response.get('Parameters', []):
            param_name = param['Name'].split('/')[-1]
            if 'stop_timeout' in param_name:
                parameters['stop_timeout'] = int(param['Value'])
            elif 'terminate_timeout' in param_name:
                parameters['terminate_timeout'] = int(param['Value'])
            elif 'hard_terminate_timeout' in param_name:
                parameters['hard_terminate_timeout'] = int(param['Value'])
            elif 'admin_cleanup' in param_name:
                parameters['admin_cleanup_days'] = int(param['Value'])
        
        # Use defaults for missing parameters
        result = {**defaults, **parameters}
        logger.info(f"Loaded timeout parameters for {workshop_name}: {result}")
        return result
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            logger.info(f"Timeout parameters not found for {workshop_name}, using defaults")
            return defaults
        logger.warning(f"Error retrieving timeout parameters: {str(e)}, using defaults")
        return defaults
    except Exception as e:
        logger.error(f"Unexpected error retrieving timeout parameters: {str(e)}, using defaults")
        return defaults

def update_timeout_parameters(workshop_name, stop_timeout=None, terminate_timeout=None, 
                              hard_terminate_timeout=None, admin_cleanup_days=None):
    """Update timeout parameters in SSM Parameter Store for a workshop
    
    Args:
        workshop_name: Workshop identifier
        stop_timeout: Minutes before stopping unassigned running instances
        terminate_timeout: Minutes before terminating stopped instances
        hard_terminate_timeout: Minutes before hard terminating any instance
        admin_cleanup_days: Days before admin instances are deleted
    
    Returns:
        dict with success status and updated parameters
    """
    parameter_prefix = f'/classroom/{workshop_name}/{ENVIRONMENT}'
    updated = {}
    
    try:
        if stop_timeout is not None:
            ssm.put_parameter(
                Name=f"{parameter_prefix}/instance_stop_timeout_minutes",
                Value=str(int(stop_timeout)),
                Type='String',
                Overwrite=True,
                Description=f"Timeout in minutes before stopping unassigned running instances for {workshop_name}"
            )
            updated['stop_timeout'] = int(stop_timeout)
        
        if terminate_timeout is not None:
            ssm.put_parameter(
                Name=f"{parameter_prefix}/instance_terminate_timeout_minutes",
                Value=str(int(terminate_timeout)),
                Type='String',
                Overwrite=True,
                Description=f"Timeout in minutes before terminating stopped instances for {workshop_name}"
            )
            updated['terminate_timeout'] = int(terminate_timeout)
        
        if hard_terminate_timeout is not None:
            ssm.put_parameter(
                Name=f"{parameter_prefix}/instance_hard_terminate_timeout_minutes",
                Value=str(int(hard_terminate_timeout)),
                Type='String',
                Overwrite=True,
                Description=f"Timeout in minutes before hard terminating any instance for {workshop_name}"
            )
            updated['hard_terminate_timeout'] = int(hard_terminate_timeout)
        
        if admin_cleanup_days is not None:
            ssm.put_parameter(
                Name=f"{parameter_prefix}/admin_cleanup_interval_days",
                Value=str(int(admin_cleanup_days)),
                Type='String',
                Overwrite=True,
                Description=f"Days before admin instances are automatically deleted for {workshop_name}"
            )
            updated['admin_cleanup_days'] = int(admin_cleanup_days)
        
        logger.info(f"Updated timeout parameters for {workshop_name}: {updated}")
        return {'success': True, 'updated': updated}
        
    except Exception as e:
        logger.error(f"Error updating timeout parameters: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_template_map():
    """Load workshop template map from SSM Parameter Store
    
    Prioritizes individual parameters first (new approach), then falls back to combined map (backward compatibility)
    Cache expires after 60 seconds to ensure fresh templates are loaded
    """
    global _template_map_cache, _template_map_cache_time

    # Check if cache is still valid (within TTL)
    if _template_map_cache is not None and _template_map_cache_time is not None:
        cache_age = time.time() - _template_map_cache_time
        if cache_age < TEMPLATE_MAP_CACHE_TTL:
            logger.info(f"Using cached template map (age: {int(cache_age)}s, TTL: {TEMPLATE_MAP_CACHE_TTL}s)")
            return _template_map_cache
        else:
            logger.info(f"Template cache expired (age: {int(cache_age)}s, TTL: {TEMPLATE_MAP_CACHE_TTL}s), refreshing...")
            _template_map_cache = None
            _template_map_cache_time = None

    if not TEMPLATE_MAP_PARAMETER:
        logger.warning("INSTANCE_MANAGER_TEMPLATE_MAP_PARAMETER not set, workshop selection disabled")
        _template_map_cache = {}
        return _template_map_cache

    template_map = {}
    loaded_from_individual = False
    
    # PRIORITY 1: Try to load individual workshop templates first (new approach, more reliable)
    # This avoids issues with old combined maps that may have outdated templates
    # The base path (e.g., /classroom/templates/dev) is used to construct individual paths:
    # - /classroom/templates/dev/fellowship
    # - /classroom/templates/dev/testus_patronus
    # - /classroom/templates/dev/fellowship-of-the-build
    workshop_names = ['fellowship', 'testus_patronus']
    
    logger.info(f"Attempting to load individual workshop templates from base path: {TEMPLATE_MAP_PARAMETER}")
    
    for workshop_name in workshop_names:
        try:
            workshop_param = f"{TEMPLATE_MAP_PARAMETER}/{workshop_name}"
            logger.info(f"Trying to load template from: {workshop_param}")
            response = ssm.get_parameter(Name=workshop_param)
            workshop_template = json.loads(response['Parameter']['Value'])
            template_map[workshop_name] = workshop_template
            logger.info(f"✓ Successfully loaded template for workshop: {workshop_name} from {workshop_param}")
            loaded_from_individual = True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.debug(f"Template not found for {workshop_name} at {workshop_param} (this is OK if workshop doesn't exist)")
            else:
                logger.warning(f"Error retrieving template for {workshop_name} from {workshop_param}: {str(e)}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid template JSON for {workshop_name} from {workshop_param}: {str(e)}")
        except Exception as e:
            logger.warning(f"Unexpected error retrieving template for {workshop_name} from {workshop_param}: {str(e)}")
    
    # If we successfully loaded individual parameters, use them
    if loaded_from_individual and len(template_map) > 0:
        _template_map_cache = template_map
        _template_map_cache_time = time.time()
        logger.info(f"Loaded workshop template map with {len(_template_map_cache)} entries (from individual parameters)")
        logger.info(f"Template cache keys: {list(_template_map_cache.keys())}")
        return _template_map_cache
    
    # PRIORITY 2: Fallback to combined map (backward compatibility)
    # Only use this if individual parameters don't exist
    logger.info("Individual parameters not found or empty, trying combined template map (backward compatibility)")
    try:
        response = ssm.get_parameter(Name=TEMPLATE_MAP_PARAMETER)
        template_map = json.loads(response['Parameter']['Value'])
        if isinstance(template_map, dict) and len(template_map) > 0:
            _template_map_cache = template_map
            _template_map_cache_time = time.time()
            logger.info(f"Loaded workshop template map from combined parameter with {len(_template_map_cache)} entries")
            logger.info(f"Template cache keys: {list(_template_map_cache.keys())}")
            logger.warning("Using combined template map - consider migrating to individual parameters for better reliability")
            return _template_map_cache
    except ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            logger.warning("Combined template map also not found - no templates available")
        else:
            logger.warning(f"Error retrieving combined template map from SSM: {str(e)}")
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid template map JSON in SSM: {str(e)}")
    except Exception as e:
        logger.warning(f"Unexpected error retrieving combined template map: {str(e)}")
    
    # No templates found
    _template_map_cache = {}
    _template_map_cache_time = time.time()
    logger.warning("No workshop templates found in SSM (neither individual parameters nor combined map)")
    return _template_map_cache

def clear_template_cache():
    """Clear the template cache to force refresh on next access"""
    global _template_map_cache, _template_map_cache_time
    _template_map_cache = None
    _template_map_cache_time = None
    logger.info("Template cache cleared")

def get_template_for_workshop(workshop_name):
    """Get the template config for a given workshop"""
    template_map = get_template_map()
    if not template_map:
        logger.warning(f"Template map is empty, cannot get template for workshop: {workshop_name}")
        return None
    
    template = template_map.get(workshop_name)
    if template:
        logger.info(f"Found template for workshop: {workshop_name}")
    else:
        logger.warning(f"No template found for workshop: {workshop_name}")
        logger.info(f"Available workshops in template map: {list(template_map.keys())}")
    return template

def get_default_vpc_id():
    response = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    vpcs = response.get('Vpcs', [])
    if not vpcs:
        raise RuntimeError("No default VPC found for HTTPS ALB")
    return vpcs[0]['VpcId']

def get_default_subnet_ids(vpc_id):
    response = ec2.describe_subnets(Filters=[
        {'Name': 'vpc-id', 'Values': [vpc_id]},
        {'Name': 'default-for-az', 'Values': ['true']}
    ])
    subnets = response.get('Subnets', [])
    if len(subnets) < 2:
        raise RuntimeError("Need at least two default subnets for ALB")
    return [subnet['SubnetId'] for subnet in subnets]

def ensure_https_security_group(vpc_id):
    response = ec2.describe_security_groups(Filters=[
        {'Name': 'group-name', 'Values': [HTTPS_ALB_SG_NAME]},
        {'Name': 'vpc-id', 'Values': [vpc_id]}
    ])
    groups = response.get('SecurityGroups', [])
    if groups:
        return groups[0]['GroupId']

    sg = ec2.create_security_group(
        GroupName=HTTPS_ALB_SG_NAME,
        Description=f"ALB security group for HTTPS instances ({ENVIRONMENT})",
        VpcId=vpc_id,
        TagSpecifications=[{
            'ResourceType': 'security-group',
            'Tags': [
                {'Key': 'Project', 'Value': 'classroom'},
                {'Key': 'Environment', 'Value': ENVIRONMENT},
                {'Key': 'Company', 'Value': 'TestingFantasy'}
            ]
        }]
    )
    sg_id = sg['GroupId']
    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 443,
            'ToPort': 443,
            'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTPS'}]
        }]
    )
    return sg_id

def ensure_https_alb():
    try:
        response = elbv2.describe_load_balancers(Names=[HTTPS_ALB_NAME])
        lbs = response.get('LoadBalancers', [])
        if lbs:
            return lbs[0]
    except ClientError as e:
        if e.response['Error']['Code'] != 'LoadBalancerNotFound':
            raise

    vpc_id = get_default_vpc_id()
    subnet_ids = get_default_subnet_ids(vpc_id)
    sg_id = ensure_https_security_group(vpc_id)

    lb = elbv2.create_load_balancer(
        Name=HTTPS_ALB_NAME,
        Subnets=subnet_ids,
        SecurityGroups=[sg_id],
        Scheme='internet-facing',
        Type='application',
        IpAddressType='ipv4',
        Tags=[
            {'Key': 'Project', 'Value': 'classroom'},
            {'Key': 'Environment', 'Value': ENVIRONMENT},
            {'Key': 'Company', 'Value': 'TestingFantasy'}
        ]
    )
    return lb['LoadBalancers'][0]

def ensure_https_listener(load_balancer_arn):
    listeners = elbv2.describe_listeners(LoadBalancerArn=load_balancer_arn).get('Listeners', [])
    for listener in listeners:
        if listener.get('Port') == 443:
            return listener

    listener = elbv2.create_listener(
        LoadBalancerArn=load_balancer_arn,
        Protocol='HTTPS',
        Port=443,
        Certificates=[{'CertificateArn': HTTPS_CERT_ARN}],
        DefaultActions=[{
            'Type': 'fixed-response',
            'FixedResponseConfig': {
                'StatusCode': '404',
                'ContentType': 'text/plain',
                'MessageBody': 'Not found'
            }
        }]
    )
    return listener['Listeners'][0]

def get_next_rule_priority(listener_arn):
    rules = elbv2.describe_rules(ListenerArn=listener_arn).get('Rules', [])
    priorities = [int(r['Priority']) for r in rules if r.get('Priority') not in ['default', None]]
    return max(priorities, default=0) + 1

def sanitize_domain_name(domain):
    """Sanitize domain name by replacing invalid DNS characters.
    
    DNS domain names can only contain letters, numbers, hyphens, and dots.
    Underscores are not valid in DNS names and will cause Let's Encrypt to reject certificates.
    
    Args:
        domain: Domain name string (may contain underscores or other invalid chars)
    
    Returns:
        Sanitized domain name with underscores replaced by hyphens
    """
    # Replace underscores with hyphens (most common invalid character)
    # Also ensure no double hyphens are created
    sanitized = domain.replace('_', '-')
    # Remove any double hyphens that might result
    while '--' in sanitized:
        sanitized = sanitized.replace('--', '-')
    return sanitized

def setup_caddy_domain(instance_id, workshop_name, machine_name=None, domain=None):
    """Setup Caddy domain with Route53 A record and instance tags
    
    Uses predictable machine names (e.g., 'fellowship-pool-0') instead of instance IDs
    to avoid timing issues. Domain is known before instance creation.
    
    Args:
        instance_id: EC2 instance ID
        workshop_name: Workshop identifier (e.g., 'fellowship', 'testus_patronus')
        machine_name: Optional predictable machine name (e.g., 'fellowship-pool-0')
        domain: Optional pre-computed domain name (if provided, machine_name is ignored)
    
    Returns:
        dict with domain and https_url, or None if domain setup is skipped
    """
    if not HTTPS_BASE_DOMAIN or not HTTPS_HOSTED_ZONE_ID:
        logger.warning("HTTPS_BASE_DOMAIN or HTTPS_HOSTED_ZONE_ID not configured, skipping Caddy domain setup")
        return None
    
    try:
        # Use provided domain or construct from machine_name, fallback to instance_id
        if domain:
            final_domain = sanitize_domain_name(domain)
        elif machine_name:
            # Sanitize machine_name before using it in domain
            sanitized_machine_name = sanitize_domain_name(machine_name)
            final_domain = f"{sanitized_machine_name}.{workshop_name}.{HTTPS_BASE_DOMAIN}"
        else:
            # Fallback to instance ID (backward compatibility)
            final_domain = f"{instance_id}.{workshop_name}.{HTTPS_BASE_DOMAIN}"
        
        # Ensure the final domain is sanitized (in case workshop_name or HTTPS_BASE_DOMAIN has issues)
        final_domain = sanitize_domain_name(final_domain)
        
        https_url = f"https://{final_domain}"
        
        # Get instance public IP (with retries - instance may not have IP immediately)
        public_ip = None
        for attempt in range(1, 6):
            try:
                response = ec2.describe_instances(InstanceIds=[instance_id])
                if response.get('Reservations') and response['Reservations'][0].get('Instances'):
                    instance = response['Reservations'][0]['Instances'][0]
                    public_ip = instance.get('PublicIpAddress')
                    if public_ip:
                        logger.info(f"Got public IP for {instance_id}: {public_ip} (attempt {attempt})")
                        break
            except Exception as e:
                logger.warning(f"Error getting instance info (attempt {attempt}): {str(e)}")
            
            if attempt < 5:
                time.sleep(2)
        
        # Create/update Route53 A record
        route53 = boto3.client('route53')
        if public_ip:
            route53.change_resource_record_sets(
                HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': final_domain,
                            'Type': 'A',
                            'TTL': 300,
                            'ResourceRecords': [{'Value': public_ip}]
                        }
                    }]
                }
            )
            logger.info(f"Created Route53 A record: {final_domain} -> {public_ip}")
        else:
            logger.warning(f"Instance {instance_id} has no public IP yet, Route53 record will be created when IP is available")
            logger.info(f"  Domain: {final_domain} (will be updated when instance gets public IP)")
            # Note: Route53 record will be created/updated when IP becomes available
            # The tags are already set, so setup script can use the domain immediately
        
        # Update instance tags (may already be set, but ensure they're correct)
        ec2.create_tags(
            Resources=[instance_id],
            Tags=[
                {'Key': 'HttpsDomain', 'Value': final_domain},
                {'Key': 'HttpsUrl', 'Value': https_url},
                {'Key': 'HttpsEnabled', 'Value': 'true'}
            ]
        )
        logger.info(f"Updated instance tags with HTTPS domain: {final_domain}")
        
        return {
            'domain': final_domain,
            'https_url': https_url,
            'public_ip': public_ip
        }
    except Exception as e:
        logger.error(f"Error setting up Caddy domain for {instance_id}: {str(e)}", exc_info=True)
        return None

def create_route53_alias(record_name, lb_dns, lb_zone_id):
    """Legacy ALB function - kept for backward compatibility but not used with Caddy"""
    if not HTTPS_HOSTED_ZONE_ID:
        raise RuntimeError("INSTANCE_MANAGER_HOSTED_ZONE_ID is not configured")

    route53 = boto3.client('route53')
    route53.change_resource_record_sets(
        HostedZoneId=HTTPS_HOSTED_ZONE_ID,
        ChangeBatch={
            'Changes': [{
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': record_name,
                    'Type': 'A',
                    'AliasTarget': {
                        'HostedZoneId': lb_zone_id,
                        'DNSName': lb_dns,
                        'EvaluateTargetHealth': False
                    }
                }
            }]
        }
    )

def delete_route53_alias(record_name, lb_dns, lb_zone_id):
    if not HTTPS_HOSTED_ZONE_ID:
        return
    route53 = boto3.client('route53')
    route53.change_resource_record_sets(
        HostedZoneId=HTTPS_HOSTED_ZONE_ID,
        ChangeBatch={
            'Changes': [{
                'Action': 'DELETE',
                'ResourceRecordSet': {
                    'Name': record_name,
                    'Type': 'A',
                    'AliasTarget': {
                        'HostedZoneId': lb_zone_id,
                        'DNSName': lb_dns,
                        'EvaluateTargetHealth': False
                    }
                }
            }]
        }
    )

def enable_https_for_instance(instance_id, workshop_name, app_port):
    if not HTTPS_CERT_ARN or not HTTPS_BASE_DOMAIN:
        raise RuntimeError("HTTPS certificate or base domain is not configured")

    lb = ensure_https_alb()
    listener = ensure_https_listener(lb['LoadBalancerArn'])

    vpc_id = get_default_vpc_id()
    target_group_name = f"cls-https-{ENVIRONMENT}-{instance_id[-8:]}"[:32]
    target_group = elbv2.create_target_group(
        Name=target_group_name,
        Protocol='HTTP',
        Port=app_port,
        VpcId=vpc_id,
        TargetType='instance',
        HealthCheckProtocol='HTTP',
        HealthCheckPort=str(app_port),
        HealthCheckPath='/'
    )
    target_group_arn = target_group['TargetGroups'][0]['TargetGroupArn']
    elbv2.register_targets(TargetGroupArn=target_group_arn, Targets=[{'Id': instance_id, 'Port': app_port}])

    if SECURITY_GROUP_IDS:
        try:
            ec2.authorize_security_group_ingress(
                GroupId=SECURITY_GROUP_IDS[0],
                IpPermissions=[{
                    'IpProtocol': 'tcp',
                    'FromPort': app_port,
                    'ToPort': app_port,
                    'UserIdGroupPairs': [{'GroupId': lb['SecurityGroups'][0]}]
                }]
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'InvalidPermission.Duplicate':
                raise

    record_name = f"{instance_id}.{workshop_name}.{HTTPS_BASE_DOMAIN}"
    rule_priority = get_next_rule_priority(listener['ListenerArn'])
    rule = elbv2.create_rule(
        ListenerArn=listener['ListenerArn'],
        Priority=rule_priority,
        Conditions=[{
            'Field': 'host-header',
            'HostHeaderConfig': {'Values': [record_name]}
        }],
        Actions=[{
            'Type': 'forward',
            'TargetGroupArn': target_group_arn
        }]
    )
    rule_arn = rule['Rules'][0]['RuleArn']

    create_route53_alias(record_name, lb['DNSName'], lb['CanonicalHostedZoneId'])

    # Tag instance for traceability
    ec2.create_tags(
        Resources=[instance_id],
        Tags=[
            {'Key': 'HttpsEnabled', 'Value': 'true'},
            {'Key': 'HttpsDomain', 'Value': record_name},
            {'Key': 'HttpsTargetGroupArn', 'Value': target_group_arn},
            {'Key': 'HttpsListenerRuleArn', 'Value': rule_arn},
            {'Key': 'AppPort', 'Value': str(app_port)}
        ]
    )

    return {
        'domain': f"https://{record_name}",
        'target_group_arn': target_group_arn,
        'rule_arn': rule_arn
    }

def disable_https_for_instance(instance_id, workshop_name, tags):
    lb = ensure_https_alb()
    record_name = tags.get('HttpsDomain') or f"{instance_id}.{workshop_name}.{HTTPS_BASE_DOMAIN}"
    target_group_arn = tags.get('HttpsTargetGroupArn')
    rule_arn = tags.get('HttpsListenerRuleArn')

    if rule_arn:
        try:
            elbv2.delete_rule(RuleArn=rule_arn)
        except Exception as e:
            logger.warning(f"Failed to delete listener rule: {str(e)}")

    if target_group_arn:
        try:
            elbv2.delete_target_group(TargetGroupArn=target_group_arn)
        except Exception as e:
            logger.warning(f"Failed to delete target group: {str(e)}")

    try:
        delete_route53_alias(record_name, lb['DNSName'], lb['CanonicalHostedZoneId'])
    except Exception as e:
        logger.warning(f"Failed to delete Route53 record: {str(e)}")

    # Remove HTTPS tags
    ec2.create_tags(
        Resources=[instance_id],
        Tags=[
            {'Key': 'HttpsEnabled', 'Value': 'false'}
        ]
    )

    return {'domain': record_name}

def check_password_auth(body, query_params):
    """Check if the provided password matches the secret (simplified auth for single-user)"""
    password = get_password_from_secret()
    if not password:
        # If no password is configured, allow access (backward compatibility)
        return True
    
    # Get password from body or query params
    provided_password = body.get('password') or query_params.get('password', '')
    if not provided_password:
        return False
    
    # Simple password comparison
    return provided_password == password

def get_user_data_script(template_config=None):
    """Get the user_data script content"""
    if template_config:
        user_data_base64 = template_config.get('user_data_base64')
        if user_data_base64:
            try:
                user_data = base64.b64decode(user_data_base64).decode('utf-8')
                logger.info(f"Successfully decoded user_data from template (length: {len(user_data)} chars)")
                # Log first few lines to verify it's the correct script
                first_lines = '\n'.join(user_data.split('\n')[:5])
                logger.info(f"User data script preview:\n{first_lines}...")
                return user_data
            except Exception as e:
                logger.warning(f"Failed to decode user_data_base64: {str(e)}")
        else:
            logger.warning("Template config provided but user_data_base64 is missing")
    else:
        logger.warning("No template config provided, using fallback user_data script")

    # Fallback to inline script if template data is missing
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
    """Get the latest Amazon Linux 2 AMI for the current region"""
    try:
        response = ec2.describe_images(
            Owners=['amazon'],
            Filters=[
                {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
                {'Name': 'virtualization-type', 'Values': ['hvm']},
                {'Name': 'state', 'Values': ['available']}
            ],
            MostRecent=True
        )
        if response['Images']:
            ami_id = response['Images'][0]['ImageId']
            logger.info(f"Found latest Amazon Linux 2 AMI: {ami_id} in region {REGION}")
            return ami_id
        else:
            error_msg = f"No Amazon Linux 2 AMI found in region {REGION}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Error getting AMI in region {REGION}: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

def create_instance(count=1, instance_type='pool', cleanup_days=None, workshop_name=None,
                    stop_timeout=None, terminate_timeout=None, hard_terminate_timeout=None,
                    tutorial_session_id=None, purchase_type='on-demand', spot_duration_hours=2,
                    spot_max_price=None):
    """Create EC2 instance(s) for a workshop template
    
    Args:
        count: Number of instances to create
        instance_type: 'pool' for pool instances or 'admin' for admin instances
        cleanup_days: Number of days before admin instances are deleted (only for admin instances, default: 7)
        workshop_name: Workshop identifier used to select template
        stop_timeout: Minutes before stopping unassigned running instances (optional, uses SSM default if not provided)
        terminate_timeout: Minutes before terminating stopped instances (optional, uses SSM default if not provided)
        hard_terminate_timeout: Minutes before hard terminating any instance (optional, uses SSM default if not provided)
        tutorial_session_id: Tutorial session ID to tag instances with (optional)
        purchase_type: 'on-demand' or 'spot' for EC2 instance purchase type (default: 'on-demand')
        spot_duration_hours: Deprecated, ignored for regular Spot instances
        spot_max_price: Optional maximum Spot price in USD/hour (string or Decimal)
    """
    try:
        if purchase_type == 'spot':
            if spot_max_price is not None:
                try:
                    spot_max_price = Decimal(str(spot_max_price))
                    if spot_max_price <= 0:
                        logger.warning(f"Invalid spot_max_price ({spot_max_price}); ignoring and using market default")
                        spot_max_price = None
                except (TypeError, ValueError, InvalidOperation):
                    logger.warning(f"Invalid spot_max_price format ({spot_max_price}); ignoring and using market default")
                    spot_max_price = None
        
        workshop_name = workshop_name or WORKSHOP_NAME
        logger.info("=" * 80)
        logger.info(f"INSTANCE CREATION REQUEST")
        logger.info(f"  Workshop: {workshop_name}")
        logger.info(f"  Instance Type: {instance_type}")
        logger.info(f"  Count: {count}")
        logger.info(f"  Purchase Type: {purchase_type}")
        if purchase_type == 'spot':
            logger.info(f"  Spot Max Price: {spot_max_price if spot_max_price is not None else 'market default'}")
        logger.info(f"  Tutorial Session ID: {tutorial_session_id}")
        logger.info(f"  Region: {REGION}")
        logger.info(f"  Environment: {ENVIRONMENT}")
        logger.info("=" * 80)
        
        template_config = get_template_for_workshop(workshop_name)
        
        if not template_config:
            logger.error(f"❌ No template found for workshop: {workshop_name}")
            logger.info("Available templates will be logged by get_template_map()")
            # Log available templates for debugging
            template_map = get_template_map()
            if template_map:
                logger.info(f"Available workshops in template map: {list(template_map.keys())}")
            else:
                logger.warning("Template map is empty - no templates loaded from SSM")
        else:
            logger.info(f"✓ Template found for workshop: {workshop_name}")
            logger.info(f"  Template keys: {list(template_config.keys())}")
            logger.info(f"  Has user_data_base64: {'user_data_base64' in template_config}")
            logger.info(f"  AMI ID: {template_config.get('ami_id', 'NOT SET')}")
            logger.info(f"  Instance Type Override: {template_config.get('instance_type', 'NOT SET')}")
            logger.info(f"  App Port: {template_config.get('app_port', 'NOT SET')}")
            
            # Log SSM parameter path used
            ssm_param_path = f"{TEMPLATE_MAP_PARAMETER}/{workshop_name}"
            logger.info(f"  SSM Parameter Path: {ssm_param_path}")
        
        ami_id = template_config.get('ami_id') if template_config else None
        
        # If no AMI ID in template, try to get the latest Amazon Linux 2 AMI
        if not ami_id:
            logger.warning(f"No AMI ID found in template for workshop {workshop_name}, attempting to get latest Amazon Linux 2 AMI")
            try:
                ami_id = get_latest_ami()
            except RuntimeError as e:
                error_msg = f"Cannot create instances: {str(e)}. Please ensure the template for workshop '{workshop_name}' includes a valid 'ami_id' for region {REGION}."
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
        
        if not ami_id:
            error_msg = f"No AMI ID available for workshop {workshop_name} in region {REGION}. Please configure the template with a valid AMI ID."
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        
        instance_type_override = template_config.get('instance_type') if template_config else None
        selected_instance_type = instance_type_override or INSTANCE_TYPE
        logger.info(f"Selected instance type: {selected_instance_type} (override: {instance_type_override}, default: {INSTANCE_TYPE})")
        
        user_data = get_user_data_script(template_config)
        
        # Log user_data details for debugging
        logger.info("=" * 80)
        logger.info("USER DATA SCRIPT ANALYSIS")
        logger.info(f"  Script length: {len(user_data)} characters")
        logger.info(f"  Source: {'Template from SSM' if template_config and template_config.get('user_data_base64') else 'Fallback script'}")
        
        # Check for key markers in user_data
        markers = {
            'fellowship-sut': 'fellowship-sut' in user_data.lower(),
            'docker-compose': 'docker-compose' in user_data.lower() or 'docker compose' in user_data.lower(),
            'LOG_FILE': 'LOG_FILE' in user_data,
            'user-data.log': '/var/log/user-data.log' in user_data,
            'S3 download': 'aws s3 cp' in user_data or 's3://' in user_data,
            'SSM parameter': 'aws ssm get-parameter' in user_data,
            'devops-escape-room': 'devops-escape-room' in user_data.lower(),
            'dify': 'dify' in user_data.lower()
        }
        
        logger.info("  Script markers:")
        for marker, found in markers.items():
            status = "✓" if found else "✗"
            logger.info(f"    {status} {marker}: {found}")
        
        if workshop_name in ['fellowship', 'fellowship-of-the-build']:
            if markers['fellowship-sut']:
                logger.info("  ✓ Fellowship SUT deployment code DETECTED in user_data")
            else:
                logger.warning("  ⚠ Fellowship SUT deployment code NOT FOUND - instance will NOT have SUT deployed!")
        
        logger.info("=" * 80)
        
        # Get timeout parameters - use provided values or fall back to SSM defaults
        timeouts = get_timeout_parameters(workshop_name)
        final_stop_timeout = stop_timeout if stop_timeout is not None else timeouts.get('stop_timeout', 4)
        final_terminate_timeout = terminate_timeout if terminate_timeout is not None else timeouts.get('terminate_timeout', 20)
        final_hard_terminate_timeout = hard_terminate_timeout if hard_terminate_timeout is not None else timeouts.get('hard_terminate_timeout', 45)
        
        instances = []
        
        # Get the next instance index for this tutorial session
        # This ensures unique naming even if create_instance is called multiple times
        instance_index_offset = 0
        if tutorial_session_id:
            try:
                # Query for existing instances in this tutorial session
                ec2_filter_response = ec2.describe_instances(
                    Filters=[
                        {'Name': 'tag:TutorialSessionID', 'Values': [tutorial_session_id]},
                        {'Name': 'tag:Type', 'Values': [instance_type]},
                        {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopped']}
                    ]
                )
                existing_count = 0
                for reservation in ec2_filter_response.get('Reservations', []):
                    existing_count += len(reservation.get('Instances', []))
                instance_index_offset = existing_count
                logger.info(f"Found {existing_count} existing {instance_type} instances in session {tutorial_session_id}")
            except Exception as e:
                logger.warning(f"Could not query existing instances for session {tutorial_session_id}: {str(e)}, starting index from 0")
                instance_index_offset = 0
        
        for i in range(count):
            # Calculate actual instance index to ensure unique naming
            instance_index = instance_index_offset + i
            
            # Determine naming and tags based on type
            if instance_type == 'admin':
                name = f'{workshop_name}-admin-{instance_index}'
                if tutorial_session_id:
                    name = f'{workshop_name}-{tutorial_session_id}-admin-{instance_index}'
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
                    {'Key': 'CleanupDays', 'Value': cleanup_days_value},  # Days until cleanup
                    {'Key': 'WorkshopID', 'Value': workshop_name},
                    {'Key': 'Template', 'Value': workshop_name},
                    {'Key': 'AppPort', 'Value': str(template_config.get('app_port', 80)) if template_config else '80'},
                    {'Key': 'Company', 'Value': 'TestingFantasy'},
                    {'Key': 'StopTimeout', 'Value': str(final_stop_timeout)},
                    {'Key': 'TerminateTimeout', 'Value': str(final_terminate_timeout)},
                    {'Key': 'HardTerminateTimeout', 'Value': str(final_hard_terminate_timeout)}
                ]
            else:  # pool
                name = f'{workshop_name}-pool-{instance_index}'
                if tutorial_session_id:
                    name = f'{workshop_name}-{tutorial_session_id}-pool-{instance_index}'
                tags = [
                    {'Key': 'Name', 'Value': name},
                    {'Key': 'Status', 'Value': 'available'},
                    {'Key': 'Project', 'Value': 'classroom'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Type', 'Value': 'pool'},
                    {'Key': 'CreatedBy', 'Value': 'lambda-manager'},
                    {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()},
                    {'Key': 'WorkshopID', 'Value': workshop_name},
                    {'Key': 'Template', 'Value': workshop_name},
                    {'Key': 'AppPort', 'Value': str(template_config.get('app_port', 80)) if template_config else '80'},
                    {'Key': 'Company', 'Value': 'TestingFantasy'},
                    {'Key': 'StopTimeout', 'Value': str(final_stop_timeout)},
                    {'Key': 'TerminateTimeout', 'Value': str(final_terminate_timeout)},
                    {'Key': 'HardTerminateTimeout', 'Value': str(final_hard_terminate_timeout)}
                ]
            
            # Add TutorialSessionID tag if provided
            if tutorial_session_id:
                tags.append({'Key': 'TutorialSessionID', 'Value': tutorial_session_id})
            
            # Add spot instance tags if using spot
            if purchase_type == 'spot':
                tags.append({'Key': 'PurchaseType', 'Value': 'spot'})
                if spot_max_price is not None:
                    tags.append({'Key': 'SpotMaxPrice', 'Value': str(spot_max_price)})
            else:
                tags.append({'Key': 'PurchaseType', 'Value': 'on-demand'})
            # Generate predictable domain name BEFORE instance creation
            # This eliminates timing issues - domain is known immediately
            machine_name = name  # Use the same name as the instance name
            if HTTPS_BASE_DOMAIN and HTTPS_HOSTED_ZONE_ID:
                # Sanitize machine_name to ensure valid DNS characters
                sanitized_machine_name = sanitize_domain_name(machine_name)
                domain = f"{sanitized_machine_name}.{workshop_name}.{HTTPS_BASE_DOMAIN}"
                # Sanitize the entire domain to be safe
                domain = sanitize_domain_name(domain)
                https_url = f"https://{domain}"
                
                # Add domain tags BEFORE instance creation
                # This ensures setup script can read them immediately
                tags.append({'Key': 'HttpsDomain', 'Value': domain})
                tags.append({'Key': 'HttpsUrl', 'Value': https_url})
                tags.append({'Key': 'HttpsEnabled', 'Value': 'true'})
                tags.append({'Key': 'MachineName', 'Value': machine_name})  # Keep original for reference
                
                logger.info(f"Generated domain name BEFORE instance creation: {domain} (sanitized from machine_name: {machine_name})")
                
                # Inject domain information into user_data as environment variables
                # This ensures the domain is available immediately without needing EC2 metadata service
                domain_exports = f"""# Domain information injected by Lambda (available immediately)
export CADDY_DOMAIN={domain}
export MACHINE_NAME={machine_name}
export WORKSHOP_NAME={workshop_name}
"""
                
                # Inject after shebang and set -e, but before any other code
                if user_data.startswith('#!/bin/bash'):
                    lines = user_data.split('\n')
                    # Find where to insert (after shebang, after set -e if present)
                    insert_pos = 1
                    # Skip shebang
                    if len(lines) > 1:
                        # Check if second line is set -e or similar
                        if lines[1].strip().startswith('set '):
                            insert_pos = 2
                        # Check for comments after shebang
                        elif lines[1].strip().startswith('#'):
                            # Find first non-comment, non-empty line
                            for j in range(1, min(5, len(lines))):
                                if lines[j].strip() and not lines[j].strip().startswith('#'):
                                    insert_pos = j
                                    break
                    
                    # Insert domain exports
                    lines.insert(insert_pos, domain_exports.rstrip())
                    user_data = '\n'.join(lines)
                    logger.info(f"Injected domain information into user_data: CADDY_DOMAIN={domain}, MACHINE_NAME={machine_name}")
                else:
                    # No shebang, prepend
                    user_data = domain_exports + user_data
                    logger.info(f"Prepended domain information to user_data: CADDY_DOMAIN={domain}, MACHINE_NAME={machine_name}")
            else:
                domain = None
                machine_name = None
                logger.warning("HTTPS not configured - domain tags will not be set")
                logger.warning("  Domain will not be injected into user_data (HTTPS may not work initially)")
            
            logger.info("=" * 80)
            logger.info(f"LAUNCHING INSTANCE {i+1}/{count}")
            logger.info(f"  AMI ID: {ami_id}")
            logger.info(f"  Instance Type: {selected_instance_type}")
            logger.info(f"  IAM Instance Profile: {IAM_INSTANCE_PROFILE}")
            logger.info(f"  Subnet ID: {SUBNET_ID or 'Default VPC subnet'}")
            logger.info(f"  Security Groups: {SECURITY_GROUP_IDS if SECURITY_GROUP_IDS else 'Default'}")
            logger.info(f"  User Data Length: {len(user_data)} characters")
            logger.info(f"  User Data Preview (first 200 chars): {user_data[:200]}...")
            logger.info("=" * 80)
            
            # Build EC2 run_instances parameters
            run_instances_params = {
                'ImageId': ami_id,
                'InstanceType': selected_instance_type,
                'MinCount': 1,
                'MaxCount': 1,
                'UserData': user_data,
                'IamInstanceProfile': {'Name': IAM_INSTANCE_PROFILE},
                'SubnetId': SUBNET_ID if SUBNET_ID else None,
                'SecurityGroupIds': SECURITY_GROUP_IDS if SECURITY_GROUP_IDS else None,
                'TagSpecifications': [
                    {
                        'ResourceType': 'instance',
                        'Tags': tags
                    }
                ],
                'MetadataOptions': {
                    'HttpTokens': 'required',
                    'HttpEndpoint': 'enabled'
                },
                'BlockDeviceMappings': [
                    {
                        'DeviceName': '/dev/xvda',
                        'Ebs': {
                            'VolumeSize': 40,
                            'VolumeType': 'gp3',
                            'DeleteOnTermination': True
                        }
                    }
                ]
            }
            
            # Add spot instance options if using spot market
            if purchase_type == 'spot':
                run_instances_params['InstanceMarketOptions'] = {
                    'MarketType': 'spot',
                    'SpotOptions': {
                        'SpotInstanceType': 'persistent',
                        # Keep Spot instances stoppable and restartable for test workflows.
                        'InstanceInterruptionBehavior': 'stop'
                    }
                }
                if spot_max_price is not None:
                    run_instances_params['InstanceMarketOptions']['SpotOptions']['MaxPrice'] = str(spot_max_price)
                logger.info(f"  Purchase Type: SPOT (persistent with stop behavior)")
                logger.info(f"  SpotInstanceType: persistent")
                logger.info(f"  InstanceInterruptionBehavior: stop")
                logger.info(f"  Spot MaxPrice: {run_instances_params['InstanceMarketOptions']['SpotOptions'].get('MaxPrice', 'market default')}")
            else:
                logger.info(f"  Purchase Type: ON-DEMAND")
            
            response = ec2.run_instances(**run_instances_params)
            
            instance_id = response['Instances'][0]['InstanceId']
            initial_state = response['Instances'][0]['State']['Name']
            private_ip = response['Instances'][0].get('PrivateIpAddress', 'Not assigned yet')
            
            logger.info("=" * 80)
            logger.info(f"✓ INSTANCE CREATED SUCCESSFULLY")
            logger.info(f"  Instance ID: {instance_id}")
            logger.info(f"  Initial State: {initial_state}")
            logger.info(f"  Private IP: {private_ip}")
            logger.info(f"  Workshop: {workshop_name}")
            logger.info(f"  Purchase Type: {purchase_type.upper()}")
            logger.info(f"  Type: {instance_type}")
            logger.info(f"  Template Source: {ssm_param_path if template_config else 'FALLBACK (no template)'}")
            logger.info(f"  User Data Source: {'SSM Template' if template_config and template_config.get('user_data_base64') else 'Fallback Script'}")
            logger.info(f"  Tutorial Session: {tutorial_session_id or 'N/A'}")
            logger.info("=" * 80)
            
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
                'type': instance_type,
                'workshop': workshop_name,
                'purchase_type': purchase_type,
                'spot_max_price': float(spot_max_price) if (purchase_type == 'spot' and spot_max_price is not None) else None
            })
            
            logger.info(f"Created {instance_type} instance {instance_id} ({i+1}/{count}) - will be stopped automatically once running")
            
            # Setup Caddy domain (Route53 A record)
            # Domain name and tags are already set before instance creation
            # Now we just need to create/update the Route53 record with the public IP
            if domain and machine_name:
                caddy_setup = None
                max_retries = 5
                retry_delay = 10  # seconds
                
                for attempt in range(1, max_retries + 1):
                    try:
                        # Pass machine_name and domain to avoid reconstructing
                        caddy_setup = setup_caddy_domain(instance_id, workshop_name, machine_name=machine_name, domain=domain)
                        if caddy_setup:
                            logger.info(f"✓ Caddy domain setup (attempt {attempt}/{max_retries}): {caddy_setup['https_url']}")
                            # Update instance info with HTTPS URL
                            instances[-1]['https_url'] = caddy_setup['https_url']
                            instances[-1]['https_domain'] = caddy_setup['domain']
                            if caddy_setup.get('public_ip'):
                                logger.info(f"  Route53 record created: {caddy_setup['domain']} -> {caddy_setup['public_ip']}")
                            else:
                                logger.info(f"  Route53 record will be created when instance gets public IP: {caddy_setup['domain']}")
                            break
                        else:
                            if attempt < max_retries:
                                logger.info(f"⚠ Caddy domain setup attempt {attempt}/{max_retries} failed (no public IP yet), retrying in {retry_delay}s...")
                                time.sleep(retry_delay)
                            else:
                                logger.warning(f"⚠ Caddy Route53 record creation failed after {max_retries} attempts (instance may not have public IP yet)")
                                logger.info(f"   Domain tags are already set: {domain}")
                                logger.info(f"   Route53 record will be created automatically when instance gets public IP")
                                # Still add domain info to instance response (tags are already set)
                                instances[-1]['https_url'] = f"https://{domain}"
                                instances[-1]['https_domain'] = domain
                    except Exception as e:
                        if attempt < max_retries:
                            logger.warning(f"Error setting up Caddy domain (attempt {attempt}/{max_retries}): {str(e)}, retrying...")
                            time.sleep(retry_delay)
                        else:
                            logger.warning(f"Error setting up Caddy Route53 record after {max_retries} attempts (non-fatal): {str(e)}")
                            logger.info(f"   Domain tags are already set: {domain}")
                            # Still add domain info to instance response (tags are already set)
                            instances[-1]['https_url'] = f"https://{domain}"
                            instances[-1]['https_domain'] = domain
            else:
                logger.info("HTTPS not configured - skipping Caddy domain setup")
        
        return {
            'success': True,
            'instances': instances,
            'count': len(instances),
            'type': instance_type,
            'workshop': workshop_name
        }
    except Exception as e:
        logger.error(f"Error creating instances: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def list_instances(include_terminated=False, tutorial_session_id=None, include_health=False):
    """List all EC2 instances with their assignments and IPs
    
    Args:
        include_terminated: If True, include terminated instances in the results
        tutorial_session_id: If provided, filter instances by this tutorial session ID
        include_health: If True, fetch health status from workshop endpoint for each instance
    """
    try:
        # Get all instances (both pool and admin)
        # Note: terminated instances are automatically excluded by default
        filters = [
            {'Name': 'tag:Project', 'Values': ['classroom']}
        ]
        
        # Filter by tutorial session if provided
        if tutorial_session_id:
            filters.append({'Name': 'tag:TutorialSessionID', 'Values': [tutorial_session_id]})
        
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
                
                # Extract HTTPS info from tags
                https_domain = tags.get('HttpsDomain')
                https_url = tags.get('HttpsUrl')
                
                instance_info = {
                    'instance_id': instance_id,
                    'state': state,
                    'public_ip': instance.get('PublicIpAddress'),
                    'private_ip': instance.get('PrivateIpAddress'),
                    'instance_type': instance.get('InstanceType'),
                    'launch_time': instance.get('LaunchTime').isoformat() if instance.get('LaunchTime') else None,
                    'tags': tags,
                    'type': instance_type,
                    'workshop': tags.get('WorkshopID', tags.get('Template', 'unknown')),
                    'tutorial_session_id': tags.get('TutorialSessionID'),
                    'assigned_to': assignment.get('student_name'),
                    'assignment_status': assignment.get('status'),
                    'assigned_at': assignment.get('assigned_at'),
                    'cleanup_days': cleanup_days,  # Total cleanup days configured
                    'cleanup_days_remaining': cleanup_days_remaining,  # Days remaining before deletion
                    'https_domain': https_domain,  # HTTPS domain from tags
                    'https_url': https_url  # Full HTTPS URL from tags
                }

                if include_health:
                    workshop_for_health = tags.get('WorkshopID', tags.get('Template', WORKSHOP_NAME))
                    health_status, health_checked_at, health_error = check_instance_health(
                        instance.get('PublicIpAddress'),
                        workshop_for_health
                    )
                    instance_info['health_status'] = health_status
                    instance_info['health_checked_at'] = health_checked_at
                    if health_error:
                        instance_info['health_error'] = health_error
                
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
                # Check instance state and purchase type first
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
                    # Stop the instance (on-demand or spot)
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
                # Get instance tags before deletion to retrieve domain information
                instance_tags = {}
                domain_to_delete = None
                try:
                    response = ec2.describe_instances(InstanceIds=[instance_id])
                    if response.get('Reservations') and response['Reservations'][0].get('Instances'):
                        instance = response['Reservations'][0]['Instances'][0]
                        instance_tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                        domain_to_delete = instance_tags.get('HttpsDomain')
                except Exception as e:
                    logger.warning(f"Error getting instance tags for {instance_id}: {str(e)}")
                
                # Clean up Route53 record if domain exists
                if domain_to_delete and HTTPS_HOSTED_ZONE_ID:
                    try:
                        route53 = boto3.client('route53')
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

def get_cors_headers():
    """Get CORS headers for API responses"""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }

def get_swagger_spec():
    """Generate OpenAPI/Swagger specification for the API"""
    base_url = os.environ.get('API_GATEWAY_URL', '')
    if base_url and not base_url.endswith('/'):
        base_url += '/'
    
    swagger_spec = {
        'openapi': '3.0.0',
        'info': {
            'title': 'EC2 Instance Manager API',
            'description': 'REST API for managing EC2 classroom instances',
            'version': '1.0.0'
        },
        'servers': [
            {
                'url': base_url if base_url else 'https://api.example.com',
                'description': 'API Gateway endpoint'
            }
        ],
        'paths': {
            '/api/health': {
                'get': {
                    'summary': 'Health check',
                    'description': 'Check if the API is healthy',
                    'responses': {
                        '200': {
                            'description': 'API is healthy',
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'status': {'type': 'string'},
                                            'timestamp': {'type': 'string'},
                                            'environment': {'type': 'string'},
                                            'workshop_name': {'type': 'string'},
                                            'region': {'type': 'string'}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            '/api/login': {
                'post': {
                    'summary': 'Login',
                    'description': 'Authenticate with password',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'password': {'type': 'string'}
                                    },
                                    'required': ['password']
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {'description': 'Authentication successful'},
                        '401': {'description': 'Invalid password'}
                    }
                }
            },
            '/api/templates': {
                'get': {
                    'summary': 'Get workshop templates',
                    'description': 'Get available workshop templates',
                    'responses': {
                        '200': {
                            'description': 'List of templates',
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'success': {'type': 'boolean'},
                                            'templates': {'type': 'object'}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            '/api/list': {
                'get': {
                    'summary': 'List instances',
                    'description': 'List all EC2 instances',
                    'parameters': [
                        {
                            'name': 'password',
                            'in': 'query',
                            'required': True,
                            'schema': {'type': 'string'}
                        },
                        {
                            'name': 'include_terminated',
                            'in': 'query',
                            'required': False,
                            'schema': {'type': 'boolean'}
                        },
                        {
                            'name': 'include_health',
                            'in': 'query',
                            'required': False,
                            'schema': {'type': 'boolean'}
                        }
                    ],
                    'responses': {
                        '200': {'description': 'List of instances'},
                        '401': {'description': 'Authentication required'}
                    }
                }
            },
            '/api/create': {
                'post': {
                    'summary': 'Create instances',
                    'description': 'Create EC2 instances',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'count': {'type': 'integer'},
                                        'type': {'type': 'string', 'enum': ['pool', 'admin']},
                                        'workshop': {'type': 'string'},
                                        'cleanup_days': {'type': 'integer'},
                                        'password': {'type': 'string'}
                                    },
                                    'required': ['count', 'type']
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {'description': 'Instances created'},
                        '400': {'description': 'Invalid request'},
                        '401': {'description': 'Authentication required'}
                    }
                }
            },
            '/api/assign': {
                'post': {
                    'summary': 'Assign instance',
                    'description': 'Assign an instance to a student',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'instance_id': {'type': 'string'},
                                        'student_name': {'type': 'string'},
                                        'password': {'type': 'string'}
                                    },
                                    'required': ['instance_id', 'student_name']
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {'description': 'Instance assigned'},
                        '400': {'description': 'Invalid request'},
                        '401': {'description': 'Authentication required'}
                    }
                }
            },
            '/api/delete': {
                'post': {
                    'summary': 'Delete instances',
                    'description': 'Delete EC2 instances',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'instance_ids': {'type': 'array', 'items': {'type': 'string'}},
                                        'instance_id': {'type': 'string'},
                                        'delete_type': {'type': 'string'},
                                        'password': {'type': 'string'}
                                    }
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {'description': 'Instances deleted'},
                        '401': {'description': 'Authentication required'}
                    }
                }
            },
            '/api/stop': {
                'post': {
                    'summary': 'Stop instances',
                    'description': 'Stop EC2 instances',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'instance_ids': {'type': 'array', 'items': {'type': 'string'}},
                                        'instance_id': {'type': 'string'},
                                        'password': {'type': 'string'}
                                    }
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {'description': 'Instances stopped'},
                        '401': {'description': 'Authentication required'}
                    }
                }
            },
            '/api/timeout_settings': {
                'get': {
                    'summary': 'Get timeout settings',
                    'description': 'Get timeout settings for a workshop',
                    'parameters': [
                        {
                            'name': 'workshop',
                            'in': 'query',
                            'required': True,
                            'schema': {'type': 'string'}
                        },
                        {
                            'name': 'password',
                            'in': 'query',
                            'required': True,
                            'schema': {'type': 'string'}
                        }
                    ],
                    'responses': {
                        '200': {'description': 'Timeout settings'},
                        '401': {'description': 'Authentication required'}
                    }
                }
            },
            '/api/update_timeout_settings': {
                'post': {
                    'summary': 'Update timeout settings',
                    'description': 'Update timeout settings for a workshop',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'workshop': {'type': 'string'},
                                        'stop_timeout': {'type': 'integer'},
                                        'terminate_timeout': {'type': 'integer'},
                                        'hard_terminate_timeout': {'type': 'integer'},
                                        'admin_cleanup_days': {'type': 'integer'},
                                        'password': {'type': 'string'}
                                    },
                                    'required': ['workshop']
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {'description': 'Settings updated'},
                        '401': {'description': 'Authentication required'}
                    }
                }
            }
        }
    }
    
    return {
        'statusCode': 200,
        'headers': get_cors_headers(),
        'body': json.dumps(swagger_spec, indent=2)
    }

def normalize_event(event):
    """Normalize Function URL and API Gateway events to common format
    
    Supports both:
    - Lambda Function URL format: event['requestContext']['http']['method']
    - API Gateway format: event['httpMethod']
    """
    # Check if it's API Gateway format (has httpMethod at root level)
    if 'httpMethod' in event:
        # API Gateway format
        return {
            'method': event.get('httpMethod', 'GET'),
            'path': event.get('path', '/'),
            'queryParams': event.get('queryStringParameters') or {},
            'body': event.get('body', ''),
            'headers': event.get('headers', {})
        }
    else:
        # Function URL format (existing)
        request_context = event.get('requestContext', {})
        http_context = request_context.get('http', {})
        return {
            'method': http_context.get('method', 'GET'),
            'path': http_context.get('path', '/'),
            'queryParams': event.get('queryStringParameters') or {},
            'body': event.get('body', ''),
            'headers': event.get('headers', {})
        }

def lambda_handler(event, context):
    """Lambda handler for EC2 instance pool management - API only
    
    Supports both Lambda Function URL and API Gateway event formats
    """
    logger.info("=" * 50)
    logger.info("Lambda handler invoked")
    logger.info(f"Event type: {type(event)}")
    logger.info(f"Event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}")
    logger.info(f"Context: {context}")
    
    try:
        # Normalize event format (supports both Function URL and API Gateway)
        normalized = normalize_event(event)
        http_method = normalized['method']
        path = normalized['path']
        query_params = normalized['queryParams']
        body_str = normalized['body']
        headers = normalized['headers']
        
        logger.info(f"HTTP Method: {http_method}, Path: {path}")
        logger.info(f"Event format: {'API Gateway' if 'httpMethod' in event else 'Function URL'}")
        
        # Handle OPTIONS for CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': ''
            }
        
        # Strip stage prefix if present (e.g., /dev/api/login -> /api/login)
        # API Gateway stage paths are typically /dev, /prod, /staging, etc.
        normalized_path = path
        if '/' in path[1:]:  # Check if there's a second slash (stage prefix)
            parts = path.split('/', 3)  # Split into ['', 'dev', 'api', 'login']
            if len(parts) >= 3 and parts[2] == 'api':
                # Path has stage prefix: /dev/api/login -> /api/login
                normalized_path = '/api/' + '/'.join(parts[3:]) if len(parts) > 3 else '/api'
                logger.info(f"Stripped stage prefix: {path} -> {normalized_path}")
            elif len(parts) >= 2 and parts[1] in ['swagger.json', 'dev', 'staging', 'prod']:
                # Handle swagger.json at root level (e.g., /dev/swagger.json -> /swagger.json)
                if parts[1] == 'swagger.json':
                    normalized_path = '/swagger.json'
                elif len(parts) >= 3 and parts[2] == 'swagger.json':
                    normalized_path = '/swagger.json'
                    logger.info(f"Stripped stage prefix: {path} -> {normalized_path}")
        
        # Handle swagger.json endpoint (no authentication required)
        if normalized_path == '/swagger.json' and http_method == 'GET':
            return get_swagger_spec()
        
        # Only handle /api/* paths - let CloudFront route everything else to S3
        if not normalized_path.startswith('/api'):
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'success': False,
                    'error': 'Not found - API endpoints must start with /api'
                })
            }
        
        # Remove /api prefix for routing
        api_path = normalized_path[4:] if normalized_path.startswith('/api') else normalized_path
        
        # Parse body if it exists
        body = {}
        if body_str:
            try:
                # API Gateway may pass body as string, Function URL may pass as dict
                if isinstance(body_str, str):
                    body = json.loads(body_str) if body_str else {}
                else:
                    body = body_str
            except (json.JSONDecodeError, TypeError):
                body = {}
        
        # Handle health/live endpoint (no authentication required)
        if api_path == '/health' and http_method == 'GET':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'status': 'ok',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'environment': ENVIRONMENT,
                    'workshop_name': WORKSHOP_NAME,
                    'region': REGION,
                    'message': 'Instance Manager API is healthy'
                })
            }
        
        # Handle login endpoint (no authentication required)
        if api_path == '/login' and http_method == 'POST':
            password = get_password_from_secret()
            if not password:
                # No password configured, allow access
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': True,
                        'message': 'No password configured, access granted'
                    })
                }
            
            provided_password = body.get('password') or query_params.get('password', '')
            if provided_password == password:
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': True,
                        'message': 'Authentication successful'
                    })
                }
            else:
                return {
                    'statusCode': 401,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': 'Invalid password'
                    })
                }
        
        # Check authentication for all other endpoints (simplified: password in body/query)
        if not check_password_auth(body, query_params):
            # Password is configured but not provided or incorrect
            return {
                'statusCode': 401,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'success': False,
                    'error': 'Authentication required. Please provide password in request body or query parameter.',
                    'requires_auth': True
                })
            }
        
        # Route based on method and path (api_path already has /api removed)
        if api_path == '/templates' and http_method == 'GET':
            # Return workshop templates for landing page
            template_map = get_template_map()
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'success': True,
                    'templates': template_map
                })
            }
        
        if api_path == '/create' and http_method == 'POST':
            count = int(body.get('count', query_params.get('count', 1)))
            instance_type = body.get('type', query_params.get('type', 'pool'))
            cleanup_days = body.get('cleanup_days') or query_params.get('cleanup_days')
            workshop_name = body.get('workshop') or query_params.get('workshop') or WORKSHOP_NAME
            purchase_type = body.get('purchase_type') or query_params.get('purchase_type', 'on-demand')
            spot_max_price_raw = body.get('spot_max_price') or query_params.get('spot_max_price')
            if cleanup_days is not None:
                cleanup_days = int(cleanup_days)

            spot_max_price = None
            if spot_max_price_raw not in [None, '']:
                try:
                    spot_max_price = Decimal(str(spot_max_price_raw))
                    if spot_max_price <= 0:
                        return {
                            'statusCode': 400,
                            'headers': get_cors_headers(),
                            'body': json.dumps({
                                'success': False,
                                'error': 'spot_max_price must be greater than 0'
                            })
                        }
                except (TypeError, ValueError, InvalidOperation):
                    return {
                        'statusCode': 400,
                        'headers': get_cors_headers(),
                        'body': json.dumps({
                            'success': False,
                            'error': 'spot_max_price must be a valid number'
                        })
                    }
            
            # Get timeout parameters from request or use defaults
            stop_timeout = body.get('stop_timeout') or query_params.get('stop_timeout')
            terminate_timeout = body.get('terminate_timeout') or query_params.get('terminate_timeout')
            hard_terminate_timeout = body.get('hard_terminate_timeout') or query_params.get('hard_terminate_timeout')
            
            if count < 1 or count > 120:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': 'Count must be between 1 and 120'
                    })
                }
            
            if instance_type not in ['pool', 'admin']:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': 'Type must be "pool" or "admin"'
                    })
                }

            if purchase_type not in ['on-demand', 'spot']:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': 'purchase_type must be "on-demand" or "spot"'
                    })
                }

            if instance_type == 'admin' and cleanup_days is not None:
                if cleanup_days < 1 or cleanup_days > 365:
                    return {
                        'statusCode': 400,
                        'headers': get_cors_headers(),
                        'body': json.dumps({
                            'success': False,
                            'error': 'Cleanup days must be between 1 and 365'
                        })
                    }
            
            template_map = get_template_map()
            if template_map and workshop_name not in template_map:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': f'Unknown workshop: {workshop_name}',
                        'available_workshops': sorted(template_map.keys())
                    })
                }

            # Get optional tutorial_session_id
            tutorial_session_id = body.get('tutorial_session_id') or query_params.get('tutorial_session_id')

            # Enforce tutorial-level purchase policy when creating inside a tutorial session
            if tutorial_session_id:
                try:
                    sessions_table = get_tutorial_sessions_table(workshop_name)
                    session_response = sessions_table.get_item(Key={'session_id': tutorial_session_id})
                    session_item = session_response.get('Item')

                    if not session_item:
                        return {
                            'statusCode': 404,
                            'headers': get_cors_headers(),
                            'body': json.dumps({
                                'success': False,
                                'error': f'Tutorial session {tutorial_session_id} not found for workshop {workshop_name}'
                            })
                        }

                    productive_tutorial = parse_bool(session_item.get('productive_tutorial'))
                    if productive_tutorial is None:
                        productive_tutorial = session_item.get('purchase_type', 'on-demand') == 'on-demand'

                    if productive_tutorial:
                        purchase_type = 'on-demand'
                        spot_max_price = None
                    else:
                        purchase_type = 'spot'
                        stored_spot_max_price = session_item.get('spot_max_price')
                        try:
                            spot_max_price = Decimal(str(stored_spot_max_price)) if stored_spot_max_price not in [None, ''] else spot_max_price
                        except (TypeError, ValueError, InvalidOperation):
                            pass
                except Exception as e:
                    logger.error(f"Failed to enforce tutorial purchase policy for {tutorial_session_id}: {str(e)}", exc_info=True)
                    return {
                        'statusCode': 500,
                        'headers': get_cors_headers(),
                        'body': json.dumps({
                            'success': False,
                            'error': 'Failed to resolve tutorial purchase policy'
                        })
                    }
            
            result = create_instance(
                count=count,
                instance_type=instance_type,
                cleanup_days=cleanup_days,
                workshop_name=workshop_name,
                stop_timeout=stop_timeout,
                terminate_timeout=terminate_timeout,
                hard_terminate_timeout=hard_terminate_timeout,
                tutorial_session_id=tutorial_session_id,
                purchase_type=purchase_type,
                spot_max_price=spot_max_price
            )
            # Add a message indicating the operation is async
            if result['success']:
                result['message'] = f"✅ Initiated creation of {result['count']} {instance_type} instance(s). They will be stopped automatically once running. Refresh to see updates."
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': get_cors_headers(),
                'body': json.dumps(result)
            }
        
        elif api_path == '/list' and http_method == 'GET':
            # Check if include_terminated parameter is set
            include_terminated = query_params.get('include_terminated', 'false').lower() == 'true'
            # Check if include_health parameter is set (manual/on-demand only)
            include_health = query_params.get('include_health', 'false').lower() == 'true'
            # Check if tutorial_session_id filter is provided
            tutorial_session_id = query_params.get('tutorial_session_id')
            result = list_instances(
                include_terminated=include_terminated,
                tutorial_session_id=tutorial_session_id,
                include_health=include_health
            )
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': get_cors_headers(),
                'body': json.dumps(result, indent=2)
            }
        
        elif api_path == '/update_cleanup_days' and http_method == 'POST':
            # Update cleanup days for an admin instance
            instance_id = body.get('instance_id') or query_params.get('instance_id')
            new_cleanup_days = body.get('cleanup_days') or query_params.get('cleanup_days')
            
            if not instance_id:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': 'instance_id is required'
                    })
                }
            
            if new_cleanup_days is None:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
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
                        'headers': get_cors_headers(),
                        'body': json.dumps({
                            'success': False,
                            'error': 'Cleanup days must be between 1 and 365'
                        })
                    }
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
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
                        'headers': get_cors_headers(),
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
                        'headers': get_cors_headers(),
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
                    'headers': get_cors_headers(),
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
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': str(e)
                    })
                }
        
        elif api_path == '/assign' and http_method == 'POST':
            # Manual assignment endpoint
            instance_id = body.get('instance_id') or query_params.get('instance_id')
            student_name = body.get('student_name') or query_params.get('student_name')
            
            if not instance_id:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': 'instance_id is required'
                    })
                }
            
            if not student_name:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
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
                        'headers': get_cors_headers(),
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
                        'headers': get_cors_headers(),
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
                            'headers': get_cors_headers(),
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
                        {'Key': 'Student', 'Value': student_name},
                        {'Key': 'Company', 'Value': 'TestingFantasy'}
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
                        {'Key': 'Student', 'Value': student_name},
                        {'Key': 'Company', 'Value': 'TestingFantasy'}
                    ]
                )
                
                logger.info(f"Manually assigned instance {instance_id} to {student_name}")
                
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
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
                        'headers': get_cors_headers(),
                        'body': json.dumps({
                            'success': False,
                            'error': 'Instance is already assigned or assignment in progress'
                        })
                    }
                logger.error(f"Error assigning instance: {str(e)}")
                return {
                    'statusCode': 500,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': str(e)
                    })
                }
            except Exception as e:
                logger.error(f"Error assigning instance: {str(e)}", exc_info=True)
                return {
                    'statusCode': 500,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': False,
                        'error': str(e)
                    })
                }
        
        elif api_path == '/stop' and http_method == 'POST':
            instance_ids = body.get('instance_ids') or (query_params.get('instance_ids', '').split(',') if query_params.get('instance_ids') else None)
            
            if not instance_ids:
                instance_id = body.get('instance_id') or query_params.get('instance_id')
                if instance_id:
                    instance_ids = [instance_id]
                else:
                    return {
                        'statusCode': 400,
                        'headers': get_cors_headers(),
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
                'headers': get_cors_headers(),
                'body': json.dumps(result)
            }
        
        elif api_path == '/delete' and http_method in ['DELETE', 'POST']:
            instance_ids = body.get('instance_ids') or (query_params.get('instance_ids', '').split(',') if query_params.get('instance_ids') else None)
            delete_type = body.get('delete_type', query_params.get('delete_type', 'individual'))
            
            if delete_type == 'individual' and not instance_ids:
                instance_id = body.get('instance_id') or query_params.get('instance_id')
                if instance_id:
                    instance_ids = [instance_id]
                else:
                    return {
                        'statusCode': 400,
                        'headers': get_cors_headers(),
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
                'headers': get_cors_headers(),
                'body': json.dumps(result)
            }

        elif api_path == '/bulk_delete' and http_method == 'POST':
            # Alias for /delete with delete_type
            delete_type = body.get('delete_type') or query_params.get('delete_type', 'pool')
            result = delete_instances(instance_ids=[], delete_type=delete_type)
            if result['success']:
                result['message'] = f"✅ Initiated deletion of {result['count']} instance(s). Termination is in progress. Refresh to see updates."
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': get_cors_headers(),
                'body': json.dumps(result)
            }

        elif api_path == '/enable_https' and http_method == 'POST':
            instance_id = body.get('instance_id') or query_params.get('instance_id')
            if not instance_id:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'instance_id is required'})
                }

            instance = ec2.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            workshop_name = tags.get('WorkshopID') or WORKSHOP_NAME
            template_config = get_template_for_workshop(workshop_name) or {}
            app_port = int(template_config.get('app_port') or tags.get('AppPort') or 80)

            result = enable_https_for_instance(instance_id, workshop_name, app_port)
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({'success': True, 'domain': result['domain']})
            }

        elif api_path == '/delete_https' and http_method == 'POST':
            instance_id = body.get('instance_id') or query_params.get('instance_id')
            if not instance_id:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'instance_id is required'})
                }

            instance = ec2.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            workshop_name = tags.get('WorkshopID') or WORKSHOP_NAME
            result = disable_https_for_instance(instance_id, workshop_name, tags)
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({'success': True, 'domain': result['domain']})
            }
        
        elif api_path == '/timeout_settings' and http_method == 'GET':
            workshop_name = query_params.get('workshop')
            if not workshop_name:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'Workshop name is required'})
                }
            
            timeouts = get_timeout_parameters(workshop_name)
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({'success': True, 'settings': timeouts, 'timeouts': timeouts})
            }
        
        elif api_path == '/update_timeout_settings' and http_method == 'POST':
            workshop_name = body.get('workshop')
            stop_timeout = body.get('stop_timeout')
            terminate_timeout = body.get('terminate_timeout')
            hard_terminate_timeout = body.get('hard_terminate_timeout')
            admin_cleanup_days = body.get('admin_cleanup_days')
            
            if not workshop_name:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'Workshop name is required'})
                }
            
            result = update_timeout_parameters(
                workshop_name,
                stop_timeout=stop_timeout,
                terminate_timeout=terminate_timeout,
                hard_terminate_timeout=hard_terminate_timeout,
                admin_cleanup_days=admin_cleanup_days
            )
            return {
                'statusCode': 200 if result['success'] else 500,
                'headers': get_cors_headers(),
                'body': json.dumps(result)
            }
        
        elif api_path == '/create_tutorial_session' and http_method == 'POST':
            # Create a new tutorial session
            session_id = body.get('session_id')
            workshop_name = body.get('workshop_name')
            pool_count = int(body.get('pool_count', 0))
            admin_count = int(body.get('admin_count', 0))
            admin_cleanup_days = int(body.get('admin_cleanup_days', 7))
            productive_tutorial = parse_bool(body.get('productive_tutorial', False))

            if productive_tutorial is None:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'productive_tutorial must be a boolean'})
                }

            if productive_tutorial:
                purchase_type = 'on-demand'
                spot_max_price = None
            else:
                purchase_type = 'spot'
                spot_max_price_raw = body.get('spot_max_price')
                spot_max_price = None
                if spot_max_price_raw not in [None, '']:
                    try:
                        spot_max_price = Decimal(str(spot_max_price_raw))
                        if spot_max_price <= 0:
                            return {
                                'statusCode': 400,
                                'headers': get_cors_headers(),
                                'body': json.dumps({'success': False, 'error': 'spot_max_price must be greater than 0'})
                            }
                    except (TypeError, ValueError, InvalidOperation):
                        return {
                            'statusCode': 400,
                            'headers': get_cors_headers(),
                            'body': json.dumps({'success': False, 'error': 'spot_max_price must be a valid number'})
                        }
            
            if not session_id:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'session_id is required'})
                }
            
            if not workshop_name:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'workshop_name is required'})
                }
            
            if pool_count < 0 or admin_count < 0:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'Counts must be non-negative'})
                }
            
            if pool_count == 0 and admin_count == 0:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'At least one pool or admin instance must be created'})
                }

            try:
                # Get tutorial sessions table for this workshop
                sessions_table = get_tutorial_sessions_table(workshop_name)
                table_name = f"tutorial-sessions-{workshop_name}-{ENVIRONMENT}"
                
                # Verify table exists by attempting to describe it
                try:
                    dynamodb_client.describe_table(TableName=table_name)
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        return {
                            'statusCode': 500,
                            'headers': get_cors_headers(),
                            'body': json.dumps({
                                'success': False,
                                'error': f'DynamoDB table "{table_name}" does not exist. Please deploy the infrastructure first using: ./scripts/setup_classroom.sh --name my-classroom --cloud aws --region eu-west-3 --workshop {workshop_name} --environment {ENVIRONMENT}'
                            })
                        }
                    # Re-raise if it's a different ClientError
                    raise
                except Exception as e:
                    logger.warning(f"Error describing table {table_name}: {str(e)}")
                
                # Check if session already exists
                try:
                    existing = sessions_table.get_item(Key={'session_id': session_id})
                    if 'Item' in existing:
                        return {
                            'statusCode': 409,
                            'headers': get_cors_headers(),
                            'body': json.dumps({'success': False, 'error': f'Session {session_id} already exists for workshop {workshop_name}'})
                        }
                except Exception as e:
                    logger.warning(f"Error checking existing session: {str(e)}")
                
                # Create session record in DynamoDB
                session_item = {
                    'session_id': session_id,
                    'workshop_name': workshop_name,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'pool_count': pool_count,
                    'admin_count': admin_count,
                    'admin_cleanup_days': admin_cleanup_days,
                    'productive_tutorial': productive_tutorial,
                    'purchase_type': purchase_type,
                    'spot_max_price': spot_max_price if purchase_type == 'spot' else None,
                    'status': 'creating'
                }
                sessions_table.put_item(Item=session_item)
                
                # Create instances
                created_instances = []
                errors = []
                
                # Create pool instances
                if pool_count > 0:
                    pool_result = create_instance(
                        count=pool_count,
                        instance_type='pool',
                        workshop_name=workshop_name,
                        tutorial_session_id=session_id,
                        purchase_type=purchase_type,
                        spot_max_price=spot_max_price
                    )
                    if pool_result['success']:
                        created_instances.extend(pool_result['instances'])
                    else:
                        errors.append(f"Pool instances: {pool_result.get('error', 'Unknown error')}")
                
                # Create admin instances
                if admin_count > 0:
                    admin_result = create_instance(
                        count=admin_count,
                        instance_type='admin',
                        cleanup_days=admin_cleanup_days,
                        workshop_name=workshop_name,
                        tutorial_session_id=session_id,
                        purchase_type=purchase_type,
                        spot_max_price=spot_max_price
                    )
                    if admin_result['success']:
                        created_instances.extend(admin_result['instances'])
                    else:
                        errors.append(f"Admin instances: {admin_result.get('error', 'Unknown error')}")
                
                # Update session status
                if errors:
                    sessions_table.update_item(
                        Key={'session_id': session_id},
                        UpdateExpression='SET #status = :status, #errors = :errors',
                        ExpressionAttributeNames={'#status': 'status', '#errors': 'errors'},
                        ExpressionAttributeValues={':status': 'partial', ':errors': errors}
                    )
                else:
                    sessions_table.update_item(
                        Key={'session_id': session_id},
                        UpdateExpression='SET #status = :status',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={':status': 'active'}
                    )
                
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': True,
                        'session': {
                            'session_id': session_id,
                            'workshop_name': workshop_name,
                            'pool_count': pool_count,
                            'admin_count': admin_count,
                            'productive_tutorial': productive_tutorial,
                            'purchase_type': purchase_type,
                            'spot_max_price': float(spot_max_price) if (purchase_type == 'spot' and spot_max_price is not None) else None,
                            'created_at': session_item['created_at'],
                            'status': 'partial' if errors else 'active'
                        },
                        'instances': created_instances,
                        'errors': errors if errors else None
                    })
                }
            except Exception as e:
                logger.error(f"Error creating tutorial session: {str(e)}", exc_info=True)
                return {
                    'statusCode': 500,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': str(e)})
                }
        
        elif api_path == '/tutorial_sessions' and http_method == 'GET':
            # List tutorial sessions for a workshop
            workshop_name = query_params.get('workshop')
            if not workshop_name:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'workshop parameter is required'})
                }
            
            try:
                sessions_table = get_tutorial_sessions_table(workshop_name)
                
                # Query sessions by workshop_name using GSI
                response = sessions_table.query(
                    IndexName='workshop_name-index',
                    KeyConditionExpression='workshop_name = :wn',
                    ExpressionAttributeValues={':wn': workshop_name}
                )
                
                sessions = []
                for item in response.get('Items', []):
                    # Get instance counts for each session
                    session_id = item['session_id']
                    instances_result = list_instances(tutorial_session_id=session_id)
                    instance_count = len(instances_result.get('instances', [])) if instances_result.get('success') else 0
                    
                    # Convert Decimal values to int/float for JSON serialization
                    pool_count = item.get('pool_count', 0)
                    admin_count = item.get('admin_count', 0)
                    spot_max_price = item.get('spot_max_price')
                    productive_tutorial = parse_bool(item.get('productive_tutorial'))
                    if productive_tutorial is None:
                        productive_tutorial = item.get('purchase_type', 'on-demand') == 'on-demand'
                    if isinstance(pool_count, Decimal):
                        pool_count = int(pool_count) if pool_count % 1 == 0 else float(pool_count)
                    if isinstance(admin_count, Decimal):
                        admin_count = int(admin_count) if admin_count % 1 == 0 else float(admin_count)
                    if isinstance(spot_max_price, Decimal):
                        spot_max_price = int(spot_max_price) if spot_max_price % 1 == 0 else float(spot_max_price)
                    
                    sessions.append({
                        'session_id': item['session_id'],
                        'workshop_name': item['workshop_name'],
                        'created_at': item['created_at'],
                        'pool_count': pool_count,
                        'admin_count': admin_count,
                        'productive_tutorial': productive_tutorial,
                        'purchase_type': item.get('purchase_type', 'on-demand' if productive_tutorial else 'spot'),
                        'spot_max_price': spot_max_price,
                        'status': item.get('status', 'unknown'),
                        'actual_instance_count': instance_count
                    })
                
                # Sort by created_at descending (newest first)
                sessions.sort(key=lambda x: x['created_at'], reverse=True)
                
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': True,
                        'sessions': sessions
                    })
                }
            except Exception as e:
                logger.error(f"Error listing tutorial sessions: {str(e)}", exc_info=True)
                return {
                    'statusCode': 500,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': str(e)})
                }
        
        elif api_path.startswith('/tutorial_session/') and http_method == 'GET':
            # Get a specific tutorial session
            session_id = api_path.split('/tutorial_session/')[1]
            workshop_name = query_params.get('workshop')
            
            if not workshop_name:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'workshop parameter is required'})
                }
            
            try:
                sessions_table = get_tutorial_sessions_table(workshop_name)
                response = sessions_table.get_item(Key={'session_id': session_id})
                
                if 'Item' not in response:
                    return {
                        'statusCode': 404,
                        'headers': get_cors_headers(),
                        'body': json.dumps({'success': False, 'error': 'Session not found'})
                    }
                
                item = response['Item']
                
                # Get instances for this session
                instances_result = list_instances(tutorial_session_id=session_id)
                instances = instances_result.get('instances', []) if instances_result.get('success') else []
                
                # Calculate stats
                pool_instances = [i for i in instances if i.get('type') == 'pool']
                admin_instances = [i for i in instances if i.get('type') == 'admin']
                running_count = len([i for i in instances if i.get('state') == 'running'])
                stopped_count = len([i for i in instances if i.get('state') == 'stopped'])
                
                # Convert Decimal values to int/float for JSON serialization
                pool_count = item.get('pool_count', 0)
                admin_count = item.get('admin_count', 0)
                admin_cleanup_days = item.get('admin_cleanup_days', 7)
                spot_max_price = item.get('spot_max_price')
                productive_tutorial = parse_bool(item.get('productive_tutorial'))
                if productive_tutorial is None:
                    productive_tutorial = item.get('purchase_type', 'on-demand') == 'on-demand'
                if isinstance(pool_count, Decimal):
                    pool_count = int(pool_count) if pool_count % 1 == 0 else float(pool_count)
                if isinstance(admin_count, Decimal):
                    admin_count = int(admin_count) if admin_count % 1 == 0 else float(admin_count)
                if isinstance(admin_cleanup_days, Decimal):
                    admin_cleanup_days = int(admin_cleanup_days) if admin_cleanup_days % 1 == 0 else float(admin_cleanup_days)
                if isinstance(spot_max_price, Decimal):
                    spot_max_price = int(spot_max_price) if spot_max_price % 1 == 0 else float(spot_max_price)
                
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': True,
                        'session': {
                            'session_id': item['session_id'],
                            'workshop_name': item['workshop_name'],
                            'created_at': item['created_at'],
                            'pool_count': pool_count,
                            'admin_count': admin_count,
                            'admin_cleanup_days': admin_cleanup_days,
                            'productive_tutorial': productive_tutorial,
                            'purchase_type': item.get('purchase_type', 'on-demand' if productive_tutorial else 'spot'),
                            'spot_max_price': spot_max_price,
                            'status': item.get('status', 'unknown')
                        },
                        'stats': {
                            'total_instances': len(instances),
                            'pool_instances': len(pool_instances),
                            'admin_instances': len(admin_instances),
                            'running': running_count,
                            'stopped': stopped_count
                        },
                        'instances': instances
                    })
                }
            except Exception as e:
                logger.error(f"Error getting tutorial session: {str(e)}", exc_info=True)
                return {
                    'statusCode': 500,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': str(e)})
                }
        
        elif api_path.startswith('/tutorial_session/') and http_method == 'DELETE':
            # Delete a tutorial session
            session_id = api_path.split('/tutorial_session/')[1]
            workshop_name = query_params.get('workshop')
            # Initialize should_delete_instances at the start to avoid reference errors
            # Use different variable name to avoid shadowing the delete_instances() function
            delete_instances_param = query_params.get('delete_instances', 'false')
            should_delete_instances = delete_instances_param.lower() == 'true' if delete_instances_param else False
            
            if not workshop_name:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': 'workshop parameter is required'})
                }
            
            try:
                sessions_table = get_tutorial_sessions_table(workshop_name)
                
                # Check if session exists
                response = sessions_table.get_item(Key={'session_id': session_id})
                if 'Item' not in response:
                    return {
                        'statusCode': 404,
                        'headers': get_cors_headers(),
                        'body': json.dumps({'success': False, 'error': 'Session not found'})
                    }
                
                # Get instances for this session
                instances_result = list_instances(tutorial_session_id=session_id)
                instances = instances_result.get('instances', []) if instances_result.get('success') else []
                
                # Delete instances if requested
                if should_delete_instances and instances:
                    instance_ids = [i['instance_id'] for i in instances if i.get('state') != 'terminated']
                    if instance_ids:
                        try:
                            ec2.terminate_instances(InstanceIds=instance_ids)
                            logger.info(f"Terminated {len(instance_ids)} instances for session {session_id}")
                        except Exception as e:
                            logger.error(f"Error terminating instances: {str(e)}")
                
                # Delete session record
                sessions_table.delete_item(Key={'session_id': session_id})
                
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': True,
                        'message': f'Session {session_id} deleted',
                        'instances_deleted': should_delete_instances
                    })
                }
            except Exception as e:
                logger.error(f"Error deleting tutorial session: {str(e)}", exc_info=True)
                return {
                    'statusCode': 500,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'success': False, 'error': str(e)})
                }
        
        else:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'success': False,
                    'error': 'Not found',
                    'available_endpoints': {
                        'GET /api/health': 'Health check endpoint (no auth required)',
                        'POST /api/login': 'Login endpoint (no auth required)',
                        'GET /api/templates': 'Get workshop templates',
                        'POST /api/create': 'Create instances',
                        'GET /api/list': 'List all instances',
                        'POST /api/update_cleanup_days': 'Update cleanup days',
                        'POST /api/assign': 'Assign instance',
                        'POST /api/delete': 'Delete instances',
                        'POST /api/bulk_delete': 'Bulk delete instances',
                        'POST /api/enable_https': 'Enable HTTPS',
                        'POST /api/delete_https': 'Disable HTTPS',
                        'GET /api/timeout_settings': 'Get timeout settings',
                        'POST /api/update_timeout_settings': 'Update timeout settings'
                    }
                })
            }
    
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
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
    template_map = get_template_map()
    templates_json = json.dumps(template_map)
    default_workshop = WORKSHOP_NAME
    html = """<!DOCTYPE html>
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
                        <label>Workshop:</label>
                        <select id="poolWorkshop"></select>
                    </div>
                    <div class="form-group">
                        <label>Number of instances:</label>
                        <input type="number" id="poolCount" min="1" max="120" value="4" required>
                    </div>
                    <div class="form-group">
                        <label>Stop Timeout (minutes, optional):</label>
                        <input type="number" id="poolStopTimeout" min="1" max="1440" placeholder="Uses SSM default">
                        <small style="color: #666; font-size: 0.85em;">Minutes before stopping unassigned running instances</small>
                    </div>
                    <div class="form-group">
                        <label>Terminate Timeout (minutes, optional):</label>
                        <input type="number" id="poolTerminateTimeout" min="1" max="1440" placeholder="Uses SSM default">
                        <small style="color: #666; font-size: 0.85em;">Minutes before terminating stopped instances</small>
                    </div>
                    <div class="form-group">
                        <label>Hard Terminate Timeout (minutes, optional):</label>
                        <input type="number" id="poolHardTerminateTimeout" min="1" max="10080" placeholder="Uses SSM default">
                        <small style="color: #666; font-size: 0.85em;">Minutes before hard terminating any instance</small>
                    </div>
                    <button type="submit">Create Pool</button>
                </form>
            </div>

            <div class="card">
                <h2>Create Admin Instance</h2>
                <form id="createAdminForm">
                    <div class="form-group">
                        <label>Workshop:</label>
                        <select id="adminWorkshop"></select>
                    </div>
                    <div class="form-group">
                        <label>Number of instances:</label>
                        <input type="number" id="adminCount" min="1" max="5" value="1" required>
                    </div>
                    <div class="form-group">
                        <label>Cleanup after (days):</label>
                        <input type="number" id="adminCleanupDays" min="1" max="365" value="7" required>
                        <small style="color: #666; font-size: 0.85em;">Instances will be automatically deleted after this many days (default: 7)</small>
                    </div>
                    <div class="form-group">
                        <label>Stop Timeout (minutes, optional):</label>
                        <input type="number" id="adminStopTimeout" min="1" max="1440" placeholder="Uses SSM default">
                        <small style="color: #666; font-size: 0.85em;">Minutes before stopping unassigned running instances</small>
                    </div>
                    <div class="form-group">
                        <label>Terminate Timeout (minutes, optional):</label>
                        <input type="number" id="adminTerminateTimeout" min="1" max="1440" placeholder="Uses SSM default">
                        <small style="color: #666; font-size: 0.85em;">Minutes before terminating stopped instances</small>
                    </div>
                    <div class="form-group">
                        <label>Hard Terminate Timeout (minutes, optional):</label>
                        <input type="number" id="adminHardTerminateTimeout" min="1" max="10080" placeholder="Uses SSM default">
                        <small style="color: #666; font-size: 0.85em;">Minutes before hard terminating any instance</small>
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

            <div class="card">
                <h2>Workshop Timeout Settings (SSM Defaults)</h2>
                <p style="color: #666; font-size: 0.9em; margin-bottom: 15px;">Configure default timeout values per workshop. These are used when creating instances without custom timeout values.</p>
                <form id="timeoutSettingsForm">
                    <div class="form-group">
                        <label>Workshop:</label>
                        <select id="timeoutWorkshop"></select>
                    </div>
                    <div class="form-group">
                        <label>Stop Timeout (minutes):</label>
                        <input type="number" id="stopTimeout" min="1" max="1440" required>
                        <small style="color: #666; font-size: 0.85em;">Default minutes before stopping unassigned running instances</small>
                    </div>
                    <div class="form-group">
                        <label>Terminate Timeout (minutes):</label>
                        <input type="number" id="terminateTimeout" min="1" max="1440" required>
                        <small style="color: #666; font-size: 0.85em;">Default minutes before terminating stopped instances</small>
                    </div>
                    <div class="form-group">
                        <label>Hard Terminate Timeout (minutes):</label>
                        <input type="number" id="hardTerminateTimeout" min="1" max="10080" required>
                        <small style="color: #666; font-size: 0.85em;">Default minutes before hard terminating any instance (max: 7 days)</small>
                    </div>
                    <div class="form-group">
                        <label>Admin Cleanup Days:</label>
                        <input type="number" id="adminCleanupDaysSetting" min="1" max="365" required>
                        <small style="color: #666; font-size: 0.85em;">Default days before admin instances are deleted</small>
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button type="submit">Save Defaults</button>
                        <button type="button" onclick="loadTimeoutSettings()" style="background: #666;">Load Current</button>
                    </div>
                </form>
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
        const WORKSHOP_TEMPLATES = __TEMPLATES_JSON__;
        const DEFAULT_WORKSHOP = "__DEFAULT_WORKSHOP__";

        function showMessage(text, type = 'success') {
            const messageDiv = document.getElementById('message');
            messageDiv.className = type;
            messageDiv.textContent = text;
            messageDiv.style.display = 'block';
            setTimeout(() => {
                messageDiv.style.display = 'none';
            }, 5000);
        }

        function getSelectedWorkshop(type) {
            const selectId = type === 'admin' ? 'adminWorkshop' : 'poolWorkshop';
            const select = document.getElementById(selectId);
            return select ? select.value : DEFAULT_WORKSHOP;
        }

        function populateWorkshopSelects() {
            const workshops = Object.keys(WORKSHOP_TEMPLATES);
            const options = workshops.length > 0 ? workshops : [DEFAULT_WORKSHOP];
            const selects = [document.getElementById('poolWorkshop'), document.getElementById('adminWorkshop'), document.getElementById('timeoutWorkshop')];

            selects.forEach(select => {
                if (!select) return;
                select.innerHTML = '';
                options.forEach(workshop => {
                    const option = document.createElement('option');
                    option.value = workshop;
                    option.textContent = workshop;
                    if (workshop === DEFAULT_WORKSHOP) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });
            });
        }

        async function createInstances(count, type, cleanupDays = null, stopTimeout = null, terminateTimeout = null, hardTerminateTimeout = null) {
            try {
                showMessage('Creating instances...', 'success');
                const payload = {count, type};
                payload.workshop = getSelectedWorkshop(type);
                if (type === 'admin' && cleanupDays !== null) {
                    payload.cleanup_days = cleanupDays;
                }
                if (stopTimeout !== null && stopTimeout !== '') {
                    payload.stop_timeout = parseInt(stopTimeout);
                }
                if (terminateTimeout !== null && terminateTimeout !== '') {
                    payload.terminate_timeout = parseInt(terminateTimeout);
                }
                if (hardTerminateTimeout !== null && hardTerminateTimeout !== '') {
                    payload.hard_terminate_timeout = parseInt(hardTerminateTimeout);
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

        async function enableHttps(instanceId) {
            try {
                showMessage('Enabling HTTPS...', 'success');
                const response = await fetch(`${API_URL}/https/enable`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({instance_id: instanceId})
                });
                const data = await response.json();
                if (data.success) {
                    showMessage(`✅ HTTPS enabled: ${data.domain}`, 'success');
                    refreshList();
                } else {
                    showMessage(`❌ Error: ${data.error}`, 'error');
                }
            } catch (error) {
                showMessage(`❌ Error: ${error.message}`, 'error');
            }
        }

        async function disableHttps(instanceId) {
            try {
                showMessage('Disabling HTTPS...', 'success');
                const response = await fetch(`${API_URL}/https/disable`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({instance_id: instanceId})
                });
                const data = await response.json();
                if (data.success) {
                    showMessage('✅ HTTPS disabled', 'success');
                    refreshList();
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

                let tableHTML = '<table><thead><tr><th>Instance ID</th><th>Workshop</th><th>Type</th><th>State</th><th>Public IP</th><th>Assigned To</th><th>Days Remaining</th><th>Actions</th></tr></thead><tbody>';
                
                data.instances.forEach(instance => {
                    const workshop = instance.tags && instance.tags.WorkshopID ? instance.tags.WorkshopID : '-';
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
                    
                    // Make HTTPS URL or IP a clickable link
                    let publicIpCell;
                    if (instance.https_url) {
                        // Prefer HTTPS URL with friendly "Visit me" text
                        publicIpCell = `<a href="${instance.https_url}" target="_blank">Visit me</a>`;
                    } else if (instance.public_ip) {
                        // Fallback to HTTP IP link (backward compatibility)
                        publicIpCell = `<a href="http://${instance.public_ip}" target="_blank">${instance.public_ip}</a>`;
                    } else {
                        publicIpCell = '-';
                    }
                    
                    // HTTPS toggle button
                    const httpsEnabled = instance.tags && instance.tags.HttpsEnabled === 'true';
                    const httpsButton = instance.state === 'terminated'
                        ? '<span style="color: #999;">-</span>'
                        : (httpsEnabled
                            ? `<button class="btn-small" style="background: #ff9800;" onclick="disableHttps('${instance.instance_id}')">Disable HTTPS</button>`
                            : `<button class="btn-small" style="background: #3f51b5;" onclick="enableHttps('${instance.instance_id}')">Enable HTTPS</button>`);

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
                            <td>${workshop}</td>
                            <td>${typeBadge}</td>
                            <td>${stateBadge}</td>
                            <td>${publicIpCell}</td>
                            <td>${assignedBadge}</td>
                            <td>${daysRemainingCell}</td>
                            <td>${httpsButton}<br>${deleteButton}</td>
                        </tr>
                    `;
                });
                
                tableHTML += '</tbody></table>';
                listDiv.innerHTML = tableHTML;
            } catch (error) {
                listDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            }
        }

        populateWorkshopSelects();

        // Form handlers
        document.getElementById('createPoolForm').addEventListener('submit', (e) => {
            e.preventDefault();
            const count = parseInt(document.getElementById('poolCount').value);
            const stopTimeout = document.getElementById('poolStopTimeout').value;
            const terminateTimeout = document.getElementById('poolTerminateTimeout').value;
            const hardTerminateTimeout = document.getElementById('poolHardTerminateTimeout').value;
            createInstances(count, 'pool', null, stopTimeout, terminateTimeout, hardTerminateTimeout);
        });

        document.getElementById('createAdminForm').addEventListener('submit', (e) => {
            e.preventDefault();
            const count = parseInt(document.getElementById('adminCount').value);
            const cleanupDays = parseInt(document.getElementById('adminCleanupDays').value);
            const stopTimeout = document.getElementById('adminStopTimeout').value;
            const terminateTimeout = document.getElementById('adminTerminateTimeout').value;
            const hardTerminateTimeout = document.getElementById('adminHardTerminateTimeout').value;
            createInstances(count, 'admin', cleanupDays, stopTimeout, terminateTimeout, hardTerminateTimeout);
        });

        document.getElementById('timeoutSettingsForm').addEventListener('submit', saveTimeoutSettings);
        
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

        async function loadTimeoutSettings() {
            const workshop = document.getElementById('timeoutWorkshop').value;
            if (!workshop) {
                showMessage('Please select a workshop', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_URL}/timeout_settings?workshop=${workshop}`);
                const data = await response.json();
                if (data.success) {
                    document.getElementById('stopTimeout').value = data.timeouts.stop_timeout;
                    document.getElementById('terminateTimeout').value = data.timeouts.terminate_timeout;
                    document.getElementById('hardTerminateTimeout').value = data.timeouts.hard_terminate_timeout;
                    document.getElementById('adminCleanupDaysSetting').value = data.timeouts.admin_cleanup_days;
                    showMessage('✅ Settings loaded', 'success');
                } else {
                    showMessage(`❌ Error: ${data.error}`, 'error');
                }
            } catch (error) {
                showMessage(`❌ Error: ${error.message}`, 'error');
            }
        }

        async function saveTimeoutSettings(event) {
            event.preventDefault();
            const workshop = document.getElementById('timeoutWorkshop').value;
            const stopTimeout = parseInt(document.getElementById('stopTimeout').value);
            const terminateTimeout = parseInt(document.getElementById('terminateTimeout').value);
            const hardTerminateTimeout = parseInt(document.getElementById('hardTerminateTimeout').value);
            const adminCleanupDays = parseInt(document.getElementById('adminCleanupDaysSetting').value);
            
            if (!workshop) {
                showMessage('Please select a workshop', 'error');
                return;
            }
            
            try {
                showMessage('Saving settings...', 'success');
                const response = await fetch(`${API_URL}/update_timeout_settings`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        workshop,
                        stop_timeout: stopTimeout,
                        terminate_timeout: terminateTimeout,
                        hard_terminate_timeout: hardTerminateTimeout,
                        admin_cleanup_days: adminCleanupDays
                    })
                });
                const data = await response.json();
                if (data.success) {
                    showMessage(`✅ Settings saved for ${workshop}`, 'success');
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
    return html.replace("__TEMPLATES_JSON__", templates_json).replace("__DEFAULT_WORKSHOP__", default_workshop)
