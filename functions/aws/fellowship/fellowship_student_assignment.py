"""
Fellowship Student Assignment Lambda Function

Provides fellowship workshop students with:
- Student ID and password
- SUT (System Under Test) URL
- Jenkins folder URL
- Gitea repository URL
- Azure LLM secrets

This function is themed for Lord of the Rings and integrates with:
- classroom_instance_manager.py (for EC2 instance assignment)
- AWS Secrets Manager (for LLM secrets)
- DynamoDB (for tracking student assignments)
- EC2 (for instance management)
"""

from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import boto3
import os
import sys
import logging
import time
import secrets
import string
import urllib.parse
from datetime import datetime, timedelta
import requests


# Initialize AWS clients first
# (No import of common module - we'll call instance_manager via HTTP endpoint instead)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ════════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT CONFIGURATION — Master Configuration for Fellowship Student Assignment
# ════════════════════════════════════════════════════════════════════════════════

# ─── Regional & Contextualization ──────────────────────────────────────────────
REGION = os.environ.get('AWS_DEFAULT_REGION', os.environ.get('AWS_REGION', 'eu-west-3'))
WORKSHOP_NAME = os.environ.get('WORKSHOP_NAME', 'fellowship')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# ─── Inter-Lambda Communication ────────────────────────────────────────────────
# Instance manager endpoint (classroom_instance_manager Lambda) for student assignment
INSTANCE_MANAGER_URL = os.environ.get('INSTANCE_MANAGER_URL', '')
INSTANCE_MANAGER_PASSWORD_SECRET = os.environ.get('INSTANCE_MANAGER_PASSWORD_SECRET', '')  # Cached in _password_cache

# ─── Fellowship Service Domains ────────────────────────────────────────────────
# Used to generate URLs returned to frontend after successful assignment
FELLOWSHIP_SUT_DOMAIN = os.environ.get('FELLOWSHIP_SUT_DOMAIN', 'sut.fellowship.testingfantasy.com')
FELLOWSHIP_JENKINS_DOMAIN = os.environ.get('FELLOWSHIP_JENKINS_DOMAIN', 'jenkins.fellowship.testingfantasy.com')
FELLOWSHIP_GITEA_DOMAIN = os.environ.get('FELLOWSHIP_GITEA_DOMAIN', 'gitea.fellowship.testingfantasy.com')
FELLOWSHIP_GITEA_ORG = os.environ.get('FELLOWSHIP_GITEA_ORG', 'fellowship-org')

# ─── External Documentation & Community Links ──────────────────────────────────
# Links displayed in HTML response for student reference
DOCS_LINK = os.environ.get('DOCS_LINK', 'https://docs.fellowship.testingfantasy.com/')
TESTINGFANTASY_LINK = os.environ.get('TESTINGFANTASY_LINK', 'https://www.testingfantasy.com/')

# ─── Status & Monitoring ──────────────────────────────────────────────────────
STATUS_LAMBDA_URL = os.environ.get('STATUS_LAMBDA_URL', '')

# ─── Security & Feature Flags ──────────────────────────────────────────────────
DESTROY_KEY = os.environ.get('DESTROY_KEY', 'default_destroy_key')
SKIP_IAM_USER_CREATION = os.environ.get('SKIP_IAM_USER_CREATION', 'false').lower() == 'true'

logger.info("=" * 80)
logger.info("Module fellowship_student_assignment.py loaded")
logger.info(f"REGION: {REGION} | WORKSHOP: {WORKSHOP_NAME} | ENVIRONMENT: {ENVIRONMENT}")
logger.info(f"Instance Manager: {INSTANCE_MANAGER_URL if INSTANCE_MANAGER_URL else 'Not configured'}")
logger.info(f"Auth Secret: {INSTANCE_MANAGER_PASSWORD_SECRET if INSTANCE_MANAGER_PASSWORD_SECRET else 'Not configured'}")
logger.info(f"Docs: {DOCS_LINK} | Community: {TESTINGFANTASY_LINK}")
logger.info("=" * 80)

# Initialize AWS clients
try:
    iam = boto3.client('iam')
    secretsmanager = boto3.client('secretsmanager', region_name=REGION)
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    ec2 = boto3.client('ec2', region_name=REGION)
    table = dynamodb.Table(f"instance-assignments-{WORKSHOP_NAME}-{ENVIRONMENT}")
except Exception as e:
    logger.error(f"Error initializing AWS clients: {str(e)}", exc_info=True)
    raise

# Password cache for Secrets Manager
_password_cache = None

# ─── Lookup Maps for URL Generation ───────────────────────────────────────────
FELLOWSHIP_DOMAINS = {
    'sut': FELLOWSHIP_SUT_DOMAIN,
    'jenkins': FELLOWSHIP_JENKINS_DOMAIN,
    'gitea': FELLOWSHIP_GITEA_DOMAIN,
    'gitea_api': FELLOWSHIP_GITEA_DOMAIN,
}
GITEA_ORG = FELLOWSHIP_GITEA_ORG


# ─── Secrets Management ─────────────────────────────────────────────────────────
def get_password_from_secret():
    """Get the instance manager password from AWS Secrets Manager"""
    global _password_cache
    
    if _password_cache is not None:
        return _password_cache
    
    if not INSTANCE_MANAGER_PASSWORD_SECRET:
        logger.warning("INSTANCE_MANAGER_PASSWORD_SECRET not configured, inter-Lambda authentication may fail")
        return None
    
    try:
        response = secretsmanager.get_secret_value(SecretId=INSTANCE_MANAGER_PASSWORD_SECRET)
        _password_cache = response['SecretString']
        logger.info("Successfully retrieved instance manager password from Secrets Manager")
        return _password_cache
    except ClientError as e:
        logger.error(f"Error retrieving password from Secrets Manager: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving password: {str(e)}")
        return None


