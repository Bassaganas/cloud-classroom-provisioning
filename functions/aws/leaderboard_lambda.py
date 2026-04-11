"""
leaderboard_lambda.py — AWS Lambda handler for SQS -> DynamoDB leaderboard.

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
}


def _get_dynamodb():
    import boto3

    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-west-1"))


def _process_event(record: dict, table) -> dict:
    body = json.loads(record["body"])
    student_id = body["student_id"]
    exercise_id = body["exercise_id"]
    status = body["status"]
    timestamp = body.get("timestamp", datetime.now(timezone.utc).isoformat())

    logger.info("Processing event: student=%s exercise=%s status=%s", student_id, exercise_id, status)

    if status != "completed":
        logger.info("Skipping non-completion event: %s", status)
        return {"student_id": student_id, "exercise_id": exercise_id, "status": status, "action": "skipped"}

    points = EXERCISE_POINTS.get(exercise_id, 0)

    try:
        table.put_item(
            Item={
                "pk": f"COMPLETION#{student_id}#{exercise_id}",
                "sk": "v1",
                "student_id": student_id,
                "exercise_id": exercise_id,
                "points": points,
                "completed_at": timestamp,
            },
            ConditionExpression="attribute_not_exists(pk)",
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
        logger.info("Recorded completion: %s/%s +%spts", student_id, exercise_id, points)
        return {"student_id": student_id, "exercise_id": exercise_id, "status": status, "action": "recorded"}
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        logger.info("Duplicate completion ignored: %s/%s", student_id, exercise_id)
        return {"student_id": student_id, "exercise_id": exercise_id, "status": status, "action": "duplicate"}


def handler(event: dict, context) -> dict:
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