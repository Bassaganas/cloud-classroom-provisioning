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
from datetime import datetime

# Initialize AWS clients
iam = boto3.client('iam')
resource_groups = boto3.client('resource-groups')
secretsmanager = boto3.client('secretsmanager', region_name='eu-west-3')

# Get account ID from environment variable
ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID', '087559609246')

# Add this constant at the top of the file
DESTROY_KEY = os.environ.get('DESTROY_KEY', 'default_destroy_key')

#Status Lambda URL
status_lambda_url = os.environ.get('STATUS_LAMBDA_URL')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_secret():
    """Retrieve Azure OpenAI configuration from AWS Secrets Manager"""
    secret_name = "azure/llm/configs"
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except ClientError as e:
        logger.error(f"Error retrieving secret: {str(e)}")
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

def generate_html_response(user_info, resource_group_url, status_lambda_url):
    azure_configs_html = ""
    if 'azure_configs' in user_info and user_info['azure_configs']:
        azure_configs = user_info['azure_configs']
        azure_configs_html = f"""
        <div class="info-box">
            <h2>LLM Models</h2>
            <div class="azure-cards">
        """
        for i, config in enumerate(azure_configs, 1):
            azure_configs_html += f"""
            <div class="azure-card">
                <div class="config-title">{config['config_name']}</div>
                <div class="config-row"><span>Deployment Name:</span> <span class="mono">{config['deployment_name']}</span> <button class="copy-btn" onclick="copyToClipboard('{config['deployment_name']}')"><i class="fas fa-copy"></i></button></div>
                <div class="config-row"><span>API Key:</span> <span class="mono">{config['api_key']}</span> <button class="copy-btn" onclick="copyToClipboard('{config['api_key']}')"><i class="fas fa-copy"></i></button></div>
                <div class="config-row"><span>Endpoint:</span> <span class="mono">{config['endpoint']}</span> <button class="copy-btn" onclick="copyToClipboard('{config['endpoint']}')"><i class="fas fa-copy"></i></button></div>
                <div class="config-row"><span>Version:</span> <span class="mono">{config['api_version']}</span></div>
            </div>
            """
        azure_configs_html += "</div></div>"

    html_content = f"""
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
        <meta charset=\"UTF-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
        <title>Testus Patronus</title>
        <subtitle>No magic, just AI with your company context</subtitle>
        <link rel=\"icon\" href=\"https://www.eicc.co.uk/media/1bpegpql/eurostar2025-logo-500px-x-500px-002.jpg?rmode=max&width=720&height=720&quality=70&v=1db515dc4767eb0\">
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
            .top-bar {{
                background: var(--pink);
                height: 8px;
                width: 100vw;
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
                max-width: 180px;
                border-radius: 12px;
                background: var(--white);
                box-shadow: 0 2px 8px rgba(30,52,178,0.08);
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
                grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
                gap: 18px;
            }}
            .azure-card {{
                background: var(--white);
                border: 2px solid var(--blue);
                border-radius: 10px;
                padding: 16px 18px;
                margin-bottom: 0;
                box-shadow: 0 2px 8px rgba(30,52,178,0.06);
            }}
            .config-title {{
                font-weight: 700;
                color: var(--blue);
                margin-bottom: 8px;
                font-size: 1.1rem;
            }}
            .config-row {{
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 6px;
                font-size: 1.05rem;
            }}
            .config-row span:first-child {{
                min-width: 120px;
                color: var(--blue);
                font-weight: 500;
            }}
            .mono {{
                font-family: 'Fira Mono', 'Consolas', monospace;
                background: #f0f0fa;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.98em;
                word-break: break-all;
                white-space: pre-wrap;
                overflow-wrap: anywhere;
                display: inline-block;
                max-width: 100%;
            }}
            .config-row span.mono {{
                display: block;
                max-width: 100%;
            }}
            .copy-btn {{
                background: var(--pink);
                color: var(--blue);
                border: none;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 1em;
                margin-left: 4px;
                cursor: pointer;
                transition: background 0.2s;
            }}
            .copy-btn:hover {{
                background: var(--yellow);
                color: var(--blue);
            }}
            .url-box {{
                background: var(--yellow);
                border-radius: 6px;
                padding: 10px 14px;
                margin-bottom: 12px;
                font-size: 1.1rem;
                color: var(--blue);
                font-weight: 600;
                text-align: center;
                box-shadow: 0 2px 8px rgba(30,52,178,0.04);
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
        </style>
        <script>
            function copyToClipboard(text) {{
                navigator.clipboard.writeText(text).then(function() {{
                    alert('Copied to clipboard!');
                }});
            }}

            // Dify polling logic
            document.addEventListener('DOMContentLoaded', function() {{
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
                            if (data.ready && data.ip) {{
                                difyLink.href = 'http://' + data.ip;
                                difyLink.textContent = 'http://' + data.ip;
                                difyLink.classList.add('ready');
                                difyLink.style.pointerEvents = 'auto';
                                spinner.style.display = 'none';
                                statusMsg.textContent = 'Your Dify instance is ready!';
                            }} else {{
                                statusMsg.textContent = 'Starting your Dify instance...';
                                if (pollCount < 60) setTimeout(pollStatus, 5000);
                                else statusMsg.textContent = 'Still waiting for your instance. Please refresh if this takes too long.';
                            }}
                        }})
                        .catch(err => {{
                            statusMsg.textContent = 'Checking instance status...';
                            if (pollCount < 60) setTimeout(pollStatus, 5000);
                        }});
                }}
                pollStatus();
            }});
        </script>
    </head>
    <body>
        <div class="top-bar"></div>
        <div class="container">
            <img src="https://www.eicc.co.uk/media/1bpegpql/eurostar2025-logo-500px-x-500px-002.jpg?rmode=max&width=720&height=720&quality=70&v=1db515dc4767eb0" alt="EuroSTAR 2025 Logo" class="logo">
            <div class="main-title">Testus Patronus</div>
            <div class="subtitle">No magic, just AI with your company context</div>
            <h2>Welcome! Here are your Azure LLM credentials and your Dify instance link.</h2>
            <div class="url-box">
                <div class="dify-link-container">
                    <a id="dify-link" class="dify-link" href="#" target="_blank" tabindex="-1">Loading...</a>
                    <span id="dify-spinner" class="spinner"></span>
                </div>
                <div id="dify-status-msg" style="margin-top:8px;font-size:0.98em;color:var(--blue);"></div>
            </div>
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
    """Destroy all service and console users and their associated resources."""
    try:
        # Initialize AWS clients
        ec2 = boto3.client('ec2', region_name='eu-west-3')
        
        # 1. Get all users
        users = iam.list_users()['Users']
        logger.info(f"Found {len(users)} total users")
        
        for user in users:
            user_name = user['UserName']
            logger.info(f"Checking user: {user_name}")
            
            if user_name.startswith('conference-user-') or user_name.startswith('service-conference-user-'):
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
        
        # 8. Delete resource groups
        groups = resource_groups.list_groups()['GroupIdentifiers']
        logger.info(f"Found {len(groups)} resource groups")
        for group in groups:
            if group['Name'].startswith('conference-user-') or group['Name'].startswith('service-conference-user-'):
                try:
                    logger.info(f"Deleting resource group {group['Name']}")
                    resource_groups.delete_group(GroupName=group['Name'])
                except Exception as e:
                    logger.error(f"Error deleting resource group {group['Name']}: {str(e)}")
        
        logger.info(f"Destroy process completed. Deleted {len(users)} users and {len(groups)} resources")
        
    except Exception as e:
        logger.error(f"Error in destroy_users: {str(e)}")

def lambda_handler(event, context):
    logger.info(f"Lambda handler invoked. Event: {json.dumps(event)}")
    # Check if it's a GET request
    if event['requestContext']['http']['method'] == 'GET':
        path = event['requestContext']['http']['path']
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
        elif path == '/':
            # Existing code for creating users
            try:
                logger.info("Starting user creation process...")
                user_info, resource_group_url = create_user()
                logger.info(f"User created: {user_info['user_name']}")
                html_content = generate_html_response(user_info, resource_group_url, status_lambda_url)
                logger.info("HTML content generated for user response.")
                return {
                    'statusCode': 200,
                    'body': html_content,
                    'headers': {
                        'Content-Type': 'text/html'
                    }
                }
            except Exception as e:
                logger.error(f"Error during user creation: {str(e)}", exc_info=True)
                error_html = f"""
                <html>
                    <head>
                        <title>ETL Testing Framework - Error</title>
                    </head>
                    <body>
                        <h1>Error</h1>
                        <p>{str(e)}</p>
                    </body>
                </html>
                """
                return {
                    'statusCode': 500,
                    'body': error_html,
                    'headers': {
                        'Content-Type': 'text/html'
                    }
                }
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

def create_user():
    account_id = ACCOUNT_ID
    logger.info("Starting create_user()...")
    suffix = os.urandom(4).hex()
    console_user_name = f"conference-user-{suffix}"
    service_user_name = f"service-conference-user-{suffix}"
    logger.info(f"Generated user names: {console_user_name}, {service_user_name}")
    if user_exists(console_user_name) or user_exists(service_user_name):
        logger.warning("User already exists. Try again.")
        raise Exception("User already exists. Try again.")

    user = create_console_user(console_user_name, account_id)
    user.update(create_service_user(service_user_name))

    # Get all Azure OpenAI configurations
    azure_configs = get_secret()
    logger.info(f"Fetched Azure LLM configs from Secrets Manager: {azure_configs}")
    user['azure_configs'] = azure_configs

    # Assign EC2 instance from pool instead of launching a new one
    try:
        public_ip = assign_ec2_instance_to_student(console_user_name)
        logger.info(f"Assigned EC2 instance: {public_ip}")
        user['ec2_ip'] = public_ip
    except Exception as e:
        logger.error(f"No available EC2 instances: {str(e)}")
        user['ec2_ip'] = None
        user['instance_error'] = str(e)

    # Create a resource group for the console user
    resource_group_url = create_resource_group_for_user(console_user_name)
    logger.info(f"Created resource group URL: {resource_group_url}")

    logger.info(f"User info passed to HTML: {user}")
    return user, resource_group_url


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

    # Store the account and user information
    login_url = f"https://{account_id}.signin.aws.amazon.com/console"
    account_info = {
        'account_id': account_id,
        'user_name': user_name,
        'password': password,
        'login_url': login_url
    }
    return account_info


def create_service_user(user_name):
    """Creates a service user with access keys for programmatic access and tags the user as a service user."""
    iam.create_user(UserName=user_name)

    # Tag the user as a service user
    iam.tag_user(
        UserName=user_name,
        Tags=[
            {
                'Key': 'UserType',
                'Value': 'service'
            }
        ]
    )

    # Create access keys for the service user
    access_keys = iam.create_access_key(UserName=user_name)

    attach_custom_service_policy(user_name=user_name)

    # Store the service user's access keys
    account_info = {
        'access_key_id': access_keys['AccessKey']['AccessKeyId'],
        'secret_access_key': access_keys['AccessKey']['SecretAccessKey']
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


def attach_custom_service_policy(user_name):
    policy_arn = "arn:aws:iam::087559609246:policy/ServiceUserRestrictedPolicy"  # Replace with your custom policy ARN
    iam.attach_user_policy(
        UserName=user_name,
        PolicyArn=policy_arn
    )


def create_resource_group_for_user(user_name):
    """Creates a resource group for the user based on the Owner tag and returns the console URL."""
    group_name = f"{user_name}-resources"
    resource_query = {
        'ResourceTypeFilters': [
            'AWS::AllSupported'
        ],
        'TagFilters': [
            {
                'Key': 'Owner',
                'Values': [user_name]
            }
        ]
    }

    try:
        response = resource_groups.create_group(
            Name=group_name,
            Description=f"Resources owned by {user_name}",
            ResourceQuery={
                'Type': 'TAG_FILTERS_1_0',
                'Query': json.dumps(resource_query)
            }
        )
        print(f"Created resource group: {group_name}")

        # Generate the console URL for the resource group
        encoded_group_name = urllib.parse.quote(group_name)
        console_url = f"https://console.aws.amazon.com/resource-groups/group/{encoded_group_name}?region={resource_groups.meta.region_name}"
        return console_url
    except resource_groups.exceptions.BadRequestException as e:
        print(f"Error creating resource group: {str(e)}")
        return None

def assign_ec2_instance_to_student(student_name):
    client = boto3.client('ec2', region_name='eu-west-3')

    # Check if student already has an assigned instance
    filters = [
        {'Name': 'tag:Student', 'Values': [student_name]},
        {'Name': 'tag:Status', 'Values': ['assigned']},
        {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopped']}
    ]
    response = client.describe_instances(Filters=filters)
    reservations = response.get('Reservations', [])
    assigned_instances = [i for r in reservations for i in r['Instances']]
    if assigned_instances:
        # Return the existing instance info
        instance = assigned_instances[0]
        return {
            'instance_id': instance['InstanceId'],
            'status': 'already_assigned'
        }

    # 1. Find a stopped, available instance in the pool
    filters = [
        {'Name': 'tag:Status', 'Values': ['available']},
        {'Name': 'tag:Type', 'Values': ['pool']},
        {'Name': 'instance-state-name', 'Values': ['stopped']}
    ]
    response = client.describe_instances(Filters=filters)
    reservations = response.get('Reservations', [])
    instances = [i for r in reservations for i in r['Instances'] if i['State']['Name'] == 'stopped']

    if not instances:
        raise Exception("No available EC2 instances in the pool.")

    instance = instances[0]
    instance_id = instance['InstanceId']

    # 2. Tag the instance as assigned to the student before starting
    client.create_tags(
        Resources=[instance_id],
        Tags=[
            {'Key': 'Status', 'Value': 'assigned'},
            {'Key': 'Student', 'Value': student_name}
        ]
    )

    # 3. Start the instance asynchronously
    client.start_instances(InstanceIds=[instance_id])

    # 4. Return immediately with the instance ID for status tracking
    return {
        'instance_id': instance_id,
        'status': 'starting'
    }