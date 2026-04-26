import json
import boto3
import os
from botocore.exceptions import ClientError
import time
import urllib.parse
import csv
import io
import secrets
import string
import traceback
import logging
import threading
import re
from datetime import datetime, timedelta
import random
import time as _debug_time
import uuid

# Get region and workshop context from environment variables
REGION = os.environ.get('AWS_DEFAULT_REGION', os.environ.get('AWS_REGION', 'eu-west-3'))
WORKSHOP_NAME = os.environ.get('WORKSHOP_NAME', 'fellowship')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# Initialize AWS clients
secretsmanager = boto3.client('secretsmanager', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
ec2 = boto3.client('ec2', region_name=REGION)
table = dynamodb.Table(f"instance-assignments-{WORKSHOP_NAME}-{ENVIRONMENT}")

# Get account ID from environment variable
ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID', '087559609246')

# Add this constant at the top of the file
DESTROY_KEY = os.environ.get('DESTROY_KEY', 'default_destroy_key')

#Status Lambda URL
status_lambda_url = os.environ.get('STATUS_LAMBDA_URL')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

NO_CACHE_HEADERS = {
    'Content-Type': 'text/html',
    'Cache-Control': 'no-store, no-cache, must-revalidate, private, max-age=0',
    'Pragma': 'no-cache',
    'Vary': '*',
}


def _build_response(status_code, body, cookies=None, content_type='text/html'):
    """Build an HTTP response with anti-caching headers.

    Every response from this Lambda MUST go through this helper so that
    CloudFront never caches or collapses user-specific responses.
    """
    headers = {
        'Content-Type': content_type,
        'Cache-Control': 'no-store, no-cache, must-revalidate, private, max-age=0',
        'Pragma': 'no-cache',
        'Vary': '*',
    }
    response = {
        'statusCode': status_code,
        'body': body,
        'headers': headers,
    }
    if cookies:
        response['cookies'] = cookies
    return response


def is_valid_fellowship_student_name(student_name):
    """Fellowship student IDs must match character_uuid format (e.g. legolas_ab12)."""
    if not student_name:
        return False
    return bool(re.match(r'^[a-z]+_[a-z0-9]{3,4}$', student_name.strip()))

# region agent debug log
def _debug_log(hypothesis_id, location, message, data=None):
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(_debug_time.time() * 1000)
        }
        with open("/Users/paula.bassaganas/Repositories/Bassagan/cloud-classroom-provisioning/.cursor/debug.log", "a") as log_file:
            log_file.write(json.dumps(payload) + "\n")
        logger.info("DEBUG_NDJSON %s", json.dumps(payload))
    except Exception:
        pass
# endregion agent debug log

def create_cookie_headers(user_info):
    """Create Set-Cookie headers for user session information"""
    cookies = []
    max_age = 7 * 24 * 60 * 60  # 7 days in seconds
    
    if user_info.get('user_name'):
        user_cookie = f"testus_patronus_user={urllib.parse.quote(user_info['user_name'])}; Path=/; Max-Age={max_age}; Secure; SameSite=Lax"
        cookies.append(user_cookie)
    
    if user_info.get('instance_id'):
        instance_cookie = f"testus_patronus_instance_id={urllib.parse.quote(user_info['instance_id'])}; Path=/; Max-Age={max_age}; Secure; SameSite=Lax"
        cookies.append(instance_cookie)
    
    if user_info.get('ec2_ip'):
        ip_cookie = f"testus_patronus_ip={urllib.parse.quote(user_info['ec2_ip'])}; Path=/; Max-Age={max_age}; Secure; SameSite=Lax"
        cookies.append(ip_cookie)
    
    # Return as a list for multi-value headers (Lambda Function URLs support this)
    return cookies

def get_secret():
    """Retrieve Azure OpenAI configuration from AWS Secrets Manager"""
    secret_name = "azure/llm/configs"
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        logger.info(f"[Azure Config] Successfully retrieved secret '{secret_name}': {len(secret)} configs found.")
        if not secret:
            logger.warning(f"[Azure Config] No LLM configs found in secret '{secret_name}'.")
        return secret
    except ClientError as e:
        logger.error(f"[Azure Config] Error retrieving secret '{secret_name}': {str(e)}")
        return []

def get_available_pool_instances(workshop_name=None, region=None):
    """
    Query EC2 for ALL available pool instances (FIFO fairness).
    
    Returns a list so callers can iterate and claim atomically,
    preventing race conditions when multiple requests arrive concurrently.
    
    Filters:
    - AssignedStudent=false (not yet assigned)
    - Type=pool
    - WorkshopID=<workshop> (prevents cross-workshop pickup)
    - instance-state-name: running, pending, stopped, stopping
    - Sort by CreatedAt ascending (FIFO fairness)
    
    Returns:
        list of dicts, each with instance details (sorted oldest-first):
        [{
          'instance_id': str,
          'student_name': str (from Student tag),
          'machine_name': str (from MachineName tag),
          'https_domain': str (from HttpsDomain tag),
          'jenkins_domain': str (from JenkinsDomain tag),
          'gitea_domain': str (from GiteaDomain tag),
          'ide_domain': str (from IdeDomain tag),
          'tags': dict (all EC2 tags)
        }]
    """
    workshop = workshop_name or WORKSHOP_NAME
    region_to_use = region or REGION
    
    try:
        ec2_client = boto3.client('ec2', region_name=region_to_use)
        response = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:AssignedStudent', 'Values': ['false']},
                {'Name': 'tag:Type', 'Values': ['pool']},
                {'Name': 'tag:WorkshopID', 'Values': [workshop]},
                {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped', 'stopping']}
            ]
        )
        
        available_instances = []
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                created_at = instance.get('LaunchTime') or datetime.utcnow()
                available_instances.append({
                    'instance_id': instance['InstanceId'],
                    'created_at': created_at,
                    'tags': tags,
                    'state': instance['State']['Name']
                })
        
        if not available_instances:
            logger.warning(f"No available pool instances found for workshop '{workshop}'")
            return []
        
        # Sort by CreatedAt ascending (FIFO fairness - oldest first)
        available_instances.sort(key=lambda x: x['created_at'])
        
        results = []
        for inst in available_instances:
            tags = inst['tags']
            student_name = tags.get('Student', '').strip()
            if not is_valid_fellowship_student_name(student_name):
                logger.warning(
                    f"Skipping pool instance {inst['instance_id']} with invalid Student tag '{student_name}'"
                )
                continue
            results.append({
                'instance_id': inst['instance_id'],
                'student_name': student_name,
                'machine_name': tags.get('MachineName', ''),
                'https_domain': tags.get('HttpsDomain', ''),
                'jenkins_domain': tags.get('JenkinsDomain', ''),
                'gitea_domain': tags.get('GiteaDomain', ''),
                'ide_domain': tags.get('IdeDomain', ''),
                'tags': tags
            })
        
        logger.info(f"Found {len(results)} available pool instances for workshop '{workshop}'")
        return results
    
    except Exception as e:
        logger.error(f"Error getting available pool instance: {str(e)}", exc_info=True)
        return None

def claim_pool_instance(instance_id, student_name, workshop_name=None, environment=None):
    """
    Finalize the assignment of a pool instance to a student.
    
    Steps:
    1. Update EC2 tags: AssignedStudent + Status = assigned
    2. Start the instance if stopped
    3. Update DynamoDB: Convert pool_created → assigned
    
    Args:
        instance_id: EC2 instance ID
        student_name: Student identifier (e.g., legolas_xy37)
        workshop_name: Workshop identifier (defaults to WORKSHOP_NAME)
        environment: Environment (defaults to ENVIRONMENT)
    
    Returns:
        dict: {'success': bool, 'instance_id': str, 'student_name': str, 'message': str}
    """
    workshop = workshop_name or WORKSHOP_NAME
    env = environment or ENVIRONMENT
    
    try:
        # Step 1: Atomic DynamoDB conditional write (prevents race condition)
        # This MUST happen BEFORE EC2 tag updates to act as a distributed lock.
        # Only succeeds if:
        #   - No record exists for this instance_id, OR
        #   - Existing record has a non-assigned status (pool_created, stopped, available)
        assignment_table = dynamodb.Table(f"instance-assignments-{workshop}-{env}")
        timestamp = datetime.utcnow().isoformat()
        ttl_seconds = 90 * 24 * 60 * 60  # 90 days
        ttl_epoch = int((datetime.utcnow() + timedelta(seconds=ttl_seconds)).timestamp())
        
        try:
            assignment_table.put_item(
                Item={
                    'instance_id': instance_id,
                    'student_name': student_name,
                    'password': student_name,  # Default password = student name
                    'workshop': workshop,
                    'status': 'assigned',
                    'assignment_source': 'fellowship_user_management',
                    'created_at': timestamp,
                    'assigned_at': timestamp,
                    'instance_type': 'pool',
                    'ttl': ttl_epoch
                },
                ConditionExpression='attribute_not_exists(instance_id) OR #s IN (:pool_created, :stopped, :available)',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':pool_created': 'pool_created',
                    ':stopped': 'stopped',
                    ':available': 'available'
                }
            )
            logger.info(f"✓ DynamoDB atomic claim succeeded: instance {instance_id} assigned to {student_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Instance {instance_id} already claimed by another request (conditional check failed)")
                return {
                    'success': False,
                    'instance_id': instance_id,
                    'student_name': student_name,
                    'reason': 'already_claimed',
                    'message': f'Instance {instance_id} was already claimed by another concurrent request'
                }
            raise  # Re-raise other ClientErrors
        
        # Step 2: Update EC2 tags (AssignedStudent + Status)
        # This is now safe because DynamoDB conditional write succeeded
        ec2.create_tags(
            Resources=[instance_id],
            Tags=[
                {'Key': 'AssignedStudent', 'Value': student_name},
                {'Key': 'Status', 'Value': 'assigned'},
            ]
        )
        logger.info(f"✓ Updated EC2 tags AssignedStudent={student_name}, Status=assigned for instance {instance_id}")
        
        # Step 3: Start instance if stopped
        try:
            instance_response = ec2.describe_instances(InstanceIds=[instance_id])
            instance_state = instance_response['Reservations'][0]['Instances'][0]['State']['Name']
            if instance_state in ('stopped', 'stopping'):
                ec2.start_instances(InstanceIds=[instance_id])
                logger.info(f"✓ Started stopped instance {instance_id}")
        except Exception as start_err:
            logger.warning(f"Could not start instance {instance_id}: {str(start_err)}")
        
        return {
            'success': True,
            'instance_id': instance_id,
            'student_name': student_name,
            'message': f'Successfully claimed instance {instance_id} for student {student_name}'
        }
    
    except Exception as e:
        logger.error(f"Error claiming pool instance {instance_id}: {str(e)}", exc_info=True)
        return {
            'success': False,
            'instance_id': instance_id,
            'student_name': student_name,
            'message': f'Failed to claim instance: {str(e)}'
        }

