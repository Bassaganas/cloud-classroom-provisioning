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

# Environment variables
REGION = os.environ.get('AWS_DEFAULT_REGION', os.environ.get('AWS_REGION', 'eu-west-3'))
WORKSHOP_NAME = os.environ.get('WORKSHOP_NAME', 'fellowship')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
STATUS_LAMBDA_URL = os.environ.get('STATUS_LAMBDA_URL', '')
DESTROY_KEY = os.environ.get('DESTROY_KEY', 'default_destroy_key')
SKIP_IAM_USER_CREATION = os.environ.get('SKIP_IAM_USER_CREATION', 'false').lower() == 'true'
INSTANCE_MANAGER_URL = os.environ.get('INSTANCE_MANAGER_URL', '')  # URL to the instance_manager Lambda endpoint
INSTANCE_MANAGER_PASSWORD_SECRET = os.environ.get('INSTANCE_MANAGER_PASSWORD_SECRET', '')  # Secret name in AWS Secrets Manager

logger.info("=" * 60)
logger.info("Module fellowship_student_assignment.py loaded")
logger.info(f"REGION: {REGION}")
logger.info(f"WORKSHOP_NAME: {WORKSHOP_NAME}")
logger.info(f"ENVIRONMENT: {ENVIRONMENT}")
logger.info(f"INSTANCE_MANAGER_PASSWORD_SECRET: {INSTANCE_MANAGER_PASSWORD_SECRET if INSTANCE_MANAGER_PASSWORD_SECRET else 'Not configured'}")
logger.info("=" * 60)

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

# Fellowship domain configuration
FELLOWSHIP_DOMAINS = {
    'sut': os.environ.get('FELLOWSHIP_SUT_DOMAIN', 'sut.fellowship.testingfantasy.com'),
    'jenkins': os.environ.get('FELLOWSHIP_JENKINS_DOMAIN', 'jenkins.fellowship.testingfantasy.com'),
    'gitea': os.environ.get('FELLOWSHIP_GITEA_DOMAIN', 'gitea.fellowship.testingfantasy.com'),
    'gitea_api': os.environ.get('FELLOWSHIP_GITEA_API_DOMAIN', 'gitea.fellowship.testingfantasy.com'),
}

GITEA_ORG = os.environ.get('FELLOWSHIP_GITEA_ORG', 'fellowship-org')


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
        request_body = {
            'workshop': WORKSHOP_NAME,
        }
        
        # Get password from parameter or retrieve from Secrets Manager
        auth_password = password or get_password_from_secret()
        if auth_password:
            request_body['password'] = auth_password
        else:
            logger.warning("No instance manager password available - request may fail with 401 if authentication is required")
        
        logger.info(f"Calling /api/assign-student endpoint on {INSTANCE_MANAGER_URL}")
        response = requests.post(url, json=request_body, timeout=60)
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


