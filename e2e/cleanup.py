"""Cleanup script to remove leftover E2E test resources."""
import logging
import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

from aws_helpers import cleanup_e2e_resources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run global cleanup."""
    logger.info("Starting E2E test cleanup...")
    cleanup_e2e_resources(prefix='e2e-tests-')
    logger.info("Cleanup completed successfully")

if __name__ == '__main__':
    main()