def extract_sut_urls_from_instance(tags):
    """
    Extract service URLs from EC2 instance tags.
    
    Builds proper URLs from domain tags and student name.
    JenkinsDomain/GiteaDomain may be just the domain or may contain
    legacy full-URL values (with 'None') — handles both cases.
    
    Args:
        tags: dict of EC2 tags (Key-Value pairs)
    
    Returns:
        dict: {
          'sut_url': str,
          'jenkins_url': str,
          'gitea_url': str,
          'ide_url': str
        }
    """
    student_name = tags.get('Student', '')
    https_domain = tags.get('HttpsDomain', '')
    sut_url = f"https://{https_domain}" if https_domain else ''
    
    # Build Jenkins URL: domain + /job/{student_name}/
    jenkins_domain_raw = tags.get('JenkinsDomain', '')
    jenkins_url = ''
    if jenkins_domain_raw and student_name:
        # Strip protocol and path to get just the domain
        jd = jenkins_domain_raw.replace('https://', '').replace('http://', '').split('/')[0]
        jenkins_url = f"https://{jd}/job/{student_name}/"
    
    # Build Gitea URL as login page with redirect to student repo.
    # Example:
    # https://gitea.fellowship.testingfantasy.com/user/login?redirect_to=%2ffellowship-org%2ffellowship-sut-legolas_ab12
    gitea_domain_raw = tags.get('GiteaDomain', '')
    gitea_org = tags.get('GiteaOrg', 'fellowship-org')
    gitea_url = ''
    if gitea_domain_raw and student_name:
        # Strip protocol and path to get just the domain
        gd = gitea_domain_raw.replace('https://', '').replace('http://', '').split('/')[0]
        repo_path = f"/{gitea_org}/fellowship-sut-{student_name}"
        redirect_to = urllib.parse.quote(repo_path, safe='')
        gitea_url = f"https://{gd}/user/login?redirect_to={redirect_to}"
    
    # Build IDE URL
    ide_domain = tags.get('IdeDomain', '')
    ide_url = f"https://{ide_domain}" if ide_domain else ''
    
    return {
        'sut_url': sut_url,
        'jenkins_url': jenkins_url,
        'gitea_url': gitea_url,
        'ide_url': ide_url
    }

def enrich_user_info_with_urls(user_info, instance_tags):
    """
    Enrich user_info dict with SUT/Jenkins/Gitea/IDE URLs extracted from EC2 instance tags.
    Only sets URLs that are not already present in user_info.
    """
    if not instance_tags:
        return user_info
    urls = extract_sut_urls_from_instance(instance_tags)
    for key in ('sut_url', 'jenkins_url', 'gitea_url', 'ide_url'):
        if not user_info.get(key) and urls.get(key):
            user_info[key] = urls[key]
    return user_info

def generate_student_env_content(user_info, azure_configs=None):
    """
    Generate a complete .env file content for the student to use in their IDE.

    Combines:
    - Student profile & event sourcing (STUDENT_ID, SQS, AWS_REGION)
    - Azure OpenAI credentials (from Secrets Manager)
    - Jenkins connection details (from EC2 instance tags)
    - Gitea connection details (from EC2 instance tags)
    - SUT backend configuration

    Args:
        user_info: dict with student assignment data (user_name, jenkins_url, gitea_url, etc.)
        azure_configs: list of Azure OpenAI config dicts from Secrets Manager

    Returns:
        str: Complete .env file content ready for download
    """
    student_name = user_info.get('user_name', '')
    sut_url = user_info.get('sut_url', '')
    jenkins_url = user_info.get('jenkins_url', '')
    gitea_url = user_info.get('gitea_url', '')

    # Extract Jenkins base URL (strip /job/student-name/ path)
    jenkins_base = ''
    if jenkins_url:
        # jenkins_url is like https://jenkins.fellowship.testingfantasy.com/job/student_name/
        parts = jenkins_url.split('/job/')
        jenkins_base = parts[0] if parts else jenkins_url.rstrip('/')

    # Extract Gitea base URL and org/repo from the URL.
    # Supports both direct repo URL and login redirect URL.
    gitea_base = ''
    gitea_owner = ''
    gitea_repo = ''
    if gitea_url:
        # gitea_url can be either:
        # - https://gitea.../fellowship-org/fellowship-sut-student_name
        # - https://gitea.../user/login?redirect_to=%2ffellowship-org%2ffellowship-sut-student_name
        try:
            from urllib.parse import urlparse
            parsed = urlparse(gitea_url)
            gitea_base = f"{parsed.scheme}://{parsed.netloc}"
            if parsed.path.strip('/') == 'user/login' and parsed.query:
                query = urllib.parse.parse_qs(parsed.query)
                redirect_values = query.get('redirect_to', [])
                if redirect_values:
                    decoded_path = urllib.parse.unquote(redirect_values[0]).strip('/')
                    path_parts = decoded_path.split('/')
                    if len(path_parts) >= 1:
                        gitea_owner = path_parts[0]
                    if len(path_parts) >= 2:
                        gitea_repo = path_parts[1]
            else:
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 1:
                    gitea_owner = path_parts[0]
                if len(path_parts) >= 2:
                    gitea_repo = path_parts[1]
        except Exception:
            gitea_base = gitea_url

    # Pick the first Azure config (or empty placeholders)
    azure_endpoint = ''
    azure_api_key = ''
    azure_deployment = ''
    azure_api_version = ''
    azure_max_tokens = '500'
    azure_temperature = '0.7'
    if azure_configs and len(azure_configs) > 0:
        cfg = azure_configs[0]
        azure_endpoint = cfg.get('endpoint', '')
        azure_api_key = cfg.get('api_key', '')
        azure_deployment = cfg.get('deployment_name', '')
        azure_api_version = cfg.get('api_version', '2024-12-01-preview')
        azure_max_tokens = str(cfg.get('max_tokens', 500))
        azure_temperature = str(cfg.get('temperature', 0.7))

    # SQS Queue URL — construct from known pattern
    sqs_queue_url = f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT_ID}/sqs-student-progress-{WORKSHOP_NAME}-{ENVIRONMENT}-euwest1"

    env_content = f"""# ════════════════════════════════════════════════════════════════════════════════
# FELLOWSHIP WORKSHOP — Student .env Configuration
# ════════════════════════════════════════════════════════════════════════════════
# Generated for: {student_name}
# Place this file in the repository root: palantir-jenkins-ai/.env
#
# This file is also used by the SUT backend (lotr_sut/sut/backend/.env)

# ── STUDENT PROFILE & EVENT SOURCING ─────────────────────────────────────────
STUDENT_ID={student_name}
SQS_QUEUE_URL={sqs_queue_url}
AWS_REGION={REGION}
ENVIRONMENT=aws
TRACKER_LOG_LEVEL=INFO

# ── Azure OpenAI (LLM Provider) ──────────────────────────────────────────────
# Used by: ex1, ex2 (query_client), ex3, ex4, ex5, SUT backend
AZURE_OPENAI_ENDPOINT={azure_endpoint}
AZURE_OPENAI_API_KEY={azure_api_key}
AZURE_OPENAI_DEPLOYMENT={azure_deployment}
AZURE_OPENAI_API_VERSION={azure_api_version}
AZURE_OPENAI_MAX_TOKENS={azure_max_tokens}
AZURE_OPENAI_TEMPERATURE={azure_temperature}

# ── Jenkins ───────────────────────────────────────────────────────────────────
# Used by: ex2-jenkins-mcp-server, ex4-gitea-mcp, ex5-grand-finale
JENKINS_URL={jenkins_base}
JENKINS_USER={student_name}
JENKINS_TOKEN=<your-jenkins-api-token>
JENKINS_PIPELINE=fellowship-pipeline
JENKINS_STUDENT={student_name}

# ── Gitea ─────────────────────────────────────────────────────────────────────
# Used by: ex3-notification-mcp, ex4-gitea-mcp, ex5-grand-finale
GITEA_URL={gitea_base}
GITEA_TOKEN=<your-gitea-api-token>
GITEA_OWNER={gitea_owner}
GITEA_REPO={gitea_repo}
GITEA_USER={student_name}

# ── Email Service (Maildog) ───────────────────────────────────────────────────
# Used by: ex3-notification-mcp, ex5-grand-finale
MAILDOG_URL=https://maildog.fellowship.testingfantasy.com
MAILDOG_API_TOKEN=<your-maildog-token>
STUDENT_EMAIL={student_name}@fellowship.testingfantasy.com

# ── SUT Backend (Flask) ──────────────────────────────────────────────────────
# Used by: lotr_sut/sut/backend
SECRET_KEY=dev-secret-key-change-in-production

# ── Leaderboard (local only) ─────────────────────────────────────────────────
LEADERBOARD_DB=.docker/leaderboard.db
API_HOST=0.0.0.0
API_PORT=5050

# ── Your SUT URL ──────────────────────────────────────────────────────────────
DEPLOYED_SUT_URL={sut_url}
"""
    return env_content.strip() + '\n'

