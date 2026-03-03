#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_DIR="$ROOT_DIR/tests"
BACKEND_DIR="$ROOT_DIR/sut/backend"
VENV_DIR="$ROOT_DIR/.venv"

export PYTHONUNBUFFERED=1

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Runs Fellowship SUT test suite in phases:
  1) API + unit (+ non-UI pytest tests)
  2) UI pytest tests in headed mode (Playwright)

Options:
  --setup               Create venv and install test deps + playwright chromium
  --start-backend       Start backend automatically in background
  --base-url URL        Base URL for UI tests (default: https://localhost)
  --keep-backend        Do not stop backend started by this script
  --api-unit-only       Run only API/unit/non-UI tests
  --ui-only             Run only UI tests (headed)
  -h, --help            Show this help
EOF
}

SETUP=0
START_BACKEND=0
KEEP_BACKEND=0
API_UNIT_ONLY=0
UI_ONLY=0
BASE_URL="https://localhost"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup) SETUP=1; shift ;;
    --start-backend) START_BACKEND=1; shift ;;
    --keep-backend) KEEP_BACKEND=1; shift ;;
    --api-unit-only) API_UNIT_ONLY=1; shift ;;
    --ui-only) UI_ONLY=1; shift ;;
    --base-url)
      BASE_URL="${2:-}"
      [[ -n "$BASE_URL" ]] || { echo "--base-url requires a value"; exit 2; }
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 2 ;;
  esac
done

if [[ "$API_UNIT_ONLY" -eq 1 && "$UI_ONLY" -eq 1 ]]; then
  echo "Cannot combine --api-unit-only and --ui-only"
  exit 2
fi

cd "$ROOT_DIR"

if [[ "$SETUP" -eq 1 ]]; then
  echo "[setup] creating virtual environment in $VENV_DIR"
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/pip" install -r "$TESTS_DIR/requirements.txt"
  if [[ -x "$VENV_DIR/bin/playwright" ]]; then
    "$VENV_DIR/bin/playwright" install chromium
  else
    "$VENV_DIR/bin/pip" install playwright
    "$VENV_DIR/bin/playwright" install chromium
  fi
fi

[[ -x "$VENV_DIR/bin/python" ]] || { echo "Virtual env not found at $VENV_DIR"; exit 1; }
[[ -x "$VENV_DIR/bin/pytest" ]] || { echo "pytest not found in $VENV_DIR"; exit 1; }

PYTHON="$VENV_DIR/bin/python"
PYTEST="$VENV_DIR/bin/pytest"

BACKEND_PID=""
cleanup() {
  if [[ -n "$BACKEND_PID" && "$KEEP_BACKEND" -eq 0 ]]; then
    echo "[cleanup] stopping backend (pid=$BACKEND_PID)"
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "$START_BACKEND" -eq 1 ]]; then
  echo "[backend] starting backend from $BACKEND_DIR"
  (
    cd "$BACKEND_DIR"
    "$PYTHON" app.py
  ) >/tmp/fellowship_backend.log 2>&1 &
  BACKEND_PID=$!
  echo "[backend] pid=$BACKEND_PID"
  echo "[backend] waiting for server..."
  sleep 4
fi

export BASE_URL="$BASE_URL"
echo "[info] ROOT_DIR=$ROOT_DIR"
echo "[info] BASE_URL=$BASE_URL"

if [[ "$UI_ONLY" -eq 0 ]]; then
  echo "[run] API + unit + non-UI pytest tests"
  "$PYTEST" -v "$TESTS_DIR" -m "not ui" \
    --ignore "$TESTS_DIR/test_bargaining_market_playwright.py" \
    --ignore "$TESTS_DIR/test_bargaining_specification.py" \
    --ignore "$TESTS_DIR/test_api.py" \
    --disable-warnings
fi

if [[ "$API_UNIT_ONLY" -eq 0 ]]; then
  echo "[run] UI tests in headed mode"
  "$PYTEST" -v "$TESTS_DIR" -m "ui" --headed --browser chromium --disable-warnings
fi

echo "[done] test run completed"
