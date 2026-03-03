"""Pytest configuration and fixtures for Playwright tests."""

import importlib
import os
import subprocess
import sys
import time
from pathlib import Path

# Suppress SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables from .env (default) or .env.dev if ENV_FILE is set
from dotenv import load_dotenv
env_file = os.getenv('ENV_FILE', None)
if env_file:
    load_dotenv(dotenv_path=env_file, override=True)
else:
    load_dotenv(override=True)

import pytest
import requests

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
_project_root_removed = False
if _PROJECT_ROOT in sys.path:
    sys.path.remove(_PROJECT_ROOT)
    _project_root_removed = True

_playwright_sync_api = importlib.import_module("playwright.sync_api")
sync_playwright = _playwright_sync_api.sync_playwright
Page = _playwright_sync_api.Page
Browser = _playwright_sync_api.Browser
BrowserContext = _playwright_sync_api.BrowserContext

if _project_root_removed:
    sys.path.insert(0, _PROJECT_ROOT)


def _run_compose_command(args: list[str]) -> None:
    root = Path(__file__).resolve().parent.parent
    compose_v2 = ["docker", "compose", *args]
    compose_v1 = ["docker-compose", *args]
    try:
        subprocess.run(compose_v2, cwd=root, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        subprocess.run(compose_v1, cwd=root, check=True)


def _wait_for_url(url: str, timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for service readiness at {url}")


@pytest.fixture(scope="session")
def ensure_real_stack():
    """Ensure real SUT stack is running via docker compose (no mocks)."""
    if os.getenv("FELLOWSHIP_USE_MOCKS", "false").lower() in {"1", "true", "yes"}:
        raise RuntimeError("Mocks are disabled for Fellowship real-stack tests")

    _run_compose_command(["up", "-d", "--build"])
    _wait_for_url("http://localhost/api/health")
    _wait_for_url("http://localhost/login")
    _wait_for_url("http://localhost:3000")
    yield

@pytest.fixture(scope="session")
def playwright():
    """Playwright instance (session-scoped)."""
    with sync_playwright() as p:
        yield p

@pytest.fixture(scope="session")
def browser(playwright):
    """Browser instance (session-scoped)."""
    import os
    browser = None
    launch_errors = []
    headless = os.getenv("HEADED", "").lower() != "true"  # Set HEADED=true to run headed mode
    launchers = [
        ("firefox", lambda: playwright.firefox.launch(headless=headless)),
        ("webkit", lambda: playwright.webkit.launch(headless=headless)),
        (
            "chromium",
            lambda: playwright.chromium.launch(
                headless=headless,
                args=["--disable-dev-shm-usage", "--disable-gpu", "--no-sandbox"],
            ),
        ),
    ]

    for name, launcher in launchers:
        try:
            browser = launcher()
            break
        except Exception as exc:  # pragma: no cover - fallback path
            launch_errors.append(f"{name}: {exc}")

    if browser is None:
        raise RuntimeError("Failed to launch Playwright browser. " + " | ".join(launch_errors))

    yield browser
    browser.close()

@pytest.fixture
def context(browser: Browser):
    """Browser context fixture with video recording."""
    video_dir = Path(__file__).resolve().parent.parent / "reports" / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(
        record_video_dir=str(video_dir),
        ignore_https_errors=True,
    )
    yield context
    context.close()

@pytest.fixture
def page(context: BrowserContext) -> Page:
    """Browser page fixture."""
    page = context.new_page()
    yield page
    page.close()

@pytest.fixture
def base_url() -> str:
    """Base URL for SUT."""
    return os.getenv('BASE_URL') or os.getenv('SUT_URL', 'http://localhost')


@pytest.fixture(autouse=True)
def _realstack_guard(request):
    """Run realstack tests only when explicitly enabled via RUN_REALSTACK=true."""
    if request.node.get_closest_marker("realstack"):
        if os.getenv("RUN_REALSTACK", "false").lower() not in {"1", "true", "yes"}:
            pytest.skip("realstack tests require RUN_REALSTACK=true")
        request.getfixturevalue("ensure_real_stack")

@pytest.fixture
def test_credentials():
    """Test user credentials."""
    return {
        'username': 'frodo_baggins',
        'password': 'fellowship123'
    }


@pytest.fixture(autouse=True)
def reset_db_for_test(base_url):
    """Reset database state before each test to ensure clean slate."""
    try:
        requests.post(f"{base_url}/api/shop/test-reset", timeout=5, verify=False)
    except requests.RequestException as e:
        # Database reset may not always be available, continue with test
        print(f"Warning: Could not reset test database: {e}")
    yield
