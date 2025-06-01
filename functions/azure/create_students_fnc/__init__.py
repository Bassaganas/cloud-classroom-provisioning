import azure.functions as func
import logging
import os
import uuid
import secrets
import string
from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.models.user import User
from msgraph.generated.models.password_profile import PasswordProfile
from msgraph.generated.models.reference_create import ReferenceCreate
from datetime import datetime, timezone, timedelta
from azure.keyvault.secrets import SecretClient

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClassroomManager:
    def __init__(self):
        logger.info("Initializing ClassroomManager")
        try:
            # Get required environment variables
            self.tenant_id = os.environ.get("AZURE_TENANT_ID")
            client_id = os.environ.get("AZURE_CLIENT_ID")
            client_secret = os.environ.get("AZURE_CLIENT_SECRET")
            self.subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
            
            # Get Terraform service principal credentials
            self.terraform_client_id = os.environ.get("TERRAFORM_CLIENT_ID")
            self.terraform_client_secret = os.environ.get("TERRAFORM_CLIENT_SECRET")
            
            if not all([self.tenant_id, client_id, client_secret, self.subscription_id, 
                       self.terraform_client_id, self.terraform_client_secret]):
                raise ValueError("Missing required environment variables")
            
            # Initialize the credential
            self.credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            
            # Initialize Graph client
            self.graph_client = GraphServiceClient(
                credentials=self.credential,
                scopes=["https://graph.microsoft.com/.default"]
            )
            
            # Get Key Vault URL from environment
            key_vault_url = os.environ.get("AZURE_KEY_VAULT_URL")
            if not key_vault_url:
                raise ValueError("AZURE_KEY_VAULT_URL environment variable not set")
            
            # Initialize Key Vault client
            self.key_vault_client = SecretClient(
                vault_url=key_vault_url,
                credential=self.credential
            )
            
            # Get latest credentials from Key Vault
            self.terraform_client_id = self.key_vault_client.get_secret("terraform-client-id").value
            
            # Try to get current secret first
            try:
                current_secret = self.key_vault_client.get_secret("terraform-client-secret-current")
                self.terraform_client_secret = current_secret.value
                self.terraform_secret_expiry = current_secret.properties.expires_on
            except Exception as e:
                logger.warning(f"Could not get current secret, trying next secret: {str(e)}")
                # If current secret is expired/invalid, try the next one
                next_secret = self.key_vault_client.get_secret("terraform-client-secret-next")
                self.terraform_client_secret = next_secret.value
                self.terraform_secret_expiry = next_secret.properties.expires_on
            
            # Check if secret is about to expire
            if self.terraform_secret_expiry:
                warning_threshold = timedelta(days=1)
                time_to_expiry = self.terraform_secret_expiry - datetime.now(timezone.utc)
                if time_to_expiry < warning_threshold:
                    logger.warning(f"Terraform credentials will expire in {time_to_expiry}")
            
            logger.info("Successfully initialized Azure clients")
        except Exception as e:
            logger.error(f"Error initializing ClassroomManager: {str(e)}")
            raise

    def generate_password(self):
        """Generate a secure password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for i in range(16))
        return password
    
    async def assign_student_roles(self, user_object_id):
        """Add the user to the students group"""
        try:
            group_id = os.environ.get("STUDENTS_GROUP_ID")
            if not group_id:
                raise ValueError("STUDENTS_GROUP_ID environment variable not set")
            
            reference = ReferenceCreate(
                odata_id=f"https://graph.microsoft.com/v1.0/users/{user_object_id}"
            )
            
            await self.graph_client.groups.by_group_id(group_id).members.ref.post(
                body=reference
            )
            logger.info(f"Added user {user_object_id} to students group")
        except Exception as e:
            logger.error(f"Error adding user to students group: {str(e)}")
            raise

    async def create_student_user(self):
        """Create a student user account"""
        try:
            username = f"student_{uuid.uuid4().hex[:8]}"
            password = self.generate_password()
            domain = os.environ.get("AZURE_DOMAIN", "paulabassaganasgmail.onmicrosoft.com")
            logger.info(f"Creating student user with username: {username}")

            # Create user
            request_body = User(
                account_enabled=True,
                display_name=f"Student {username}",
                mail_nickname=username,
                user_principal_name=f"{username}@{domain}",
                password_profile=PasswordProfile(
                    force_change_password_next_sign_in=False,
                    password=password
                )
            )

            created_user = await self.graph_client.users.post(request_body)
            await self.assign_student_roles(created_user.id)
            
            # Format expiry date for display
            expiry_date = None
            if hasattr(self, 'terraform_secret_expiry'):
                expiry_date = self.terraform_secret_expiry.strftime("%Y-%m-%d %H:%M UTC")
            
            return {
                "username": created_user.user_principal_name,
                "password": password,
                "terraform": {
                    "arm_client_id": self.terraform_client_id,
                    "arm_client_secret": self.terraform_client_secret,
                    "arm_tenant_id": self.tenant_id,
                    "arm_subscription_id": self.subscription_id,
                    "expiry_date": expiry_date
                }
            }
        except Exception as e:
            logger.error(f"Error creating student user: {str(e)}")
            raise

async def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        manager = ClassroomManager()
        credentials = await manager.create_student_user()
        
        # Add any missing variables needed by the template
        background = "#3f0383"  # or whatever value you need
        
        return func.HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Cloud Classroom Access</title>
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
                <style>
                    :root {{
                        --pink: #f452cb;
                        --background-purple: #3f0383;
                        --yellow: #ffd101;
                        --dark-blue: #1B1464;
                        --white: #FFFFFF;
                    }}
                    
                    html {{
                        font-size: 62.5%;
                        -webkit-font-smoothing: antialiased;
                        -moz-osx-font-smoothing: grayscale;
                    }}
                    
                    body {{
                        font-family: 'Open Sans', sans-serif;
                        font-size: 2.1rem;
                        font-weight: 300;
                        line-height: 1.2;
                        margin: 0;
                        padding-top: 80px;
                        overflow-x: hidden;
                        background-color: var(--background-purple);
                        color: var(--white);
                    }}

                    .top-bar {{
                        position: fixed;
                        top: 0;
                        left: 0;
                        right: 0;
                        z-index: 9999;
                        background: var(--pink);
                        color: var(--dark-blue);
                        font-weight: bold;
                        box-shadow: 0 2px 6px 0 rgba(0, 0, 0, .07);
                        height: 80px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}

                    .container {{
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 2rem;
                    }}

                    .section-title {{
                        position: relative;
                        color: var(--white);
                        font-size: 4rem;
                        font-weight: 700;
                        margin-bottom: 3rem;
                        padding-bottom: 1.5rem;
                        text-align: center;
                    }}

                    .credentials-section {{
                        display: grid;
                        grid-template-columns: repeat(2, 1fr);
                        gap: 3rem;
                        margin: 4rem 0;
                    }}

                    .card {{
                        border-radius: 15px;
                        padding: 3rem;
                        position: relative;
                        overflow: hidden;
                        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                        width: 100%;
                    }}

                    .individual-credentials {{
                        background: var(--yellow);
                        border: 3px solid var(--dark-blue);
                        min-width: min-content;
                    }}

                    .group-info {{
                        background: var(--pink);
                        color: var(--white);
                    }}

                    .card h2 {{
                        font-size: 3rem;
                        font-weight: 700;
                        margin-top: 0;
                        margin-bottom: 2rem;
                        color: var(--background-purple);
                    }}

                    .group-info h2 {{
                        color: var(--white);
                    }}

                    .credential-item {{
                        margin-bottom: 2rem;
                    }}

                    .credential-item strong {{
                        display: block;
                        margin-bottom: 1rem;
                        font-size: 2rem;
                        font-weight: 600;
                        color: var(--background-purple);
                    }}

                    .credential-value {{
                        background: var(--white);
                        padding: 1.5rem;
                        border-radius: 8px;
                        font-family: monospace;
                        font-size: 1.8rem;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                        color: var(--background-purple);
                        white-space: nowrap;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        gap: 1rem;
                    }}

                    .credential-text {{
                        flex: 1;
                        overflow-x: auto;
                    }}

                    .copy-button {{
                        background: none;
                        border: none;
                        padding: 0;
                        cursor: pointer;
                        color: var(--background-purple);
                        transition: all 0.3s ease;
                    }}

                    .copy-button:hover {{
                        color: var(--pink);
                    }}

                    .copy-button i {{
                        font-size: 2rem;
                    }}

                    .terraform-instructions {{
                        margin-top: 3rem;
                        padding: 2rem;
                        background: var(--yellow);
                        border-radius: 8px;
                        color: var(--dark-blue);
                    }}

                    .terraform-instructions h3 {{
                        color: var(--dark-blue);
                        margin-top: 0;
                    }}

                    .terraform-instructions ol {{
                        padding-left: 2rem;
                    }}

                    .terraform-instructions pre {{
                        background: var(--white);
                        padding: 1rem;
                        border-radius: 4px;
                        margin: 1rem 0;
                        overflow-x: auto;
                    }}

                    .note {{
                        font-style: italic;
                        margin-top: 2rem;
                        font-size: 1.6rem;
                    }}

                    .download-button {{
                        display: block;
                        width: 100%;
                        background-color: var(--background-purple);
                        color: var(--white);
                        border: none;
                        border-radius: 8px;
                        padding: 1.5rem;
                        margin-top: 2rem;
                        font-size: 1.6rem;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        font-weight: 600;
                    }}

                    .download-button:hover {{
                        background-color: var(--pink);
                        transform: translateY(-2px);
                    }}

                    @media (max-width: 1200px) {{
                        .credentials-section {{
                            grid-template-columns: 1fr;
                        }}
                    }}

                    @media (max-width: 480px) {{
                        html {{
                            font-size: 55%;
                        }}
                    }}

                    .expiry-warning {{
                        background-color: rgba(255, 209, 1, 0.1);
                        border-left: 4px solid var(--yellow);
                        padding: 1rem;
                        margin-top: 2rem;
                    }}

                    .terraform-credentials {{
                        background: var(--pink);
                        color: var(--white);
                    }}

                    .terraform-credentials h2 {{
                        color: var(--white);
                    }}

                    .terraform-credentials .credential-item strong {{
                        color: var(--white);
                    }}

                    .terraform-credentials .terraform-instructions h3 {{
                        color: var(--white);
                    }}

                    .terraform-instructions-container {{
                        grid-column: 1 / -1;
                        margin-top: 3rem;
                    }}

                    .azure-portal-button {{
                        display: block;
                        width: 100%;
                        background-color: var(--dark-blue);
                        color: var(--white);
                        border: none;
                        border-radius: 8px;
                        padding: 1.5rem;
                        margin-top: 2rem;
                        font-size: 1.6rem;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        font-weight: 600;
                        text-decoration: none;
                        text-align: center;
                    }}

                    .azure-portal-button:hover {{
                        background-color: var(--pink);
                        transform: translateY(-2px);
                    }}
                </style>
                <script>
                    function copyToClipboard(text, elementId) {{
                        navigator.clipboard.writeText(text).then(function() {{
                            const element = document.getElementById(elementId);
                            element.innerHTML = '<i class="fas fa-check"></i>';
                            setTimeout(function() {{
                                element.innerHTML = '<i class="fas fa-copy"></i>';
                            }}, 2000);
                        }});
                    }}

                    function downloadTerraformEnv() {{
                        const clientId = document.getElementById('terraform-client-id').textContent.trim();
                        const clientSecret = document.getElementById('terraform-client-secret').textContent.trim();
                        const tenantId = document.getElementById('terraform-tenant-id').textContent.trim();
                        const subId = document.getElementById('terraform-sub-id').textContent.trim();
                        
                        const envContent = `ARM_CLIENT_ID=${{clientId}}
ARM_CLIENT_SECRET=${{clientSecret}}
ARM_TENANT_ID=${{tenantId}}
ARM_SUBSCRIPTION_ID=${{subId}}`;
                        
                        const blob = new Blob([envContent], {{ type: 'text/plain' }});
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.setAttribute('href', url);
                        a.setAttribute('download', 'terraform.env');
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(url);
                    }}
                </script>
            </head>
            <body>
                <div class="top-bar">
                    <div class="wrap">
                        Your Cloud Classroom is Ready!
                    </div>
                </div>
                
                <div class="container">
                    <h1 class="section-title">Welcome to Testus Patronus</h1>
                    
                    <div class="credentials-section">
                        <div class="card individual-credentials">
                            <h2>Your Azure Credentials</h2>
                            <div class="credential-item">
                                <strong>Username</strong>
                                <div class="credential-value">
                                    <span class="credential-text">{credentials['username']}</span>
                                    <button class="copy-button" id="copyUsername" 
                                        onclick="copyToClipboard('{credentials['username']}', 'copyUsername')">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="credential-item">
                                <strong>Password</strong>
                                <div class="credential-value">
                                    <span class="credential-text">{credentials['password']}</span>
                                    <button class="copy-button" id="copyPassword" 
                                        onclick="copyToClipboard('{credentials['password']}', 'copyPassword')">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </div>
                            </div>
                            <a href="https://portal.azure.com" target="_blank" class="azure-portal-button">
                                <i class="fas fa-external-link-alt"></i> Go to Azure Portal
                            </a>
                        </div>

                        <div class="card terraform-credentials">
                            <h2>Terraform Credentials</h2>
                            <div class="credential-item">
                                <strong>Client ID</strong>
                                <div class="credential-value">
                                    <span class="credential-text" id="terraform-client-id">
                                        {credentials['terraform']['arm_client_id']}
                                    </span>
                                    <button class="copy-button" id="copyClientId" 
                                        onclick="copyToClipboard('{credentials['terraform']['arm_client_id']}', 'copyClientId')">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="credential-item">
                                <strong>Client Secret</strong>
                                <div class="credential-value">
                                    <span class="credential-text" id="terraform-client-secret">
                                        {credentials['terraform']['arm_client_secret']}
                                    </span>
                                    <button class="copy-button" id="copyClientSecret" 
                                        onclick="copyToClipboard('{credentials['terraform']['arm_client_secret']}', 'copyClientSecret')">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="credential-item">
                                <strong>Tenant ID</strong>
                                <div class="credential-value">
                                    <span class="credential-text" id="terraform-tenant-id">
                                        {credentials['terraform']['arm_tenant_id']}
                                    </span>
                                    <button class="copy-button" id="copyTenantId" 
                                        onclick="copyToClipboard('{credentials['terraform']['arm_tenant_id']}', 'copyTenantId')">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="credential-item">
                                <strong>Subscription ID</strong>
                                <div class="credential-value">
                                    <span class="credential-text" id="terraform-sub-id">
                                        {credentials['terraform']['arm_subscription_id']}
                                    </span>
                                    <button class="copy-button" id="copySubId" 
                                        onclick="copyToClipboard('{credentials['terraform']['arm_subscription_id']}', 'copySubId')">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div class="terraform-instructions-container">
                            <div class="terraform-instructions">
                                <h3>How to use these credentials</h3>
                                <ol>
                                    <li>Download the environment file</li>
                                    <li>Load the environment variables:
                                        <pre>source terraform.env</pre>
                                    </li>
                                    <li>Run Terraform commands:
                                        <pre>terraform init
terraform plan
terraform apply</pre>
                                    </li>
                                </ol>
                                <p class="note">Note: These Terraform credentials are shared with your classmates. All resources will be created under the same service principal.</p>

                                <div class="expiry-warning">
                                    <p>⚠️ These credentials will expire on: {credentials['terraform'].get('expiry_date', 'N/A')}</p>
                                    <p>Please get new credentials before the expiration date.</p>
                                </div>
                            </div>
                            
                            <button onclick="downloadTerraformEnv()" class="download-button">
                                Download Terraform Environment File
                            </button>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """,
            status_code=200,
            mimetype="text/html"
        )

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Cloud Classroom - Error</title>
                <style>
                    :root {{
                        --pink: #f452cb;
                        --background-purple: #3f0383;
                        --yellow: #ffd101;
                        --dark-blue: #1B1464;
                        --white: #FFFFFF;
                    }}
                    
                    html {{
                        font-size: 62.5%;
                    }}
                    
                    body {{
                        font-family: 'Open Sans', sans-serif;
                        font-size: 2.1rem;
                        margin: 0;
                        padding-top: 80px;
                        background-color: var(--background-purple);
                        color: var(--white);
                    }}

                    .container {{
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 2rem;
                        text-align: center;
                    }}

                    .error-card {{
                        background: var(--white);
                        border-radius: 15px;
                        padding: 3rem;
                        margin-top: 4rem;
                        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                        border: 3px solid var(--pink);
                    }}

                    .error-title {{
                        color: var(--pink);
                        font-size: 3rem;
                        font-weight: 700;
                        margin-bottom: 2rem;
                    }}

                    .error-message {{
                        color: var(--background-purple);
                        font-size: 2rem;
                        margin-bottom: 3rem;
                    }}

                    .action-button {{
                        display: inline-block;
                        background-color: var(--yellow);
                        color: var(--background-purple);
                        padding: 1.5rem 3rem;
                        text-decoration: none;
                        border-radius: 50px;
                        transition: all 0.3s ease;
                        font-weight: 700;
                        font-size: 1.8rem;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                        border: none;
                        cursor: pointer;
                    }}

                    .action-button:hover {{
                        background-color: var(--pink);
                        color: var(--white);
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-card">
                        <h1 class="error-title">Oops! Something went wrong</h1>
                        <p class="error-message">
                            An error occurred while creating your user account.<br>
                            Please try again later.
                        </p>
                        <a href="javascript:window.location.reload()" class="action-button">
                            Try Again
                        </a>
                    </div>
                </div>
            </body>
            </html>
            """,
            status_code=500,
            mimetype="text/html"
        )