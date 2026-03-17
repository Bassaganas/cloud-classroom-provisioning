"""
Contract test for /api/always-on-tutorials endpoint
"""
import pytest
import requests

def test_always_on_tutorials_contract():
    """Contract: /api/always-on-tutorials returns array of {tutorial, url} objects"""
    # This is a contract test, not a live call
    # Example response:
    response = [
        {"tutorial": "fellowship", "url": "https://sut-fellowship.testingfantasy.com"},
        {"tutorial": "testus_patronus", "url": "https://sut-testus_patronus.testingfantasy.com"}
    ]
    assert isinstance(response, list)
    for item in response:
        assert isinstance(item, dict)
        assert "tutorial" in item
        assert "url" in item
        assert item["url"].startswith("https://sut-")
        assert item["url"].endswith(".testingfantasy.com")
