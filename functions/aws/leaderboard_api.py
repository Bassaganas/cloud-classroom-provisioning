"""
leaderboard_api.py — API Gateway Lambda for leaderboard endpoints.

Exposes read-only REST endpoints backed by the DynamoDB leaderboard table.
"""
import json
import logging
import os
from decimal import Decimal
from typing import Optional

from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)


REALM_STOPS = [
    {"name": "The Shire", "x_pct": 18.0, "y_pct": 62.0},
    {"name": "Bree", "x_pct": 31.0, "y_pct": 56.0},
    {"name": "Rivendell", "x_pct": 43.0, "y_pct": 50.0},
    {"name": "Moria", "x_pct": 50.0, "y_pct": 59.0},
    {"name": "Lothlorien", "x_pct": 58.0, "y_pct": 53.0},
    {"name": "Mount Doom", "x_pct": 82.0, "y_pct": 74.0},
]


def _get_dynamodb():
    import boto3

    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-west-1"))


def _get_table():
    table_name = os.environ.get("LEADERBOARD_TABLE")
    if not table_name:
        raise RuntimeError("LEADERBOARD_TABLE not configured")
    return _get_dynamodb().Table(table_name)


def _to_json_safe(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_safe(item) for key, item in value.items()}
    return value


def _response(status_code: int, payload: dict, content_type: str = "application/json") -> dict:
    body = payload if content_type == "application/json" else payload
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body) if content_type == "application/json" else body,
    }


def _normalize_path(event: dict) -> str:
    raw_path = event.get("rawPath") or event.get("path") or "/"
    parts = [part for part in raw_path.split("/") if part]
    stage_name = os.environ.get("ENVIRONMENT", "")

    if parts and stage_name and parts[0] == stage_name:
        parts = parts[1:]
    if parts and parts[0] == "api":
        parts = parts[1:]

    if not parts:
        return "/"
    return "/" + "/".join(parts)


def _get_method(event: dict) -> str:
    return (event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "GET").upper()


def _map_progress_fields(completed_exercises: list) -> dict:
    progress_count = max(0, min(len(completed_exercises), 5))
    stop = REALM_STOPS[progress_count]
    return {
        "current_realm": stop["name"],
        "map_position": {
            "x": stop["x_pct"],
            "y": stop["y_pct"],
            "unit": "percent",
            "checkpoint": progress_count,
        },
    }


def _list_entries(table) -> list[dict]:
    items = []
    scan_kwargs = {
        "FilterExpression": Attr("pk").begins_with("STUDENT#") & Attr("sk").eq("profile")
    }

    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    entries = []
    sorted_items = sorted(
        items,
        key=lambda item: (-int(item.get("total_points", 0)), str(item.get("student_id", ""))),
    )
    for index, item in enumerate(sorted_items, start=1):
        completed_exercises = _to_json_safe(item.get("completed_exercises", []))
        map_progress = _map_progress_fields(completed_exercises)
        entries.append(
            {
                "rank": index,
                "student_id": item.get("student_id", item.get("pk", "").replace("STUDENT#", "")),
                "total_points": int(_to_json_safe(item.get("total_points", 0))),
                "completed_exercises": completed_exercises,
                "progress": f"{len(completed_exercises)}/5",
                "last_updated": item.get("last_updated"),
                **map_progress,
            }
        )
    return entries


def _get_student(table, student_id: str) -> Optional[dict]:
    response = table.get_item(Key={"pk": f"STUDENT#{student_id}", "sk": "profile"})
    item = response.get("Item")
    if not item:
        return None

    completed_exercises = _to_json_safe(item.get("completed_exercises", []))
    map_progress = _map_progress_fields(completed_exercises)
    return {
        "student_id": student_id,
        "total_points": int(_to_json_safe(item.get("total_points", 0))),
        "completed_exercises": completed_exercises,
        "progress": f"{len(completed_exercises)}/5",
        "last_updated": item.get("last_updated"),
        **map_progress,
    }


def _swagger_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Leaderboard API",
            "version": "1.0.0",
            "description": "Read-only leaderboard API for workshop progress rankings.",
        },
        "paths": {
            "/api/health": {
                "get": {
                    "summary": "Health check",
                    "responses": {"200": {"description": "Service healthy"}},
                }
            },
            "/api/leaderboard": {
                "get": {
                    "summary": "Get leaderboard",
                    "responses": {"200": {"description": "Leaderboard snapshot"}},
                }
            },
            "/api/student/{student_id}": {
                "get": {
                    "summary": "Get one student progress",
                    "parameters": [
                        {
                            "name": "student_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Student progress"},
                        "404": {"description": "Student not found"},
                    },
                }
            },
        },
    }


def lambda_handler(event, context):
    try:
        method = _get_method(event)
        path = _normalize_path(event)
        logger.info("Leaderboard API request: method=%s path=%s", method, path)

        if method != "GET":
            return _response(405, {"error": "Method not allowed"})

        if path == "/swagger.json":
            return _response(200, _swagger_spec())

        if path in {"/", "/health"}:
            return _response(200, {"status": "ok", "service": "leaderboard-api"})

        table = _get_table()

        if path == "/leaderboard":
            entries = _list_entries(table)
            timestamp = entries[0].get("last_updated") if entries else None
            return _response(200, {"timestamp": timestamp, "entries": entries})

        if path.startswith("/student/"):
            student_id = path.split("/", 2)[2]
            student = _get_student(table, student_id)
            if not student:
                return _response(404, {"error": "Student not found"})

            entries = _list_entries(table)
            student["rank"] = next((entry["rank"] for entry in entries if entry["student_id"] == student_id), None)
            student["timestamp"] = student.get("last_updated")
            return _response(200, student)

        return _response(404, {"error": "Not found"})
    except Exception as exc:
        logger.error("Leaderboard API request failed: %s", exc, exc_info=True)
        return _response(500, {"error": "Internal server error"})