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
from typing import Any
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

INSTANCE_RATES_ESTIMATE_USD = {
    't3.small': {'on_demand': 0.0208, 'spot': 0.0062},
    't3.medium': {'on_demand': 0.0416, 'spot': 0.0125},
    't3.large': {'on_demand': 0.0832, 'spot': 0.0250}
}
DEFAULT_INSTANCE_RATES_ESTIMATE_USD = {'on_demand': 0.0416, 'spot': 0.0125}

_ce_client = None

def _to_float(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == '':
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None

def _normalize_purchase_type(value, fallback='on-demand'):
    normalized = str(value or '').strip().lower()
    if 'spot' in normalized:
        return 'spot'
    if 'on-demand' in normalized or normalized == 'ondemand':
        return 'on-demand'
    return fallback

def _get_cost_explorer_client():
    global _ce_client
    if _ce_client is None:
        _ce_client = boto3.client('ce', region_name='us-east-1')
    return _ce_client

def _get_tutorial_session_defaults(tutorial_session_id, workshop_name=None):
    if not tutorial_session_id:
        return {}
    try:
        sessions_table = get_tutorial_sessions_table(workshop_name)
        response = sessions_table.get_item(Key={'session_id': tutorial_session_id})
        item = response.get('Item')
        if not item:
            return {}
        productive_tutorial = parse_bool(item.get('productive_tutorial'))
        if productive_tutorial is None:
            productive_tutorial = item.get('purchase_type', 'on-demand') == 'on-demand'
        purchase_type = item.get('purchase_type', 'on-demand' if productive_tutorial else 'spot')
        return {
            'purchase_type': _normalize_purchase_type(purchase_type, 'on-demand'),
            'spot_max_price': _to_float(item.get('spot_max_price'))
        }
    except Exception as e:
        logger.warning(f"Unable to load tutorial session defaults for {tutorial_session_id}: {str(e)}")
        return {}

def _estimate_instance_costs(instance_type, purchase_type, spot_max_price, launch_time):
    rates = INSTANCE_RATES_ESTIMATE_USD.get(instance_type, DEFAULT_INSTANCE_RATES_ESTIMATE_USD)
    spot_rate = rates['spot']
    if spot_max_price is not None:
        spot_rate = min(spot_rate, spot_max_price)
    hourly_rate = spot_rate if purchase_type == 'spot' else rates['on_demand']

    estimated_runtime_hours = 0.0
    if isinstance(launch_time, datetime):
        launch_dt = launch_time if launch_time.tzinfo else launch_time.replace(tzinfo=timezone.utc)
        estimated_runtime_hours = max(0.0, (datetime.now(timezone.utc) - launch_dt).total_seconds() / 3600.0)

    return {
        'hourly_rate_estimate_usd': round(hourly_rate, 6),
        'estimated_runtime_hours': round(estimated_runtime_hours, 4),
        'estimated_cost_usd': round(hourly_rate * estimated_runtime_hours, 6),
        'estimated_cost_24h_usd': round(hourly_rate * 24.0, 6)
    }

def _fetch_actual_costs_for_instances(instance_ids):
    if not instance_ids:
        return {
            'costs_by_instance': {},
            'actual_total_usd': 0.0,
            'actual_data_source': 'cost-explorer'
        }

    try:
        ce = _get_cost_explorer_client()
        end_date = datetime.now(timezone.utc).date() + timedelta(days=1)
        start_date = end_date - timedelta(days=14)

        response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': ['Amazon Elastic Compute Cloud - Compute']
                }
            },
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'RESOURCE_ID'}]
        )

        instance_id_set = set(instance_ids)
        costs_by_instance = {}

        for day in response.get('ResultsByTime', []):
            for group in day.get('Groups', []):
                keys = group.get('Keys', [])
                resource_id = keys[0] if keys else None
                if resource_id not in instance_id_set:
                    continue
                amount_str = group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount')
                amount = _to_float(amount_str) or 0.0
                costs_by_instance[resource_id] = round(costs_by_instance.get(resource_id, 0.0) + amount, 6)

        actual_total = round(sum(costs_by_instance.values()), 6)
        return {
            'costs_by_instance': costs_by_instance,
            'actual_total_usd': actual_total,
            'actual_data_source': 'cost-explorer'
        }
    except Exception as e:
        logger.warning(f"Cost Explorer unavailable, skipping actual costs: {str(e)}")
        return {
            'costs_by_instance': {},
            'actual_total_usd': None,
            'actual_data_source': 'unavailable'
        }

# Get configuration from environment variables
INSTANCE_TYPE = os.environ.get('EC2_INSTANCE_TYPE', 't3.medium')
DEFAULT_POOL_INSTANCE_TYPE = 't3.medium'
ALLOWED_EC2_INSTANCE_TYPES = {
    't2.small',
    't2.medium',
    't2.large',
    't3.small',
    't3.medium',
    't3.large',
}
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

# ── Shared-Core mode ────────────────────────────────────────────────────────
# When SHARED_CORE_MODE=true, student assignments receive Jenkins/Gitea URLs
# pointing to the shared-core EC2 node instead of per-student services.
# This is the reversible cutover switch described in the migration plan.
SHARED_CORE_MODE = os.environ.get('SHARED_CORE_MODE', 'false').strip().lower() in ('true', '1', 'yes')
SHARED_JENKINS_URL = os.environ.get('SHARED_JENKINS_URL', '')
SHARED_GITEA_URL = os.environ.get('SHARED_GITEA_URL', '')


def get_shared_core_urls(student_id: str = '', workshop_name: str = '') -> dict:
    """Return the shared Jenkins and Gitea URLs for a student in shared-core mode.

    When SHARED_CORE_MODE is active these URLs are issued in every student
    assignment response instead of per-student hostnames.  The per-student
    ``workshop_name`` and ``student_id`` are used to build the scoped paths
    inside the shared services (Jenkins folder, Gitea repo).

    Returns a dict with keys: jenkins_url, gitea_url, jenkins_job_url,
    gitea_repo_url, shared_core_mode (bool).
    """
    if not SHARED_CORE_MODE:
        return {'shared_core_mode': False}

    if not SHARED_JENKINS_URL or not SHARED_GITEA_URL:
        logger.warning(
            "SHARED_CORE_MODE is enabled but SHARED_JENKINS_URL or "
            "SHARED_GITEA_URL is not set — falling back to per-student URLs"
        )
        return {'shared_core_mode': False}

    base_jenkins = SHARED_JENKINS_URL.rstrip('/')
    base_gitea = SHARED_GITEA_URL.rstrip('/')
    org = os.environ.get('GITEA_ORG_NAME', 'fellowship-org')

    result: dict = {
        'shared_core_mode': True,
        'jenkins_url': base_jenkins + '/',
        'gitea_url': base_gitea + '/',
    }

    if student_id:
        result['jenkins_job_url'] = (
            f"{base_jenkins}/job/{student_id}/job/fellowship-pipeline/"
        )
        result['gitea_repo_url'] = (
            f"{base_gitea}/{org}/fellowship-sut-{student_id}"
        )

    return result


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

def get_latest_sut_artifact_key(bucket_name, prefix="fellowship-sut-", suffix=".tar.gz"):
    """Get the most recent SUT artifact key from S3 by LastModified timestamp
    
    Args:
        bucket_name: S3 bucket name
        prefix: Prefix to filter objects (default: "fellowship-sut-")
        suffix: Suffix to filter objects (default: ".tar.gz")
    
    Returns:
        dict with keys: artifact_key (str), last_modified (datetime), or None if no artifacts found
    """
    if not bucket_name:
        logger.warning("S3 bucket name is empty, cannot list artifacts")
        return None
    
    try:
        s3 = boto3.client('s3', region_name=REGION)
        logger.info(f"Listing S3 objects: bucket={bucket_name}, prefix={prefix}, suffix={suffix}")
        
        paginator = s3.get_paginator('list_objects_v2')
        latest_obj = None
        latest_modified = None
        
        try:
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    # Filter by suffix
                    if not key.endswith(suffix):
                        continue
                    
                    last_modified = obj['LastModified']
                    
                    # Track the most recently modified object
                    if latest_modified is None or last_modified > latest_modified:
                        latest_obj = obj
                        latest_modified = last_modified
                        logger.debug(f"Found newer artifact: {key} (modified: {last_modified.isoformat()})")
        except s3.exceptions.NoSuchBucket:
            logger.error(f"S3 bucket does not exist: {bucket_name}")
            return None
        
        if latest_obj:
            artifact_key = latest_obj['Key']
            logger.info(f"✓ Found latest SUT artifact: {artifact_key} (modified: {latest_modified.isoformat()})")
            return {
                'artifact_key': artifact_key,
                'last_modified': latest_modified  
            }
        else:
            logger.warning(f"No SUT artifacts found in bucket {bucket_name} with prefix={prefix} and suffix={suffix}")
            return None
    
    except Exception as e:
        logger.error(f"Error listing S3 artifacts from {bucket_name}: {str(e)}")
        return None

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
    sanitized = str(domain).replace('_', '-').lower()
    # Remove any double hyphens that might result
    while '--' in sanitized:
        sanitized = sanitized.replace('--', '-')
    return sanitized