# ─── Instance Manager Endpoint Wrapper ────────────────────────────────────────
def call_assign_student_endpoint(password=None):
    """Call the /api/assign-student endpoint on instance_manager.
    
    This unified endpoint handles:
    - Generating student name
    - Creating IAM user
    - Assigning pool EC2 instance
    - Provisioning on shared-core
    - Returning LLM secrets
    
    Args:
        password: Optional password for authentication to instance_manager (defaults to Secrets Manager value)
        
    Returns:
        dict with keys: success, student_name, password, instance_id, sut_url,
                        jenkins_url, gitea_url, llm_secrets, shared_core_provision
    """
    if not INSTANCE_MANAGER_URL:
        logger.error("INSTANCE_MANAGER_URL not configured")
        return {'success': False, 'error': 'Instance manager endpoint not configured'}
    
    try:
        # Build request to /api/assign-student endpoint
        url = INSTANCE_MANAGER_URL.rstrip('/') + '/api/assign-student'
        
        # Get password from parameter or retrieve from Secrets Manager
        auth_password = password or get_password_from_secret()
        
        # Build request body with password for endpoint authentication
        request_body = {
            'workshop': WORKSHOP_NAME,
        }
        if auth_password:
            request_body['password'] = auth_password
            logger.info(f"Adding password to request body for endpoint authentication")
        else:
            logger.warning("No instance manager password available - request may fail with 401 if authentication is required")
        
        logger.info(f"Calling /api/assign-student endpoint on {INSTANCE_MANAGER_URL} with workshop={WORKSHOP_NAME}")
        response = requests.post(url, json=request_body, timeout=60)
        
        # Log response details for debugging
        logger.info(f"Response status code: {response.status_code}")
        if response.status_code != 200:
            logger.warning(f"Response body: {response.text[:500]}")
        
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Student assignment response: {data.get('message', 'OK')}")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling /api/assign-student: {str(e)}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.error(f"Unexpected error calling /api/assign-student: {str(e)}")
        return {'success': False, 'error': str(e)}


def create_cookie_headers(user_info):
    """Create Set-Cookie headers for user session information"""
    cookies = []
    max_age = 7 * 24 * 60 * 60  # 7 days in seconds

    if user_info.get('student_name'):
        student_cookie = f"fellowship_student={urllib.parse.quote(user_info['student_name'])}; Path=/; Max-Age={max_age}; Secure; SameSite=Lax"
        cookies.append(student_cookie)

    if user_info.get('instance_id'):
        instance_cookie = f"fellowship_instance_id={urllib.parse.quote(user_info['instance_id'])}; Path=/; Max-Age={max_age}; Secure; SameSite=Lax"
        cookies.append(instance_cookie)

    if user_info.get('sut_url'):
        sut_cookie = f"fellowship_sut_url={urllib.parse.quote(user_info['sut_url'])}; Path=/; Max-Age={max_age}; Secure; SameSite=Lax"
        cookies.append(sut_cookie)

    return cookies




def generate_fellowship_urls(student_name, sut_url):
    """Generate all fellowship URLs for the student"""
    return {
        'sut_url': sut_url,
        'jenkins_url': f"https://{FELLOWSHIP_DOMAINS['jenkins']}/job/{student_name}/",
        'gitea_url': f"https://{FELLOWSHIP_DOMAINS['gitea']}/{GITEA_ORG}/fellowship-sut-{student_name}",
        'gitea_api_url': f"https://{FELLOWSHIP_DOMAINS['gitea_api']}/api/v1/repos/{GITEA_ORG}/fellowship-sut-{student_name}",
    }


# ─── Azure LLM & Service Credentials (Shared Classroom Config) ────────────────
# MASTER ENV CONFIGURATION — All variables passed to student .env file
# If a student has per-student LLM config in DynamoDB, it overrides these
_AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
_AZURE_OPENAI_API_KEY = os.environ.get('AZURE_OPENAI_API_KEY', '')
_AZURE_OPENAI_DEPLOYMENT = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
_AZURE_OPENAI_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
_SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')  # Event sourcing / progress tracking
_MCP_TOKEN = os.environ.get('MCP_TOKEN', '')  # Model Context Protocol token
_MAILDOG_API_URL = os.environ.get('MAILDOG_API_URL', '')  # Email service
_MAILDOG_TOKEN = os.environ.get('MAILDOG_TOKEN', '')  # Email service credentials