def generate_html_response(user_info, error_message=None, status_lambda_url=None):
    """Generate LOTR-themed HTML response with student assignment information"""
    if error_message:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - Fellowship Student Assignment</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: linear-gradient(135deg, #1a0000 0%, #330000 100%);
                    margin: 0;
                    padding: 0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .error-container {{
                    background: #fff;
                    padding: 40px;
                    border-radius: 12px;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
                    text-align: center;
                    max-width: 420px;
                    border-left: 6px solid #b30000;
                }}
                .error-icon {{
                    font-size: 48px;
                    margin-bottom: 12px;
                }}
                h1 {{
                    color: #b30000;
                    margin-bottom: 8px;
                }}
                .error-details {{
                    background: #f8f8f8;
                    color: #b30000;
                    font-size: 0.95em;
                    padding: 10px 12px;
                    border-radius: 6px;
                    margin-bottom: 18px;
                    word-break: break-all;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-icon">⚔️</div>
                <h1>The Road is Dark</h1>
                <p>An error has occurred in your quest.</p>
                <div class="error-details">{error_message}</div>
                <button onclick="location.reload()" style="background: #1a0000; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">Try Again</button>
            </div>
        </body>
        </html>
        """

    student_name = user_info.get('student_name', 'Unknown')
    password = user_info.get('password', '')
    instance_id = user_info.get('instance_id', 'N/A')
    sut_url = user_info.get('sut_url', '#')
    jenkins_url = user_info.get('jenkins_url', '#')
    gitea_url = user_info.get('gitea_url', '#')
    llm_configs = user_info.get('llm_configs', [])
    instance_error = user_info.get('instance_error', '')

    # Build LLM configs section
    llm_section = ""
    if llm_configs:
        llm_section = "<div class=\"info-box\"><h2>Azure LLM Configuration</h2><div class=\"config-grid\">"
        for config in llm_configs:
            llm_section += f"""
            <div class="config-card">
                <div class="config-title">{config.get('config_name', 'Unknown')}</div>
                <div class="config-row">
                    <span class="config-label">Deployment</span>
                    <span class="config-value">{config.get('deployment_name', 'N/A')}</span>
                    <button class="copy-btn" onclick="copyToClipboard('{config.get('deployment_name', '')}')">📋</button>
                </div>
                <div class="config-row">
                    <span class="config-label">API Key</span>
                    <span class="config-value">••••••••</span>
                    <button class="copy-btn" onclick="copyToClipboard('{config.get('api_key', '')}')">📋</button>
                </div>
                <div class="config-row">
                    <span class="config-label">Endpoint</span>
                    <span class="config-value">{config.get('endpoint', 'N/A')}</span>
                    <button class="copy-btn" onclick="copyToClipboard('{config.get('endpoint', '')}')">📋</button>
                </div>
            </div>
            """
        llm_section += "</div></div>"

    instance_section = ""
    if instance_id and instance_id != 'N/A':
        instance_section = f"""
        <div class="info-box">
            <h2>Your System Under Test (SUT)</h2>
            <div class="sut-info">
                <div class="info-row">
                    <span class="label">Instance ID</span>
                    <span class="value">{instance_id}</span>
                </div>
                <div class="info-row">
                    <span class="label">SUT URL</span>
                    <span class="value"><a href="{sut_url}" target="_blank">{sut_url}</a></span>
                    <button class="copy-btn" onclick="copyToClipboard('{sut_url}')">📋</button>
                </div>
            </div>
        </div>
        """
    elif instance_error:
        instance_section = f"""
        <div class="warning-box">
            <strong>⚠️ Note:</strong> Unable to assign an instance at this time. Reason: {instance_error}
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Fellowship - Student Assignment</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
        <style>
            :root {{
                --gold: #d4af37;
                --silver: #c0c0c0;
                --dark: #1a0000;
                --red: #8b0000;
                --light: #f5f1e8;
            }}

            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: 'Georgia', serif;
                background: linear-gradient(135deg, var(--dark) 0%, #330000 100%);
                color: var(--dark);
                padding: 20px;
                min-height: 100vh;
            }}

            .container {{
                max-width: 1000px;
                margin: 40px auto;
                background: var(--light);
                border-radius: 8px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }}

            .header {{
                background: linear-gradient(135deg, var(--dark) 0%, var(--red) 100%);
                color: var(--gold);
                padding: 30px;
                text-align: center;
                border-bottom: 3px solid var(--gold);
            }}

            .header h1 {{
                font-size: 2.5rem;
                margin-bottom: 5px;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
            }}

            .header .subtitle {{
                font-size: 1.1rem;
                color: var(--silver);
                font-style: italic;
            }}

            .content {{
                padding: 30px;
            }}

            .greeting {{
                background: #fff8f0;
                border-left: 4px solid var(--gold);
                padding: 20px;
                margin-bottom: 30px;
                border-radius: 4px;
            }}

            .greeting h2 {{
                color: var(--dark);
                margin-bottom: 10px;
                font-size: 1.4rem;
            }}

            .credentials-box {{
                background: #f0f0f0;
                border: 2px solid var(--gold);
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
            }}

            .credentials-box h2 {{
                color: var(--dark);
                margin-bottom: 20px;
                font-size: 1.3rem;
                border-bottom: 2px solid var(--gold);
                padding-bottom: 10px;
            }}

            .credential-item {{
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}

            .credential-item .label {{
                font-weight: bold;
                color: var(--red);
                min-width: 120px;
            }}

            .credential-item .value {{
                font-family: 'Courier New', monospace;
                background: white;
                padding: 8px 12px;
                border-radius: 4px;
                flex: 1;
                word-break: break-all;
            }}

            .credential-item .copy-btn {{
                background: var(--gold);
                color: var(--dark);
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s ease;
            }}

            .credential-item .copy-btn:hover {{
                background: var(--silver);
                transform: scale(1.05);
            }}

            .info-box {{
                background: #f9f9f9;
                border: 2px solid var(--dark);
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
            }}

            .info-box h2 {{
                color: var(--dark);
                margin-bottom: 20px;
                font-size: 1.3rem;
                border-bottom: 2px solid var(--red);
                padding-bottom: 10px;
            }}

            .info-row {{
                display: flex;
                align-items: center;
                gap: 15px;
                margin-bottom: 12px;
                padding: 12px;
                background: white;
                border-radius: 4px;
            }}

            .info-row .label {{
                font-weight: bold;
                color: var(--red);
                min-width: 120px;
            }}

            .info-row .value {{
                flex: 1;
                font-family: 'Courier New', monospace;
                word-break: break-all;
            }}

            .info-row a {{
                color: var(--red);
                text-decoration: none;
                font-weight: bold;
            }}

            .info-row a:hover {{
                text-decoration: underline;
            }}

            .config-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
            }}

            .config-card {{
                background: white;
                border: 2px solid var(--gold);
                border-radius: 8px;
                padding: 16px;
            }}

            .config-title {{
                font-weight: bold;
                color: var(--red);
                margin-bottom: 12px;
                font-size: 1.1rem;
            }}

            .config-row {{
                margin-bottom: 10px;
                padding: 10px;
                background: #f9f9f9;
                border-radius: 4px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}

            .config-label {{
                font-weight: bold;
                color: var(--dark);
                min-width: 100px;
                font-size: 0.9rem;
            }}

            .config-value {{
                flex: 1;
                font-family: 'Courier New', monospace;
                font-size: 0.9rem;
                word-break: break-all;
            }}

            .warning-box {{
                background: #fff3cd;
                border-left: 4px solid var(--red);
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 4px;
                color: var(--dark);
            }}

            .footer {{
                background: #f0f0f0;
                padding: 20px;
                text-align: center;
                border-top: 2px solid var(--gold);
                color: var(--dark);
                font-size: 0.9rem;
            }}

            .copy-btn {{
                background: var(--gold);
                color: var(--dark);
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s ease;
            }}

            .copy-btn:hover {{
                background: var(--silver);
                transform: scale(1.05);
            }}

            /* Responsive design */
            @media (max-width: 768px) {{
                .container {{
                    margin: 20px auto;
                }}

                .header h1 {{
                    font-size: 2rem;
                }}

                .content {{
                    padding: 20px;
                }}

                .config-grid {{
                    grid-template-columns: 1fr;
                }}

                .info-row {{
                    flex-direction: column;
                    align-items: flex-start;
                }}
            }}
        </style>
        <script>
            function copyToClipboard(text) {{
                navigator.clipboard.writeText(text).then(function() {{
                    showNotification("Copied to clipboard!");
                }}).catch(function(err) {{
                    console.error('Failed to copy:', err);
                }});
            }}

            function showNotification(message) {{
                const notification = document.createElement('div');
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: var(--gold);
                    color: var(--dark);
                    padding: 15px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    z-index: 1000;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                    animation: slideIn 0.3s ease;
                `;
                notification.textContent = message;
                document.body.appendChild(notification);

                setTimeout(() => {{
                    notification.style.animation = 'slideOut 0.3s ease';
                    setTimeout(() => {{
                        document.body.removeChild(notification);
                    }}, 300);
                }}, 2000);
            }}

            function getNewStudent() {{
                // Clear cookies and reload to get a new student assignment
                document.cookie = "fellowship_student=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                document.cookie = "fellowship_instance_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                document.cookie = "fellowship_sut_url=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                window.location.href = '/';
            }}

            style = document.createElement('style');
            style.textContent = `
                @keyframes slideIn {{
                    from {{ transform: translateX(100%); opacity: 0; }}
                    to {{ transform: translateX(0); opacity: 1; }}
                }}
                @keyframes slideOut {{
                    from {{ transform: translateX(0); opacity: 1; }}
                    to {{ transform: translateX(100%); opacity: 0; }}
                }}
            `;
            document.head.appendChild(style);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🧝 Fellowship Quest</h1>
                <div class="subtitle">Your Journey to Testing Mastery Awaits</div>
            </div>

            <div class="content">
                <div class="greeting">
                    <h2>Welcome, Fellowship Candidate!</h2>
                    <p>You have been selected for the Fellowship tour. Below are your credentials and resources to begin your quest.</p>
                </div>

                <div class="credentials-box">
                    <h2>⚔️ Your Credentials</h2>
                    <div class="credential-item">
                        <span class="label">Student ID:</span>
                        <span class="value">{student_name}</span>
                        <button class="copy-btn" onclick="copyToClipboard('{student_name}')">📋</button>
                    </div>
                    <div class="credential-item">
                        <span class="label">Password:</span>
                        <span class="value">{password}</span>
                        <button class="copy-btn" onclick="copyToClipboard('{password}')">📋</button>
                    </div>
                </div>

                {instance_section}

                <div class="info-box">
                    <h2>🏰 Fellowship Resources</h2>
                    <div class="info-row">
                        <span class="label">Jenkins Folder:</span>
                        <span class="value"><a href="{jenkins_url}" target="_blank">{jenkins_url}</a></span>
                        <button class="copy-btn" onclick="copyToClipboard('{jenkins_url}')">📋</button>
                    </div>
                    <div class="info-row">
                        <span class="label">Gitea Repository:</span>
                        <span class="value"><a href="{gitea_url}" target="_blank">{gitea_url}</a></span>
                        <button class="copy-btn" onclick="copyToClipboard('{gitea_url}')">📋</button>
                    </div>
                </div>

                {llm_section}

                <div class="footer">
                    <p>Your quest resources will be available for the duration of the Fellowship program.</p>
                    <p>May your tests be true and your code be strong.</p>
                    <button onclick="getNewStudent()" style="margin-top: 10px; background: var(--dark); color: var(--gold); border: 1px solid var(--gold); padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold;">Get New Student Assignment</button>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content


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


def lambda_handler(event, context):
    """Main Lambda handler for fellowship student assignment"""
    try:
        logger.info(f"Lambda handler invoked. Event: {json.dumps(event)}")
        logger.info(f"Status Lambda URL: {STATUS_LAMBDA_URL}")

        if not STATUS_LAMBDA_URL:
            logger.warning("STATUS_LAMBDA_URL not configured")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html'},
                'body': generate_html_response(
                    {},
                    error_message="The status service is not properly configured. Please try again in a few minutes.",
                    status_lambda_url=None
                )
            }

        # Check if GET request
        if event.get('requestContext', {}).get('http', {}).get('method') != 'GET':
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'text/html'},
                'body': '<html><body><h1>Method Not Allowed</h1><p>Only GET requests are supported.</p></body></html>'
            }

        # Get request path
        path = event.get('requestContext', {}).get('http', {}).get('path', '/').rstrip('/')
        logger.info(f"Request path: {path}")

        # Handle destroy endpoint
        if path == '/destroy':
            query_params = event.get('queryStringParameters', {}) or {}
            if query_params.get('key') == DESTROY_KEY:
                logger.info("Destroy request initiated")
                cleanup_expired_sessions()
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'status': 'cleanup_initiated'})
                }
            else:
                logger.warning("Invalid destroy key")
                return {
                    'statusCode': 403,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Invalid destroy key'})
                }

        # Get student from cookies or create new one
        headers = event.get('headers', {}) or {}
        cookies_list = event.get('cookies', [])
        student_name = None

        # Try to get student from cookies
        if cookies_list:
            for cookie in cookies_list:
                if cookie.startswith('fellowship_student='):
                    student_name = urllib.parse.unquote(cookie.split('=', 1)[1])
                    break

        # If no student in cookies, create new one
        if not student_name:
            logger.info("Creating new student assignment")
            user_info = create_student()
        else:
            logger.info(f"Using existing student: {student_name}")
            # Retrieve existing student info from DynamoDB
            try:
                response = table.get_item(Key={'student_name': student_name})
                if 'Item' in response:
                    item = response['Item']
                    user_info = {
                        'student_name': student_name,
                        'instance_id': item.get('instance_id'),
                        'sut_url': item.get('sut_url'),
                    }
                    if item.get('llm_config_name'):
                        user_info['llm_configs'] = [{
                            'config_name': item.get('llm_config_name'),
                            'api_key': item.get('llm_api_key'),
                        }]
                    # Regenerate URLs
                    urls = generate_fellowship_urls(student_name, item.get('sut_url', ''))
                    user_info.update(urls)
                else:
                    logger.warning(f"Student {student_name} not found in DynamoDB, creating new")
                    user_info = create_student()
            except Exception as e:
                logger.error(f"Error retrieving student info: {str(e)}")
                user_info = create_student()

        # Generate HTML response
        html_content = generate_html_response(
            user_info=user_info,
            error_message=None,
            status_lambda_url=STATUS_LAMBDA_URL
        )

        # Build response
        response = {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/html'},
            'body': html_content,
        }

        # Add cookies if present
        cookie_headers = create_cookie_headers(user_info)
        if cookie_headers:
            response['cookies'] = cookie_headers

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