def _build_instance_name_prefix(workshop_name, tutorial_session_id, instance_type):
    if tutorial_session_id:
        return f"{workshop_name}-{tutorial_session_id}-{instance_type}-"
    return f"{workshop_name}-{instance_type}-"

def _extract_index_from_name(name, prefix):
    if not name or not name.startswith(prefix):
        return None
    suffix = name[len(prefix):]
    if suffix.isdigit():
        return int(suffix)
    return None

def _get_next_instance_index(workshop_name, tutorial_session_id, instance_type):
    """Return the next safe numeric index and currently used indices for instance naming."""
    filters = [
        {'Name': 'tag:Project', 'Values': ['classroom']},
        {'Name': 'tag:WorkshopID', 'Values': [workshop_name]},
        {'Name': 'tag:Type', 'Values': [instance_type]},
        {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped', 'starting']}
    ]
    if tutorial_session_id:
        filters.append({'Name': 'tag:TutorialSessionID', 'Values': [tutorial_session_id]})

    used_indices = set()
    name_prefix = _build_instance_name_prefix(workshop_name, tutorial_session_id, instance_type)

    paginator = ec2.get_paginator('describe_instances')
    for page in paginator.paginate(Filters=filters):
        for reservation in page.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                existing_name = tags.get('Name', '')
                index = _extract_index_from_name(existing_name, name_prefix)
                if index is not None:
                    used_indices.add(index)

    next_index = (max(used_indices) + 1) if used_indices else 0
    return next_index, used_indices

COUNTER_ITEM_PREFIX = '__endpoint_counter__'
IDEMPOTENCY_ITEM_PREFIX = '__create_request__'


def _build_counter_item_key(workshop_name, tutorial_session_id, instance_type):
    session_part = tutorial_session_id if tutorial_session_id else 'global'
    return f"{COUNTER_ITEM_PREFIX}:{ENVIRONMENT}:{workshop_name}:{session_part}:{instance_type}"


def _build_create_request_item_key(workshop_name, tutorial_session_id, instance_type, idempotency_key):
    session_part = tutorial_session_id if tutorial_session_id else 'global'
    return f"{IDEMPOTENCY_ITEM_PREFIX}:{ENVIRONMENT}:{workshop_name}:{session_part}:{instance_type}:{idempotency_key}"


def _reserve_instance_indices(workshop_name, tutorial_session_id, instance_type, count):
    """Atomically reserve a unique contiguous index range using DynamoDB."""
    if count <= 0:
        return []

    next_index_from_ec2, _ = _get_next_instance_index(workshop_name, tutorial_session_id, instance_type)
    counter_key = _build_counter_item_key(workshop_name, tutorial_session_id, instance_type)

    try:
        table.update_item(
            Key={'instance_id': counter_key},
            UpdateExpression='SET next_index = if_not_exists(next_index, :initial_next), updated_at = :now',
            ExpressionAttributeValues={
                ':initial_next': next_index_from_ec2,
                ':now': datetime.now(timezone.utc).isoformat()
            }
        )

        update_response = table.update_item(
            Key={'instance_id': counter_key},
            UpdateExpression='ADD next_index :count SET updated_at = :now',
            ExpressionAttributeValues={
                ':count': count,
                ':now': datetime.now(timezone.utc).isoformat()
            },
            ReturnValues='UPDATED_NEW'
        )
        updated_next = int(update_response['Attributes']['next_index'])
        start_index = updated_next - count
        return list(range(start_index, updated_next))
    except Exception as e:
        logger.warning(
            f"Atomic index reservation failed for workshop={workshop_name}, "
            f"tutorial_session_id={tutorial_session_id}, type={instance_type}: {str(e)}. "
            "Falling back to in-memory reservation from EC2 scan."
        )
        return list(range(next_index_from_ec2, next_index_from_ec2 + count))


def _normalize_route53_record_name(record_name):
    if not record_name:
        return ''
    # Always lowercase for DNS
    record_name = record_name.lower()
    return record_name if record_name.endswith('.') else f"{record_name}."
    return record_name if record_name.endswith('.') else f"{record_name}."


def _delete_route53_a_record(domain_name, strict=False, max_retries=3):
    """Delete a Route53 A record by exact name.

    Returns dict: {success, deleted, skipped, reason, attempts}
    """
    if not domain_name:
        return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'no-domain', 'attempts': 0}
    if not HTTPS_HOSTED_ZONE_ID:
        return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'hosted-zone-not-configured', 'attempts': 0}

    normalized_domain = _normalize_route53_record_name(domain_name)
    route53 = boto3.client('route53', region_name=REGION)

    for attempt in range(1, max_retries + 1):
        try:
            response = route53.list_resource_record_sets(
                HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                StartRecordName=domain_name,
                StartRecordType='A',
                MaxItems='10'
            )

            record_to_delete = None
            for record in response.get('ResourceRecordSets', []):
                if record.get('Type') == 'A' and _normalize_route53_record_name(record.get('Name')) == normalized_domain:
                    record_to_delete = record
                    break

            if not record_to_delete:
                logger.info(f"Route53 A record not found for {domain_name}; treating as already deleted")
                return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'already-deleted', 'attempts': attempt}

            route53.change_resource_record_sets(
                HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': record_to_delete
                    }]
                }
            )
            logger.info(f"Deleted Route53 A record: {domain_name}")
            return {'success': True, 'deleted': True, 'skipped': False, 'reason': 'deleted', 'attempts': attempt}
        except ClientError as e:
            error_code = e.response['Error'].get('Code', 'Unknown')
            if error_code == 'InvalidChangeBatch':
                logger.info(f"Route53 record {domain_name} already absent (InvalidChangeBatch)")
                return {'success': True, 'deleted': False, 'skipped': True, 'reason': 'already-deleted', 'attempts': attempt}
            if error_code == 'NoSuchHostedZone':
                logger.error(f"Hosted zone {HTTPS_HOSTED_ZONE_ID} not found while deleting {domain_name}")
                return {
                    'success': not strict,
                    'deleted': False,
                    'skipped': False,
                    'reason': 'hosted-zone-missing',
                    'attempts': attempt,
                    'error': str(e)
                }
            logger.warning(f"Route53 delete attempt {attempt}/{max_retries} failed for {domain_name}: {str(e)}")
            if attempt < max_retries:
                time.sleep(attempt)
            else:
                return {
                    'success': not strict,
                    'deleted': False,
                    'skipped': False,
                    'reason': 'delete-failed',
                    'attempts': attempt,
                    'error': str(e)
                }
        except Exception as e:
            logger.warning(f"Unexpected Route53 delete error attempt {attempt}/{max_retries} for {domain_name}: {str(e)}")
            if attempt < max_retries:
                time.sleep(attempt)
            else:
                return {
                    'success': not strict,
                    'deleted': False,
                    'skipped': False,
                    'reason': 'delete-failed',
                    'attempts': attempt,
                    'error': str(e)
                }

    return {'success': not strict, 'deleted': False, 'skipped': False, 'reason': 'delete-failed', 'attempts': max_retries}


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
        
        # Create/update Route53 A records for main, jenkins, and ide subdomains
        route53 = boto3.client('route53')
        domains_to_create = [final_domain]
        if str(workshop_name or '').strip().lower() == 'fellowship':
            domains_to_create.append(f"jenkins-{final_domain}")
            domains_to_create.append(f"ide-{final_domain}")
            domains_to_create.append(f"gitea-{final_domain}")

        if public_ip:
            changes = []
            for d in domains_to_create:
                changes.append({
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': d,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': public_ip}]
                    }
                })
            route53.change_resource_record_sets(
                HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                ChangeBatch={'Changes': changes}
            )
            logger.info(f"Created Route53 A records: {domains_to_create} -> {public_ip}")
        else:
            logger.warning(f"Instance {instance_id} has no public IP yet, Route53 records will be created when IP is available")
            logger.info(f"  Domains: {domains_to_create} (will be updated when instance gets public IP)")
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
        
        # Create/update Route53 A records for main, jenkins, and ide subdomains
        route53 = boto3.client('route53')
        domains_to_create = [final_domain]
        if str(workshop_name or '').strip().lower() == 'fellowship':
            domains_to_create.append(f"jenkins-{final_domain}")
            domains_to_create.append(f"ide-{final_domain}")

        if public_ip:
            changes = []
            for d in domains_to_create:
                changes.append({
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': d,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': public_ip}]
                    }
                })
            route53.change_resource_record_sets(
                HostedZoneId=HTTPS_HOSTED_ZONE_ID,
                ChangeBatch={'Changes': changes}
            )
            logger.info(f"Created Route53 A records: {domains_to_create} -> {public_ip}")
        else:
            logger.warning(f"Instance {instance_id} has no public IP yet, Route53 records will be created when IP is available")
            logger.info(f"  Domains: {domains_to_create} (will be updated when instance gets public IP)")
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

    record_name = f"{instance_id}.{workshop_name}.{HTTPS_BASE_DOMAIN}".lower()
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
    record_name = (tags.get('HttpsDomain') or f"{instance_id}.{workshop_name}.{HTTPS_BASE_DOMAIN}").lower()
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