def generate_env_content(user_info):
    """Generate unified .env file content from student provisioning data.

    Includes all variables needed for IDE, exercises, and services.
    All values are fully populated where available; empty string fallback otherwise.

    Args:
        user_info: dict from create_student() with keys: student_name, instance_id,
                   sut_url, jenkins_url, gitea_url, llm_configs, password

    Returns:
        str: full .env file content
    """
    student_name = user_info.get('student_name', '')
    password = user_info.get('password', student_name)

    # Extract Jenkins token from LLM configs not ideal, but token may come later via API
    # For now, use environment variable if available
    jenkins_user = student_name
    jenkins_url_base = f"https://{FELLOWSHIP_DOMAINS['jenkins']}"
    gitea_url_base = f"https://{FELLOWSHIP_DOMAINS['gitea']}"
    gitea_user = student_name
    gitea_repo = f"fellowship-sut-{student_name}"
    gitea_org = GITEA_ORG

    # Azure OpenAI from Lambda env vars (shared classroom config)
    azure_endpoint = _AZURE_OPENAI_ENDPOINT
    azure_api_key = _AZURE_OPENAI_API_KEY
    azure_deployment = _AZURE_OPENAI_DEPLOYMENT
    azure_api_version = _AZURE_OPENAI_API_VERSION

    # If LLM configs list is present, use first entry (per-student configs override shared)
    llm_configs = user_info.get('llm_configs', [])
    if llm_configs:
        first = llm_configs[0]
        if first.get('api_key'):
            azure_api_key = first['api_key']
        if first.get('endpoint'):
            azure_endpoint = first['endpoint']
        if first.get('deployment_name'):
            azure_deployment = first['deployment_name']

    env_content = f"""# ════════════════════════════════════════════════════════════════════════════════
# MASTER CONFIGURATION — Single .env for the entire repository
# ════════════════════════════════════════════════════════════════════════════════
# Generated for student: {student_name}
# Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
#
# All exercises (ex1–ex5), services, and scripts load from this file.
# Place this file in the repository root: palantir-jenkins-ai/.env
#
# ⚠️ This file contains sensitive credentials. Do NOT commit to git. Do NOT share.

# ── STUDENT PROFILE & EVENT SOURCING ─────────────────────────────────────────
#
# REQUIRED: Student identifier — appears in all progress events and leaderboard
STUDENT_ID={student_name}

# AWS SQS Configuration for progress tracking
SQS_QUEUE_URL={_SQS_QUEUE_URL}
AWS_REGION={REGION}

# Environment mode: 'local' (no AWS) or 'aws' (sends events to SQS)
ENVIRONMENT={ENVIRONMENT}

# Event sourcing logging level (uncomment DEBUG to see detail)
TRACKER_LOG_LEVEL=INFO

# ── LEADERBOARD SERVICE (LOCAL ONLY) ─────────────────────────────────────────
#
LEADERBOARD_DB=.docker/leaderboard.db
API_HOST=0.0.0.0
API_PORT=5050

# ── Azure OpenAI (LLM Provider) ──────────────────────────────────────────────
#
# Used by: ex1, ex2 (query_client), ex3, ex4, ex5
AZURE_OPENAI_ENDPOINT={azure_endpoint}
AZURE_OPENAI_API_KEY={azure_api_key}
AZURE_OPENAI_DEPLOYMENT={azure_deployment}
AZURE_OPENAI_API_VERSION={azure_api_version}
AZURE_OPENAI_MAX_TOKENS=500
AZURE_OPENAI_TEMPERATURE=0.7

# ── Jenkins ───────────────────────────────────────────────────────────────────
#
# Used by: ex2-jenkins-mcp-server, ex4-gitea-mcp, ex5-grand-finale
JENKINS_URL={jenkins_url_base}
JENKINS_USER={jenkins_user}
JENKINS_TOKEN={password}
JENKINS_PIPELINE=fellowship-pipeline
JENKINS_STUDENT={student_name}

# ── Gitea ─────────────────────────────────────────────────────────────────────
#
# Used by: ex4-gitea-mcp, ex5-grand-finale
GITEA_URL={gitea_url_base}
GITEA_TOKEN={password}
GITEA_OWNER={gitea_org}
GITEA_REPO={gitea_repo}
GITEA_USER={gitea_user}

# ── Email Service (Maildog) ───────────────────────────────────────────────────
#
# Used by: ex3-notification-mcp, ex5-grand-finale
MAILDOG_API_URL={_MAILDOG_API_URL}
MAILDOG_TOKEN={_MAILDOG_TOKEN}

# ── MCP Token ─────────────────────────────────────────────────────────────────
MCP_TOKEN={_MCP_TOKEN}

# ── IDE / Local Development ────────────────────────────────────────────────────
COMPOSE_PROJECT_NAME=fellowship-local
CADDY_PORT_HTTP=9000
CADDY_PORT_HTTPS=9443
CADDY_DOMAIN=localhost
FRONTEND_MODE=dev
REACT_APP_API_URL=/api
REACT_APP_ENABLE_TEST_CONTROLS=true
DATABASE_URL=sqlite:////app/data/fellowship.db
SECRET_KEY=dev-secret-key-change-in-production
NODE_ENV=development
"""
    return env_content.lstrip()


