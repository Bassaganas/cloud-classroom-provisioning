"""Tests for API endpoints."""
import pytest
import requests
import urllib3
import os

@pytest.fixture
def api_base_url() -> str:
    @pytest.fixture(autouse=True)
    def disable_ssl_warnings():
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    """Base URL for API."""
    base_url = os.getenv('SUT_URL', 'http://localhost')
    return f"{base_url}/api"

def test_health_endpoint(api_base_url: str):
    """Test health check endpoint."""
    response = requests.get(f"{api_base_url}/health")
        assert response.status_code == 200, f"Health endpoint should return 200, got {response.status_code}"
        response = requests.get(f"{api_base_url}/health", verify=False)
    data = response.json()
    assert data['status'] == 'healthy', "Health status should be 'healthy'"

def test_swagger_ui_accessible(api_base_url: str):
    """Test that Swagger UI is accessible."""
    base_url = api_base_url.replace('/api', '')
    response = requests.get(f"{base_url}/api/swagger/")
        assert response.status_code == 200, f"Swagger UI should be accessible, got {response.status_code}"
        response = requests.get(f"{base_url}/api/swagger/", verify=False)

def test_get_quests_endpoint(api_base_url: str):
    """Test GET /quests endpoint."""
    response = requests.get(f"{api_base_url}/quests/")
        assert response.status_code == 200, f"Get quests should return 200, got {response.status_code}"
        response = requests.get(f"{api_base_url}/quests/", verify=False)
    data = response.json()
    assert isinstance(data, list), "Quests endpoint should return a list"

def test_get_members_endpoint(api_base_url: str):
    """Test GET /members endpoint."""
    response = requests.get(f"{api_base_url}/members/")
        assert response.status_code == 200, f"Get members should return 200, got {response.status_code}"
        response = requests.get(f"{api_base_url}/members/", verify=False)
    data = response.json()
    assert isinstance(data, list), "Members endpoint should return a list"
    assert len(data) > 0, "Should have at least one member"

def test_get_locations_endpoint(api_base_url: str):
    """Test GET /locations endpoint."""
    response = requests.get(f"{api_base_url}/locations/")
        assert response.status_code == 200, f"Get locations should return 200, got {response.status_code}"
        response = requests.get(f"{api_base_url}/locations/", verify=False)
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
        response = requests.post(
            f"{api_base_url}/auth/login",
            json={
                'username': 'frodo_baggins',
                'password': 'fellowship123'
            },
            verify=False
        )
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
        response = requests.post(
            f"{api_base_url}/auth/login",
            json={
                'username': 'invalid_user',
                'password': 'wrong_password'
            },
            verify=False
        )

def test_get_quest_by_id(api_base_url: str):
    """Test GET /quests/{id} endpoint."""
    # First get all quests to find an ID
    response = requests.get(f"{api_base_url}/quests/")
        assert response.status_code == 200
        response = requests.get(f"{api_base_url}/quests/", verify=False)
    quests = response.json()
    
    if len(quests) > 0:
        quest_id = quests[0]['id']
        response = requests.get(f"{api_base_url}/quests/{quest_id}")
        assert response.status_code == 200, f"Get quest by ID should return 200, got {response.status_code}"
        data = response.json()
        assert data['id'] == quest_id, "Should return the correct quest"

def test_quest_has_new_fields(api_base_url: str):
    """Test that quests include new LOTR fields."""
    response = requests.get(f"{api_base_url}/quests/")
        assert response.status_code == 200
        response = requests.get(f"{api_base_url}/quests/", verify=False)
    quests = response.json()
    
    if len(quests) > 0:
        quest = quests[0]
        # Check for new fields (may be None for existing quests)
        assert 'quest_type' in quest, "Quest should have quest_type field"
        assert 'priority' in quest, "Quest should have priority field"
        assert 'is_dark_magic' in quest, "Quest should have is_dark_magic field"
        assert 'character_quote' in quest, "Quest should have character_quote field"
        assert 'completed_at' in quest, "Quest should have completed_at field"

def test_filter_quests_by_status(api_base_url: str):
    """Test filtering quests by status."""
    response = requests.get(f"{api_base_url}/quests/?status=it_is_done")
        assert response.status_code == 200
        response = requests.get(f"{api_base_url}/quests/?status=it_is_done", verify=False)
    quests = response.json()
    assert isinstance(quests, list), "Should return a list"
    # All returned quests should have the filtered status
    for quest in quests:
        assert quest['status'] in ['it_is_done', 'completed'], f"Quest {quest['id']} should have status it_is_done or completed"