INLINE_GOLDEN_AMI_BOOTSTRAP_WORKSHOPS = {'fellowship', 'fellowship-of-the-build'}


def _uses_inline_golden_ami_bootstrap(workshop_name, template_config=None):
    """Return True when a workshop should use the inline golden AMI bootstrap."""
    normalized_workshop = str(workshop_name or WORKSHOP_NAME).strip().lower()
    if normalized_workshop not in INLINE_GOLDEN_AMI_BOOTSTRAP_WORKSHOPS:
        return False
    return bool(template_config and template_config.get('ami_id'))


def _get_inline_golden_ami_bootstrap_script(workshop_name):
    """Return the minimal bootstrap used for golden AMI-based workshops."""
    normalized_workshop = str(workshop_name or WORKSHOP_NAME).strip().lower()
    if normalized_workshop == 'fellowship-of-the-build':
        normalized_workshop = 'fellowship'

    if normalized_workshop != 'fellowship':
        raise ValueError(f"Unsupported inline golden AMI bootstrap workshop: {workshop_name}")

    return """#!/bin/bash
set -euo pipefail

LOG_FILE="/var/log/user-data.log"
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"
}

log "Starting golden AMI bootstrap for ${WORKSHOP_NAME:-fellowship}"

SUT_DIR="/opt/fellowship-sut"
ESCAPE_ROOM_DIR="/opt/fellowship-sut/devops-escape-room"

if command -v systemctl >/dev/null 2>&1; then
    systemctl enable docker || true
    systemctl start docker
fi

for attempt in $(seq 1 30); do
    if docker info >/dev/null 2>&1; then
        break
    fi
    echo "Waiting for Docker daemon to become ready (${attempt}/30)..."
    sleep 2
done

docker info >/dev/null 2>&1

wait_for_escape_room_init() {
    local max_attempts=90
    local attempt=1
    local restart_attempted=false

    while [ $attempt -le $max_attempts ]; do
        local init_container_id
        local init_status
        local init_exit

        init_container_id=$(docker compose ps -q gitea-init 2>/dev/null || true)
        if [ -z "$init_container_id" ]; then
            [ $((attempt % 6)) -eq 0 ] && log "Waiting for gitea-init container to appear (${attempt}/${max_attempts})..."
            sleep 10
            attempt=$((attempt + 1))
            continue
        fi

        init_status=$(docker inspect --format '{{.State.Status}}' "$init_container_id" 2>/dev/null || echo "unknown")
        init_exit=$(docker inspect --format '{{.State.ExitCode}}' "$init_container_id" 2>/dev/null || echo "999")

        case "$init_status" in
            exited)
                if [ "$init_exit" = "0" ]; then
                    log "gitea-init completed successfully; reconciling dependent services..."
                    docker compose up -d
                    return 0
                fi

                log "WARNING: gitea-init exited with code ${init_exit}"
                docker compose logs --tail 80 gitea-init || true

                if [ "$restart_attempted" = false ]; then
                    restart_attempted=true
                    log "Retrying gitea-init one additional time..."
                    docker compose up -d gitea-init || true
                    sleep 10
                    attempt=$((attempt + 1))
                    continue
                fi

                return 1
                ;;
            running|restarting)
                [ $((attempt % 6)) -eq 0 ] && log "Waiting for gitea-init to finish (${attempt}/${max_attempts})..."
                ;;
            *)
                [ $((attempt % 6)) -eq 0 ] && log "gitea-init status is ${init_status} (${attempt}/${max_attempts})"
                ;;
        esac

        sleep 10
        attempt=$((attempt + 1))
    done

    log "WARNING: Timed out waiting for gitea-init to finish"
    docker compose logs --tail 80 gitea-init || true
    return 1
}

# ── IMDS Credential Retrieval for Caddy ───────
# Caddy's Route53 DNS plugin automatically retrieves fresh AWS credentials
# from EC2 Instance Metadata Service (IMDS) at 169.254.169.254 when needed.
# Credentials are NOT written to .env — Caddy handles IMDS access directly.
# This ensures credentials are always fresh and valid for ACME renewals.
log "IMDS will be used by Caddy for Route53 DNS-01 challenges"
log "  - IMDS IP: 169.254.169.254 (routed to host via Docker extra_hosts)"
log "  - EC2 instance must have IAM role with route53:* permissions"

log "Writing .env (CADDY_DOMAIN=${CADDY_DOMAIN:-localhost})"
cat > "${SUT_DIR}/.env" <<EOF
CADDY_DOMAIN=${CADDY_DOMAIN:-localhost}
JENKINS_DOMAIN=${JENKINS_DOMAIN:-}
IDE_DOMAIN=${IDE_DOMAIN:-}
GITEA_DOMAIN=${GITEA_DOMAIN:-}
MACHINE_NAME=${MACHINE_NAME:-fellowship}
WORKSHOP_NAME=${WORKSHOP_NAME:-fellowship}
ROUTE53_ZONE_ID=${ROUTE53_ZONE_ID:-}
CADDYFILE_PATH=./caddy/Caddyfile.fellowship
FRONTEND_MODE=prod
WDS_SOCKET_PROTOCOL=wss
# AWS credentials NOT stored in .env — Caddy will retrieve fresh credentials
# from EC2 IAM instance profile via IMDS (Instance Metadata Service).
# This allows Caddy to automatically refresh credentials before expiration,
# ensuring ACME certificate renewals work even after 30+ days.
AWS_REGION=${AWS_REGION:-eu-west-1}
EOF

# ── Event sourcing queue bootstrap (SQS) ─────────────────────────────────────
# Mirrors fellowship user_data.sh behavior for the inline golden-AMI path.
# This keeps event emission enabled even when template user_data.sh is bypassed.
# Keep a concrete region variable so set -u cannot fail if AWS_REGION was never injected.
SQS_AWS_REGION="${AWS_REGION:-${REGION:-eu-west-1}}"
export AWS_REGION="${SQS_AWS_REGION}"

SSM_SQS_KEY="/classroom/${WORKSHOP_NAME:-fellowship}/${ENVIRONMENT:-dev}/messaging/student_progress_queue_url"
log "Fetching SQS queue URL from SSM: ${SSM_SQS_KEY}"
SQS_QUEUE_URL=$(aws ssm get-parameter --name "${SSM_SQS_KEY}" \
    --query "Parameter.Value" --output text --region "${SQS_AWS_REGION}" 2>/dev/null || echo "")
if [ -n "${SQS_QUEUE_URL}" ] && [ "${SQS_QUEUE_URL}" != "None" ]; then
    export SQS_QUEUE_URL
    log "SQS queue URL configured"
    # Persist to .env so compose services can consume it where needed.
    echo "SQS_QUEUE_URL=${SQS_QUEUE_URL}" >> "${SUT_DIR}/.env"
else
    log "WARNING: Could not fetch SQS queue URL from SSM — event sourcing will be disabled on this instance"
fi

# ── Wildcard cert: try Secrets Manager first, fall back to per-instance ACME ──
# The issue-wildcard-cert GitHub Actions workflow stores a shared
# *.fellowship.testingfantasy.com certificate in Secrets Manager at
# /classroom/wildcard-cert/fellowship.  Fetching it here means this instance
# never needs to call Let's Encrypt, eliminating the 50-certs/week rate limit
# regardless of how many instances are provisioned simultaneously.
CERT_DIR="${SUT_DIR}/caddy/certs"
WILDCARD_SECRET="/classroom/wildcard-cert/fellowship"

log "Attempting to fetch shared wildcard cert from Secrets Manager (${WILDCARD_SECRET})..."

mkdir -p "$CERT_DIR"
export AWS_REGION="${AWS_REGION:-eu-west-1}"

if python3 - <<'PYEOF'
import sys, json, subprocess, os

region = os.environ.get("AWS_REGION", "eu-west-1")
secret_id = "/classroom/wildcard-cert/fellowship"
cert_dir = "/opt/fellowship-sut/caddy/certs"

result = subprocess.run(
    ["aws", "secretsmanager", "get-secret-value",
     "--secret-id", secret_id,
     "--region", region,
     "--query", "SecretString",
     "--output", "text"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"aws secretsmanager error: {result.stderr.strip()}", file=sys.stderr)
    sys.exit(1)

data = json.loads(result.stdout.strip())
if "cert" not in data or "key" not in data:
    print("Secret exists but is missing 'cert' or 'key' fields", file=sys.stderr)
    sys.exit(1)

with open(os.path.join(cert_dir, "wildcard.crt"), "w") as f:
    f.write(data["cert"])
with open(os.path.join(cert_dir, "wildcard.key"), "w") as f:
    f.write(data["key"])

# Restrict key permissions
os.chmod(os.path.join(cert_dir, "wildcard.key"), 0o600)

expires = data.get("expires", "unknown")
print(f"Wildcard cert written (expires: {expires})")
PYEOF
then
    log "✓ Shared wildcard cert fetched from Secrets Manager — zero ACME calls needed"
    log "  Rate limit impact: 0 new cert orders (cert was issued once by CI)"
    # Switch to the pre-loaded cert Caddyfile
    sed -i 's|CADDYFILE_PATH=.*|CADDYFILE_PATH=./caddy/Caddyfile.fellowship-wildcard|' "${SUT_DIR}/.env"
    log "  Using Caddyfile.fellowship-wildcard (pre-issued wildcard cert)"
else
    log "WARNING: Could not fetch wildcard cert from Secrets Manager"
    log "  Falling back to Caddyfile.fellowship (per-instance ACME via Route53)"
    log "  This will consume 1 cert from the LE 50/week limit for this instance."
    log "  To fix: run the issue-wildcard-cert workflow in the lotr_sut repo and re-provision."
fi

log "Starting SUT stack..."
cd "$SUT_DIR"

docker compose up -d
log "SUT stack started."

if [ -n "${JENKINS_DOMAIN:-}" ] && [ -d "$ESCAPE_ROOM_DIR" ]; then
    log "Starting DevOps Escape Room stack..."
    cd "$ESCAPE_ROOM_DIR"
    export JENKINS_URL="https://${JENKINS_DOMAIN}/"
    if docker compose up -d; then
        log "Initial devops-escape-room compose run completed"
    else
        log "WARNING: Initial devops-escape-room compose run reported a failure"
    fi

    if wait_for_escape_room_init; then
        log "DevOps escape-room services reconciled after gitea-init"
    else
        log "WARNING: DevOps escape-room stack did not fully converge during bootstrap"
    fi

    log "Started devops-escape-room stack for ${JENKINS_DOMAIN}"
elif [ -n "${JENKINS_DOMAIN:-}" ]; then
    log "WARNING: JENKINS_DOMAIN set but ${ESCAPE_ROOM_DIR} not found"
fi

if [ -n "${JENKINS_DOMAIN:-}" ] && [ -d "$ESCAPE_ROOM_DIR" ] && [ ! -f "$ESCAPE_ROOM_DIR/.env" ]; then
    log "WARNING: ${ESCAPE_ROOM_DIR}/.env not found (using exported env vars for compose substitution)"
fi

log "==========================="

log "Find Jenkins at https://${JENKINS_DOMAIN:-<no-jenkins-domain-configured>}/"
log "Find IDE at https://${IDE_DOMAIN:-<no-ide-domain-configured>}/"
log "Find Gitea at https://${GITEA_DOMAIN:-<no-gitea-domain-configured>}/"
log "Find SUT frontend at https://${CADDY_DOMAIN:-<no-caddy-domain-configured>}/"

log "==========================="

log "Golden AMI bootstrap completed"
"""