def generate_html_response(user_info, error_message=None, status_lambda_url=None):
    if error_message:
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>Fellowship Workshop</title>
            <link rel="icon" href="https://lotr-prod.testingfantasy.com/middle-earth-map/icons/the_one_ring.ico" type="image/x-icon">
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700;900&family=Lora:ital,wght@0,400;0,600;0,700;1,400&display=swap" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
            <style>
                :root {{
                    --blue: #2a2118;
                    --pink: #b48a2b;
                    --yellow: #c9b28b;
                    --white: #f4e4bc;
                    --gray: #fbf3e2;
                    --shadow: 0 8px 32px rgba(35,26,18,0.18);
                }}
                body {{
                    background: var(--blue);
                    font-family: 'Lora', Georgia, serif;
                    margin: 0;
                    padding: 0;
                    color: var(--blue);
                }}
                .container {{
                    max-width: 700px;
                    margin: 60px auto;
                    background: var(--white);
                    border-radius: 18px;
                    box-shadow: var(--shadow);
                    padding: 40px 36px 36px 36px;
                    text-align: center;
                }}
                .header-row {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 24px;
                    margin-bottom: 28px;
                    flex-wrap: wrap;
                }}
                .logo {{
                    max-width: 200px;
                    border-radius: 12px;
                    object-fit: contain;
                }}
                .main-title {{
                    color: var(--blue);
                    text-align: center;
                    margin-bottom: 0px;
                    font-size: 2.8rem;
                    font-weight: 900;
                    font-family: 'Cinzel', serif;
                    letter-spacing: 1px;
                    margin-top: 0.3em;
                }}
                .subtitle {{
                    color: var(--pink);
                    text-align: center;
                    font-size: 1.2rem;
                    font-weight: 700;
                    margin-bottom: 28px;
                    margin-top: 0.4em;
                }}
                .error-box {{
                    background: var(--gray);
                    border: 2px solid var(--pink);
                    border-radius: 12px;
                    padding: 28px 24px;
                    margin-bottom: 24px;
                }}
                .error-icon {{
                    font-size: 3rem;
                    margin-bottom: 12px;
                }}
                .error-title {{
                    font-family: 'Cinzel', serif;
                    font-size: 1.4rem;
                    font-weight: 700;
                    color: var(--blue);
                    margin-bottom: 10px;
                }}
                .error-message {{
                    color: #5c4a22;
                    font-size: 1.05rem;
                    line-height: 1.6;
                    margin-bottom: 20px;
                }}
                .retry-button {{
                    background: var(--pink);
                    color: var(--white);
                    border: none;
                    padding: 12px 32px;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-family: 'Cinzel', serif;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background 0.2s, transform 0.2s;
                    box-shadow: 0 2px 8px rgba(35,26,18,0.15);
                }}
                .retry-button:hover {{
                    background: var(--blue);
                    transform: translateY(-2px);
                }}
                .header-link {{
                    color: var(--blue);
                    text-decoration: none;
                    font-weight: 600;
                    font-size: 0.9rem;
                    padding: 8px 16px;
                    background: var(--white);
                    border-radius: 8px;
                    border: 2px solid var(--blue);
                    transition: all 0.3s ease;
                    display: inline-block;
                }}
                .header-link:hover {{
                    background: var(--pink);
                    color: var(--white);
                    border-color: var(--pink);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header-row">
                    <a href="https://testingfantasy.com" class="header-link" target="_blank" rel="noopener noreferrer">Testing Fantasy</a>
                    <img src="https://lotr.fellowship.testingfantasy.com/logo.png" alt="Fellowship Quest Tracker Logo" class="logo">
                    <a href="https://docs.fellowship.testingfantasy.com" class="header-link" target="_blank" rel="noopener noreferrer">Documentation</a>
                </div>
                <div class="main-title">Fellowship Workshop</div>
                <div class="subtitle">CI/CD and AI-assisted testing with Lord of the Rings</div>
                <div class="error-box">
                    <div class="error-icon">⚔️</div>
                    <div class="error-title">The path is not yet clear</div>
                    <div class="error-message">{error_message}</div>
                    <button class="retry-button" onclick="window.location.href='/'">
                        <i class="fas fa-redo"></i> Try Again
                    </button>
                </div>
            </div>
        </body>
        </html>
        """
    # Generate .env file content for the student
    azure_configs = user_info.get('azure_configs', [])
    env_file_content = generate_student_env_content(user_info, azure_configs)
    # Escape for safe embedding in HTML/JS
    env_file_escaped = env_file_content.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')

    env_download_html = f"""
    <div class=\"info-box\">
        <h2><i class=\"fas fa-file-code\"></i> Workshop .env Configuration</h2>
        <p style=\"text-align:center;color:#5c4a22;margin-bottom:16px;\">
            Download or copy this <code>.env</code> file into your IDE workspace root
            (<code>palantir-jenkins-ai/.env</code>) to complete the exercises.
            It also works as the SUT backend config (<code>lotr_sut/sut/backend/.env</code>).
        </p>
        <div style=\"display:flex;gap:12px;justify-content:center;margin-bottom:18px;flex-wrap:wrap;\">
            <button class=\"retry-button\" onclick=\"downloadEnvFile()\" style=\"background:var(--pink);font-size:0.95rem;padding:10px 24px;\">
                <i class=\"fas fa-download\"></i> Download .env
            </button>
            <button class=\"retry-button\" onclick=\"copyEnvToClipboard()\" style=\"background:var(--blue);font-size:0.95rem;padding:10px 24px;\">
                <i class=\"fas fa-copy\"></i> Copy to Clipboard
            </button>
        </div>
        <details style=\"margin-top:8px;\">
            <summary style=\"cursor:pointer;font-weight:600;color:var(--blue);font-size:1rem;padding:8px 0;\">
                <i class=\"fas fa-eye\"></i> Preview .env contents
            </summary>
            <pre id=\"env-preview\" style=\"background:#2a2118;color:#c9b28b;padding:16px;border-radius:8px;font-size:0.85rem;overflow-x:auto;max-height:400px;overflow-y:auto;white-space:pre;margin-top:8px;\">{env_file_content}</pre>
        </details>
        <p style=\"text-align:center;color:#888;font-size:0.85rem;margin-top:12px;\">
            <i class=\"fas fa-info-circle\"></i>
            <strong>Note:</strong> <code>JENKINS_TOKEN</code>, <code>GITEA_TOKEN</code>, and <code>MAILDOG_API_TOKEN</code> must be generated from your Jenkins/Gitea/Maildog dashboards.
            See the <a href=\"https://docs.fellowship.testingfantasy.com\" target=\"_blank\">documentation</a> for instructions.
        </p>
    </div>
    """

    # Create instance info HTML based on whether instance assignment was successful
    instance_info_html = ""
    if 'instance_id' in user_info and user_info['instance_id']:
        # Build Fellowship-specific instance HTML with SUT URL and credentials
        sut_url = user_info.get('sut_url', '')
        credentials = user_info.get('credentials', {'username': '', 'password': ''})
        jenkins_url = user_info.get('jenkins_url', '')
        gitea_url = user_info.get('gitea_url', '')
        ide_url = user_info.get('ide_url', '')
        
        instance_info_html = f"""
        <div class=\"instance-section\">
            <h2>Fellowship Instance Information</h2>
            <div class=\"instance-cards\">
                <div class=\"instance-card\">
                    <div class=\"card-header\">
                        <i class=\"fas fa-server\"></i>
                        <span>SUT Instance</span>
                    </div>
                    <div class=\"sut-link-container\" id=\"sut-link-container\">
                        <div id=\"sut-spinner\" class=\"spinner\"></div>
                        <a id=\"sut-link\" href=\"{sut_url}\" target=\"_blank\" class=\"service-link{' ready' if sut_url else ''}\">
                            <i class=\"fas fa-external-link-alt\"></i> {sut_url if sut_url else 'Starting SUT...'}
                        </a>
                        <p id=\"sut-status-msg\" class=\"status-message\">{'' if sut_url else 'Waiting for SUT to become ready...'}</p>
                    </div>
                </div>
                <div class=\"instance-card\">
                    <div class=\"card-header\">
                        <i class=\"fas fa-laptop-code\"></i>
                        <span>IDE</span>
                    </div>
                    <div class=\"sut-link-container\" id=\"ide-link-container\">
                        <div id=\"ide-spinner\" class=\"spinner\"></div>
                        <a id=\"ide-link\" href=\"{ide_url}\" target=\"_blank\" class=\"service-link{' ready' if ide_url else ''}\">
                            <i class=\"fas fa-laptop-code\"></i> {ide_url if ide_url else 'Starting IDE...'}
                        </a>
                        <p id=\"ide-status-msg\" class=\"status-message\">{'' if ide_url else 'Waiting for IDE to become ready...'}</p>
                    </div>
                    <div class=\"credentials-info\" style=\"margin-top:8px;\">
                        <div class=\"config-row\">
                            <span class=\"credential-label\">IDE Password</span>
                            <span class=\"credential-value\">fellowship</span>
                            <button class=\"copy-btn\" onclick=\"copyToClipboard('fellowship')\" title=\"Copy\"><i class=\"fas fa-copy\"></i></button>
                        </div>
                    </div>
                </div>
                <div class=\"instance-card\">
                    <div class=\"card-header\">
                        <i class=\"fas fa-user-shield\"></i>
                        <span>Jenkins &amp; Gitea Access</span>
                    </div>
                    <div class=\"credentials-info\" style=\"margin-bottom:10px;\">
                        <div class=\"config-row\">
                            <span class=\"credential-label\">Username</span>
                            <span class=\"credential-value\">{credentials.get('username', '')}</span>
                            <button class=\"copy-btn\" onclick=\"copyToClipboard('{credentials.get('username', '')}')\" title=\"Copy\"><i class=\"fas fa-copy\"></i></button>
                        </div>
                        <div class=\"config-row\">
                            <span class=\"credential-label\">Password</span>
                            <span class=\"credential-value\">{credentials.get('password', '')}</span>
                            <button class=\"copy-btn\" onclick=\"copyToClipboard('{credentials.get('password', '')}')\" title=\"Copy\"><i class=\"fas fa-copy\"></i></button>
                        </div>
                    </div>
                    <div class=\"service-links\" id=\"dev-tools-container\">
                        <div id=\"dev-tools-spinner\" class=\"spinner\"></div>
                        <p id=\"dev-tools-status\" class=\"status-message\">{'Loading development tools...' if not jenkins_url else ''}</p>
                        <a id=\"jenkins-link\" href=\"{jenkins_url}\" target=\"_blank\" class=\"service-link\" style=\"display:{'block' if jenkins_url else 'none'}\"><i class=\"fas fa-gears\"></i> Jenkins</a>
                        <a id=\"gitea-link\" href=\"{gitea_url}\" target=\"_blank\" class=\"service-link\" style=\"display:{'block' if gitea_url else 'none'}\"><i class=\"fas fa-code-branch\"></i> Gitea Login</a>
                    </div>
                </div>
            </div>
        </div>
        """
    elif 'instance_error' in user_info:
        instance_info_html = f"""
        <div class=\"warning\">
            <strong>Note:</strong> Unable to assign an EC2 instance at this time. Error: {user_info['instance_error']}
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
        <meta charset=\"UTF-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
        <title>Fellowship Workshop</title>
        <link rel=\"icon\" href=\"https://lotr-prod.testingfantasy.com/middle-earth-map/icons/the_one_ring.ico\" type=\"image/x-icon\">
        <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
        <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
        <link href=\"https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700;900&family=Lora:ital,wght@0,400;0,600;0,700;1,400&display=swap\" rel=\"stylesheet\">
        <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css\">
        
        <!-- Google tag (gtag.js) -->
        <script async src=\"https://www.googletagmanager.com/gtag/js?id=G-6XDLRWMPH2\"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}
          gtag('js', new Date());
          gtag('config', 'G-6XDLRWMPH2');
        </script>
        
        <style>
            :root {{
                --blue: #2a2118;
                --pink: #b48a2b;
                --yellow: #c9b28b;
                --white: #f4e4bc;
                --gray: #fbf3e2;
                --shadow: 0 8px 32px rgba(35,26,18,0.18);
            }}
            body {{
                background: var(--blue);
                font-family: 'Lora', Georgia, serif;
                margin: 0;
                padding: 0;
                color: var(--blue);
            }}
            .container {{
                max-width: 1100px;
                margin: 40px auto;
                background: var(--white);
                border-radius: 18px;
                box-shadow: var(--shadow);
                padding: 32px 28px 28px 28px;
                position: relative;
                transition: max-width 0.3s;
            }}
            .header-row {{
                display: flex;
                align-items: center;
                justify-content: space-around;
                gap: 24px;
                margin-bottom: 24px;
                flex-wrap: wrap;
            }}
            .logo {{
                max-width: 140px;
                border-radius: 8px;
                object-fit: contain;
                flex-shrink: 0;
                order: 2;
            }}
            .header-link {{
                color: var(--blue);
                text-decoration: none;
                font-weight: 600;
                font-size: 1rem;
                padding: 10px 20px;
                background: var(--white);
                border-radius: 8px;
                border: 2px solid var(--blue);
                transition: all 0.3s ease;
                display: inline-block;
                box-shadow: 0 2px 8px rgba(30,52,178,0.15);
                flex: 0 1 auto;
            }}
            .header-link:first-child {{
                order: 1;
            }}
            .header-link:last-child {{
                order: 3;
            }}
            .header-link:hover {{
                background: var(--pink);
                color: var(--white);
                border-color: var(--pink);
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(30,52,178,0.25);
            }}
            .main-title {{
                color: var(--blue);
                text-align: center;
                margin-bottom: 0px;
                font-size: 3.2rem;
                font-weight: 900;
                letter-spacing: 1px;
                margin-top: 0.5em;
            }}
            .subtitle {{
                color: var(--pink);
                text-align: center;
                font-size: 1.5rem;
                font-weight: 700;
                margin-bottom: 18px;
                margin-top: 0.5em;
            }}
            h2 {{
                color: var(--blue);
                text-align: center;
                font-weight: 600;
                margin-bottom: 24px;
                font-size: 1.3rem;
            }}
            .info-box {{
                background: var(--gray);
                border-radius: 10px;
                padding: 18px 20px;
                margin-bottom: 24px;
                box-shadow: 0 2px 8px rgba(30,52,178,0.04);
            }}
            .azure-cards {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
                gap: 28px;
            }}
            .azure-card {{
                background: var(--white);
                border: 2px solid var(--blue);
                border-radius: 12px;
                padding: 22px 22px 18px 22px;
                margin-bottom: 0;
                box-shadow: 0 2px 8px rgba(30,52,178,0.06);
                display: flex;
                flex-direction: column;
                gap: 18px;
            }}
            .config-title {{
                font-weight: 800;
                color: var(--blue);
                margin-bottom: 10px;
                font-size: 1.2rem;
                letter-spacing: 0.5px;
            }}
            .config-row {{
                display: flex;
                flex-direction: column;
                align-items: flex-start;
                background: #f0e8d4;
                border-radius: 6px;
                padding: 10px 12px 8px 12px;
                margin-bottom: 0;
                font-size: 1.05rem;
                position: relative;
                gap: 4px;
            }}
            .config-label {{
                color: #666;
                font-size: 0.98em;
                font-weight: 600;
                margin-bottom: 2px;
            }}
            .config-value {{
                font-family: 'Fira Mono', 'Consolas', monospace;
                background: #efe1c8;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 1.04em;
                word-break: break-all;
                overflow-wrap: anywhere;
                width: 100%;
                margin-bottom: 0;
            }}
            .copy-btn {{
                position: absolute;
                top: 10px;
                right: 10px;
                background: var(--pink);
                color: var(--blue);
                border: none;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 1em;
                cursor: pointer;
                transition: background 0.2s;
            }}
            .copy-btn:hover {{
                background: var(--yellow);
                color: var(--blue);
            }}
            .instance-section {{
                margin-bottom: 32px;
            }}
            .instance-cards {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
                margin-top: 20px;
            }}
            .instance-card {{
                background: var(--white);
                border: 2px solid var(--blue);
                border-radius: 12px;
                padding: 24px;
                box-shadow: 0 4px 12px rgba(30,52,178,0.08);
                display: flex;
                flex-direction: column;
                gap: 16px;
            }}
            .card-header {{
                display: flex;
                align-items: center;
                gap: 12px;
                font-weight: 700;
                color: var(--blue);
                font-size: 1.1rem;
                border-bottom: 2px solid var(--gray);
                padding-bottom: 12px;
            }}
            .card-header i {{
                font-size: 1.2rem;
                color: var(--pink);
            }}
            .dify-link-container {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                background: var(--yellow);
                padding: 16px;
                border-radius: 8px;
                font-weight: 600;
                color: var(--blue);
            }}
            .dify-link {{
                color: var(--blue);
                text-decoration: underline;
                pointer-events: none;
                opacity: 0.6;
                transition: opacity 0.2s;
                font-size: 1.1rem;
            }}
            .dify-link.ready {{
                pointer-events: auto;
                opacity: 1;
                font-weight: bold;
            }}
            .status-message {{
                text-align: center;
                font-size: 0.95rem;
                color: var(--blue);
                font-weight: 500;
            }}
            .credentials-info {{
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}
            .credential-row {{
                display: flex;
                flex-direction: column;
                gap: 6px;
                background: var(--gray);
                padding: 12px;
                border-radius: 8px;
            }}
            .credential-label {{
                font-weight: 600;
                color: var(--blue);
                font-size: 0.9rem;
            }}
            .credential-value {{
                font-family: 'Fira Mono', 'Consolas', monospace;
                background: var(--white);
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 1rem;
                color: var(--blue);
                border: 1px solid #e0e0e0;
                word-break: break-all;
            }}
            .warning {{
                background: var(--pink);
                color: var(--white);
                border-radius: 6px;
                padding: 12px 16px;
                margin-top: 24px;
                font-size: 1rem;
                text-align: center;
            }}
            .dify-link-container, .sut-link-container {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 10px;
                margin-top: 10px;
            }}
            .dify-link {{
                color: var(--blue);
                text-decoration: underline;
                pointer-events: none;
                opacity: 0.6;
                transition: opacity 0.2s;
            }}
            .dify-link.ready, .service-link.ready {{
                pointer-events: auto;
                opacity: 1;
                font-weight: bold;
            }}
            .service-link {{
                color: var(--blue);
                text-decoration: underline;
                font-size: 1.05rem;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 6px 0;
            }}
            .spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid var(--pink);
                border-radius: 50%;
                width: 22px;
                height: 22px;
                animation: spin 1s linear infinite;
            }}
            .subtitle {{
                color: var(--pink);
                text-align: center;
                font-size: 1.5rem;
                font-weight: 700;
                margin-bottom: 18px;
                margin-top: 0.5em;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            .get-new-user-btn {{
                background: var(--pink);
                color: var(--white);
                border: none;
                padding: 10px 22px;
                border-radius: 6px;
                font-size: 1em;
                cursor: pointer;
                margin-top: 18px;
                margin-bottom: 8px;
            }}
            .get-new-user-btn:hover {{
                background: var(--yellow);
                color: var(--blue);
            }}
            
            /* Responsive design */
            @media (max-width: 768px) {{
                .header-row {{
                    flex-direction: column;
                    gap: 16px;
                }}
                .header-link {{
                    width: 100%;
                    text-align: center;
                    max-width: 300px;
                }}
                .logo {{
                    order: 1;
                }}
                .header-link:first-child {{
                    order: 2;
                }}
                .header-link:last-child {{
                    order: 3;
                }}
                .container {{
                    margin: 20px auto;
                    padding: 20px 16px;
                }}
                .main-title {{
                    font-size: 2.5rem;
                }}
                .subtitle {{
                    font-size: 1.2rem;
                }}
                .instance-cards {{
                    grid-template-columns: 1fr;
                    gap: 16px;
                }}
                .azure-cards {{
                    grid-template-columns: 1fr;
                    gap: 20px;
                }}
                .azure-card {{
                    padding: 16px;
                }}
            }}
            
            @media (max-width: 480px) {{
                .main-title {{
                    font-size: 2rem;
                }}
                .subtitle {{
                    font-size: 1rem;
                }}
                .instance-card {{
                    padding: 16px;
                }}
                .dify-link-container {{
                    padding: 12px;
                }}
            }}
        </style>
        <script>
            // Helper to set a cookie
            function setCookie(name, value, days) {{
                var d = new Date();
                d.setTime(d.getTime() + (days*24*60*60*1000));
                var expires = "expires=" + d.toUTCString();
                document.cookie = name + "=" + encodeURIComponent(value) + ";" + expires + ";path=/";
            }}
            // Helper to get a cookie
            function getCookie(name) {{
                var nameEQ = name + "=";
                var ca = document.cookie.split(';');
                for(var i=0;i < ca.length;i++) {{
                    var c = ca[i];
                    while (c.charAt(0)==' ') c = c.substring(1,c.length);
                    if (c.indexOf(nameEQ) == 0) return decodeURIComponent(c.substring(nameEQ.length,c.length));
                }}
                return null;
            }}
            document.addEventListener('DOMContentLoaded', function() {{
                var userCookie = getCookie('testus_patronus_user');
                var ipCookie = getCookie('testus_patronus_ip');
                var instanceIdCookie = getCookie('testus_patronus_instance_id');
                var sutLink = document.getElementById('sut-link');
                var sutSpinner = document.getElementById('sut-spinner');
                var sutStatusMsg = document.getElementById('sut-status-msg');
                var ideLink = document.getElementById('ide-link');
                var ideSpinner = document.getElementById('ide-spinner');
                var ideStatusMsg = document.getElementById('ide-status-msg');
                var jenkinsLink = document.getElementById('jenkins-link');
                var giteaLink = document.getElementById('gitea-link');
                var devToolsSpinner = document.getElementById('dev-tools-spinner');
                var devToolsStatus = document.getElementById('dev-tools-status');
                var userName = "{user_info['user_name']}";
                var statusLambdaUrl = "{status_lambda_url}";
                var pollCount = 0;

                function setSutStatus(msg) {{
                    if (sutStatusMsg) sutStatusMsg.textContent = msg;
                }}

                function pollStatus() {{
                    fetch(statusLambdaUrl + '?user_name=' + encodeURIComponent(userName))
                        .then(res => res.json())
                        .then(data => {{
                            pollCount++;
                            
                            // Check if reassignment is needed (instance was deleted/terminated)
                            if (data.reassign_needed) {{
                                console.log('[Fellowship] Reassignment needed. Reason:', data.reason);
                                if (data.reason === 'no_assignment' && pollCount <= 5) {{
                                    setSutStatus('Waiting for instance assignment...');
                                    setTimeout(pollStatus, 5000);
                                    return;
                                }}
                                setSutStatus('Your previous instance was deleted. Reassigning a new instance...');
                                pollCount = 999;
                                setCookie('testus_patronus_instance_id', '', -1);
                                setCookie('testus_patronus_ip', '', -1);
                                setTimeout(() => {{
                                    window.location.href = window.location.origin + window.location.pathname;
                                }}, 1500);
                                return;
                            }}
                            
                            if (data.ready && data.url) {{
                                var sutUrl = data.url;
                                if (!sutUrl.startsWith('http')) sutUrl = 'https://' + sutUrl;
                                
                                // Update SUT link
                                if (sutLink) {{
                                    sutLink.href = sutUrl;
                                    sutLink.innerHTML = '<i class="fas fa-external-link-alt"></i> Open SUT';
                                    sutLink.classList.add('ready');
                                    sutLink.style.pointerEvents = 'auto';
                                }}
                                if (sutSpinner) sutSpinner.style.display = 'none';
                                setSutStatus('Your SUT instance is ready!');
                                
                                // Update IDE link  
                                if (data.ide_url && ideLink) {{
                                    ideLink.href = data.ide_url;
                                    ideLink.innerHTML = '<i class="fas fa-laptop-code"></i> Open IDE';
                                    ideLink.classList.add('ready');
                                    ideLink.style.pointerEvents = 'auto';
                                    if (ideSpinner) ideSpinner.style.display = 'none';
                                    if (ideStatusMsg) ideStatusMsg.textContent = 'IDE is ready!';
                                }}
                                
                                // Update Jenkins link
                                if (data.jenkins_url && jenkinsLink) {{
                                    jenkinsLink.href = data.jenkins_url;
                                    jenkinsLink.style.display = 'block';
                                }}
                                
                                // Update Gitea link
                                if (data.gitea_url && giteaLink) {{
                                    giteaLink.href = data.gitea_url;
                                    giteaLink.style.display = 'block';
                                }}
                                
                                // Hide dev tools spinner
                                if (devToolsSpinner) devToolsSpinner.style.display = 'none';
                                if (devToolsStatus) devToolsStatus.style.display = 'none';
                                
                                console.log('[Fellowship] Services ready. SUT:', sutUrl);
                            }} else {{
                                setSutStatus('Starting your Fellowship instance...');
                                if (ideStatusMsg) ideStatusMsg.textContent = 'Waiting for IDE...';
                                if (pollCount < 60) setTimeout(pollStatus, 5000);
                                else setSutStatus('Still waiting for your instance. Please refresh if this takes too long.');
                            }}
                        }})
                        .catch(err => {{
                            console.error('[Fellowship] Error polling status:', err);
                            setSutStatus('Checking instance status...');
                            if (pollCount < 60) setTimeout(pollStatus, 5000);
                        }});
                }}

                if (userCookie) {{
                    console.log('[Fellowship] User found in cookies, starting status polling');
                    var instanceId = "{user_info.get('instance_id', '')}";
                    if (instanceId && !instanceIdCookie) {{
                        setCookie('testus_patronus_instance_id', instanceId, 7);
                    }}
                    pollStatus();
                }} else {{
                    console.log('[Fellowship] No user in cookies, storing and polling.');
                    setCookie('testus_patronus_user', "{user_info['user_name']}", 7);
                    var instanceId = "{user_info.get('instance_id', '')}";
                    if (instanceId) {{
                        setCookie('testus_patronus_instance_id', instanceId, 7);
                    }}
                    pollStatus();
                }}
            }});
            function getNewUser() {{
                setCookie('testus_patronus_user', '', -1);
                setCookie('testus_patronus_ip', '', -1);
                setCookie('testus_patronus_instance_id', '', -1);
                console.log('[Testus Patronus] Cleared user from cookies. Reloading for new user.');
                window.location.href = '/';
            }}
            function copyToClipboard(text) {{
                navigator.clipboard.writeText(text).then(function() {{
                    // Show a subtle notification instead of alert
                    showCopyNotification();
                }}).catch(function(err) {{
                    console.error('Failed to copy text: ', err);
                }});
            }}
            
            function showCopyNotification(msg) {{
                // Create a temporary notification element
                var notification = document.createElement('div');
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: var(--pink);
                    color: var(--white);
                    padding: 12px 20px;
                    border-radius: 6px;
                    font-weight: 600;
                    z-index: 1000;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                    transform: translateX(100%);
                    transition: transform 0.3s ease;
                `;
                notification.textContent = msg || 'Copied to clipboard!';
                document.body.appendChild(notification);
                
                // Animate in
                setTimeout(() => {{
                    notification.style.transform = 'translateX(0)';
                }}, 10);
                
                // Remove after 2 seconds
                setTimeout(() => {{
                    notification.style.transform = 'translateX(100%)';
                    setTimeout(() => {{
                        document.body.removeChild(notification);
                    }}, 300);
                }}, 2000);
            }}
            
            function downloadEnvFile() {{
                var envContent = document.getElementById('env-preview').textContent;
                var blob = new Blob([envContent], {{type: 'text/plain'}});
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = '.env';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                showCopyNotification('Downloaded .env file!');
            }}
            
            function copyEnvToClipboard() {{
                var envContent = document.getElementById('env-preview').textContent;
                navigator.clipboard.writeText(envContent).then(function() {{
                    showCopyNotification('Copied .env to clipboard!');
                }}).catch(function(err) {{
                    console.error('Failed to copy .env: ', err);
                }});
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header-row">
                <a href="https://testingfantasy.com" class="header-link" target="_blank" rel="noopener noreferrer">Visit Testing Fantasy</a>
                <img src="https://lotr.fellowship.testingfantasy.com/logo.png" alt="Fellowship Quest Tracker Logo" class="logo">
                <a href="https://docs.fellowship.testingfantasy.com" class="header-link" target="_blank" rel="noopener noreferrer">Visit Fellowship Documentation</a>
            </div>
            <div class="main-title">Fellowship Workshop</div>
            <div class="subtitle">CI/CD and AI-assisted testing with Lord of the Rings</div>
            <h2>Welcome, {user_info['user_name']}! Your Fellowship instance awaits. May your pipeline find its path.</h2>
            <button class="get-new-user-btn" onclick="getNewUser()">Get a new user</button>
            {instance_info_html}
            {env_download_html}
            <div class="warning">
                <strong>⚔️ Note:</strong> This instance will be released when the Fellowship disbands. Save your work before the quest ends.
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def reset_pool_assignments(workshop_name=None, environment=None):
    """Reset Fellowship pool assignments without deleting IAM users or terminating EC2 instances.

    This endpoint is intentionally safe for the Fellowship workflow:
    - Keep pre-seeded Student tags intact
    - Set AssignedStudent=false and Status=available on pool instances
    - Normalize DynamoDB records to status=pool_created
    """
    workshop = workshop_name or WORKSHOP_NAME
    env = environment or ENVIRONMENT
    assignment_table = dynamodb.Table(f"instance-assignments-{workshop}-{env}")

    summary = {
        'workshop': workshop,
        'environment': env,
        'instances_seen': 0,
        'instances_reset': 0,
        'dynamodb_upserts': 0,
        'skipped_no_student_tag': 0,
        'errors': []
    }

    try:
        response = ec2.describe_instances(
            Filters=[
                {'Name': 'tag:Type', 'Values': ['pool']},
                {'Name': 'tag:WorkshopID', 'Values': [workshop]},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopped', 'stopping']}
            ]
        )

        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                summary['instances_seen'] += 1
                instance_id = instance['InstanceId']
                tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
                student_name = tags.get('Student', '').strip()

                if not student_name:
                    logger.warning(f"Skipping instance {instance_id}: missing Student tag")
                    summary['skipped_no_student_tag'] += 1
                    continue

                if not is_valid_fellowship_student_name(student_name):
                    logger.warning(f"Skipping instance {instance_id}: invalid Student tag '{student_name}'")
                    summary['skipped_no_student_tag'] += 1
                    continue

                try:
                    ec2.create_tags(
                        Resources=[instance_id],
                        Tags=[
                            {'Key': 'AssignedStudent', 'Value': 'false'},
                            {'Key': 'Status', 'Value': 'available'}
                        ]
                    )
                    summary['instances_reset'] += 1

                    assignment_table.put_item(
                        Item={
                            'instance_id': instance_id,
                            'student_name': student_name,
                            'password': student_name,
                            'workshop': workshop,
                            'status': 'pool_created',
                            'assignment_source': 'fellowship_pool_reset',
                            'created_at': datetime.utcnow().isoformat(),
                            'instance_type': 'pool'
                        }
                    )
                    summary['dynamodb_upserts'] += 1
                except Exception as instance_error:
                    err = f"{instance_id}: {str(instance_error)}"
                    logger.error(f"Error resetting instance {err}", exc_info=True)
                    summary['errors'].append(err)

        return {
            'success': len(summary['errors']) == 0,
            **summary
        }
    except Exception as e:
        logger.error(f"Error resetting Fellowship pool assignments: {str(e)}", exc_info=True)
        return {
            'success': False,
            **summary,
            'errors': summary['errors'] + [str(e)]
        }

def lambda_handler(event, context):
    try:
        # Get environment variables
        environment = os.environ.get('ENVIRONMENT', 'dev')
        status_lambda_url = os.environ.get('STATUS_LAMBDA_URL')
        
        # Log environment variables for debugging
        print(f"Environment: {environment}")
        print(f"Status Lambda URL: {status_lambda_url}")
        
        if not status_lambda_url:
            print("Warning: STATUS_LAMBDA_URL environment variable is not set")
            return _build_response(
                200,
                generate_html_response(
                    user_info={},
                    error_message="The status service is not properly configured. Please try again in a few minutes.",
                    status_lambda_url=None
                )
            )
        
        logger.info(f"Lambda handler invoked. Event: {json.dumps(event)}")
        # region agent debug log
        _debug_log(
            "H1",
            "classroom_user_management.py:lambda_handler:entry",
            "Lambda handler entry",
            {
                "method": event.get("requestContext", {}).get("http", {}).get("method"),
                "path": event.get("requestContext", {}).get("http", {}).get("path"),
                "host": (event.get("headers") or {}).get("host"),
                "has_cookies_list": bool(event.get("cookies")),
                "has_cookie_header": bool((event.get("headers") or {}).get("cookie"))
            }
        )
        # endregion agent debug log
        # Check if it's a GET request
        if event['requestContext']['http']['method'] == 'GET':
            # Normalize path - handle empty paths and trailing slashes
            path = event['requestContext']['http']['path'] or '/'
            # Remove trailing slash except for root
            if path != '/' and path.endswith('/'):
                path = path.rstrip('/')
            logger.info(f"Received request for path: {path}")
            
            if path == '/destroy':
                # Check for the destroy key
                query_params = event.get('queryStringParameters', {})
                logger.info(f"Destroy key from request: {query_params.get('key') if query_params else 'None'}")
                logger.info(f"Expected destroy key: {DESTROY_KEY}")
                
                if query_params and query_params.get('key') == DESTROY_KEY:
                    try:
                        logger.info("Starting Fellowship pool reset process synchronously...")
                        result = reset_pool_assignments(WORKSHOP_NAME, ENVIRONMENT)
                        logger.info("Fellowship pool reset process completed synchronously")
                        return _build_response(200, json.dumps(result), content_type='application/json')
                    except Exception as e:
                        logger.error(f"Error in destroy process: {str(e)}", exc_info=True)
                        return _build_response(500, json.dumps({
                            'error': str(e),
                            'traceback': traceback.format_exc()
                        }), content_type='application/json')
                else:
                    logger.warning("Invalid or missing destroy key")
                    return _build_response(403, json.dumps({'error': 'Invalid or missing destroy key'}), content_type='application/json')
            elif path == '/' or path == '' or path == '/index.html':
                headers = event.get('headers', {}) or {}
                user_name = None
                instance_id_from_cookie = None
                
                # Lambda Function URL events have a 'cookies' array - use that first
                cookies_list = event.get('cookies', [])
                if cookies_list:
                    for cookie in cookies_list:
                        if cookie.startswith('testus_patronus_user='):
                            cookie_value = cookie.split('=', 1)[1].strip()
                            user_name = urllib.parse.unquote(cookie_value)
                            logger.info(f"Found user in cookies array: {user_name}")
                        elif cookie.startswith('testus_patronus_instance_id='):
                            cookie_value = cookie.split('=', 1)[1].strip()
                            instance_id_from_cookie = urllib.parse.unquote(cookie_value)
                            logger.info(f"Found instance_id in cookies array: {instance_id_from_cookie}")
                
                # Fallback to parsing cookie header
                if not user_name or not instance_id_from_cookie:
                    cookies = headers.get('cookie', '') or headers.get('Cookie', '')
                    if cookies:
                        for cookie in cookies.split(';'):
                            cookie = cookie.strip()
                            if cookie.startswith('testus_patronus_user='):
                                cookie_value = cookie.split('=', 1)[1].strip()
                                user_name = urllib.parse.unquote(cookie_value)
                                logger.info(f"Found user in cookie header: {user_name}")
                            elif cookie.startswith('testus_patronus_instance_id='):
                                cookie_value = cookie.split('=', 1)[1].strip()
                                instance_id_from_cookie = urllib.parse.unquote(cookie_value)
                                logger.info(f"Found instance_id in cookie header: {instance_id_from_cookie}")
                
                # Fallback to query param if needed
                if not user_name:
                    query_params = event.get('queryStringParameters', {}) or {}
                    user_name = query_params.get('user_name')

                if user_name and not is_valid_fellowship_student_name(user_name):
                    logger.warning(f"Discarding invalid cookie/query user '{user_name}' (not character_uuid format)")
                    user_name = None
                
                # If we have instance_id from cookie, verify it first before querying DynamoDB
                if user_name and instance_id_from_cookie:
                    logger.info(f"Found instance_id {instance_id_from_cookie} in cookie for user {user_name}, verifying instance")
                    try:
                        ec2 = boto3.client('ec2', region_name=REGION)
                        instance_response = ec2.describe_instances(InstanceIds=[instance_id_from_cookie])
                        
                        reservations = instance_response.get('Reservations', [])
                        if reservations and len(reservations) > 0:
                            instances = reservations[0].get('Instances', [])
                            if instances and len(instances) > 0:
                                instance = instances[0]
                                instance_state = instance['State']['Name']
                                # Check if instance is assigned to this user
                                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                                # Use MachineName tag (immutable, set at pool creation) as primary identity.
                                # Fall back to Student tag for backward compatibility.
                                # This prevents breakage when other systems (testus_patronus, /api/assign)
                                # overwrite the mutable Student tag.
                                machine_name = tags.get('MachineName', '')
                                student_tag = tags.get('Student', '')
                                instance_matches_user = (
                                    machine_name == user_name
                                    or student_tag == user_name
                                )
                                
                                # Exclude terminated and shutting-down instances
                                if instance_state not in ['terminated', 'shutting-down'] and instance_state in ['running', 'pending', 'stopped'] and instance_matches_user:
                                    logger.info(f"Instance {instance_id_from_cookie} is valid and assigned to {user_name} (state: {instance_state})")
                                    
                                    # Handle stopped instances - start them automatically
                                    if instance_state == 'stopped':
                                        logger.info(f"Instance {instance_id_from_cookie} is stopped, starting it automatically")
                                        try:
                                            start_response = ec2.start_instances(InstanceIds=[instance_id_from_cookie])
                                            logger.info(f"Start instances response: {start_response}")
                                            # Check if start was successful
                                            if start_response.get('StartingInstances'):
                                                starting_info = start_response['StartingInstances'][0]
                                                logger.info(f"Instance {instance_id_from_cookie} start initiated. Current state: {starting_info.get('CurrentState', {}).get('Name', 'unknown')}")
                                            
                                            # Re-fetch instance state after starting (it may have transitioned to 'pending')
                                            try:
                                                updated_response = ec2.describe_instances(InstanceIds=[instance_id_from_cookie])
                                                if updated_response.get('Reservations') and updated_response['Reservations'][0].get('Instances'):
                                                    instance = updated_response['Reservations'][0]['Instances'][0]
                                                    instance_state = instance['State']['Name']
                                                    logger.info(f"Instance state after start command: {instance_state}")
                                            except Exception as state_error:
                                                logger.warning(f"Could not re-fetch instance state: {str(state_error)}")
                                                # Assume it's starting
                                                instance_state = 'pending'
                                            
                                            # Update DynamoDB status to 'starting'
                                            try:
                                                table.update_item(
                                                    Key={'instance_id': instance_id_from_cookie},
                                                    UpdateExpression='SET #status = :status',
                                                    ExpressionAttributeNames={'#status': 'status'},
                                                    ExpressionAttributeValues={':status': 'starting'}
                                                )
                                            except Exception as db_error:
                                                logger.warning(f"Could not update DynamoDB status: {str(db_error)}")
                                        except ClientError as start_error:
                                            error_code = start_error.response.get('Error', {}).get('Code', '')
                                            error_msg = start_error.response.get('Error', {}).get('Message', str(start_error))
                                            logger.error(f"Failed to start stopped instance {instance_id_from_cookie}: {error_code} - {error_msg}")
                                        except Exception as start_error:
                                            logger.error(f"Failed to start stopped instance {instance_id_from_cookie}: {str(start_error)}", exc_info=True)
                                    
                                    # Get assignment from DynamoDB or create user_info from instance
                                    try:
                                        response = table.get_item(Key={'instance_id': instance_id_from_cookie})
                                        if 'Item' in response:
                                            user_info = response['Item']
                                            user_info['user_name'] = user_info.get('student_name', user_name)
                                            user_info['instance_id'] = instance_id_from_cookie
                                            # Set IP based on current instance state
                                            if instance_state == 'running':
                                                user_info['ec2_ip'] = instance.get('PublicIpAddress')
                                                # Clear any previous error message since instance is now running
                                                if 'instance_error' in user_info:
                                                    del user_info['instance_error']
                                                logger.info(f"Instance {instance_id_from_cookie} is running with IP: {user_info.get('ec2_ip')}")
                                            elif instance_state == 'pending':
                                                # Instance is starting (may have been started in previous request)
                                                user_info['ec2_ip'] = None
                                                user_info['instance_error'] = 'Instance is starting...'
                                                logger.info(f"Instance {instance_id_from_cookie} is pending (starting)")
                                            elif instance_state == 'stopped':
                                                # Instance is stopped - should have been handled above, but just in case
                                                user_info['ec2_ip'] = None
                                                user_info['instance_error'] = 'Instance is starting...'
                                                logger.warning(f"Instance {instance_id_from_cookie} is still stopped - may need to be started")
                                            else:
                                                user_info['ec2_ip'] = instance.get('PublicIpAddress')
                                        else:
                                            # Instance exists but no DynamoDB record - create one
                                            logger.warning(f"Instance {instance_id_from_cookie} exists but no DynamoDB record, creating one")
                                            user_info = {
                                                'user_name': user_name,
                                                'instance_id': instance_id_from_cookie,
                                                'ec2_ip': instance.get('PublicIpAddress') if instance_state == 'running' else None,
                                                'account_id': ACCOUNT_ID,
                                                'login_url': f"https://{ACCOUNT_ID}.signin.aws.amazon.com/console"
                                            }
                                            if instance_state in ['pending', 'stopped']:
                                                user_info['instance_error'] = 'Instance is starting...'
                                            # Try to create DynamoDB record
                                            try:
                                                table.put_item(Item={
                                                    'instance_id': instance_id_from_cookie,
                                                    'student_name': user_name,
                                                    'assigned_at': datetime.utcnow().isoformat(),
                                                    'status': 'starting' if instance_state in ['pending', 'stopped'] else ('running' if instance_state == 'running' else 'stopped')
                                                })
                                            except Exception as db_error:
                                                logger.warning(f"Could not create DynamoDB record: {str(db_error)}")
                                    except Exception as db_error:
                                        logger.error(f"Error getting DynamoDB record: {str(db_error)}")
                                        # Fallback to instance info
                                        user_info = {
                                            'user_name': user_name,
                                            'instance_id': instance_id_from_cookie,
                                            'ec2_ip': instance.get('PublicIpAddress') if instance_state == 'running' else None,
                                            'account_id': ACCOUNT_ID,
                                            'login_url': f"https://{ACCOUNT_ID}.signin.aws.amazon.com/console"
                                        }
                                        if instance_state in ['pending', 'stopped']:
                                            user_info['instance_error'] = 'Instance is starting...'
                                    
                                    # Enrich user_info with service URLs from instance tags
                                    enrich_user_info_with_urls(user_info, tags)
                                    
                                    # Load Azure configs
                                    try:
                                        azure_configs = get_secret()
                                        user_info['azure_configs'] = azure_configs
                                    except Exception as e:
                                        logger.error(f"Error loading Azure configurations: {str(e)}")
                                        user_info['azure_configs'] = []
                                    
                                    html_content = generate_html_response(user_info=user_info, error_message=None, status_lambda_url=status_lambda_url)
                                    cookie_headers = create_cookie_headers(user_info)
                                    return _build_response(200, html_content, cookies=cookie_headers)
                                elif instance_state in ['terminated', 'shutting-down']:
                                    logger.warning(f"Instance {instance_id_from_cookie} is {instance_state}, cannot be reused")
                                    # Instance is terminated - clear cookie and continue to find/create new assignment
                                    instance_id_from_cookie = None
                                else:
                                    logger.warning(f"Instance {instance_id_from_cookie} state={instance_state}, student_tag={student_tag}, not assigned to {user_name}")
                                    # Instance exists but not assigned to this user or in wrong state - clear cookie and continue
                                    instance_id_from_cookie = None
                            else:
                                logger.warning(f"Instance {instance_id_from_cookie} not found in reservations")
                                instance_id_from_cookie = None
                        else:
                            logger.warning(f"Instance {instance_id_from_cookie} not found (no reservations)")
                            instance_id_from_cookie = None
                    except ClientError as e:
                        error_code = e.response.get('Error', {}).get('Code', '')
                        if error_code == 'InvalidInstanceID.NotFound':
                            logger.warning(f"Instance {instance_id_from_cookie} not found (InvalidInstanceID.NotFound)")
                            instance_id_from_cookie = None
                        else:
                            logger.error(f"Error checking instance {instance_id_from_cookie}: {str(e)}")
                            instance_id_from_cookie = None
                    except Exception as e:
                        logger.error(f"Error verifying instance from cookie: {str(e)}")
                        instance_id_from_cookie = None
                
                if user_name:
                    logger.info(f"[Fellowship] Reload path for user: {user_name}")
                    try:
                        response = table.query(
                            IndexName='student_name-index',
                            KeyConditionExpression='student_name = :sn',
                            ExpressionAttributeValues={':sn': user_name}
                        )
                    except Exception as query_error:
                        logger.error(f"Error querying DynamoDB for user {user_name}: {str(query_error)}", exc_info=True)
                        response = {'Items': []}

                    if response.get('Items'):
                        user_info = response['Items'][0]
                        user_info['user_name'] = user_info.get('student_name', user_name)
                        user_info['instance_id'] = user_info.get('instance_id')

                        if user_info.get('instance_id'):
                            try:
                                ec2_client = boto3.client('ec2', region_name=REGION)
                                instance_response = ec2_client.describe_instances(InstanceIds=[user_info['instance_id']])
                                reservations = instance_response.get('Reservations', [])
                                if reservations and reservations[0].get('Instances'):
                                    instance = reservations[0]['Instances'][0]
                                    state = instance['State']['Name']
                                    tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
                                    # Use MachineName (immutable) or Student tag for matching.
                                    # DynamoDB student_name is the authoritative source; EC2 tags
                                    # are only checked to confirm the instance isn't terminated.
                                    tag_machine_name = tags.get('MachineName', '')
                                    tag_student = tags.get('Student', '')
                                    instance_matches_user = (
                                        tag_machine_name == user_name
                                        or tag_student == user_name
                                    )

                                    if instance_matches_user and state not in ['terminated', 'shutting-down']:
                                        if state == 'stopped':
                                            ec2_client.start_instances(InstanceIds=[user_info['instance_id']])
                                            user_info['instance_error'] = 'Instance is starting...'
                                        elif state == 'pending':
                                            user_info['instance_error'] = 'Instance is starting...'
                                        else:
                                            user_info['ec2_ip'] = instance.get('PublicIpAddress')

                                        enrich_user_info_with_urls(user_info, tags)
                                        try:
                                            user_info['azure_configs'] = get_secret()
                                        except Exception as azure_error:
                                            logger.error(f"Error loading Azure configurations: {str(azure_error)}")
                                            user_info['azure_configs'] = []

                                        html_content = generate_html_response(user_info=user_info, error_message=None, status_lambda_url=status_lambda_url)
                                        cookie_headers = create_cookie_headers(user_info)
                                        return _build_response(200, html_content, cookies=cookie_headers)

                                    logger.warning(
                                        f"Cookie user {user_name} has stale assignment instance={user_info['instance_id']} "
                                        f"state={state} tag_student={tag_student} tag_machine_name={tag_machine_name}; falling back to pool claim"
                                    )
                                else:
                                    logger.warning(f"Cookie user {user_name} has non-existing instance {user_info['instance_id']}; falling back to pool claim")
                            except Exception as validate_error:
                                logger.error(f"Error validating cookie assignment for {user_name}: {str(validate_error)}", exc_info=True)
                        else:
                            logger.warning(f"Cookie user {user_name} has no instance_id in DynamoDB; falling back to pool claim")

                    # If cookie user is stale/invalid, force new claim path.
                    user_name = None
                    instance_id_from_cookie = None
                
                # No user_name in cookie or cookie user invalid: claim a pool instance (Fellowship workflow)
                logger.info(f"[Fellowship] Pool instance claim path")
                
                # ── Anti-collapsing nonce redirect ──────────────────────────────
                # CloudFront may collapse concurrent cache-miss requests with the
                # same cache key (identical URL + no cookies) during the Lambda
                # cold-start window.  To guarantee each browser gets its own Lambda
                # invocation, redirect cookieless visitors to a URL with a unique
                # _nonce query parameter.  This makes the cache keys different so
                # CloudFront cannot serve the same response to multiple browsers.
                query_params_nonce = event.get('queryStringParameters', {}) or {}
                if not query_params_nonce.get('_nonce'):
                    nonce = uuid.uuid4().hex[:12]
                    redirect_qs = urllib.parse.urlencode({**query_params_nonce, '_nonce': nonce})
                    redirect_url = f"/?{redirect_qs}"
                    logger.info(f"[Fellowship] Redirecting cookieless request with nonce: {nonce}")
                    return {
                        'statusCode': 302,
                        'headers': {
                            'Location': redirect_url,
                            'Cache-Control': 'no-store, no-cache, must-revalidate, private, max-age=0',
                            'Pragma': 'no-cache',
                            'Vary': '*',
                            'Content-Type': 'text/html',
                        },
                        'body': '',
                    }
                
                logger.info(f"[Fellowship] Pool claim with nonce={query_params_nonce.get('_nonce')}")
                
                # Step 1: Get ALL available pool instances (sorted FIFO)
                available_instances = get_available_pool_instances(WORKSHOP_NAME, REGION)
                if not available_instances:
                    logger.error("[Fellowship] No pool instances available")
                    return _build_response(
                        503,
                        generate_html_response(
                            user_info={},
                            error_message="No Fellowship instances are available at this time. All quests may be in progress or the workshop has not started yet. Please wait a moment and try again.",
                            status_lambda_url=status_lambda_url
                        )
                    )
                
                # Step 2: Try to atomically claim each instance until one succeeds
                # This prevents the race condition where two concurrent requests
                # both see the same instance as available
                pool_instance = None
                claim_result = None
                for candidate in available_instances:
                    student_name = candidate.get('student_name', '')
                    if not student_name:
                        logger.warning(f"[Fellowship] Pool instance {candidate['instance_id']} has no Student tag, skipping")
                        continue

                    if not is_valid_fellowship_student_name(student_name):
                        logger.warning(
                            f"[Fellowship] Pool instance {candidate['instance_id']} has invalid Student tag '{student_name}', skipping"
                        )
                        continue
                    
                    claim_result = claim_pool_instance(candidate['instance_id'], student_name, WORKSHOP_NAME, ENVIRONMENT)
                    if claim_result['success']:
                        pool_instance = candidate
                        logger.info(f"[Fellowship] Successfully claimed instance {candidate['instance_id']} for student {student_name}")
                        break
                    elif claim_result.get('reason') == 'already_claimed':
                        logger.info(f"[Fellowship] Instance {candidate['instance_id']} already claimed, trying next")
                        continue
                    else:
                        logger.error(f"[Fellowship] Failed to claim instance {candidate['instance_id']}: {claim_result['message']}")
                        continue
                
                if not pool_instance or not claim_result or not claim_result['success']:
                    logger.error("[Fellowship] Could not claim any available pool instance")
                    return _build_response(
                        503,
                        generate_html_response(
                            user_info={},
                            error_message="All Fellowship instances are currently being claimed by other adventurers. Please try again in a moment — the One Ring grants no shortcuts!",
                            status_lambda_url=status_lambda_url
                        )
                    )
                
                student_name = pool_instance.get('student_name', '')
                
                # Step 3: Extract URLs from EC2 tags
                urls = extract_sut_urls_from_instance(pool_instance['tags'])
                
                # Step 5: Build user_info with credentials
                user_info = {
                    'user_name': student_name,
                    'instance_id': pool_instance['instance_id'],
                    'sut_url': urls.get('sut_url', ''),
                    'jenkins_url': urls.get('jenkins_url', ''),
                    'gitea_url': urls.get('gitea_url', ''),
                    'ide_url': urls.get('ide_url', ''),
                    'credentials': {
                        'username': student_name,
                        'password': student_name
                    }
                }
                logger.info(f"[Fellowship] Successfully claimed instance {pool_instance['instance_id']} for student {student_name}")

                # region agent debug log
                _debug_log(
                    "H2",
                    "classroom_user_management.py:lambda_handler:new_user",
                    "Created user info for new user path",
                    {
                        "has_instance_id": bool(user_info.get("instance_id")),
                        "has_instance_error": bool(user_info.get("instance_error")),
                        "has_azure_configs": bool(user_info.get("azure_configs"))
                    }
                )
                # endregion agent debug log
                # Always load Azure LLM configurations for new users as well
                try:
                    azure_configs = get_secret()
                    user_info['azure_configs'] = azure_configs
                    logger.info(f"[Azure Config] For new user {user_info.get('user_name')}, loaded {len(azure_configs)} configs: {azure_configs}")
                    if not azure_configs:
                        logger.warning(f"[Azure Config] No LLM configs available for user {user_info.get('user_name')} (new user path)")
                except Exception as e:
                    logger.error(f"Error loading Azure configurations: {str(e)}")
                    user_info['azure_configs'] = []
                html_content = generate_html_response(user_info=user_info, error_message=None, status_lambda_url=status_lambda_url)
                cookie_headers = create_cookie_headers(user_info)
                response = _build_response(200, html_content, cookies=cookie_headers)
                # region agent debug log
                _debug_log(
                    "H1",
                    "classroom_user_management.py:lambda_handler:new_user_response",
                    "Built response for new user path",
                    {
                        "statusCode": response.get("statusCode"),
                        "response_keys": sorted(list(response.keys())),
                        "cookie_count": len(cookie_headers) if cookie_headers else 0,
                        "has_multi_value_headers": "multiValueHeaders" in response
                    }
                )
                # endregion agent debug log
                return response
            else:
                logger.warning(f"Unknown path requested: {path}")
                return _build_response(404, json.dumps({'error': 'Not found'}), content_type='application/json')
        else:
            logger.warning("Method not allowed. Only GET is supported.")
            method_not_allowed_html = """
            <html>
                <head>
                    <title>ETL Testing Framework - Method Not Allowed</title>
                </head>
                <body>
                    <h1>Method Not Allowed</h1>
                    <p>This endpoint only supports GET requests.</p>
                </body>
            </html>
            """
            return _build_response(405, method_not_allowed_html)
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        # region agent debug log
        _debug_log(
            "H3",
            "classroom_user_management.py:lambda_handler:exception",
            "Unhandled exception in lambda_handler",
            {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        # endregion agent debug log
        return _build_response(
            500,
            json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            }),
            content_type='application/json'
        )
