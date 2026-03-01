"""Integration tests for NPC chat API endpoints."""
import os
import requests
import pytest


@pytest.fixture
def api_base_url() -> str:
    base_url = os.getenv('SUT_URL', 'http://localhost')
    return f"{base_url}/api"


def _login_session(api_base_url: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{api_base_url}/auth/login",
        json={
            'username': 'frodo_baggins',
            'password': 'fellowship123',
        },
    )
    assert response.status_code == 200
    return session


def test_chat_requires_auth(api_base_url: str):
    response = requests.post(f"{api_base_url}/chat/start", json={'character': 'gandalf'})
    assert response.status_code == 401


def test_chat_start_and_message_flow(api_base_url: str):
    session = _login_session(api_base_url)

    started = session.post(f"{api_base_url}/chat/start", json={'character': 'sam'})
    assert started.status_code == 200
    started_data = started.json()
    assert started_data['character'] == 'sam'
    assert 'opener' in started_data
    assert 'suggested_action' in started_data
    assert started_data['suggested_action']['goal_type'] in {
        'resolve_dark_magic',
        'finish_critical_in_progress',
        'assign_critical',
        'scout_map_hotspot',
        'advance_next_quest',
        'propose_side_quest',
    }
    assert 'target' in started_data['suggested_action']
    target = started_data['suggested_action']['target']
    assert target.get('route') in ['/quests', '/map', '/dashboard']
    if target.get('route') in ['/quests', '/map']:
        assert isinstance(target.get('query'), dict)
        assert len(target.get('query', {})) > 0

    replied = session.post(
        f"{api_base_url}/chat/message",
        json={'character': 'sam', 'message': 'What should I do first?'},
    )
    assert replied.status_code == 200
    replied_data = replied.json()
    assert replied_data['character'] == 'sam'
    assert 'message' in replied_data
    assert 'suggested_action' in replied_data
    assert len(replied_data['messages']) >= 3
    assert 'target' in replied_data['suggested_action']


def test_chat_proposes_side_quest_when_all_done(api_base_url: str):
    session = _login_session(api_base_url)

    quests_response = session.get(f"{api_base_url}/quests/")
    assert quests_response.status_code == 200
    quests = quests_response.json()
    assert len(quests) > 0

    for quest in quests:
        complete_response = session.put(f"{api_base_url}/quests/{quest['id']}/complete")
        assert complete_response.status_code == 200

    started = session.post(f"{api_base_url}/chat/start", json={'character': 'gandalf'})
    assert started.status_code == 200
    payload = started.json()

    assert payload['suggested_action']['goal_type'] == 'propose_side_quest'
    assert payload['suggested_action']['target']['route'] == '/quests'
    query = payload['suggested_action']['target'].get('query', {})
    assert query.get('propose') == 1
    assert query.get('seedTitle')
    assert query.get('seedDescription')
    assert query.get('seedType')
    assert query.get('seedPriority')


def test_chat_session_and_reset(api_base_url: str):
    session = _login_session(api_base_url)
    session.post(f"{api_base_url}/chat/start", json={'character': 'frodo'})

    session_data = session.get(f"{api_base_url}/chat/session?character=frodo")
    assert session_data.status_code == 200
    payload = session_data.json()
    assert payload['character'] == 'frodo'
    assert isinstance(payload['messages'], list)

    reset = session.post(f"{api_base_url}/chat/reset", json={'character': 'frodo'})
    assert reset.status_code == 200
    reset_payload = reset.json()
    assert reset_payload['reset'] is True
    assert reset_payload['messages'] == []