def get_user_data_script(template_config=None, workshop_name=None):
    """Get the user_data script content"""
    workshop_name = workshop_name or WORKSHOP_NAME

    if _uses_inline_golden_ami_bootstrap(workshop_name, template_config):
        logger.info(
            "Using inline golden AMI bootstrap for workshop %s (AMI: %s)",
            workshop_name,
            template_config.get('ami_id')
        )
        return _get_inline_golden_ami_bootstrap_script(workshop_name)

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
                    spot_max_price=None, idempotency_key=None, fallback_to_on_demand=False,
                    ec2_instance_type=None):
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
        fallback_to_on_demand: If True, retry with on-demand instances if Spot capacity is exhausted (default: False)
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
        idempotency_item_key = None
        if idempotency_key:
            idempotency_item_key = _build_create_request_item_key(
                workshop_name=workshop_name,
                tutorial_session_id=tutorial_session_id,
                instance_type=instance_type,
                idempotency_key=idempotency_key
            )

            existing_request = table.get_item(Key={'instance_id': idempotency_item_key})
            existing_item = existing_request.get('Item')
            if existing_item and existing_item.get('status') == 'success' and existing_item.get('result_json'):
                logger.info(f"Idempotent replay detected for key={idempotency_key}, returning stored create result")
                replay_result = json.loads(existing_item['result_json'])
                replay_result['idempotent_replay'] = True
                return replay_result
            if existing_item and existing_item.get('status') == 'in_progress':
                return {
                    'success': False,
                    'error': 'A create request with this idempotency key is already in progress',
                    'status_code': 409
                }
            if existing_item and existing_item.get('status') == 'failed':
                return {
                    'success': False,
                    'error': existing_item.get('error_message', 'Previous request with this idempotency key failed'),
                    'idempotent_replay': True,
                    'status_code': 500
                }

            table.put_item(
                Item={
                    'instance_id': idempotency_item_key,
                    'status': 'in_progress',
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'request_type': 'create_instance',
                    'idempotency_key': idempotency_key,
                    'workshop_name': workshop_name,
                    'instance_type': instance_type,
                    'tutorial_session_id': tutorial_session_id or ''
                },
                ConditionExpression='attribute_not_exists(instance_id)'
            )

        logger.info("=" * 80)
        logger.info(f"INSTANCE CREATION REQUEST")
        logger.info(f"  Workshop: {workshop_name}")
        logger.info(f"  Instance Type: {instance_type}")
        logger.info(f"  Count: {count}")
        logger.info(f"  Purchase Type: {purchase_type}")
        if purchase_type == 'spot':
            logger.info(f"  Spot Max Price: {spot_max_price if spot_max_price is not None else 'market default'}")
        logger.info(f"  Tutorial Session ID: {tutorial_session_id}")
        logger.info(f"  Idempotency Key: {idempotency_key or 'N/A'}")
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
        
        template_instance_type = template_config.get('instance_type') if template_config else None
        requested_instance_type = str(ec2_instance_type or '').strip().lower() or None
        selected_instance_type = requested_instance_type or template_instance_type or INSTANCE_TYPE
        if instance_type == 'pool' and requested_instance_type is None:
            # Keep pool defaults predictable across workshops and templates.
            selected_instance_type = DEFAULT_POOL_INSTANCE_TYPE
        if workshop_name == 'fellowship' and instance_type == 'admin' and selected_instance_type == 't3.small':
            logger.info("Upgrading fellowship admin instance type from t3.small to t3.medium for bootstrap reliability")
            selected_instance_type = 't3.medium'
        logger.info(
            "Selected instance type: %s (requested=%s, template=%s, default=%s)",
            selected_instance_type,
            requested_instance_type,
            template_instance_type,
            INSTANCE_TYPE
        )
        
        # Save the base user_data BEFORE the loop so each iteration gets a fresh copy.
        # Mutating user_data inside the loop without resetting causes domain exports
        # from iteration N to accumulate into the user_data of iteration N+1.
        base_user_data = get_user_data_script(template_config, workshop_name=workshop_name)
        user_data = base_user_data  # will be reset at the start of each loop iteration
        
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
            'setup_fellowship.sh': 'setup_fellowship.sh' in user_data,
            'exec setup script': 'exec "$SETUP_SCRIPT"' in user_data or "exec '$SETUP_SCRIPT'" in user_data,
            'devops-escape-room': 'devops-escape-room' in user_data.lower(),
            'dify': 'dify' in user_data.lower(),
            'golden-ami-bootstrap': '/opt/fellowship-sut' in user_data and 'docker compose' in user_data
        }
        
        logger.info("  Script markers:")
        for marker, found in markers.items():
            status = "✓" if found else "✗"
            logger.info(f"    {status} {marker}: {found}")
        
        if workshop_name in ['fellowship', 'fellowship-of-the-build']:
            if markers['golden-ami-bootstrap']:
                logger.info("  ✓ Fellowship golden AMI bootstrap DETECTED in user_data")
            elif markers['fellowship-sut']:
                logger.info("  ✓ Fellowship SUT deployment code DETECTED in user_data")
            elif markers['setup_fellowship.sh'] and markers['exec setup script'] and markers['S3 download']:
                logger.info("  ✓ Fellowship deployment is delegated to setup_fellowship.sh from S3")
            else:
                logger.warning("  ⚠ Fellowship SUT deployment code NOT FOUND - instance will NOT have SUT deployed!")
        
        logger.info("=" * 80)
        
        # Get timeout parameters - use provided values or fall back to SSM defaults
        timeouts = get_timeout_parameters(workshop_name)
        final_stop_timeout = stop_timeout if stop_timeout is not None else timeouts.get('stop_timeout', 4)
        final_terminate_timeout = terminate_timeout if terminate_timeout is not None else timeouts.get('terminate_timeout', 20)
        final_hard_terminate_timeout = hard_terminate_timeout if hard_terminate_timeout is not None else timeouts.get('hard_terminate_timeout', 45)
        
        instances = []
        
        reserved_indices = _reserve_instance_indices(
            workshop_name=workshop_name,
            tutorial_session_id=tutorial_session_id,
            instance_type=instance_type,
            count=count
        )
        logger.info(
            f"Reserved instance indices for workshop={workshop_name}, "
            f"tutorial_session_id={tutorial_session_id}, type={instance_type}: {reserved_indices}"
        )

        for i, instance_index in enumerate(reserved_indices):
            # Reset user_data to the base template for each iteration.
            # Without this, domain exports injected for instance N accumulate
            # into the user_data string passed to instance N+1.
            user_data = base_user_data
            
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
                if HTTPS_HOSTED_ZONE_ID:
                    tags.append({'Key': 'Route53ZoneId', 'Value': HTTPS_HOSTED_ZONE_ID})
                
                # Derive jenkins/ide subdomains (mirrors what setup_fellowship.sh does at boot)
                jenkins_domain = f"jenkins-{domain}"
                ide_domain = f"ide-{domain}"
                gitea_domain = f"gitea-{domain}"
                tags.append({'Key': 'GiteaDomain', 'Value': gitea_domain})
                tags.append({'Key': 'JenkinsDomain', 'Value': jenkins_domain})
                tags.append({'Key': 'IdeDomain', 'Value': ide_domain})
                
                logger.info(f"Generated domain name BEFORE instance creation: {domain} (sanitized from machine_name: {machine_name})")
                
                # Get S3 bucket and latest artifact for instance setup
                s3_bucket_name = None
                latest_artifact_key = None
                try:
                    # Retrieve S3 bucket name from SSM parameter
                    sut_bucket_param = f"/classroom/{workshop_name}/sut-bucket"
                    response = ssm.get_parameter(Name=sut_bucket_param)
                    s3_bucket_name = response['Parameter']['Value']
                    logger.info(f"Retrieved S3 bucket from SSM ({sut_bucket_param}): {s3_bucket_name}")
                    
                    # Get the latest artifact by LastModified timestamp
                    artifact_info = get_latest_sut_artifact_key(s3_bucket_name)
                    if artifact_info:
                        latest_artifact_key = artifact_info['artifact_key']
                        logger.info(f"✓ Latest artifact: {latest_artifact_key} (modified: {artifact_info['last_modified'].isoformat()})")
                    else:
                        logger.warning(f"No artifacts found in S3 bucket {s3_bucket_name} - using market default")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ParameterNotFound':
                        logger.info(f"S3 bucket parameter not found ({sut_bucket_param}) - S3 artifact injection skipped")
                    else:
                        logger.warning(f"Error retrieving S3 bucket from SSM: {str(e)}")
                except Exception as e:
                    logger.warning(f"Error getting latest S3 artifact: {str(e)}")
                
                # Inject domain and S3 artifact information into user_data as environment variables
                # This ensures the domain and artifact are available immediately without needing EC2 metadata service
                domain_exports = f"""# Domain information injected by Lambda (available immediately)
export CADDY_DOMAIN={domain}
export JENKINS_DOMAIN={jenkins_domain}
export GITEA_DOMAIN={gitea_domain}
export IDE_DOMAIN={ide_domain}
export MACHINE_NAME={machine_name}
export WORKSHOP_NAME={workshop_name}
export ROUTE53_ZONE_ID={HTTPS_HOSTED_ZONE_ID}
export AWS_REGION={REGION}
export ENVIRONMENT={ENVIRONMENT}
"""
                
                # Add S3 artifact information if available
                if s3_bucket_name:
                    domain_exports += f"export SUT_BUCKET={s3_bucket_name}\n"
                    logger.info(f"Injected S3 bucket: SUT_BUCKET={s3_bucket_name}")
                
                if latest_artifact_key:
                    domain_exports += f"export LATEST_TAR={latest_artifact_key}\n"
                    logger.info(f"Injected latest artifact: LATEST_TAR={latest_artifact_key}")
                
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
                    logger.info(f"Injected domain information into user_data: CADDY_DOMAIN={domain}, JENKINS_DOMAIN={jenkins_domain}, IDE_DOMAIN={ide_domain}, MACHINE_NAME={machine_name}, GITEA_DOMAIN={gitea_domain}")
                else:
                    # No shebang, prepend
                    user_data = domain_exports + user_data
                    logger.info(f"Prepended domain information to user_data: CADDY_DOMAIN={domain}, JENKINS_DOMAIN={jenkins_domain}, IDE_DOMAIN={ide_domain}, MACHINE_NAME={machine_name}, GITEA_DOMAIN={gitea_domain}")
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
                'TagSpecifications': [
                    {
                        'ResourceType': 'instance',
                        'Tags': tags
                    }
                ],
                'MetadataOptions': {
                    'HttpTokens': 'required',
                    'HttpEndpoint': 'enabled',
                    'HttpPutResponseHopLimit': 2
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

            if SUBNET_ID:
                run_instances_params['SubnetId'] = SUBNET_ID
            if SECURITY_GROUP_IDS:
                run_instances_params['SecurityGroupIds'] = SECURITY_GROUP_IDS
            
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
            
            # Launch instance with error handling for capacity issues
            try:
                response = ec2.run_instances(**run_instances_params)
            except ClientError as e:
                error_code = e.response['Error'].get('Code', 'Unknown')
                error_msg = e.response['Error'].get('Message', str(e))
                
                # Handle Spot capacity exhaustion
                if error_code == 'InsufficientInstanceCapacity' and purchase_type == 'spot':
                    logger.warning(f"Spot instance capacity exhausted: {error_msg}")
                    
                    # If fallback to on-demand is enabled, retry with on-demand
                    if fallback_to_on_demand:
                        logger.info("⚠ Spot capacity unavailable - retrying with ON-DEMAND instances (as per fallback_to_on_demand=True)")
                        # Remove Spot instance options and retry
                        if 'InstanceMarketOptions' in run_instances_params:
                            del run_instances_params['InstanceMarketOptions']
                        
                        try:
                            logger.info(f"  Retrying instance creation with ON-DEMAND instead of SPOT")
                            response = ec2.run_instances(**run_instances_params)
                            logger.info(f"✓ Instance created successfully with ON-DEMAND (fallback from Spot)")
                            # Mark instance as fallback in response
                            instances.append({
                                'note': 'Created with on-demand (Spot capacity unavailable)',
                                'fallback_from_spot': True
                            })
                        except ClientError as fallback_error:
                            fallback_error_code = fallback_error.response['Error'].get('Code', 'Unknown')
                            fallback_error_msg = fallback_error.response['Error'].get('Message', str(fallback_error))
                            logger.error(f"On-demand fallback also failed ({fallback_error_code}): {fallback_error_msg}")
                            
                            error_response = {
                                'success': False,
                                'error': f'Instance creation failed: {fallback_error_msg}',
                                'error_code': fallback_error_code,
                                'details': f'Spot capacity unavailable. On-demand fallback also failed.',
                                'instances_created': len(instances)
                            }
                            
                            if idempotency_item_key:
                                table.update_item(
                                    Key={'instance_id': idempotency_item_key},
                                    UpdateExpression='SET #status = :status, error_message = :error, completed_at = :completed_at',
                                    ExpressionAttributeNames={'#status': 'status'},
                                    ExpressionAttributeValues={
                                        ':status': 'failed',
                                        ':error': fallback_error_msg,
                                        ':completed_at': datetime.now(timezone.utc).isoformat()
                                    }
                                )
                            return error_response
                    else:
                        # No fallback - return error with suggestions
                        logger.info("Suggestions for resolving Spot capacity issues:")
                        logger.info("1. Set fallback_to_on_demand=true to automatically use on-demand instances")
                        logger.info("2. Try creating fewer instances (reduce count)")
                        logger.info("3. Try a different instance type (e.g., t3.small instead of t3.medium)")
                        logger.info("4. Try a different region or availability zone")
                        logger.info("5. Wait a few minutes and retry (Spot capacity changes frequently)")
                        
                        error_response = {
                            'success': False,
                            'error': f'Spot instance capacity not available: {error_msg}',
                            'error_code': error_code,
                            'suggestions': [
                                'Set fallback_to_on_demand=true to automatically retry with on-demand',
                                'Reduce the number of instances requested',
                                'Try a different instance type (t3.small, t3.large, etc)',
                                'Wait a few minutes - Spot capacity changes frequently',
                                'Check AWS Spot capacity dashboard for your region'
                            ],
                            'instances_created': len(instances),
                            'instances': instances if instances else None
                        }
                        
                        if idempotency_item_key:
                            table.update_item(
                                Key={'instance_id': idempotency_item_key},
                                UpdateExpression='SET #status = :status, error_message = :error, completed_at = :completed_at',
                                ExpressionAttributeNames={'#status': 'status'},
                                ExpressionAttributeValues={
                                    ':status': 'failed',
                                    ':error': error_msg,
                                    ':completed_at': datetime.now(timezone.utc).isoformat()
                                }
                            )
                        
                        return error_response
                
                # Handle other errors
                logger.error(f"EC2 RunInstances error ({error_code}): {error_msg}")
                raise
            
            
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
            if _uses_inline_golden_ami_bootstrap(workshop_name, template_config):
                user_data_source = 'Inline Golden AMI Bootstrap'
            elif template_config and template_config.get('user_data_base64'):
                user_data_source = 'SSM Template'
            else:
                user_data_source = 'Fallback Script'
            logger.info(f"  User Data Source: {user_data_source}")
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
        
        result = {
            'success': True,
            'instances': instances,
            'count': len(instances),
            'type': instance_type,
            'workshop': workshop_name
        }

        if idempotency_item_key:
            table.update_item(
                Key={'instance_id': idempotency_item_key},
                UpdateExpression='SET #status = :status, result_json = :result_json, completed_at = :completed_at',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'success',
                    ':result_json': json.dumps(convert_decimal(result)),
                    ':completed_at': datetime.now(timezone.utc).isoformat()
                }
            )

        return result
    except Exception as e:
        logger.error(f"Error creating instances: {str(e)}", exc_info=True)
        if 'idempotency_item_key' in locals() and idempotency_item_key:
            try:
                table.update_item(
                    Key={'instance_id': idempotency_item_key},
                    UpdateExpression='SET #status = :status, error_message = :error_message, completed_at = :completed_at',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':status': 'failed',
                        ':error_message': str(e),
                        ':completed_at': datetime.now(timezone.utc).isoformat()
                    }
                )
            except Exception as update_error:
                logger.warning(f"Failed to persist idempotency failure state: {str(update_error)}")
        return {
            'success': False,
            'error': str(e)
        }

