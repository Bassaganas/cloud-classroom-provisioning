# Cloud Classroom Provisioning

This project provides infrastructure and automation for managing cloud classroom environments in both AWS and Azure. It includes user management, resource provisioning, and cleanup scripts.

## Development Environment Setup

### Option 1: Using GitHub Codespaces (Recommended)

GitHub Codespaces provides a pre-configured development environment in the cloud.

1. Navigate to the repository on GitHub
2. Click the green "Code" button
3. Select "Create codespace on main"
4. Wait for the environment to be created

The Codespace includes:
- Python 3.9+
- AWS CLI
- Azure CLI
- Terraform
- Virtual environment management
- All required VS Code extensions

### Option 2: Using Dev Containers (Alternative)

This project includes a `.devcontainer` configuration that provides a consistent development environment.

1. Install prerequisites:
   - [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - [Visual Studio Code](https://code.visualstudio.com/)
   - [Remote - Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

2. Open the project in VS Code:
   ```bash
   code .
   ```

3. When prompted, click "Reopen in Container" or use the command palette (F1) and select "Remote-Containers: Reopen in Container"

The dev container includes:
- Python 3.9+
- AWS CLI
- Azure CLI
- Terraform
- Virtual environment management

### Option 3: Local Setup

#### 1. Install Python and Virtual Environment

**macOS (using Homebrew)**:
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python

# Install virtualenv
pip3 install virtualenv
```

**Windows**:
```bash
# Install Python from https://www.python.org/downloads/
# During installation, check "Add Python to PATH"

# Install virtualenv
pip install virtualenv
```

#### 2. Install AWS CLI

**macOS**:
```bash
brew install awscli
```

**Windows**:
```bash
# Download and run the MSI installer from:
# https://awscli.amazonaws.com/AWSCLIV2.msi
```

#### 3. Install Azure CLI

**macOS**:
```bash
brew install azure-cli
```

**Windows**:
```bash
# Download and run the MSI installer from:
# https://aka.ms/installazurecliwindows
```

#### 4. Install Terraform

**macOS**:
```bash
brew install terraform
```

**Windows**:
```bash
# Download from https://www.terraform.io/downloads.html
# Extract and add to PATH
```

## Authentication Setup

### AWS Authentication

1. Configure AWS credentials:
   ```bash
   aws configure
   ```
   You'll need:
   - AWS Access Key ID
   - AWS Secret Access Key
   - Default region (e.g., us-east-1)
   - Default output format (json)

2. Or use environment variables:
   ```bash
   export AWS_ACCESS_KEY_ID="your_access_key"
   export AWS_SECRET_ACCESS_KEY="your_secret_key"
   export AWS_DEFAULT_REGION="your_region"
   ```

### Azure Authentication

1. Login to Azure:
   ```bash
   az login
   ```
   This will open a browser window for authentication.

2. Set subscription:
   ```bash
   az account set --subscription "your-subscription-id"
   ```

## Project Structure

```
.
├── iac/                    # Infrastructure as Code
│   ├── aws/               # AWS infrastructure
│   │   └── iam/          # IAM policies and roles
│   └── azure/            # Azure infrastructure
├── functions/             # Cloud functions
│   ├── aws/              # AWS Lambda functions
│   └── azure/            # Azure Functions
├── scripts/              # Utility scripts
│   ├── cleanup_aws_users.sh
│   └── cleanup_azure_users.sh
└── README.md
```

## User Management

### AWS Users

The system creates two types of users:
1. Conference Users (`conference-user-*`)
   - Console access (username/password)
   - Limited permissions for resource management
   - Access to AWS Management Console

2. Service Users (`service-conference-user-*`)
   - Programmatic access (access key/secret key)
   - Permissions for ETL execution
   - Used for automated deployments

### Azure Users

The system creates:
1. Conference Users (`conference-user-*`)
   - Azure AD user with portal access
   - Limited permissions for resource management
   - Access to Azure Portal

2. Service Principals (`service-conference-user-*`)
   - Azure AD application with service principal
   - Permissions for ETL execution
   - Used for automated deployments

## Resource Cleanup

The project includes cleanup scripts for both AWS and Azure environments. See the [scripts documentation](scripts/README.md) for detailed information.

## Security Considerations

1. **Access Control**:
   - Use principle of least privilege
   - Regular rotation of credentials
   - Audit logging enabled

2. **Resource Protection**:
   - Resource tagging
   - Resource locks where appropriate
   - Backup strategies

3. **Monitoring**:
   - CloudWatch/Azure Monitor alerts
   - Cost monitoring
   - Usage tracking

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please:
1. Check the documentation
2. Review existing issues
3. Open a new issue with detailed information
4. Contact the maintainers 