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
from datetime import datetime, timedelta
import random

# Get region from environment variable
REGION = os.environ.get('AWS_DEFAULT_REGION', os.environ.get('AWS_REGION', 'eu-west-3'))

# Initialize AWS clients
iam = boto3.client('iam')
secretsmanager = boto3.client('secretsmanager', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(f"instance-assignments-{os.environ.get('ENVIRONMENT', 'dev')}")

# Get account ID from environment variable
ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID', '087559609246')

# Add this constant at the top of the file
DESTROY_KEY = os.environ.get('DESTROY_KEY', 'default_destroy_key')

#Status Lambda URL
status_lambda_url = os.environ.get('STATUS_LAMBDA_URL')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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

def get_next_available_api_key():
    """Get the next available API key from the secret"""
    configs = get_secret()
    if not configs:
        return None
    
    # Get all users to check which API keys are in use
    users = iam.list_users()['Users']
    used_keys = set()
    
    for user in users:
        try:
            tags = iam.list_user_tags(UserName=user['UserName'])['Tags']
            api_key_tag = next((tag for tag in tags if tag['Key'] == 'AzureApiKey'), None)
            if api_key_tag:
                used_keys.add(api_key_tag['Value'])
        except:
            continue
    
    # Find the first unused API key
    for config in configs:
        if config['api_key'] not in used_keys:
            return config
    
    return None

def generate_html_response(user_info, error_message=None, status_lambda_url=None):
    if error_message:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - Testus Patronus</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: #f5f5f5;
                    margin: 0;
                    padding: 0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .error-container {{
                    background: #fff;
                    padding: 40px 32px 32px 32px;
                    border-radius: 12px;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                    text-align: center;
                    max-width: 420px;
                }}
                .logo {{
                    width: 120px;
                    margin-bottom: 16px;
                }}
                .error-icon {{
                    font-size: 48px;
                    color: #e74c3c;
                    margin-bottom: 12px;
                }}
                h1 {{
                    color: #e74c3c;
                    margin-bottom: 8px;
                }}
                .subtitle {{
                    color: #555;
                    margin-bottom: 18px;
                    font-size: 1.1em;
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
                .retry-button {{
                    background: #3498db;
                    color: #fff;
                    border: none;
                    padding: 12px 28px;
                    border-radius: 6px;
                    font-size: 1em;
                    cursor: pointer;
                    margin-bottom: 8px;
                }}
                .retry-button:hover {{
                    background: #217dbb;
                }}
                .support-link {{
                    display: block;
                    margin-top: 10px;
                    color: #888;
                    font-size: 0.95em;
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <img src="https://testus-patronus.s3.amazonaws.com/logo.png" alt="Testus Patronus Logo" class="logo">
                <div class="error-icon">⚠️</div>
                <h1>Error</h1>
                <div class="subtitle">Something went wrong. Please try again.</div>
                <div class="error-details">{error_message}</div>
                <button class="retry-button" onclick="window.location.href='/'">Try Again</button>
            </div>
        </body>
        </html>
        """
    # Always ensure azure_configs is present
    azure_configs = user_info.get('azure_configs', [])
    azure_configs_html = """
    <div class=\"info-box\">
        <h2>LLM Models</h2>
        <div class=\"azure-cards\">
    """
    if azure_configs:
        for i, config in enumerate(azure_configs, 1):
            azure_configs_html += f"""
            <div class=\"azure-card\">
                <div class=\"config-title\">{config['config_name']}</div>
                <div class=\"config-row\">
                    <span class=\"config-label\">Deployment Name</span>
                    <span class=\"config-value\">{config['deployment_name']}</span>
                    <button class=\"copy-btn\" onclick=\"copyToClipboard('{config['deployment_name']}')\" title=\"Copy\"><i class=\"fas fa-copy\"></i></button>
                </div>
                <div class=\"config-row\">
                    <span class=\"config-label\">API Key</span>
                    <span class=\"config-value\">{config['api_key']}</span>
                    <button class=\"copy-btn\" onclick=\"copyToClipboard('{config['api_key']}')\" title=\"Copy\"><i class=\"fas fa-copy\"></i></button>
                </div>
                <div class=\"config-row\">
                    <span class=\"config-label\">Endpoint</span>
                    <span class=\"config-value\">{config['endpoint']}</span>
                    <button class=\"copy-btn\" onclick=\"copyToClipboard('{config['endpoint']}')\" title=\"Copy\"><i class=\"fas fa-copy\"></i></button>
                </div>
                <div class=\"config-row\">
                    <span class=\"config-label\">Version</span>
                    <span class=\"config-value\">{config['api_version']}</span>
                </div>
            </div>
            """
    else:
        azure_configs_html += "<div>No LLM configs available for this user.</div>"
    azure_configs_html += "</div></div>"

    # Create instance info HTML based on whether instance assignment was successful
    instance_info_html = ""
    if 'instance_id' in user_info and user_info['instance_id']:
        instance_info_html = f"""
        <div class=\"instance-section\">
            <h2>Dify Instance Information</h2>
            <div class=\"instance-cards\">
                <div class=\"instance-card\">
                    <div class=\"card-header\">
                        <i class=\"fas fa-server\"></i>
                        <span>Dify Instance</span>
                    </div>
                    <div class=\"dify-link-container\">
                        <a id=\"dify-link\" class=\"dify-link\" href=\"#\" target=\"_blank\" tabindex=\"-1\">Loading...</a>
                        <span id=\"dify-spinner\" class=\"spinner\"></span>
                    </div>
                    <div id=\"dify-status-msg\" class=\"status-message\"></div>
                </div>
                <div class=\"instance-card\">
                    <div class=\"card-header\">
                        <i class=\"fas fa-user-shield\"></i>
                        <span>Admin Credentials</span>
                    </div>
                    <div class=\"credentials-info\">
                        <div class=\"config-row\">
                            <span class=\"credential-label\">Username</span>
                            <span class=\"credential-value\">admin@dify.local</span>
                            <button class=\"copy-btn\" onclick=\"copyToClipboard('admin@dify.local')\" title=\"Copy\"><i class=\"fas fa-copy\"></i></button>
                        </div>
                        <details>
                            <summary style=\"cursor: pointer; font-weight: 600; color: var(--blue); margin: 8px 0; padding: 8px; background: #f7f8fa; border-radius: 6px; border: 1px solid #e0e0e0;\">
                                <i class=\"fas fa-key\"></i> Show Password
                            </summary>
                            <div class=\"config-row\" style=\"margin-top: 8px;\">
                                <span class=\"credential-label\">Password</span>
                                <span class=\"credential-value\">AutomationSTAR2025</span>
                                <button class=\"copy-btn\" onclick=\"copyToClipboard('AutomationSTAR2025')\" title=\"Copy\"><i class=\"fas fa-copy\"></i></button>
                            </div>
                        </details>
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
        <title>Testus Patronus</title>
        <subtitle>No magic, just AI with your company context</subtitle>
        <link rel=\"icon\" href=\"https://automation.eurostarsoftwaretesting.com/wp-content/uploads/2025/04/AS2025-Amsterdam-Header-Graphic-1.webp">
        <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css\">
        <style>
            :root {{
                --blue: #1B1464;
                --pink: #f452cb;
                --yellow: #ffd101;
                --white: #fff;
                --gray: #f4f7fa;
                --shadow: 0 8px 32px rgba(30,52,178,0.12);
            }}
            body {{
                background: var(--blue);
                font-family: 'Open Sans', 'Segoe UI', Arial, sans-serif;
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
            .logo {{
                display: block;
                margin: 0 auto 24px auto;
                max-width: 300px;
                border-radius: 12px;
                background: var(--white);
                box-shadow: 0 2px 8px rgba(30,52,178,0.08);
                object-fit: contain;
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
                background: #f7f8fa;
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
                background: #f0f0fa;
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
            .dify-link-container {{
                display: flex;
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
            .dify-link.ready {{
                pointer-events: auto;
                opacity: 1;
                font-weight: bold;
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
                background: ##82d642;
                color: #1B1464;
                border: none;
                padding: 10px 22px;
                border-radius: 6px;
                font-size: 1em;
                cursor: pointer;
                margin-top: 18px;
                margin-bottom: 8px;
            }}
            .get-new-user-btn:hover {{
                background: #fff;
            }}
            
            /* Responsive design */
            @media (max-width: 768px) {{
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
                var difyLink = document.getElementById('dify-link');
                var spinner = document.getElementById('dify-spinner');
                var statusMsg = document.getElementById('dify-status-msg');
                var userName = "{user_info['user_name']}";
                var statusLambdaUrl = "{status_lambda_url}";
                var pollCount = 0;

                function pollStatus() {{
                    fetch(statusLambdaUrl + '?user_name=' + encodeURIComponent(userName))
                        .then(res => res.json())
                        .then(data => {{
                            pollCount++;
                            
                            // Check if reassignment is needed (instance was deleted/terminated)
                            if (data.reassign_needed) {{
                                console.log('[Testus Patronus] Instance was deleted/terminated, triggering reassignment. Reason:', data.reason);
                                statusMsg.textContent = 'Your previous instance was deleted. Reassigning a new instance...';
                                // Stop polling
                                pollCount = 999; // Prevent further polling
                                // Clear the instance_id cookie to force reassignment
                                setCookie('testus_patronus_instance_id', '', -1);
                                setCookie('testus_patronus_ip', '', -1);
                                // Reload the page to trigger reassignment in user_management Lambda
                                setTimeout(() => {{
                                    window.location.href = window.location.origin + window.location.pathname;
                                }}, 1500);
                                return;
                            }}
                            
                            if (data.ready && data.ip) {{
                                difyLink.href = 'http://' + data.ip;
                                difyLink.textContent = 'http://' + data.ip;
                                difyLink.classList.add('ready');
                                difyLink.style.pointerEvents = 'auto';
                                spinner.style.display = 'none';
                                statusMsg.textContent = 'Your Dify instance is ready!';
                                // Update cookies with IP
                                setCookie('testus_patronus_ip', data.ip, 7);
                                console.log('[Testus Patronus] Updated cookies with IP:', data.ip);
                            }} else {{
                                statusMsg.textContent = 'Starting your Dify instance...';
                                if (pollCount < 60) setTimeout(pollStatus, 5000);
                                else statusMsg.textContent = 'Still waiting for your instance. Please refresh if this takes too long.';
                            }}
                        }})
                        .catch(err => {{
                            console.error('[Testus Patronus] Error polling status:', err);
                            statusMsg.textContent = 'Checking instance status...';
                            if (pollCount < 60) setTimeout(pollStatus, 5000);
                        }});
                }}

                if (userCookie) {{
                    // We have a user, always start polling
                    console.log('[Testus Patronus] User found in cookies, starting status polling');
                    // Ensure instance_id cookie is set if we have it in the response
                    var instanceId = "{user_info.get('instance_id', '')}";
                    if (instanceId && !instanceIdCookie) {{
                        setCookie('testus_patronus_instance_id', instanceId, 7);
                        console.log('[Testus Patronus] Stored instance_id in cookie from response:', instanceId);
                    }}
                    // Start polling immediately
                    pollStatus();
                }} else {{
                    // No user in cookies, let backend/user creation logic run as normal
                    console.log('[Testus Patronus] No user in cookies, proceeding with normal logic.');
                    // After assignment, store the user and instance_id in cookies if not already present
                    setCookie('testus_patronus_user', "{user_info['user_name']}", 7);
                    var instanceId = "{user_info.get('instance_id', '')}";
                    if (instanceId) {{
                        setCookie('testus_patronus_instance_id', instanceId, 7);
                        console.log('[Testus Patronus] Stored instance_id in cookie:', instanceId);
                    }}
                    // Start polling for new assignments
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
            
            function showCopyNotification() {{
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
                notification.textContent = 'Copied to clipboard!';
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
        </script>
    </head>
    <body>
        <div class="container">
            <img src="https://automation.eurostarsoftwaretesting.com/wp-content/uploads/2025/04/AS2025-Amsterdam-Header-Graphic-1.webp" alt="AutomationSTAR 2025 Amsterdam Logo" class="logo">
            <div class="main-title">Testus Patronus</div>
            <div class="subtitle">No magic, just AI with your company context</div>
            <h2>Welcome! Here are your Azure LLM credentials and your Dify instance. This is your user: {user_info['user_name']}</h2>
            <button class="get-new-user-btn" onclick="getNewUser()">Get a new user</button>
            {instance_info_html}
            {azure_configs_html}
            <div class="warning">
                <strong>Note:</strong> This Dify instance will be deleted after the tutorial. Please save any important information before the session ends.
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def get_next_student_number(iam, classroom_name):
    """Get the next available student number for the classroom"""
    try:
        # List all users with the classroom tag
        paginator = iam.get_paginator('list_users')
        max_number = 0
        
        for page in paginator.paginate():
            for user in page['Users']:
                try:
                    tags = iam.list_user_tags(UserName=user['UserName'])['Tags']
                    classroom_tag = next((tag for tag in tags if tag['Key'] == 'Classroom' and tag['Value'] == classroom_name), None)
                    number_tag = next((tag for tag in tags if tag['Key'] == 'StudentNumber'), None)
                    
                    if classroom_tag and number_tag:
                        student_num = int(number_tag['Value'])
                        max_number = max(max_number, student_num)
                except:
                    continue
        
        return max_number + 1
    except:
        return 1

def destroy_users():
    """Destroy all console users and their associated resources."""
    try:
        # Initialize AWS clients
        ec2 = boto3.client('ec2', region_name=REGION)
        
        # 1. Get all users
        users = iam.list_users()['Users']
        logger.info(f"Found {len(users)} total users")
        
        for user in users:
            user_name = user['UserName']
            logger.info(f"Checking user: {user_name}")
            
            if user_name.startswith('conference-user-'):
                logger.info(f"Processing user for deletion: {user_name}")
                try:
                    # 2. Delete access keys
                    access_keys = iam.list_access_keys(UserName=user_name)['AccessKeyMetadata']
                    for key in access_keys:
                        logger.info(f"Deleting access key for user {user_name}")
                        iam.delete_access_key(UserName=user_name, AccessKeyId=key['AccessKeyId'])
                    
                    # 3. Delete login profile if it exists
                    try:
                        logger.info(f"Deleting login profile for user {user_name}")
                        iam.delete_login_profile(UserName=user_name)
                    except iam.exceptions.NoSuchEntityException:
                        logger.info(f"No login profile found for user {user_name}")
                        pass
                    
                    # 4. Detach all managed policies
                    attached_policies = iam.list_attached_user_policies(UserName=user_name)['AttachedPolicies']
                    for policy in attached_policies:
                        logger.info(f"Detaching policy {policy['PolicyArn']} from user {user_name}")
                        iam.detach_user_policy(UserName=user_name, PolicyArn=policy['PolicyArn'])
                    
                    # 5. Delete all inline policies
                    inline_policies = iam.list_user_policies(UserName=user_name)['PolicyNames']
                    for policy_name in inline_policies:
                        logger.info(f"Deleting inline policy {policy_name} from user {user_name}")
                        iam.delete_user_policy(UserName=user_name, PolicyName=policy_name)
                    
                    # 6. Delete the user
                    logger.info(f"Deleting user {user_name}")
                    iam.delete_user(UserName=user_name)
                    
                    # 7. Find and stop/terminate associated EC2 instances
                    filters = [
                        {'Name': 'tag:Student', 'Values': [user_name]},
                        {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopped']}
                    ]
                    response = ec2.describe_instances(Filters=filters)
                    for reservation in response.get('Reservations', []):
                        for instance in reservation.get('Instances', []):
                            instance_id = instance['InstanceId']
                            logger.info(f"Stopping instance {instance_id} for user {user_name}")
                            # Stop the instance first
                            ec2.stop_instances(InstanceIds=[instance_id])
                            # Wait for the instance to stop
                            waiter = ec2.get_waiter('instance_stopped')
                            waiter.wait(InstanceIds=[instance_id])
                            # Terminate the instance
                            logger.info(f"Terminating instance {instance_id} for user {user_name}")
                            ec2.terminate_instances(InstanceIds=[instance_id])
                            # Update instance tags to mark as available
                            ec2.create_tags(
                                Resources=[instance_id],
                                Tags=[
                                    {'Key': 'Status', 'Value': 'available'},
                                    {'Key': 'Student', 'Value': ''}
                                ]
                            )
                    
                except Exception as e:
                    logger.error(f"Error deleting user {user_name}: {str(e)}")
                    continue
        logger.info(f"Destroy process completed. Deleted {len(users)} users")
        
    except Exception as e:
        logger.error(f"Error in destroy_users: {str(e)}")

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
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'body': generate_html_response(
                    error_message="The status service is not properly configured. Please try again in a few minutes.",
                    status_lambda_url=None
                )
            }
        
        logger.info(f"Lambda handler invoked. Event: {json.dumps(event)}")
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
                        logger.info("Starting destroy process synchronously...")
                        result = destroy_users()
                        logger.info("Destroy process completed synchronously")
                        return {
                            'statusCode': 200,
                            'body': json.dumps(result),
                            'headers': {
                                'Content-Type': 'application/json'
                            }
                        }
                    except Exception as e:
                        logger.error(f"Error in destroy process: {str(e)}", exc_info=True)
                        return {
                            'statusCode': 500,
                            'body': json.dumps({
                                'error': str(e),
                                'traceback': traceback.format_exc()
                            }),
                            'headers': {
                                'Content-Type': 'application/json'
                            }
                        }
                else:
                    logger.warning("Invalid or missing destroy key")
                    return {
                        'statusCode': 403,
                        'body': json.dumps({'error': 'Invalid or missing destroy key'}),
                        'headers': {
                            'Content-Type': 'application/json'
                        }
                    }
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
                                student_tag = tags.get('Student', '')
                                
                                # Exclude terminated and shutting-down instances
                                if instance_state not in ['terminated', 'shutting-down'] and instance_state in ['running', 'pending', 'stopped'] and student_tag == user_name:
                                    logger.info(f"Instance {instance_id_from_cookie} is valid and assigned to {user_name}")
                                    # Get assignment from DynamoDB or create user_info from instance
                                    try:
                                        response = table.get_item(Key={'instance_id': instance_id_from_cookie})
                                        if 'Item' in response:
                                            user_info = response['Item']
                                            user_info['user_name'] = user_info.get('student_name', user_name)
                                            user_info['instance_id'] = instance_id_from_cookie
                                            user_info['ec2_ip'] = instance.get('PublicIpAddress')
                                        else:
                                            # Instance exists but no DynamoDB record - create one
                                            logger.warning(f"Instance {instance_id_from_cookie} exists but no DynamoDB record, creating one")
                                            user_info = {
                                                'user_name': user_name,
                                                'instance_id': instance_id_from_cookie,
                                                'ec2_ip': instance.get('PublicIpAddress'),
                                                'account_id': ACCOUNT_ID,
                                                'login_url': f"https://{ACCOUNT_ID}.signin.aws.amazon.com/console"
                                            }
                                            # Try to create DynamoDB record
                                            try:
                                                table.put_item(Item={
                                                    'instance_id': instance_id_from_cookie,
                                                    'student_name': user_name,
                                                    'assigned_at': datetime.utcnow().isoformat(),
                                                    'status': 'starting' if instance_state == 'pending' else ('running' if instance_state == 'running' else 'stopped')
                                                })
                                            except Exception as db_error:
                                                logger.warning(f"Could not create DynamoDB record: {str(db_error)}")
                                    except Exception as db_error:
                                        logger.error(f"Error getting DynamoDB record: {str(db_error)}")
                                        # Fallback to instance info
                                        user_info = {
                                            'user_name': user_name,
                                            'instance_id': instance_id_from_cookie,
                                            'ec2_ip': instance.get('PublicIpAddress'),
                                            'account_id': ACCOUNT_ID,
                                            'login_url': f"https://{ACCOUNT_ID}.signin.aws.amazon.com/console"
                                        }
                                    
                                    # Load Azure configs
                                    try:
                                        azure_configs = get_secret()
                                        user_info['azure_configs'] = azure_configs
                                    except Exception as e:
                                        logger.error(f"Error loading Azure configurations: {str(e)}")
                                        user_info['azure_configs'] = []
                                    
                                    html_content = generate_html_response(user_info=user_info, error_message=None, status_lambda_url=status_lambda_url)
                                    headers = {'Content-Type': 'text/html'}
                                    cookie_headers = create_cookie_headers(user_info)
                                    response = {
                                        'statusCode': 200,
                                        'body': html_content,
                                        'headers': headers
                                    }
                                    if cookie_headers:
                                        # Lambda Function URLs support multiple Set-Cookie headers via multiValueHeaders
                                        response['multiValueHeaders'] = {'Set-Cookie': cookie_headers}
                                    return response
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
                    logger.info(f"[Azure Config] Reload path for user: {user_name}")
                    # Try to look up the user in DynamoDB with retry for eventual consistency
                    response = {'Items': []}
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            logger.info(f"Querying DynamoDB for user: {user_name} (attempt {retry + 1}/{max_retries})")
                            response = table.query(
                                IndexName='student_name-index',
                                KeyConditionExpression='student_name = :sn',
                                ExpressionAttributeValues={':sn': user_name}
                            )
                            logger.info(f"DynamoDB query response: {len(response.get('Items', []))} items found")
                            if response.get('Items'):
                                break  # Found items, no need to retry
                            elif retry < max_retries - 1:
                                # Wait a bit for eventual consistency
                                time.sleep(0.5)
                        except Exception as e:
                            logger.error(f"Error querying DynamoDB for user {user_name} (attempt {retry + 1}): {str(e)}", exc_info=True)
                            if retry < max_retries - 1:
                                time.sleep(0.5)
                            else:
                                response = {'Items': []}
                    
                    if response.get('Items'):
                        # User found in DynamoDB - return existing assignment
                        logger.info(f"User {user_name} found in DynamoDB")
                        user_info = response['Items'][0]
                        user_info['user_name'] = user_info.get('student_name', user_name)
                        user_info['instance_id'] = user_info.get('instance_id')
                        
                        # Check EC2 instance status
                        if user_info['instance_id']:
                            try:
                                ec2 = boto3.client('ec2', region_name=REGION)
                                instance_response = ec2.describe_instances(
                                    InstanceIds=[user_info['instance_id']]
                                )
                                
                                # Safely check if instance exists in response
                                reservations = instance_response.get('Reservations', [])
                                if not reservations or len(reservations) == 0:
                                    logger.warning(f"Instance {user_info['instance_id']} not found in EC2 (no reservations)")
                                    # Instance doesn't exist - clean up old record and assign a new one
                                    old_instance_id = user_info['instance_id']
                                    try:
                                        # Delete the old DynamoDB record for the terminated instance
                                        try:
                                            table.delete_item(Key={'instance_id': old_instance_id})
                                            logger.info(f"Deleted old DynamoDB record for terminated instance {old_instance_id}")
                                        except Exception as delete_error:
                                            logger.warning(f"Could not delete old DynamoDB record: {str(delete_error)}")
                                        
                                        # Assign a new instance
                                        assignment_result = assign_ec2_instance_to_student(user_name)
                                        logger.info(f"Re-assigned instance: {assignment_result}")
                                        user_info['instance_id'] = assignment_result['instance_id']
                                        user_info['ec2_ip'] = assignment_result.get('public_ip')
                                    except Exception as assign_error:
                                        logger.error(f"Failed to re-assign instance: {str(assign_error)}")
                                        user_info['instance_error'] = f'Previous instance was terminated. Failed to assign new instance: {str(assign_error)}'
                                else:
                                    instances = reservations[0].get('Instances', [])
                                    if not instances or len(instances) == 0:
                                        logger.warning(f"Instance {user_info['instance_id']} has no instances in reservation")
                                        # Instance doesn't exist - clean up and reassign
                                        old_instance_id = user_info['instance_id']
                                        try:
                                            table.delete_item(Key={'instance_id': old_instance_id})
                                            logger.info(f"Deleted old DynamoDB record for instance with no instances")
                                            assignment_result = assign_ec2_instance_to_student(user_name)
                                            logger.info(f"Re-assigned instance: {assignment_result}")
                                            user_info['instance_id'] = assignment_result['instance_id']
                                            user_info['ec2_ip'] = assignment_result.get('public_ip')
                                        except Exception as assign_error:
                                            logger.error(f"Failed to re-assign instance: {str(assign_error)}")
                                            user_info['instance_error'] = f'Instance not found. Failed to assign new instance: {str(assign_error)}'
                                    else:
                                        instance = instances[0]
                                        state = instance['State']['Name']
                                        if state in ['running', 'pending']:
                                            user_info['ec2_ip'] = instance.get('PublicIpAddress')
                                        elif state == 'stopped':
                                            ec2.start_instances(InstanceIds=[user_info['instance_id']])
                                            user_info['instance_error'] = 'Instance is starting...'
                                        elif state == 'terminated':
                                            # Instance was terminated - clean up and assign a new one
                                            old_instance_id = user_info['instance_id']
                                            logger.warning(f"Instance {old_instance_id} is terminated, assigning new instance")
                                            try:
                                                # Delete the old DynamoDB record for the terminated instance
                                                try:
                                                    table.delete_item(Key={'instance_id': old_instance_id})
                                                    logger.info(f"Deleted old DynamoDB record for terminated instance {old_instance_id}")
                                                except Exception as delete_error:
                                                    logger.warning(f"Could not delete old DynamoDB record: {str(delete_error)}")
                                                
                                                # Assign a new instance
                                                assignment_result = assign_ec2_instance_to_student(user_name)
                                                logger.info(f"Re-assigned instance after termination: {assignment_result}")
                                                user_info['instance_id'] = assignment_result['instance_id']
                                                user_info['ec2_ip'] = assignment_result.get('public_ip')
                                            except Exception as assign_error:
                                                logger.error(f"Failed to re-assign instance after termination: {str(assign_error)}")
                                                user_info['instance_error'] = f'Previous instance was terminated. Failed to assign new instance: {str(assign_error)}'
                                        else:
                                            user_info['instance_error'] = f'Instance is {state}. Please try again.'
                            except ClientError as e:
                                error_code = e.response.get('Error', {}).get('Code', '')
                                if error_code == 'InvalidInstanceID.NotFound':
                                    logger.warning(f"Instance {user_info['instance_id']} not found (InvalidInstanceID.NotFound)")
                                    # Instance doesn't exist - clean up old record and assign a new one
                                    old_instance_id = user_info['instance_id']
                                    try:
                                        # Delete the old DynamoDB record for the non-existent instance
                                        try:
                                            table.delete_item(Key={'instance_id': old_instance_id})
                                            logger.info(f"Deleted old DynamoDB record for non-existent instance {old_instance_id}")
                                        except Exception as delete_error:
                                            logger.warning(f"Could not delete old DynamoDB record: {str(delete_error)}")
                                        
                                        # Assign a new instance
                                        assignment_result = assign_ec2_instance_to_student(user_name)
                                        logger.info(f"Re-assigned instance after InvalidInstanceID: {assignment_result}")
                                        user_info['instance_id'] = assignment_result['instance_id']
                                        user_info['ec2_ip'] = assignment_result.get('public_ip')
                                    except Exception as assign_error:
                                        logger.error(f"Failed to re-assign instance: {str(assign_error)}")
                                        user_info['instance_error'] = f'Previous instance was not found. Failed to assign new instance: {str(assign_error)}'
                                else:
                                    logger.error(f"Error checking instance status: {str(e)}", exc_info=True)
                                    # For any other ClientError, try to reassign
                                    old_instance_id = user_info.get('instance_id')
                                    if old_instance_id:
                                        try:
                                            table.delete_item(Key={'instance_id': old_instance_id})
                                            logger.info(f"Deleted old DynamoDB record after ClientError")
                                            assignment_result = assign_ec2_instance_to_student(user_name)
                                            logger.info(f"Re-assigned instance after ClientError: {assignment_result}")
                                            user_info['instance_id'] = assignment_result['instance_id']
                                            user_info['ec2_ip'] = assignment_result.get('public_ip')
                                        except Exception as assign_error:
                                            logger.error(f"Failed to re-assign instance: {str(assign_error)}")
                                            user_info['instance_error'] = f'Error checking instance status: {str(e)}. Failed to assign new instance: {str(assign_error)}'
                                    else:
                                        user_info['instance_error'] = f'Error checking instance status: {str(e)}'
                            except Exception as e:
                                logger.error(f"Error checking instance status: {str(e)}", exc_info=True)
                                # For any other exception, try to reassign
                                old_instance_id = user_info.get('instance_id')
                                if old_instance_id:
                                    try:
                                        table.delete_item(Key={'instance_id': old_instance_id})
                                        logger.info(f"Deleted old DynamoDB record after exception")
                                        assignment_result = assign_ec2_instance_to_student(user_name)
                                        logger.info(f"Re-assigned instance after exception: {assignment_result}")
                                        user_info['instance_id'] = assignment_result['instance_id']
                                        user_info['ec2_ip'] = assignment_result.get('public_ip')
                                    except Exception as assign_error:
                                        logger.error(f"Failed to re-assign instance: {str(assign_error)}")
                                        user_info['instance_error'] = f'Error checking instance status: {str(e)}. Failed to assign new instance: {str(assign_error)}'
                                else:
                                    user_info['instance_error'] = f'Error checking instance status: {str(e)}'
                        else:
                            # User exists in DynamoDB but no instance assigned - try to assign one
                            try:
                                assignment_result = assign_ec2_instance_to_student(user_name)
                                logger.info(f"Assignment result for existing user: {assignment_result}")
                                user_info['instance_id'] = assignment_result['instance_id']
                                user_info['ec2_ip'] = assignment_result.get('public_ip')
                            except Exception as e:
                                logger.error(f"Failed to assign instance to existing user: {str(e)}")
                                user_info['instance_error'] = str(e)
                        
                        # Always load Azure LLM configurations
                        try:
                            azure_configs = get_secret()
                            user_info['azure_configs'] = azure_configs
                            logger.info(f"[Azure Config] For user {user_name}, loaded {len(azure_configs)} configs")
                        except Exception as e:
                            logger.error(f"Error loading Azure configurations: {str(e)}")
                            user_info['azure_configs'] = []
                        
                        html_content = generate_html_response(user_info=user_info, error_message=None, status_lambda_url=status_lambda_url)
                        headers = {'Content-Type': 'text/html'}
                        cookie_headers = create_cookie_headers(user_info)
                        response = {
                            'statusCode': 200,
                            'body': html_content,
                            'headers': headers
                        }
                        if cookie_headers:
                            response['multiValueHeaders'] = {'Set-Cookie': cookie_headers}
                        return response
                    else:
                        # User found in cookie but NOT in DynamoDB - check if IAM user exists and if instance is already assigned
                        logger.info(f"User {user_name} not found in DynamoDB (Items: {response.get('Items', [])}), checking IAM and EC2")
                        # Note: 'response' here refers to the DynamoDB query response, not the HTTP response
                        # Check EC2 for existing instances assigned to this user (regardless of IAM user existence)
                        # This handles cases where the user was deleted but the instance still exists
                        logger.info(f"Checking EC2 for instances assigned to {user_name}")
                        ec2 = boto3.client('ec2', region_name=REGION)
                        filters = [
                            {'Name': 'tag:Student', 'Values': [user_name]},
                            {'Name': 'tag:Type', 'Values': ['pool']},
                            {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped']}
                        ]
                        instance_response = ec2.describe_instances(Filters=filters)
                        
                        existing_instance = None
                        for reservation in instance_response.get('Reservations', []):
                            for inst in reservation.get('Instances', []):
                                # Verify the instance is actually assigned to this user and not terminated
                                instance_state = inst['State']['Name']
                                if instance_state in ['terminated', 'shutting-down']:
                                    continue  # Skip terminated instances
                                tags = {tag['Key']: tag['Value'] for tag in inst.get('Tags', [])}
                                if tags.get('Student') == user_name:
                                    existing_instance = inst
                                    break
                            if existing_instance:
                                break
                        
                        if existing_instance:
                            # Found an existing instance assigned to this user - reuse it
                            instance_id = existing_instance['InstanceId']
                            instance_state = existing_instance['State']['Name']
                            logger.info(f"Found existing instance {instance_id} assigned to {user_name} (state: {instance_state})")
                            
                            # Check if IAM user exists - if not, we'll need to handle it
                            iam_user_exists = user_exists(user_name)
                            if not iam_user_exists:
                                logger.warning(f"User {user_name} doesn't exist in IAM but has instance {instance_id} assigned - instance will be reused but user needs to be recreated")
                                # For now, we'll reuse the instance but the user won't have IAM access
                                # This is a recovery scenario
                            
                            # Create or update DynamoDB record
                            try:
                                table.put_item(Item={
                                    'instance_id': instance_id,
                                    'student_name': user_name,
                                    'assigned_at': datetime.utcnow().isoformat(),
                                    'status': 'starting' if instance_state == 'pending' else ('running' if instance_state == 'running' else 'stopped')
                                })
                                logger.info(f"Created/updated DynamoDB record for instance {instance_id}")
                            except Exception as db_error:
                                logger.warning(f"Could not create DynamoDB record: {str(db_error)}")
                            
                            user_info = {
                                'user_name': user_name,
                                'instance_id': instance_id,
                                'ec2_ip': existing_instance.get('PublicIpAddress'),
                                'account_id': ACCOUNT_ID,
                                'login_url': f"https://{ACCOUNT_ID}.signin.aws.amazon.com/console"
                            }
                            
                            # Start instance if it's stopped
                            if instance_state == 'stopped':
                                try:
                                    ec2.start_instances(InstanceIds=[instance_id])
                                    logger.info(f"Started stopped instance {instance_id}")
                                    user_info['instance_error'] = 'Instance is starting...'
                                except Exception as start_error:
                                    logger.error(f"Failed to start instance: {str(start_error)}")
                                    user_info['instance_error'] = f'Failed to start instance: {str(start_error)}'
                            
                            # Load Azure configs
                            try:
                                azure_configs = get_secret()
                                user_info['azure_configs'] = azure_configs
                            except Exception as e:
                                logger.error(f"Error loading Azure configurations: {str(e)}")
                                user_info['azure_configs'] = []
                            
                            html_content = generate_html_response(user_info=user_info, error_message=None, status_lambda_url=status_lambda_url)
                            headers = {'Content-Type': 'text/html'}
                            cookie_headers = create_cookie_headers(user_info)
                            response = {
                                'statusCode': 200,
                                'body': html_content,
                                'headers': headers
                            }
                            if cookie_headers:
                                response['multiValueHeaders'] = {'Set-Cookie': cookie_headers}
                            return response
                        
                        # No existing instance found - check if IAM user exists
                        try:
                            if user_exists(user_name):
                                logger.info(f"User {user_name} exists in IAM but no EC2 instance found - creating new assignment")
                                user_info = {
                                    'user_name': user_name,
                                    'account_id': ACCOUNT_ID,
                                    'login_url': f"https://{ACCOUNT_ID}.signin.aws.amazon.com/console"
                                }
                                
                                # Assign EC2 instance
                                try:
                                    assignment_result = assign_ec2_instance_to_student(user_name)
                                    logger.info(f"Assignment result: {assignment_result}")
                                    user_info['instance_id'] = assignment_result['instance_id']
                                    user_info['ec2_ip'] = assignment_result.get('public_ip')
                                except Exception as e:
                                    logger.error(f"Failed to assign instance: {str(e)}")
                                    user_info['instance_error'] = str(e)
                                
                                # Load Azure configs
                                try:
                                    azure_configs = get_secret()
                                    user_info['azure_configs'] = azure_configs
                                except Exception as e:
                                    logger.error(f"Error loading Azure configurations: {str(e)}")
                                    user_info['azure_configs'] = []
                                
                                html_content = generate_html_response(user_info=user_info, error_message=None, status_lambda_url=status_lambda_url)
                                headers = {'Content-Type': 'text/html'}
                                cookie_headers = create_cookie_headers(user_info)
                                response = {
                                    'statusCode': 200,
                                    'body': html_content,
                                    'headers': headers
                                }
                                if cookie_headers:
                                    response['multiValueHeaders'] = {'Set-Cookie': cookie_headers}
                                return response
                            else:
                                # Cookie has invalid user (doesn't exist in IAM and no EC2 instance found)
                                # This means the user was deleted - clear cookies and create new user
                                logger.warning(f"User {user_name} in cookie doesn't exist in IAM and no EC2 instance found - user was likely deleted, creating new user")
                                # Fall through to create new user below
                        except Exception as e:
                            logger.error(f"Error checking IAM user existence: {str(e)}", exc_info=True)
                            logger.warning(f"Exception during IAM check, falling through to create new user")
                            # Fall through to create new user below
                
                # No user_name in cookie or cookie user invalid: create a new user
                logger.info(f"[Azure Config] New user path")
                user_info = create_user()
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
                headers = {'Content-Type': 'text/html'}
                cookie_headers = create_cookie_headers(user_info)
                response = {
                    'statusCode': 200,
                    'body': html_content,
                    'headers': headers
                }
                if cookie_headers:
                    response['multiValueHeaders'] = {'Set-Cookie': cookie_headers}
                return response
            else:
                logger.warning(f"Unknown path requested: {path}")
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': 'Not found'}),
                    'headers': {
                        'Content-Type': 'application/json'
                    }
                }
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
            return {
                'statusCode': 405,
                'body': method_not_allowed_html,
                'headers': {
                    'Content-Type': 'text/html'
                }
            }
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            }),
            'headers': {
                'Content-Type': 'application/json'
            }
        }

def create_user():
    account_id = ACCOUNT_ID
    logger.info("Starting create_user()...")
    suffix = os.urandom(4).hex()
    console_user_name = f"conference-user-{suffix}"
    logger.info(f"Generated user name: {console_user_name}")
    if user_exists(console_user_name):
        logger.warning("User already exists. Try again.")
        raise Exception("User already exists. Try again.")

    user = create_console_user(console_user_name, account_id)

    # Get all Azure OpenAI configurations
    azure_configs = get_secret()
    logger.info(f"Fetched Azure LLM configs from Secrets Manager: {azure_configs}")
    user['azure_configs'] = azure_configs

    # Assign EC2 instance from pool instead of launching a new one
    try:
        assignment_result = assign_ec2_instance_to_student(console_user_name)
        logger.info(f"Assignment result: {assignment_result}")
        user['instance_id'] = assignment_result['instance_id']
        user['ec2_ip'] = assignment_result.get('public_ip')
        if assignment_result['status'] == 'already_assigned':
            logger.info(f"EC2 instance already assigned: {assignment_result['instance_id']}")
        else:
            logger.info(f"Assigned EC2 instance: {assignment_result['instance_id']}")
    except Exception as e:
        logger.error(f"No available EC2 instances: {str(e)}")
        user['ec2_ip'] = None
        user['instance_error'] = str(e)

    logger.info(f"User info passed to HTML: {user}")
    return user

def user_exists(user_name):
    """Checks if a user already exists."""
    try:
        iam.get_user(UserName=user_name)
        return True
    except iam.exceptions.NoSuchEntityException:
        return False

def create_console_user(user_name, account_id):
    """Creates a console user with login profile."""
    iam.create_user(UserName=user_name)

    # Generate a random password for the console user
    password = generate_random_password()

    iam.create_login_profile(
        UserName=user_name,
        Password=password,
        PasswordResetRequired=False
    )

    # Attach the existing service role policy
    policy_arn = "arn:aws:iam::087559609246:policy/ServiceUserRestrictedPolicy"
    iam.attach_user_policy(
        UserName=user_name,
        PolicyArn=policy_arn
    )

    # Store the account and user information
    login_url = f"https://{account_id}.signin.aws.amazon.com/console"
    account_info = {
        'account_id': account_id,
        'user_name': user_name,
        'password': password,
        'login_url': login_url
    }
    return account_info

def generate_random_password(length=12):
    """Generates a random password with a mix of letters, digits, and allowed symbols."""
    alphabet = string.ascii_letters + string.digits + "*!?_-"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in "*!?_-" for c in password)):
            break
    return password

def cleanup_expired_assignments():
    """Clean up expired 'assigning' records and reset their instances"""
    client = boto3.client('ec2', region_name=REGION)
    current_time = int(time.time())
    
    try:
        # Scan for expired 'assigning' records
        response = table.scan(
            FilterExpression='#status = :status AND expires_at < :now',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'assigning',
                ':now': current_time
            }
        )
        
        for item in response.get('Items', []):
            instance_id = item['instance_id']
            logger.info(f"Cleaning up expired assignment for instance {instance_id}")
            
            try:
                # Reset instance tags
                client.create_tags(
                    Resources=[instance_id],
                    Tags=[
                        {'Key': 'Status', 'Value': 'available'},
                        {'Key': 'Student', 'Value': ''}
                    ]
                )
                
                # Delete DynamoDB record
                table.delete_item(
                    Key={
                        'instance_id': instance_id,
                        'student_name': item['student_name']
                    }
                )
                
                logger.info(f"Successfully cleaned up instance {instance_id}")
                
            except Exception as e:
                logger.error(f"Error cleaning up instance {instance_id}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error in cleanup_expired_assignments: {str(e)}")
        raise

def assign_ec2_instance_to_student(student_name):
    client = boto3.client('ec2', region_name=REGION)
    max_retries = 3
    base_delay = 2  # Base delay in seconds
    assignment_ttl = 600  # 10 minutes in seconds

    # First, clean up any expired assignments
    cleanup_expired_assignments()

    # Check if student already has an assigned instance
    try:
        response = table.query(
            IndexName='student_name-index',
            KeyConditionExpression='student_name = :sn',
            ExpressionAttributeValues={':sn': student_name}
        )
        if response['Items']:
            instance_id = response['Items'][0]['instance_id']
            # Verify instance still exists and is assigned to this student
            filters = [
                {'Name': 'instance-id', 'Values': [instance_id]},
                {'Name': 'tag:Student', 'Values': [student_name]},
                {'Name': 'tag:Status', 'Values': ['assigned']}
            ]
            response = client.describe_instances(Filters=filters)
            if response['Reservations']:
                return {
                    'instance_id': instance_id,
                    'status': 'already_assigned',
                    'public_ip': response['Reservations'][0]['Instances'][0].get('PublicIpAddress')
                }
    except ClientError as e:
        logger.error(f"Error checking existing assignment: {str(e)}")
        raise

    # Find available instances with retry logic
    for attempt in range(max_retries):
        try:
            # 1. Find available instances in the pool (both stopped and running)
            filters = [
                {'Name': 'tag:Type', 'Values': ['pool']},
                {'Name': 'instance-state-name', 'Values': ['stopped', 'running']}
            ]
            response = client.describe_instances(Filters=filters)
            instances = [i for r in response['Reservations'] for i in r['Instances']]

            if not instances:
                raise Exception("No available EC2 instances in the pool.")

            # Filter out instances that are already assigned in DynamoDB
            available_instances = []
            for instance in instances:
                try:
                    # Check if instance is assigned in DynamoDB
                    response = table.get_item(Key={'instance_id': instance['InstanceId']})
                    if 'Item' not in response:
                        # No record exists, instance is available
                        available_instances.append(instance)
                    elif response['Item'].get('status') == 'stopped':
                        # Instance is stopped but not assigned to a student
                        # We can reuse it, but need to preserve the last_stopped_at time
                        available_instances.append(instance)
                    # Skip instances with other statuses (assigning, starting, assigned)
                except Exception as e:
                    logger.error(f"Error checking DynamoDB for instance {instance['InstanceId']}: {str(e)}")
                    continue

            if not available_instances:
                raise Exception("No available EC2 instances in the pool (all are assigned).")

            # Randomize instance selection to reduce collision probability
            random.shuffle(available_instances)
            
            # Try to assign each instance until successful
            for instance in available_instances:
                instance_id = instance['InstanceId']
                try:
                    # Get existing record if any
                    existing_record = table.get_item(Key={'instance_id': instance_id})
                    last_stopped_at = existing_record.get('Item', {}).get('last_stopped_at')
                    
                    # Try to create or update the assignment in DynamoDB with TTL
                    item = {
                        'instance_id': instance_id,
                        'student_name': student_name,
                        'assigned_at': datetime.utcnow().isoformat(),
                        'status': 'assigning',
                        'expires_at': int(time.time()) + assignment_ttl
                    }
                    
                    # Preserve last_stopped_at if it exists
                    if last_stopped_at:
                        item['last_stopped_at'] = last_stopped_at
                    
                    table.put_item(
                        Item=item,
                        ConditionExpression='attribute_not_exists(instance_id) OR #status = :stopped',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={':stopped': 'stopped'}
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                        # Instance was already assigned or status changed, try the next one
                        logger.warning(f"Concurrent update detected for instance {instance_id}, trying next instance")
                        continue
                    else:
                        # Other error, raise it
                        raise
                # If we reach here, DynamoDB write succeeded
                try:
                    # Mark instance as starting before any operations
                    client.create_tags(
                        Resources=[instance_id],
                        Tags=[
                            {'Key': 'Status', 'Value': 'starting'},
                            {'Key': 'Student', 'Value': student_name}
                        ]
                    )
                    
                    # If instance is stopped, start it
                    if instance['State']['Name'] == 'stopped':
                        client.start_instances(InstanceIds=[instance_id])
                    
                    # Update tags to assigned after successful start
                    client.create_tags(
                        Resources=[instance_id],
                        Tags=[
                            {'Key': 'Status', 'Value': 'assigned'},
                            {'Key': 'Student', 'Value': student_name}
                        ]
                    )
                except Exception as e:
                    logger.error(f"Failed to update EC2 tags for instance {instance_id}: {str(e)}")
                    # Do not roll back the DynamoDB assignment
                # Update DynamoDB status and remove TTL
                try:
                    table.update_item(
                        Key={
                            'instance_id': instance_id
                        },
                        UpdateExpression='SET #status = :status REMOVE expires_at',
                        ConditionExpression='attribute_exists(instance_id) AND #status = :expected',
                        ExpressionAttributeNames={
                            '#status': 'status'
                        },
                        ExpressionAttributeValues={
                            ':status': 'starting',
                            ':expected': 'assigning'
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to update DynamoDB status for instance {instance_id}: {str(e)}")
                
                # Ensure DynamoDB record exists before returning
                # This helps prevent race conditions where the record might not be immediately queryable
                try:
                    # Verify the record exists
                    verify_response = table.get_item(Key={'instance_id': instance_id})
                    if 'Item' not in verify_response:
                        logger.warning(f"DynamoDB record for {instance_id} not found after assignment, recreating")
                        table.put_item(Item={
                            'instance_id': instance_id,
                            'student_name': student_name,
                            'assigned_at': datetime.utcnow().isoformat(),
                            'status': 'starting'
                        })
                    logger.info(f"Verified DynamoDB record exists for instance {instance_id}")
                except Exception as e:
                    logger.error(f"Error verifying DynamoDB record for {instance_id}: {str(e)}")
                
                return {
                    'instance_id': instance_id,
                    'status': 'starting'
                }
            # If we get here, all instances were already assigned
            raise Exception("No available EC2 instances in the pool.")
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                retry_delay = (base_delay ** attempt) + random.uniform(0, 1)
                logger.info(f"Retry attempt {attempt + 1} after {retry_delay:.2f} seconds")
                time.sleep(retry_delay)
                continue
            raise
    raise Exception("Failed to assign an instance after multiple attempts.")

def verify_instance_health(instance_id, student_name):
    """Verify that an instance is healthy and ready to use"""
    client = boto3.client('ec2', region_name=REGION)
    ssm = boto3.client('ssm', region_name=REGION)
    
    try:
        # Check instance state
        response = client.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        
        if instance['State']['Name'] != 'running':
            return False
            
        # Check if instance is reachable via SSM
        try:
            ssm.describe_instance_information(
                Filters=[{'Key': 'InstanceIds', 'Values': [instance_id]}]
            )
            return True
        except ClientError:
            return False
            
    except Exception as e:
        logger.error(f"Error verifying instance health: {str(e)}")
        return False

def cleanup_failed_assignment(instance_id, student_name):
    """Clean up a failed instance assignment"""
    client = boto3.client('ec2', region_name=REGION)
    
    try:
        # Remove DynamoDB entry
        table.delete_item(
            Key={
                'instance_id': instance_id
            }
        )
        
        # Reset EC2 tags to available
        client.create_tags(
            Resources=[instance_id],
            Tags=[
                {'Key': 'Status', 'Value': 'available'},
                {'Key': 'Student', 'Value': ''}
            ]
        )
        
        logger.info(f"Cleaned up failed assignment for instance {instance_id}")
        
    except Exception as e:
        logger.error(f"Error cleaning up failed assignment: {str(e)}")
        raise