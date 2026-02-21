"""Tests for API endpoints."""
import pytest
import requests
import os

@pytest.fixture
def api_base_url() -> str:
    """Base URL for API."""
    base_url = os.getenv('SUT_URL', 'http://localhost')
    return f"{base_url}/api"

def test_health_endpoint(api_base_url: str):
    """Test health check endpoint."""
    response = requests.get(f"{api_base_url}/health")
    assert response.status_code == 200, f"Health endpoint should return 200, got {response.status_code}"
    data = response.json()
    assert data['status'] == 'healthy', "Health status should be 'healthy'"

def test_swagger_ui_accessible(api_base_url: str):
    """Test that Swagger UI is accessible."""
    base_url = api_base_url.replace('/api', '')
    response = requests.get(f"{base_url}/api/swagger/")
    assert response.status_code == 200, f"Swagger UI should be accessible, got {response.status_code}"

def test_get_quests_endpoint(api_base_url: str):
    """Test GET /quests endpoint."""
    response = requests.get(f"{api_base_url}/quests")
    assert response.status_code == 200, f"Get quests should return 200, got {response.status_code}"
    data = response.json()
    assert isinstance(data, list), "Quests endpoint should return a list"

def test_get_members_endpoint(api_base_url: str):
    """Test GET /members endpoint."""
    response = requests.get(f"{api_base_url}/members")
    assert response.status_code == 200, f"Get members should return 200, got {response.status_code}"
    data = response.json()
    assert isinstance(data, list), "Members endpoint should return a list"
    assert len(data) > 0, "Should have at least one member"

def test_get_locations_endpoint(api_base_url: str):
    """Test GET /locations endpoint."""
    response = requests.get(f"{api_base_url}/locations")
    assert response.status_code == 200, f"Get locations should return 200, got {response.status_code}"
    data = response.json()
    assert isinstance(data, list), "Locations endpoint should return a list"
    assert len(data) > 0, "Should have at least one location"

def test_login_endpoint(api_base_url: str):
    """Test POST /auth/login endpoint."""
    response = requests.post(
        f"{api_base_url}/auth/login",
        json={
            'username': 'frodo_baggins',
            'password': 'fellowship123'
        }
    )
    assert response.status_code == 200, f"Login should return 200, got {response.status_code}"
    data = response.json()
    assert 'user' in data, "Login response should contain user"
    assert data['user']['username'] == 'frodo_baggins', "Should return correct user"

def test_login_endpoint_invalid_credentials(api_base_url: str):
    """Test POST /auth/login with invalid credentials."""
    response = requests.post(
        f"{api_base_url}/auth/login",
        json={
            'username': 'invalid_user',
            'password': 'wrong_password'
        }
    )
    assert response.status_code == 401, f"Invalid login should return 401, got {response.status_code}"

def test_get_quest_by_id(api_base_url: str):
    """Test GET /quests/{id} endpoint."""
    # First get all quests to find an ID
    response = requests.get(f"{api_base_url}/quests")
    assert response.status_code == 200
    quests = response.json()
    
    if len(quests) > 0:
        quest_id = quests[0]['id']
        response = requests.get(f"{api_base_url}/quests/{quest_id}")
        assert response.status_code == 200, f"Get quest by ID should return 200, got {response.status_code}"
        data = response.json()
        assert data['id'] == quest_id, "Should return the correct quest"