def test_filter_quests_by_type(api_base_url: str):
    """Test filtering quests by quest type."""
    response = requests.get(f"{api_base_url}/quests/?quest_type=The Journey")
        assert response.status_code == 200
        response = requests.get(f"{api_base_url}/quests/?quest_type=The Journey", verify=False)
    quests = response.json()
    assert isinstance(quests, list), "Should return a list"
    for quest in quests:
        assert quest.get('quest_type') == 'The Journey', f"Quest {quest['id']} should be of type The Journey"

def test_filter_quests_by_priority(api_base_url: str):
    """Test filtering quests by priority."""
    response = requests.get(f"{api_base_url}/quests/?priority=Critical")
        assert response.status_code == 200
        response = requests.get(f"{api_base_url}/quests/?priority=Critical", verify=False)
    quests = response.json()
    assert isinstance(quests, list), "Should return a list"
    for quest in quests:
        assert quest.get('priority') == 'Critical', f"Quest {quest['id']} should have Critical priority"

def test_filter_dark_magic_quests(api_base_url: str):
    """Test filtering dark magic quests."""
    response = requests.get(f"{api_base_url}/quests/?dark_magic=true")
        assert response.status_code == 200
        response = requests.get(f"{api_base_url}/quests/?dark_magic=true", verify=False)
    quests = response.json()
    assert isinstance(quests, list), "Should return a list"
    for quest in quests:
        assert quest.get('is_dark_magic') is True, f"Quest {quest['id']} should be a dark magic quest"

def test_complete_quest_endpoint(api_base_url: str):
    """Test PUT /quests/{id}/complete endpoint."""
    # First login to get session
    session = requests.Session()
    login_response = session.post(
        f"{api_base_url}/auth/login",
        json={
            'username': 'frodo_baggins',
            'password': 'fellowship123'
        }
    )
    assert login_response.status_code == 200, "Login should succeed"
    
    # Get a quest that's not completed
    response = session.get(f"{api_base_url}/quests/")
        assert response.status_code == 200
        response = session.get(f"{api_base_url}/quests/", verify=False)
    quests = response.json()
    
    # Find a quest that's not completed
    incomplete_quest = None
    for quest in quests:
        if quest['status'] not in ['it_is_done', 'completed']:
            incomplete_quest = quest
            break
    
    if incomplete_quest:
        quest_id = incomplete_quest['id']
        # Complete the quest
        complete_response = session.put(f"{api_base_url}/quests/{quest_id}/complete")
        assert complete_response.status_code == 200, f"Complete quest should return 200, got {complete_response.status_code}"
        data = complete_response.json()
        assert data['status'] in ['it_is_done', 'completed'], "Quest status should be it_is_done or completed"
        assert 'completed_at' in data, "Quest should have completed_at timestamp"
        assert 'message' in data, "Response should include completion message"

def test_create_quest_with_new_fields(api_base_url: str):
    """Test creating a quest with new LOTR fields."""
    # Login first
    session = requests.Session()
    login_response = session.post(
        f"{api_base_url}/auth/login",
        json={
            'username': 'frodo_baggins',
            'password': 'fellowship123'
        }
    )
    assert login_response.status_code == 200
    
    # Create quest with new fields
    quest_data = {
        'title': 'Test Quest',
        'description': 'A test quest for LOTR transformation',
        'status': 'not_yet_begun',
        'quest_type': 'The Journey',
        'priority': 'Important',
        'is_dark_magic': False,
        'character_quote': 'Test quote'
    }
    
    response = session.post(f"{api_base_url}/quests/", json=quest_data)
        assert response.status_code == 201, f"Create quest should return 201, got {response.status_code}"
        response = session.post(f"{api_base_url}/quests/", json=quest_data, verify=False)
    data = response.json()
    assert data['title'] == 'Test Quest', "Should return created quest"
    assert data['quest_type'] == 'The Journey', "Should have quest_type"
    assert data['priority'] == 'Important', "Should have priority"
    assert data['is_dark_magic'] is False, "Should have is_dark_magic"
    assert data['character_quote'] == 'Test quote', "Should have character_quote"
