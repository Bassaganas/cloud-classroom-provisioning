"""Root conftest.py for pytest configuration."""
import os
import sys
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add paths
e2e_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(e2e_dir, 'tests'))
sys.path.insert(0, os.path.join(e2e_dir, 'utils'))
sys.path.insert(0, os.path.join(e2e_dir, 'features'))

# Import clients
from gitea_client import GiteaClient
from jenkins_client import JenkinsClient
from student_utils import StudentTestHelper


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "e2e: mark test as an e2e test")
    config.addinivalue_line("markers", "slow: slow test")
    config.addinivalue_line("markers", "instance: instance management test")
    config.addinivalue_line("markers", "admin: admin instance test")
    config.addinivalue_line("markers", "session: tutorial session test")
    config.addinivalue_line("markers", "landing: landing page test")
    config.addinivalue_line("markers", "multi_student: multi-student workflow tests")
    config.addinivalue_line("markers", "student_isolation: student resource isolation tests")
    config.addinivalue_line("markers", "jenkins_webhook: jenkins webhook integration tests")
    config.addinivalue_line("markers", "webhook_basic: basic webhook configuration tests")
    config.addinivalue_line("markers", "push_triggers_pipeline: webhook-triggered pipeline tests")
    config.addinivalue_line("markers", "pipeline_execution: pipeline execution tests")
    config.addinivalue_line("markers", "e2e_workflow: complete end-to-end workflow tests")
    config.addinivalue_line("markers", "instance_isolation: instance isolation tests")
    config.addinivalue_line("markers", "repo_isolation: repository isolation tests")
    config.addinivalue_line("markers", "naming_convention: naming convention tests")


# ===== Session Fixtures =====

@pytest.fixture(scope="session")
def test_environment():
    """Determine test environment configuration."""
    env_type = os.getenv("TEST_ENVIRONMENT", "deployed")
    return {
        "type": env_type,
        "ec2_manager_url": os.getenv(
            "EC2_MANAGER_URL",
            "https://ec2-management-dev.testingfantasy.com" if env_type == "deployed" else "http://localhost:3000"
        ),
        "gitea_url": os.getenv(
            "GITEA_URL",
            "https://gitea.fellowship.testingfantasy.com" if env_type == "deployed" else "http://localhost:3000"
        ),
        "jenkins_url": os.getenv(
            "JENKINS_URL",
            "https://jenkins.fellowship.testingfantasy.com" if env_type == "deployed" else "http://localhost:8080"
        ),
        "workshop_name": os.getenv("WORKSHOP_NAME", "fellowship"),
        "environment": os.getenv("ENVIRONMENT", "dev"),
        "region": os.getenv("AWS_REGION", "eu-west-1"),
    }


@pytest.fixture(scope="session")
def gitea_client():
    """Provide Gitea API client for tests."""
    client = GiteaClient()
    if not client.health_check():
        pytest.skip("Gitea service is not available")
    return client


@pytest.fixture(scope="session")
def jenkins_client():
    """Provide Jenkins API client for tests."""
    client = JenkinsClient()
    if not client.health_check():
        pytest.skip("Jenkins service is not available")
    return client


@pytest.fixture(scope="session")
def student_helper():
    """Provide student test helper for tests."""
    return StudentTestHelper()


# ===== Function-level Fixtures =====

@pytest.fixture
def aws_environment(test_environment):
    """Provide AWS environment configuration."""
    return {
        "workshop_name": test_environment["workshop_name"],
        "environment": test_environment["environment"],
        "region": test_environment["region"],
    }


@pytest.fixture
def test_context():
    """Provide test context with unique identifiers."""
    from uuid_utils import get_test_uuid
    return {
        "test_uuid": get_test_uuid(),
        "timestamp": __import__('time').time(),
    }
