"""BDD-style real-stack tests for CORS and login flow."""
import requests
import pytest
from pytest_bdd import given, scenarios, then, when

from tests.page_objects.dashboard_page import DashboardPage
from tests.page_objects.login_page import LoginPage


scenarios("features/cors_login_realstack.feature")


@given("the real Fellowship SUT stack is running via docker compose")
def real_stack_running(ensure_real_stack):
    """Ensure stack is up using session fixture."""


@given("the Caddy API endpoint allows CORS preflight from localhost 3000")
def caddy_preflight_allows_cors():
    response = requests.options(
        "http://localhost/api/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
        timeout=8,
    )

    assert response.status_code in {200, 204}
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    methods = response.headers.get("Access-Control-Allow-Methods", "")
    assert "POST" in methods


@when("I login through the Fellowship UI with valid credentials", target_fixture="logged_in_page")
def login_via_ui(page, base_url, test_credentials):
    login_page = LoginPage(page, base_url)
    login_page.login(test_credentials["username"], test_credentials["password"])
    login_page.wait_for_dashboard()
    return page


@then("I should land on the dashboard")
def should_land_on_dashboard(logged_in_page, base_url):
    assert "/dashboard" in logged_in_page.url
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.is_loaded()


@then("the authenticated session endpoint should return the current user")
def session_endpoint_returns_user(logged_in_page):
    response = logged_in_page.context.request.get("http://localhost/api/auth/me")
    assert response.status == 200
    payload = response.json()
    assert payload.get("username")
    assert payload.get("id")


@pytest.mark.realstack
@pytest.mark.bdd
@pytest.mark.cors
@pytest.mark.login
def test_realstack_bdd_marker_anchor():
    """Anchor test to make marker selection straightforward."""
    assert True