def list_instances(include_terminated=False, tutorial_session_id=None, include_health=False, include_actual_costs=False):
    """List all EC2 instances with their assignments and IPs
    
    Args:
        include_terminated: If True, include terminated instances in the results
        tutorial_session_id: If provided, filter instances by this tutorial session ID
        include_health: If True, fetch health status from workshop endpoint for each instance
        include_actual_costs: If True, enrich instances with Cost Explorer actual costs when available
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
        
        session_defaults_cache = {}

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

                workshop_value = tags.get('WorkshopID', tags.get('Template', WORKSHOP_NAME))
                resolved_tutorial_session_id = tags.get('TutorialSessionID')

                session_defaults = {}
                if resolved_tutorial_session_id:
                    cache_key = f"{workshop_value}:{resolved_tutorial_session_id}"
                    if cache_key not in session_defaults_cache:
                        session_defaults_cache[cache_key] = _get_tutorial_session_defaults(
                            resolved_tutorial_session_id,
                            workshop_name=workshop_value
                        )
                    session_defaults = session_defaults_cache.get(cache_key, {})

                purchase_type = _normalize_purchase_type(
                    tags.get('PurchaseType') or session_defaults.get('purchase_type'),
                    'on-demand'
                )
                spot_max_price = _to_float(
                    tags.get('SpotMaxPrice') if 'SpotMaxPrice' in tags else session_defaults.get('spot_max_price')
                )
                cost_estimate = _estimate_instance_costs(
                    instance.get('InstanceType') or INSTANCE_TYPE,
                    purchase_type,
                    spot_max_price,
                    instance.get('LaunchTime')
                )
                
                instance_info = {
                    'instance_id': instance_id,
                    'state': state,
                    'public_ip': instance.get('PublicIpAddress'),
                    'private_ip': instance.get('PrivateIpAddress'),
                    'instance_type': instance.get('InstanceType'),
                    'launch_time': instance.get('LaunchTime').isoformat() if instance.get('LaunchTime') else None,
                    'tags': tags,
                    'type': instance_type,
                    'workshop': workshop_value,
                    'tutorial_session_id': resolved_tutorial_session_id,
                    'assigned_to': assignment.get('student_name'),
                    'assignment_status': assignment.get('status'),
                    'assigned_at': assignment.get('assigned_at'),
                    'cleanup_days': cleanup_days,  # Total cleanup days configured
                    'cleanup_days_remaining': cleanup_days_remaining,  # Days remaining before deletion
                    'https_domain': https_domain,  # HTTPS domain from tags
                    'https_url': https_url,  # Full HTTPS URL from tags
                    'purchase_type': purchase_type,
                    'spot_max_price': spot_max_price,
                    'hourly_rate_estimate_usd': cost_estimate['hourly_rate_estimate_usd'],
                    'estimated_runtime_hours': cost_estimate['estimated_runtime_hours'],
                    'estimated_cost_usd': cost_estimate['estimated_cost_usd'],
                    'estimated_cost_24h_usd': cost_estimate['estimated_cost_24h_usd']
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

        actual_cost_result = {
            'costs_by_instance': {},
            'actual_total_usd': None,
            'actual_data_source': 'unavailable'
        }

        if include_actual_costs:
            actual_cost_result = _fetch_actual_costs_for_instances([item['instance_id'] for item in instances])
            costs_by_instance = actual_cost_result.get('costs_by_instance', {})
            for item in instances:
                item['actual_cost_usd'] = costs_by_instance.get(item['instance_id'])
        
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
            'actual_total_usd': actual_cost_result.get('actual_total_usd'),
            'actual_data_source': actual_cost_result.get('actual_data_source', 'unavailable'),
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

def _terminate_on_demand_instance(instance_id, ec2_client, instance_details=None):
    """Terminate an on-demand EC2 instance.
    
    Args:
        instance_id: The EC2 instance ID to terminate
        ec2_client: The boto3 EC2 client
        instance_details: Optional cached instance details to avoid redundant API calls
    
    Returns:
        bool: True if termination was initiated successfully, False otherwise
    """
    try:
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        logger.info(f"Terminated on-demand instance {instance_id}")
        return True
    except Exception as e:
        logger.error(f"Error terminating on-demand instance {instance_id}: {str(e)}")
        return False


def _terminate_spot_instance(instance_id, ec2_client, instance_details=None):
    """Terminate a spot EC2 instance by canceling its Spot Instance Request first.
    
    For spot instances with 'persistent' type, terminating without canceling the spot request
    causes AWS to automatically launch replacement instances. This function:
    1. Cancels spot requests for spot instances (with TerminateInstances=True)
    2. Falls back to regular termination if spot request cancellation fails
    
    Args:
        instance_id: The EC2 instance ID to terminate
        ec2_client: The boto3 EC2 client
        instance_details: Optional cached instance details to avoid redundant API calls
    
    Returns:
        bool: True if termination was initiated successfully, False otherwise
    """
    try:
        # Get instance details if not provided
        if instance_details is None:
            response = ec2_client.describe_instances(InstanceIds=[instance_id])
            if not response['Reservations']:
                logger.warning(f"Spot instance {instance_id} not found for termination")
                return False
            instance_details = response['Reservations'][0]['Instances'][0]
        
        spot_request_id = instance_details.get('SpotInstanceRequestId')
        if spot_request_id:
            logger.info(f"Terminating spot instance {instance_id} by canceling spot request {spot_request_id}")
            try:
                ec2_client.cancel_spot_instance_requests(
                    SpotInstanceRequestIds=[spot_request_id]
                )
                logger.info(f"Canceled spot request {spot_request_id} and terminated instance {instance_id}")
            except ClientError as e:
                logger.warning(f"Failed to cancel spot request {spot_request_id}: {str(e)}, falling back to regular termination")
        else:
            logger.warning(f"Spot instance {instance_id} has no SpotInstanceRequestId, falling back to regular termination")
        
        # Fallback: Regular termination for spot instances without SIR or as fallback
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        logger.info(f"Terminated spot instance {instance_id} (fallback to regular termination)")
        return True
        
    except Exception as e:
        logger.error(f"Error terminating spot instance {instance_id}: {str(e)}")
        return False


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
                # Get instance details to check if it's spot or on-demand
                instance_details = None
                instance_tags = {}
                domain_to_delete = None
                is_spot = False
                
                try:
                    response = ec2.describe_instances(InstanceIds=[instance_id])
                    if response.get('Reservations') and response['Reservations'][0].get('Instances'):
                        instance_details = response['Reservations'][0]['Instances'][0]
                        instance_tags = {tag['Key']: tag['Value'] for tag in instance_details.get('Tags', [])}
                        domain_to_delete = instance_tags.get('HttpsDomain')
                        is_spot = instance_details.get('InstanceLifecycle') == 'spot'
                except Exception as e:
                    logger.warning(f"Error getting instance details for {instance_id}: {str(e)}")
                

                # Clean up Route53 records: main, jenkins, and ide subdomains
                domains_to_delete = [domain_to_delete]
                workshop_for_instance = str(instance_tags.get('WorkshopID', '')).strip().lower()
                if domain_to_delete and workshop_for_instance == 'fellowship':
                    domains_to_delete.append(f"jenkins-{domain_to_delete}")
                    domains_to_delete.append(f"ide-{domain_to_delete}")
                    domains_to_delete.append(f"gitea-{domain_to_delete}")
                for d in domains_to_delete:
                    dns_cleanup = _delete_route53_a_record(d, strict=False, max_retries=3)
                    if not dns_cleanup.get('success'):
                        logger.warning(
                            f"Route53 cleanup incomplete for {instance_id} (domain={d}), "
                            f"but proceeding with instance termination: reason={dns_cleanup.get('reason')}, attempts={dns_cleanup.get('attempts')}"
                        )

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
                
                # Terminate instance - handle spot and on-demand instances differently
                terminate_success = False
                if is_spot:
                    terminate_success = _terminate_spot_instance(instance_id, ec2, instance_details)
                else:
                    terminate_success = _terminate_on_demand_instance(instance_id, ec2, instance_details)
                
                if terminate_success:
                    deleted.append(instance_id)
                    logger.info(f"Initiated termination for {'spot' if is_spot else 'on-demand'} instance {instance_id} (async)")
                else:
                    errors.append(f'{instance_id}: failed to initiate termination')
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
                    errors.append(f'{instance_id}: not found')
                else:
                    errors.append(f'{instance_id}: {str(e)}')
                logger.error(f"Error processing deletion for {instance_id}: {str(e)}")
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

def get_always_on_tutorials():
    """Return always-on tutorial links and attempt light-touch recovery when needed."""
    ec2 = boto3.client('ec2', region_name=REGION)
    response = ec2.describe_instances(Filters=[
        {'Name': 'tag:Type', 'Values': ['always-on-tutorial']}
    ])

    found = {}
    for reservation in response.get('Reservations', []):
        for instance in reservation.get('Instances', []):
            tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
            tutorial = tags.get('TutorialType') or tags.get('WorkshopID')
            if tutorial:
                found.setdefault(tutorial, []).append(instance)

    tutorials = []
    for tutorial, instances in found.items():
        healthy_instance = None
        unhealthy_instance = None

        for inst in instances:
            state = inst.get('State', {}).get('Name')
            public_ip = inst.get('PublicIpAddress')
            if state == 'running' and public_ip:
                health, _, _ = check_instance_health(public_ip, tutorial)
                if health == 'healthy':
                    healthy_instance = inst
                    break
                unhealthy_instance = inst
            elif state == 'stopped':
                unhealthy_instance = inst

        instance = healthy_instance or unhealthy_instance

        if not healthy_instance:
            if unhealthy_instance:
                instance_state = unhealthy_instance.get('State', {}).get('Name')
                if instance_state == 'stopped':
                    try:
                        ec2.start_instances(InstanceIds=[unhealthy_instance['InstanceId']])
                        logger.info(f"Started stopped always-on instance for {tutorial}")
                    except Exception as e:
                        logger.warning(f"Failed to start stopped instance for {tutorial}: {e}")
                elif instance_state == 'running':
                    try:
                        ec2.reboot_instances(InstanceIds=[unhealthy_instance['InstanceId']])
                        logger.info(f"Rebooted unhealthy always-on instance for {tutorial}")
                    except Exception as e:
                        logger.warning(f"Failed to reboot unhealthy instance for {tutorial}: {e}")
            else:
                try:
                    result = create_instance(
                        count=1,
                        instance_type='always-on-tutorial',
                        workshop_name=tutorial,
                        purchase_type='spot',
                        tutorial_session_id=None
                    )
                    instance = result['instances'][0] if result.get('instances') else None
                    logger.info(f"Created new always-on instance for {tutorial}")
                except Exception as e:
                    logger.error(f"Failed to create always-on instance for {tutorial}: {e}")
                    instance = None

        url = f"https://sut-{tutorial}.testingfantasy.com"
        if instance and instance.get('PublicIpAddress'):
            try:
                setup_caddy_domain(instance['InstanceId'], tutorial, domain=f"sut-{tutorial}.testingfantasy.com")
            except Exception as e:
                logger.warning(f"Failed to update Route53 for {tutorial}: {e}")

        tutorials.append({'tutorial': tutorial, 'url': url})

    return tutorials

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

        # Handle always-on tutorials endpoint (no authentication required)
        if api_path == '/always-on-tutorials' and http_method == 'GET':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'success': True,
                    'tutorials': get_always_on_tutorials()
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
            ec2_instance_type = (
                body.get('ec2_instance_type')
                or query_params.get('ec2_instance_type')
                or body.get('ec3_instance_type')
                or query_params.get('ec3_instance_type')
                or body.get('instance_size')
                or query_params.get('instance_size')
                or None
            )
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

            if ec2_instance_type is not None:
                ec2_instance_type = str(ec2_instance_type).strip()
                if ec2_instance_type:
                    ec2_instance_type = ec2_instance_type.lower()
                if ec2_instance_type and ec2_instance_type not in ALLOWED_EC2_INSTANCE_TYPES:
                    return {
                        'statusCode': 400,
                        'headers': get_cors_headers(),
                        'body': json.dumps({
                            'success': False,
                            'error': 'ec2_instance_type must be one of: ' + ', '.join(sorted(ALLOWED_EC2_INSTANCE_TYPES))
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
            idempotency_key = (
                body.get('idempotency_key')
                or query_params.get('idempotency_key')
                or headers.get('Idempotency-Key')
                or headers.get('idempotency-key')
            )

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
                spot_max_price=spot_max_price,
                idempotency_key=idempotency_key,
                ec2_instance_type=ec2_instance_type
            )
            # Add a message indicating the operation is async
            if result['success']:
                replay_suffix = ' (idempotent replay)' if result.get('idempotent_replay') else ''
                result['message'] = f"✅ Initiated creation of {result['count']} {instance_type} instance(s){replay_suffix}. They will be stopped automatically once running. Refresh to see updates."

            status_code = result.get('status_code', 200 if result['success'] else 500)
            return {
                'statusCode': status_code,
                'headers': get_cors_headers(),
                'body': json.dumps(result)
            }
        
        elif api_path == '/list' and http_method == 'GET':
            # Check if include_terminated parameter is set
            include_terminated = query_params.get('include_terminated', 'false').lower() == 'true'
            # Check if include_health parameter is set (manual/on-demand only)
            include_health = query_params.get('include_health', 'false').lower() == 'true'
            include_actual_costs = query_params.get('include_actual_costs', 'false').lower() == 'true'
            # Check if tutorial_session_id filter is provided
            tutorial_session_id = query_params.get('tutorial_session_id')
            result = list_instances(
                include_terminated=include_terminated,
                tutorial_session_id=tutorial_session_id,
                include_health=include_health,
                include_actual_costs=include_actual_costs
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
            include_actual_costs = str(query_params.get('include_actual_costs', 'false')).lower() == 'true'
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

                instances_result = list_instances(
                    include_actual_costs=include_actual_costs
                )
                all_instances = instances_result.get('instances', []) if instances_result.get('success') else []
                # Filter instances by workshop
                workshop_instances = [inst for inst in all_instances if inst.get('workshop') == workshop_name]
                actual_data_source = instances_result.get('actual_data_source', 'unavailable')

                per_session_aggregates = {}
                for instance in workshop_instances:
                    session_id = instance.get('tutorial_session_id')
                    if not session_id:
                        continue

                    if session_id not in per_session_aggregates:
                        per_session_aggregates[session_id] = {
                            'actual_instance_count': 0,
                            'estimated_hourly_total_usd': 0.0,
                            'estimated_accrued_total_usd': 0.0,
                            'estimated_24h_total_usd': 0.0,
                            'actual_total_usd': 0.0,
                            'has_actual_costs': False
                        }

                    aggregate = per_session_aggregates[session_id]
                    aggregate['actual_instance_count'] += 1
                    aggregate['estimated_hourly_total_usd'] += float(instance.get('hourly_rate_estimate_usd') or 0.0)
                    aggregate['estimated_accrued_total_usd'] += float(instance.get('estimated_cost_usd') or 0.0)
                    aggregate['estimated_24h_total_usd'] += float(instance.get('estimated_cost_24h_usd') or 0.0)

                    actual_cost = instance.get('actual_cost_usd')
                    if actual_cost is not None:
                        aggregate['actual_total_usd'] += float(actual_cost)
                        aggregate['has_actual_costs'] = True
                
                sessions = []
                for item in response.get('Items', []):
                    session_id = item['session_id']
                    aggregate = per_session_aggregates.get(session_id, {
                        'actual_instance_count': 0,
                        'estimated_hourly_total_usd': 0.0,
                        'estimated_accrued_total_usd': 0.0,
                        'estimated_24h_total_usd': 0.0,
                        'actual_total_usd': 0.0,
                        'has_actual_costs': False
                    })
                    
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
                        'actual_instance_count': aggregate['actual_instance_count'],
                        'aggregated_estimated_cost_usd': round(aggregate['estimated_accrued_total_usd'], 6),
                        'aggregated_hourly_cost_usd': round(aggregate['estimated_hourly_total_usd'], 6),
                        'aggregated_estimated_24h_cost_usd': round(aggregate['estimated_24h_total_usd'], 6),
                        'aggregated_actual_cost_usd': round(aggregate['actual_total_usd'], 6) if aggregate['has_actual_costs'] else None,
                        'actual_data_source': actual_data_source
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
                instances_result = list_instances(tutorial_session_id=session_id, include_actual_costs=True)
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

                estimated_hourly_total_usd = round(sum((i.get('hourly_rate_estimate_usd') or 0.0) for i in instances), 6)
                estimated_accrued_total_usd = round(sum((i.get('estimated_cost_usd') or 0.0) for i in instances), 6)
                estimated_24h_total_usd = round(sum((i.get('estimated_cost_24h_usd') or 0.0) for i in instances), 6)

                instance_actual_values = [i.get('actual_cost_usd') for i in instances if i.get('actual_cost_usd') is not None]
                if instance_actual_values:
                    actual_total_usd = round(sum(instance_actual_values), 6)
                else:
                    actual_total_usd = instances_result.get('actual_total_usd')

                actual_data_source = instances_result.get('actual_data_source', 'unavailable')
                
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
                        'costs': {
                            'estimated_hourly_total_usd': estimated_hourly_total_usd,
                            'estimated_accrued_total_usd': estimated_accrued_total_usd,
                            'estimated_24h_total_usd': estimated_24h_total_usd,
                            'actual_total_usd': actual_total_usd,
                            'actual_data_source': actual_data_source
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
                delete_result = None
                if should_delete_instances and instances:
                    instance_ids = [i['instance_id'] for i in instances if i.get('state') != 'terminated']
                    if instance_ids:
                        delete_result = delete_instances(instance_ids=instance_ids, delete_type='individual')
                        if not delete_result.get('success'):
                            return {
                                'statusCode': 500,
                                'headers': get_cors_headers(),
                                'body': json.dumps({
                                    'success': False,
                                    'error': 'Failed to delete all session instances',
                                    'delete_result': delete_result
                                })
                            }
                
                # Delete session record
                sessions_table.delete_item(Key={'session_id': session_id})
                
                return {
                    'statusCode': 200,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'success': True,
                        'message': f'Session {session_id} deleted',
                        'instances_deleted': should_delete_instances,
                        'instance_delete_result': delete_result if should_delete_instances else None
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
