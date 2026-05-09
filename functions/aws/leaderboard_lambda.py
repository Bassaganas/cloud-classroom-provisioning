"""
leaderboard_lambda.py - AWS Lambda handler for SQS -> DynamoDB leaderboard.

This is the production consumer for student progress events.

Environment variables:
  LEADERBOARD_TABLE   DynamoDB table name (required)
  AWS_REGION          AWS region (injected by Lambda runtime)
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)


EXERCISE_POINTS = {
    "ex1": 10,
    "ex2": 15,
    "ex3": 20,
    "ex4": 25,
    "ex5": 30,
    "ex6": 35,
    "ex7": 40,
}

BONUS_MULTIPLIERS = {
    1: 1.5,
    2: 1.3,
    3: 1.2,
}


def get_bonus_multiplier(completion_order: int) -> float:
    """Return score multiplier by completion order for an exercise."""
    return BONUS_MULTIPLIERS.get(completion_order, 1.0)


def calculate_awarded_points(base_points: int, completion_order: int) -> int:
    """Calculate awarded points with completion-order bonus (half-up rounding)."""
    multiplier = get_bonus_multiplier(completion_order)
    return int((base_points * multiplier) + 0.5)


def _get_dynamodb():
    """Return a DynamoDB resource (cached between warm invocations)."""
    import boto3

    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-west-1"))


def _process_event(record: dict, table) -> dict:
    """Process one SQS record and return the processing outcome."""
    body = json.loads(record["body"])
    student_id = body["student_id"]
    exercise_id = body["exercise_id"]
    status = body["status"]
    execution_context = body.get("execution_context", "unknown")
    timestamp = body.get("timestamp", datetime.now(timezone.utc).isoformat())

    logger.info(
        "Processing event: student=%s exercise=%s status=%s context=%s",
        student_id,
        exercise_id,
        status,
        execution_context,
    )

    if status != "completed":
        logger.info("Skipping non-completion event: %s", status)
        return {"student_id": student_id, "exercise_id": exercise_id, "status": status, "action": "skipped"}

    if execution_context == "solution":
        logger.info("Skipping solution completion: %s/%s", student_id, exercise_id)
        return {
            "student_id": student_id,
            "exercise_id": exercise_id,
            "status": status,
            "action": "filtered_solution",
        }

    base_points = EXERCISE_POINTS.get(exercise_id, 0)

    try:
        # Reserve completion record first so duplicates are rejected early.
        table.put_item(
            Item={
                "pk": f"COMPLETION#{student_id}#{exercise_id}",
                "sk": "v1",
                "student_id": student_id,
                "exercise_id": exercise_id,
                "points": 0,
                "completion_order": 0,
                "bonus_multiplier": 1.0,
                "execution_context": execution_context,
                "completed_at": timestamp,
            },
            ConditionExpression="attribute_not_exists(pk)",
        )

        # Atomic per-exercise counter ensures deterministic completion ranking.
        counter_resp = table.update_item(
            Key={"pk": f"EXERCISE#{exercise_id}", "sk": "counter"},
            UpdateExpression="ADD completion_count :one SET last_updated = :ts",
            ExpressionAttributeValues={
                ":one": 1,
                ":ts": timestamp,
            },
            ReturnValues="UPDATED_NEW",
        )
        completion_order = int(counter_resp["Attributes"]["completion_count"])
        bonus_multiplier = get_bonus_multiplier(completion_order)
        points = calculate_awarded_points(base_points, completion_order)

        table.update_item(
            Key={"pk": f"COMPLETION#{student_id}#{exercise_id}", "sk": "v1"},
            UpdateExpression=(
                "SET points = :pts, completion_order = :order, "
                "bonus_multiplier = :mult"
            ),
            ExpressionAttributeValues={
                ":pts": points,
                ":order": completion_order,
                ":mult": bonus_multiplier,
            },
        )

        table.update_item(
            Key={"pk": f"STUDENT#{student_id}", "sk": "profile"},
            UpdateExpression=(
                "SET student_id = :sid, "
                "total_points = if_not_exists(total_points, :zero) + :pts, "
                "completed_exercises = list_append(if_not_exists(completed_exercises, :empty), :ex), "
                "last_updated = :ts"
            ),
            ExpressionAttributeValues={
                ":sid": student_id,
                ":pts": points,
                ":zero": 0,
                ":ex": [exercise_id],
                ":empty": [],
                ":ts": timestamp,
            },
        )
        logger.info(
            "Recorded completion: %s/%s (order=%s, multiplier=%.1f, +%spts)",
            student_id,
            exercise_id,
            completion_order,
            bonus_multiplier,
            points,
        )
        return {"student_id": student_id, "exercise_id": exercise_id, "status": status, "action": "recorded"}

    except table.meta.client.exceptions.ConditionalCheckFailedException:
        logger.info("Duplicate completion ignored: %s/%s", student_id, exercise_id)
        return {"student_id": student_id, "exercise_id": exercise_id, "status": status, "action": "duplicate"}


def handler(event: dict, context) -> dict:
    """Lambda entry point with partial-batch failure reporting."""
    table_name = os.environ.get("LEADERBOARD_TABLE")
    if not table_name:
        logger.error("LEADERBOARD_TABLE environment variable is not set")
        raise RuntimeError("LEADERBOARD_TABLE not configured")

    dynamodb = _get_dynamodb()
    table = dynamodb.Table(table_name)

    records = event.get("Records", [])
    logger.info("Processing batch of %s SQS records", len(records))

    batch_item_failures = []
    results = []

    for record in records:
        message_id = record.get("messageId", "unknown")
        try:
            result = _process_event(record, table)
            results.append(result)
        except Exception as exc:
            logger.error("Failed to process record %s: %s", message_id, exc, exc_info=True)
            batch_item_failures.append({"itemIdentifier": message_id})

    logger.info("Batch complete: %s processed, %s failed", len(results), len(batch_item_failures))
    return {"batchItemFailures": batch_item_failures}