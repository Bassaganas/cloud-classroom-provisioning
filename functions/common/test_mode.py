"""
Test mode initialization for classroom_instance_manager.

When TEST_MODE=true is set in environment, this module activates moto mocks
for all AWS services, allowing the Lambda code to run without creating real
AWS infrastructure.

Usage:
    export TEST_MODE=true
    export AWS_DEFAULT_REGION=eu-west-1
    python3 -c "from functions.common import test_mode; test_mode.init_test_mode()"
    # Then import and use classroom_instance_manager as normal
"""

import os
import sys
from moto import mock_ec2, mock_dynamodb, mock_secretsmanager, mock_ssm

# Global references to keep decorators active
_mocked_services = {}

def init_test_mode():
    """Initialize moto mocks for all AWS services used by classroom_instance_manager"""
    
    if not os.environ.get('TEST_MODE', 'false').lower() == 'true':
        return False
    
    print("[TEST MODE] Initializing AWS service mocks via moto...")
    
    # Start all moto mocks
    _mocked_services['ec2'] = mock_ec2()
    _mocked_services['dynamodb'] = mock_dynamodb()
    _mocked_services['secretsmanager'] = mock_secretsmanager()
    _mocked_services['ssm'] = mock_ssm()
    
    # Start each mock
    for service_name, mock_service in _mocked_services.items():
        mock_service.start()
        print(f"[TEST MODE] ✓ Started {service_name} mock")
    
    # Set AWS credentials for moto (required even though they're fake)
    os.environ.setdefault('AWS_ACCESS_KEY_ID', 'testing')
    os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
    os.environ.setdefault('AWS_SECURITY_TOKEN', 'testing')
    os.environ.setdefault('AWS_SESSION_TOKEN', 'testing')
    os.environ.setdefault('AWS_DEFAULT_REGION', 'eu-west-1')
    
    print("[TEST MODE] ✓ All AWS services mocked. Backend will not access real AWS.")
    return True

def cleanup_test_mode():
    """Stop all moto mocks"""
    for service_name, mock_service in _mocked_services.items():
        mock_service.stop()
        print(f"[TEST MODE] Stopped {service_name} mock")
    _mocked_services.clear()

def is_test_mode():
    """Check if test mode is enabled"""
    return os.environ.get('TEST_MODE', 'false').lower() == 'true'

# Auto-initialize if TEST_MODE is set
if is_test_mode():
    init_test_mode()
