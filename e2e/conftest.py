"""Root conftest.py for pytest configuration."""
import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add paths
e2e_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(e2e_dir, 'tests'))
sys.path.insert(0, os.path.join(e2e_dir, 'utils'))
sys.path.insert(0, os.path.join(e2e_dir, 'features'))

def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "e2e: mark test as an e2e test")
    config.addinivalue_line("markers", "slow: slow test")
    config.addinivalue_line("markers", "instance: instance management test")
    config.addinivalue_line("markers", "admin: admin instance test")
    config.addinivalue_line("markers", "session: tutorial session test")
    config.addinivalue_line("markers", "landing: landing page test")
