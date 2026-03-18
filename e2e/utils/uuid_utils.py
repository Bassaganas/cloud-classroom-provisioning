"""UUID and unique identifier utilities for E2E tests."""
import uuid

_test_uuid = None

def get_test_uuid():
    """Get or generate a unique test UUID for the session."""
    global _test_uuid
    if _test_uuid is None:
        _test_uuid = str(uuid.uuid4())[:8]
    return _test_uuid

def get_resource_name(resource_type):
    """Generate a unique resource name with test UUID."""
    return f"e2e-tests-{resource_type}-{get_test_uuid()}"

def get_workshop_name():
    """Get E2E test workshop name."""
    return get_resource_name('workshop')

def get_session_name():
    """Get E2E test session name."""
    return get_resource_name('session')