def generate_html_response(user_info, env_content='', error_message=None, status_lambda_url=None):
    """Generate LOTR-themed HTML response with student assignment information"""
    if error_message:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error — Fellowship Quest</title>
    <style>
        body {{ font-family: Georgia, serif; background: linear-gradient(135deg, #1a0000 0%, #330000 100%); margin: 0; padding: 40px 20px; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
        .error-card {{ background: #f5f1e8; padding: 40px; border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.4); text-align: center; max-width: 480px; border: 2px solid #8b0000; }}
        .error-icon {{ font-size: 52px; margin-bottom: 12px; }}
        h1 {{ color: #8b0000; margin-bottom: 8px; font-size: 1.8rem; }}
        p {{ color: #1a0000; margin-bottom: 16px; }}
        .error-details {{ background: #fff; color: #8b0000; font-family: 'Courier New', monospace; font-size: 0.9em; padding: 12px; border-radius: 6px; margin-bottom: 20px; word-break: break-all; border: 1px solid #d4af37; text-align: left; }}
        button {{ background: #1a0000; color: #d4af37; border: 2px solid #d4af37; padding: 10px 24px; border-radius: 4px; cursor: pointer; font-family: Georgia, serif; font-weight: bold; font-size: 1rem; }}
        button:hover {{ background: #d4af37; color: #1a0000; }}
    </style>
</head>
<body>
    <div class="error-card">
        <div class="error-icon">⚔️</div>
        <h1>The Road is Dark</h1>
        <p>An error has occurred in your quest through Middle-earth.</p>
        <div class="error-details">{error_message}</div>
        <button onclick="location.reload()">Try Again</button>
    </div>
</body>
</html>"""

    student_name = user_info.get('student_name', 'Unknown')
    password = user_info.get('password', student_name)
    instance_id = user_info.get('instance_id', '')
    sut_url = user_info.get('sut_url', '#')
    jenkins_url = user_info.get('jenkins_url', '#')
    gitea_url = user_info.get('gitea_url', '#')
    llm_configs = user_info.get('llm_configs', [])
    instance_error = user_info.get('instance_error', '')
    
    # Local references to module-level link constants
    docs_link = DOCS_LINK
    testingfantasy_link = TESTINGFANTASY_LINK

    # Get character lore from user_info (comes from instance_manager endpoint)
    lore = user_info.get('character_lore', {})
    char_display_name = lore.get('name', student_name.split('_')[0].capitalize() if '_' in student_name else student_name.capitalize())
    char_race = lore.get('race', '')
    char_role = lore.get('role', '')
    char_description = lore.get('description', 'A member of the Fellowship, bound by oath to the quest.')

    # Character icon by race
    race_icons = {
        'Hobbit': '🌿', 'Human': '⚔️', 'Elf': '🏹', 'Dwarf': '⛏️',
        'Wizard': '🧙', 'Maiar': '🔥', 'Ent': '🌳', 'Spider': '🕷️',
        'Nazgûl': '💀', 'Uruk-hai': '🛡️', 'Orc': '🪓', 'Horse': '🐎',
        'Creature': '👁️', 'Hobbit-like': '🌿', 'Demon': '🔥',
    }
    char_icon = race_icons.get(char_race, '⚔️')

    # .env file content
    env_content = generate_env_content(user_info)
    # Escape for HTML embedding in JS string (avoid breaking template literals)
    env_content_js = env_content.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')

    # Build LLM configs section
    llm_rows = ""
    if llm_configs:
        for config in llm_configs:
            llm_rows += f"""
                <div class="config-card">
                    <div class="config-card-title">{config.get('config_name', 'Azure OpenAI')}</div>
                    <div class="cred-row">
                        <span class="cred-label">Deployment</span>
                        <span class="cred-value mono">{config.get('deployment_name', 'N/A')}</span>
                        <button class="copy-btn" onclick="copy('{config.get('deployment_name', '')}')">📋</button>
                    </div>
                    <div class="cred-row">
                        <span class="cred-label">API Key</span>
                        <span class="cred-value mono">{"*" * 12}</span>
                        <button class="copy-btn" onclick="copy('{config.get('api_key', '')}')">📋</button>
                    </div>
                    <div class="cred-row">
                        <span class="cred-label">Endpoint</span>
                        <span class="cred-value mono small">{config.get('endpoint', 'N/A')}</span>
                        <button class="copy-btn" onclick="copy('{config.get('endpoint', '')}')">📋</button>
                    </div>
                </div>"""

    sut_section = ""
    if instance_id:
        sut_section = f"""
                <div class="section-box">
                    <h3 class="section-title">🏰 System Under Test</h3>
                    <div class="cred-row">
                        <span class="cred-label">Instance</span>
                        <span class="cred-value mono">{instance_id}</span>
                    </div>
                    <div class="cred-row">
                        <span class="cred-label">SUT URL</span>
                        <span class="cred-value"><a href="{sut_url}" target="_blank" class="gold-link">{sut_url}</a></span>
                        <button class="copy-btn" onclick="copy('{sut_url}')">📋</button>
                    </div>
                </div>"""
    elif instance_error:
        sut_section = f"""<div class="warning-box">⚠️ Unable to assign an instance at this time: {instance_error}</div>"""

    llm_section = ""
    if llm_rows:
        llm_section = f"""
                <div class="section-box">
                    <h3 class="section-title">🤖 Azure LLM Configuration</h3>
                    <div class="config-grid">{llm_rows}</div>
                </div>"""

    # Build .env section
    env_section = ""
    if env_content:
        # Escape for HTML display
        env_display = env_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        env_section = f"""
                <div class="env-section">
                    <div class="env-section-title">📝 Environment Configuration (.env)</div>
                    <div class="env-preview">{env_display}</div>
                    <div class="env-actions">
                        <button class="env-btn env-btn-download" onclick="downloadEnv()">⬇️ Download .env</button>
                        <button class="env-btn env-btn-copy" onclick="copyEnv()">📋 Copy to Clipboard</button>
                    </div>
                </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fellowship — Your Quest Assignment</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        :root {{
            --gold:   #d4af37;
            --silver: #c0c0c0;
            --dark:   #1a0000;
            --red:    #8b0000;
            --cream:  #f5f1e8;
            --white:  #ffffff;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: Georgia, 'Times New Roman', serif;
            background: radial-gradient(ellipse at top, #2a0000 0%, #0d0000 70%);
            color: var(--dark);
            min-height: 100vh;
            padding: 20px;
        }}

        /* ── Page wrapper ── */
        .page {{
            max-width: 980px;
            margin: 32px auto;
        }}

        /* ── Hero banner ── */
        .hero {{
            background: linear-gradient(160deg, var(--dark) 0%, #2a0000 50%, var(--red) 100%);
            border: 2px solid var(--gold);
            border-radius: 8px 8px 0 0;
            padding: 36px 32px 28px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        .hero::before {{
            content: '';
            position: absolute; inset: 0;
            background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3Ccircle cx='30' cy='30' r='28' fill='none' stroke='%23d4af3715' stroke-width='1'/%3E%3Ccircle cx='30' cy='30' r='18' fill='none' stroke='%23d4af3712' stroke-width='1'/%3E%3C/svg%3E") repeat;
            pointer-events: none;
        }}
        .hero-subtitle {{
            color: var(--silver);
            font-style: italic;
            font-size: 0.95rem;
            margin-bottom: 16px;
        }}
        .hero-title {{
            color: var(--gold);
            font-size: 2.2rem;
            letter-spacing: 2px;
            text-shadow: 0 2px 12px rgba(212,175,55,0.4);
        }}
        .hero-divider {{
            border: none; border-top: 1px solid var(--gold);
            opacity: 0.4; margin: 18px auto; width: 60%;
        }}

        /* ── Character card ── */
        .char-card {{
            background: linear-gradient(135deg, #1a0000 0%, #250000 60%, #1a0005 100%);
            border: 1px solid var(--gold);
            border-top: none;
            padding: 28px 32px;
            display: flex;
            gap: 28px;
            align-items: center;
        }}
        .char-icon {{
            font-size: 64px;
            line-height: 1;
            flex-shrink: 0;
            filter: drop-shadow(0 0 16px rgba(212,175,55,0.5));
        }}
        .char-info {{ flex: 1; }}
        .char-name {{
            color: var(--gold);
            font-size: 1.9rem;
            font-weight: bold;
            letter-spacing: 1px;
        }}
        .char-meta {{
            color: var(--silver);
            font-size: 0.9rem;
            margin: 4px 0 10px;
            font-style: italic;
        }}
        .char-desc {{
            color: #c8b89a;
            font-size: 0.95rem;
            line-height: 1.5;
        }}
        .char-id-badge {{
            background: var(--dark);
            border: 1px solid var(--gold);
            color: var(--gold);
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            padding: 4px 10px;
            border-radius: 4px;
            margin-top: 10px;
            display: inline-block;
        }}

        /* ── Main content ── */
        .card {{
            background: var(--cream);
            border: 1px solid #cbbfa0;
            border-top: none;
            padding: 28px 32px;
        }}
        .card:last-child {{
            border-radius: 0 0 8px 8px;
        }}

        /* ── Section boxes ── */
        .section-box {{
            background: var(--white);
            border: 1.5px solid #d4af37;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .section-title {{
            color: var(--dark);
            font-size: 1.1rem;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--gold);
        }}

        /* ── Credential rows ── */
        .cred-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            padding: 10px 12px;
            background: #fdfaf4;
            border-radius: 4px;
            border: 1px solid #e8e0cc;
        }}
        .cred-label {{
            font-weight: bold;
            color: var(--red);
            min-width: 110px;
            font-size: 0.88rem;
        }}
        .cred-value {{
            flex: 1;
            word-break: break-all;
            font-size: 0.93rem;
        }}
        .cred-value.mono {{
            font-family: 'Courier New', monospace;
        }}
        .cred-value.small {{
            font-size: 0.82rem;
        }}

        /* ── Copy button ── */
        .copy-btn {{
            background: var(--gold);
            color: var(--dark);
            border: none;
            padding: 5px 11px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            font-size: 0.85rem;
            flex-shrink: 0;
            transition: background 0.2s;
        }}
        .copy-btn:hover {{ background: var(--silver); }}

        /* ── .env download section ── */
        .env-section {{
            background: #0e0a00;
            border: 1.5px solid var(--gold);
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .env-section-title {{
            color: var(--gold);
            font-size: 1.1rem;
            margin-bottom: 14px;
            border-bottom: 1px solid rgba(212,175,55,0.3);
            padding-bottom: 8px;
        }}
        .env-preview {{
            background: #050300;
            color: #a8d08d;
            font-family: 'Courier New', monospace;
            font-size: 0.78rem;
            padding: 16px;
            border-radius: 4px;
            max-height: 260px;
            overflow-y: auto;
            white-space: pre;
            border: 1px solid #333;
            margin-bottom: 16px;
            line-height: 1.5;
        }}
        .env-preview .comment {{ color: #6a9955; }}
        .env-actions {{ display: flex; gap: 12px; flex-wrap: wrap; }}
        .env-btn {{
            padding: 9px 20px;
            border-radius: 4px;
            border: none;
            cursor: pointer;
            font-family: Georgia, serif;
            font-weight: bold;
            font-size: 0.9rem;
            transition: all 0.2s;
        }}
        .env-btn-download {{
            background: var(--gold);
            color: var(--dark);
        }}
        .env-btn-download:hover {{ background: #c9a52e; }}
        .env-btn-copy {{
            background: transparent;
            color: var(--gold);
            border: 2px solid var(--gold);
        }}
        .env-btn-copy:hover {{ background: var(--gold); color: var(--dark); }}

        /* ── Links section ── */
        .links-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 12px;
        }}
        .link-card {{
            background: var(--white);
            border: 1.5px solid #d4af37;
            border-radius: 6px;
            padding: 14px 16px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .link-icon {{ font-size: 1.4rem; flex-shrink: 0; }}
        .link-text {{ flex: 1; }}
        .link-text a {{ color: var(--red); text-decoration: none; font-weight: bold; font-size: 0.88rem; word-break: break-all; }}
        .link-text a:hover {{ text-decoration: underline; }}
        .link-label {{ color: #888; font-size: 0.78rem; }}

        /* ── LLM config grid ── */
        .config-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
        .config-card {{ background: var(--white); border: 1px solid var(--gold); border-radius: 6px; padding: 14px; }}
        .config-card-title {{ font-weight: bold; color: var(--red); margin-bottom: 10px; font-size: 0.95rem; }}

        /* ── Warning box ── */
        .warning-box {{
            background: #fff8e1;
            border-left: 4px solid var(--red);
            padding: 12px 16px;
            margin-bottom: 20px;
            border-radius: 4px;
            color: var(--dark);
            font-size: 0.9rem;
        }}

        /* ── Footer ── */
        .footer {{
            background: var(--dark);
            border: 1px solid var(--gold);
            border-top: 2px solid var(--gold);
            border-radius: 0 0 8px 8px;
            padding: 20px 32px;
            text-align: center;
            color: var(--silver);
            font-size: 0.88rem;
        }}
        .footer p {{ margin-bottom: 8px; }}
        .footer a {{ color: var(--gold); text-decoration: none; }}
        .footer a:hover {{ text-decoration: underline; }}
        .footer .reset-btn {{
            background: transparent;
            color: var(--gold);
            border: 1px solid rgba(212,175,55,0.4);
            padding: 7px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-family: Georgia, serif;
            font-size: 0.85rem;
            margin-top: 8px;
        }}
        .footer .reset-btn:hover {{ background: rgba(212,175,55,0.1); }}

        /* ── Gold link ── */
        .gold-link {{ color: var(--red); font-weight: bold; text-decoration: none; }}
        .gold-link:hover {{ text-decoration: underline; }}

        /* ── Toast ── */
        #toast {{
            position: fixed; top: 24px; right: 24px;
            background: var(--gold); color: var(--dark);
            padding: 12px 20px; border-radius: 6px;
            font-weight: bold; font-family: Georgia, serif;
            box-shadow: 0 4px 16px rgba(0,0,0,0.4);
            z-index: 9999; display: none;
            animation: fadeIn 0.3s ease;
        }}
        @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(-10px); }} to {{ opacity:1; transform:translateY(0); }} }}

        /* ── Responsive ── */
        @media (max-width: 640px) {{
            .char-card {{ flex-direction: column; text-align: center; }}
            .hero-title {{ font-size: 1.6rem; }}
            .cred-row {{ flex-wrap: wrap; }}
        }}
    </style>
    <script>
        var ENV_CONTENT = `{env_content_js}`;
        var STUDENT_ID  = '{student_name}';

        function copy(text) {{
            navigator.clipboard.writeText(text).then(function() {{
                showToast('Copied to clipboard!');
            }}).catch(function() {{
                showToast('Copy failed — please select and copy manually.');
            }});
        }}

        function copyEnv() {{
            navigator.clipboard.writeText(ENV_CONTENT).then(function() {{
                showToast('Config copied to clipboard!');
            }}).catch(function() {{
                showToast('Copy failed — please select text in the preview above.');
            }});
        }}

        function downloadEnv() {{
            var blob = new Blob([ENV_CONTENT], {{type: 'text/plain'}});
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'fellowship-' + STUDENT_ID + '.env';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(a.href);
            showToast('.env file downloaded!');
        }}

        function showToast(msg) {{
            var t = document.getElementById('toast');
            t.textContent = msg;
            t.style.display = 'block';
            setTimeout(function() {{ t.style.display = 'none'; }}, 2500);
        }}

        function getNewStudent() {{
            document.cookie = "fellowship_student=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            document.cookie = "fellowship_instance_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            document.cookie = "fellowship_sut_url=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            window.location.href = '/';
        }}
    </script>
</head>
<body>
<div id="toast"></div>
<div class="page">

    <!-- ── Hero ── -->
    <div class="hero">
        <div class="hero-subtitle">Testing Fantasy · Fellowship Workshop</div>
        <div class="hero-title">&#x2694; The Fellowship of the Quest &#x2694;</div>
        <hr class="hero-divider">
        <div style="color: var(--silver); font-style: italic; font-size: 0.92rem;">
            "All we have to decide is what to do with the time that is given us."
        </div>
    </div>

    <!-- ── Character card ── -->
    <div class="char-card">
        <div class="char-icon">{char_icon}</div>
        <div class="char-info">
            <div class="char-name">{char_display_name}</div>
            <div class="char-meta">{char_race} · {char_role}</div>
            <div class="char-desc">{char_description}</div>
            <div class="char-id-badge">Identity: {student_name}</div>
        </div>
    </div>

    <!-- ── Content ── -->
    <div class="card">

        <!-- Credentials -->
        <div class="section-box">
            <h3 class="section-title">⚔️ Your Credentials</h3>
            <div class="cred-row">
                <span class="cred-label">Username</span>
                <span class="cred-value mono">{student_name}</span>
                <button class="copy-btn" onclick="copy('{student_name}')">📋</button>
            </div>
            <div class="cred-row">
                <span class="cred-label">Password</span>
                <span class="cred-value mono">{password}</span>
                <button class="copy-btn" onclick="copy('{password}')">📋</button>
            </div>
            <div class="cred-row">
                <span class="cred-label">Email</span>
                <span class="cred-value mono">{student_name}@fellowship.local</span>
                <button class="copy-btn" onclick="copy('{student_name}@fellowship.local')">📋</button>
            </div>
        </div>

        {env_section}

        {sut_section}

        <!-- Links -->
        <div class="section-box">
            <h3 class="section-title">🏹 Fellowship Resources</h3>
            <div class="links-grid">
                <div class="link-card">
                    <div class="link-icon">⚙️</div>
                    <div class="link-text">
                        <div class="link-label">Jenkins Folder</div>
                        <a href="{jenkins_url}" target="_blank">{jenkins_url}</a>
                    </div>
                    <button class="copy-btn" onclick="copy('{jenkins_url}')">📋</button>
                </div>
                <div class="link-card">
                    <div class="link-icon">📚</div>
                    <div class="link-text">
                        <div class="link-label">Gitea Repository</div>
                        <a href="{gitea_url}" target="_blank">{gitea_url}</a>
                    </div>
                    <button class="copy-btn" onclick="copy('{gitea_url}')">📋</button>
                </div>
            </div>
        </div>

        {llm_section}

        <!-- .env download -->
        <div class="env-section">
            <div class="env-section-title">📜 Master Configuration (.env)</div>
            <div class="env-preview" id="envPreview">{env_content}</div>
            <div class="env-actions">
                <button class="env-btn env-btn-download" onclick="downloadEnv()">
                    ⬇ Download .env
                </button>
                <button class="env-btn env-btn-copy" onclick="copyEnv()">
                    📋 Copy to Clipboard
                </button>
            </div>
        </div>

    </div><!-- /card -->

    <!-- ── Footer ── -->
    <div class="footer">
        <p>May your tests be true and your code be strong.</p>
        <p>
            <a href="{docs_link}" target="_blank">📖 Fellowship Documentation</a> · 
            <a href="{testingfantasy_link}" target="_blank">🌐 Testing Fantasy</a>
        </p>
        <button class="reset-btn" onclick="getNewStudent()">Request New Assignment</button>
    </div>

</div><!-- /page -->
</body>
</html>"""


def create_student():
    """Create and assign a new fellowship student by calling the unified endpoint.
    
    Delegates all assignment logic to classroom_instance_manager.py's /api/assign-student endpoint:
    - Generates student name
    - Creates IAM user
    - Assigns pool EC2 instance
    - Provisions on shared-core
    - Returns LLM secrets
    
    Returns:
        dict with complete student assignment info for HTML display
    """
    logger.info("Starting create_student()...")
    
    try:
        # Call unified endpoint on instance_manager
        endpoint_response = call_assign_student_endpoint()
        
        if not endpoint_response.get('success'):
            logger.error(f"Endpoint call failed: {endpoint_response.get('error', 'Unknown error')}")
            return {
                'error': endpoint_response.get('error', 'Failed to assign student resources'),
                'instance_error': endpoint_response.get('error', 'Failed to assign student resources')
            }
        
        # Parse successful response
        student_name = endpoint_response.get('student_name')
        password = endpoint_response.get('password')
        instance_id = endpoint_response.get('instance_id')
        sut_url = endpoint_response.get('sut_url')
        jenkins_url = endpoint_response.get('jenkins_url')
        gitea_url = endpoint_response.get('gitea_url')
        llm_secrets = endpoint_response.get('llm_secrets', [])
        shared_core_provision = endpoint_response.get('shared_core_provision', {})
        
        logger.info(f"Student created successfully: {student_name}, instance: {instance_id}")
        
        # Build user_info dict for HTML rendering
        user_info = {
            'student_name': student_name,
            'password': password,
            'instance_id': instance_id,
            'sut_url': sut_url,
            'jenkins_url': jenkins_url,
            'gitea_url': gitea_url,
            'llm_configs': llm_secrets,  # List of LLM configs from instance_manager
            'shared_core_provision': shared_core_provision,
        }
        
        logger.info(f"Student creation complete: {student_name}")
        return user_info
        
    except Exception as e:
        logger.error(f"Error in create_student: {str(e)}", exc_info=True)
        return {
            'error': str(e),
            'instance_error': f"Failed to create student: {str(e)}"
        }



def cleanup_expired_sessions():
    """Clean up expired student sessions"""
    try:
        current_time = datetime.utcnow()
        expiration_days = int(os.environ.get('SESSION_EXPIRATION_DAYS', '7'))
        expiration_threshold = current_time - timedelta(days=expiration_days)

        # Scan for expired sessions
        response = table.scan(
            FilterExpression='assigned_at < :threshold AND #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':threshold': expiration_threshold.isoformat(),
                ':status': 'active'
            }
        )

        for item in response.get('Items', []):
            student_name = item['student_name']
            logger.info(f"Marking expired session for cleanup: {student_name}")
            table.update_item(
                Key={'student_name': student_name},
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'expired'}
            )
    except Exception as e:
        logger.error(f"Error in cleanup_expired_sessions: {str(e)}")


def parse_cookies(cookie_header: str) -> dict:
    """Parse Cookie header string into dict.
    
    Input: 'fellowship_student=frodo-001; fellowship_instance_id=i-xxx'
    Output: {'fellowship_student': 'frodo-001', 'fellowship_instance_id': 'i-xxx'}
    """
    cookies = {}
    if cookie_header:
        for part in cookie_header.split(';'):
            part = part.strip()
            if '=' in part:
                key, val = part.split('=', 1)
                cookies[key.strip()] = urllib.parse.unquote(val.strip())
    return cookies


def lambda_handler(event, context):
    """Main Lambda handler for fellowship student assignment.
    
    POST /api/fellowship/assign -> Assign student or return existing assignment
    
    Flow:
    1. Check for existing assignment via fellowship_student cookie
    2. If exists: return stored assignment info + .env
    3. If new: Call /api/assign-student on instance_manager
    4. Generate .env file content
    5. Generate LOTR-themed HTML response
    6. Set 7-day TTL cookies for session persistence
    """
    try:
        logger.info(f"Lambda handler invoked")
        logger.info(f"Event method: {event.get('requestContext', {}).get('http', {}).get('method') if isinstance(event, dict) else 'N/A'}")
        
        http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
        if http_method.upper() not in ['POST', 'GET']:
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})}
        
        # Parse request
        body = json.loads(event.get('body') or '{}') if event.get('body') else {}
        query_params = event.get('queryStringParameters') or {}
        headers = event.get('headers') or {}
        
        logger.info(f"Body: {body}")
        logger.info(f"Query params: {query_params}")
        
        # Parse cookies
        cookie_header = headers.get('cookie') or headers.get('Cookie') or ''
        cookies = parse_cookies(cookie_header)
        existing_student = cookies.get('fellowship_student')
        
        logger.info(f"Existing student cookie: {existing_student}")
        
        user_info = None
        
        # ── Path 1: Existing Assignment ──────────────────────────────────────
        if existing_student:
            logger.info(f"Found existing student in cookie: {existing_student}")
            try:
                # Retrieve from DynamoDB using GSI
                response = table.query(
                    IndexName='student_name-index',
                    KeyConditionExpression=Key('student_name').eq(existing_student)
                )
                
                if response.get('Items'):
                    item = response['Items'][0]
                    user_info = {
                        'student_name': existing_student,
                        'password': item.get('password', 'unknown'),
                        'instance_id': item.get('instance_id'),
                        'sut_url': item.get('sut_url', item.get('instance_id', '')),
                        'created_at': item.get('created_at', '')
                    }
                    
                    # Generate URLs
                    urls = generate_fellowship_urls(existing_student, user_info['sut_url'])
                    user_info.update(urls)
                    
                    # Generate .env
                    env_content = generate_env_content(user_info)
                    
                    logger.info(f"Returning existing assignment for {existing_student}")
                else:
                    logger.warning(f"Student {existing_student} not found in DynamoDB, treating as new")
                    user_info = None
            except Exception as e:
                logger.error(f"Error retrieving existing student: {str(e)}")
                user_info = None
        
        # ── Path 2: New Assignment ───────────────────────────────────────────
        if not user_info:
            logger.info("Creating new student assignment")
            
            # Call /api/assign-student endpoint
            assign_result = call_assign_student_endpoint()
            
            if not assign_result.get('success'):
                logger.error(f"Failed to assign student: {assign_result.get('error')}")
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'text/html; charset=utf-8'},
                    'body': generate_html_response(
                        {}, 
                        error_message=f"Failed to assign student: {assign_result.get('error')}",
                        status_lambda_url=STATUS_LAMBDA_URL
                    )
                }
            
            # Parse response from instance manager
            # Determine provisioning status: 'queued' for shared-core provision, 'success' otherwise
            shared_core_prov = assign_result.get('shared_core_provision')
            provisioning_status = 'queued' if shared_core_prov else 'success'
            
            user_info = {
                'student_name': assign_result.get('student_name', ''),
                'password': assign_result.get('password', ''),
                'instance_id': assign_result.get('instance_id', ''),
                'sut_url': assign_result.get('sut_url', ''),
                'jenkins_url': assign_result.get('jenkins_url', ''),
                'gitea_url': assign_result.get('gitea_url', ''),
                'llm_configs': assign_result.get('llm_configs', []),
                'shared_core_provision': shared_core_prov,
                'provisioning_status': provisioning_status,
                'created_at': assign_result.get('created_at', datetime.utcnow().isoformat())
            }
            
            # Store assignment in fellowship's DynamoDB so subsequent requests (via cookie)
            # can look it up without creating a duplicate student.
            if user_info['student_name']:
                try:
                    table.put_item(Item={
                        'student_name': user_info['student_name'],
                        'instance_id': user_info.get('instance_id') or 'PENDING',
                        'password': user_info.get('password', ''),
                        'sut_url': user_info.get('sut_url', ''),
                        'jenkins_url': user_info.get('jenkins_url', ''),
                        'gitea_url': user_info.get('gitea_url', ''),
                        'status': 'active',
                        'assigned_at': user_info['created_at'],
                        'workshop': WORKSHOP_NAME,
                        'provisioning_status': provisioning_status,
                    })
                    logger.info(f"Stored assignment for {user_info['student_name']} in fellowship DynamoDB (provisioning_status: {provisioning_status})")
                except Exception as ddb_err:
                    logger.warning(f"Could not store assignment in fellowship DynamoDB (non-fatal): {ddb_err}")
            
            logger.info(f"New student assigned: {user_info['student_name']} -> {user_info['instance_id']}")
        
        # ── Generate Response ────────────────────────────────────────────────
        
        # Generate .env file content
        env_content = generate_env_content(user_info)
        
        # Generate HTML response with .env display
        html_content = generate_html_response(
            user_info=user_info,
            env_content=env_content,
            error_message=None,
            status_lambda_url=STATUS_LAMBDA_URL
        )
        
        # Create Set-Cookie headers
        cookie_headers = create_cookie_headers(user_info)
        
        # Build response
        response = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html; charset=utf-8',
                'Cache-Control': 'no-cache, no-store, must-revalidate'
            }
        }
        
        # Set cookies via top-level 'cookies' field (required for Lambda Function URLs)
        # Using response['headers']['Set-Cookie'] does NOT work with Lambda Function URLs;
        # the 'cookies' top-level key is the only way to set multiple cookies.
        if cookie_headers:
            response['cookies'] = cookie_headers
        
        response['body'] = html_content
        
        logger.info(f"Returning response with {len(cookie_headers) if cookie_headers else 0} cookies")
        return response

    except Exception as e:
        logger.error(f"Unhandled error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html'},
            'body': generate_html_response(
                {},
                error_message=f"An unexpected error occurred: {str(e)}",
                status_lambda_url=None
            )
        }
