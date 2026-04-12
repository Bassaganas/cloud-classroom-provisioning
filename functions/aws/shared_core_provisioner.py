"""
shared_core_provisioner.py — Async shared-core student provisioning Lambda

Triggered by SQS (one message per student action). Reads the action from the
message body and either:
  - provisions a student  (Gitea user/repo + Jenkins job/folder + webhook)
  - deprovisions a student (removes Gitea repo + Jenkins job/folder)

via SSM Run Command on the shared-core EC2 instance.

Status is tracked in a DynamoDB table so the caller can poll by request_id:

  DynamoDB item schema:
    request_id   (PK, str)  — UUID sent back in the API response
    action       (str)      — "provision" | "deprovision"
    student_id   (str)
    workshop_name(str)
    status       (str)      — "queued" | "running" | "success" | "failed"
    ssm_command_id (str)    — populated after SSM call
    error        (str)      — error message on failure
    created_at   (str)      — ISO-8601 UTC
    updated_at   (str)      — ISO-8601 UTC
    expire_at    (int)      — Unix epoch + 7 days (DynamoDB TTL)

SQS message body (JSON):
  {
    "request_id":   "<uuid>",
    "action":       "provision" | "deprovision",
    "student_id":   "<student-id>",
    "workshop_name":"<workshop>",
    "student_password": "<password>"   # only for provision
  }
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── AWS clients ───────────────────────────────────────────────────────────────

REGION = os.environ.get("CLASSROOM_REGION", os.environ.get("AWS_REGION", "eu-west-3"))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
STATUS_TABLE_NAME = os.environ.get("PROVISIONING_STATUS_TABLE", "")

ssm_client = boto3.client("ssm", region_name=REGION)
secretsmanager_client = boto3.client("secretsmanager", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)

_status_table = None


def _get_status_table():
    global _status_table
    if _status_table is None:
        if not STATUS_TABLE_NAME:
            raise RuntimeError("PROVISIONING_STATUS_TABLE env var is not set")
        _status_table = dynamodb.Table(STATUS_TABLE_NAME)
    return _status_table


# ── DynamoDB helpers ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ttl_7_days() -> int:
    return int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())


def _update_status(request_id: str, status: str, **extra_fields):
    """Write a status record to DynamoDB. Creates or updates the item."""
    item = {
        "request_id": request_id,
        "status": status,
        "updated_at": _now_iso(),
        "expire_at": _ttl_7_days(),
    }
    item.update(extra_fields)
    try:
        _get_status_table().put_item(Item=item)
        logger.info(f"[{request_id}] status → {status}")
    except Exception as exc:
        logger.error(f"[{request_id}] Failed to write status to DynamoDB: {exc}")


# ── SSM helpers ───────────────────────────────────────────────────────────────

def _get_shared_core_instance_id() -> Optional[str]:
    """Retrieve shared-core EC2 instance ID from SSM Parameter Store."""
    param_name = f"/classroom/shared-core/{ENVIRONMENT}/instance-id"
    try:
        response = ssm_client.get_parameter(Name=param_name, WithDecryption=False)
        return response["Parameter"]["Value"]
    except ssm_client.exceptions.ParameterNotFound:
        logger.warning(f"Shared-core instance ID parameter not found: {param_name}")
        return None
    except Exception as exc:
        logger.warning(f"Error reading shared-core instance ID: {exc}")
        return None


def _get_shared_core_credentials() -> dict:
    """Retrieve Gitea/Jenkins admin credentials from SSM + Secrets Manager."""
    credentials = {
        "gitea_admin_user": "fellowship",
        "gitea_admin_password": "fellowship123",
        "jenkins_admin_user": "fellowship",
        "jenkins_admin_password": "fellowship123",
        "gitea_org_name": "fellowship-org",
    }

    # Passwords from Secrets Manager
    deploy_secret_name = f"/classroom/shared-core/{ENVIRONMENT}/deploy"
    try:
        response = secretsmanager_client.get_secret_value(SecretId=deploy_secret_name)
        if "SecretString" in response:
            secret = json.loads(response["SecretString"])
            credentials["gitea_admin_password"] = secret.get(
                "gitea_admin_password", credentials["gitea_admin_password"]
            )
            credentials["jenkins_admin_password"] = secret.get(
                "jenkins_admin_password", credentials["jenkins_admin_password"]
            )
    except secretsmanager_client.exceptions.ResourceNotFoundException:
        logger.debug(f"Deploy secret not found: {deploy_secret_name}, using defaults")
    except Exception as exc:
        logger.warning(f"Error reading deploy secret: {exc}, using defaults")

    # Usernames / org from SSM
    for param_key, cred_key, default in [
        ("gitea-admin-user", "gitea_admin_user", "fellowship"),
        ("gitea-org-name", "gitea_org_name", "fellowship-org"),
    ]:
        param_name = f"/classroom/shared-core/{ENVIRONMENT}/{param_key}"
        try:
            response = ssm_client.get_parameter(Name=param_name, WithDecryption=False)
            credentials[cred_key] = response["Parameter"]["Value"]
        except ssm_client.exceptions.ParameterNotFound:
            credentials[cred_key] = default
        except Exception as exc:
            logger.warning(f"Error reading {param_name}: {exc}, using default")

    return credentials


def _build_env_exports(env_vars: dict) -> str:
    """Build a shell export block — safely escapes values."""
    exports = ""
    for key, value in env_vars.items():
        escaped = str(value).replace("'", "'\\''")
        exports += f"export {key}='{escaped}'\n"
    return exports


def _invoke_ssm_command(
    instance_id: str,
    script_path: str,
    parameters: list,
    environment_vars: dict,
    max_retries: int = 3,
) -> dict:
    """
    Send an SSM Run Command and block until it finishes (up to 90 s).

    Returns:
        dict(success, command_id, status, output, error)
    """
    env_exports = _build_env_exports(environment_vars)
    params_str = " ".join(f"'{str(p)}'" for p in parameters)
    full_command = f"{env_exports}bash {script_path} {params_str}"

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"SSM attempt {attempt}/{max_retries}: {script_path} "
                f"params={parameters[:1]}… on {instance_id}"
            )
            response = ssm_client.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"command": [full_command]},
                TimeoutSeconds=600,
            )
            command_id = response["Command"]["CommandId"]
            logger.info(f"SSM command_id={command_id}")

            # Poll up to 90 s (18 × 5 s)
            for _ in range(18):
                time.sleep(5)
                invocation = ssm_client.get_command_invocation(
                    CommandId=command_id, InstanceId=instance_id
                )
                status = invocation["Status"]
                if status in ("Success", "Failed", "Cancelled", "TimedOut", "Cancelling"):
                    output = invocation.get("StandardOutputContent", "")
                    error = invocation.get("StandardErrorContent", "")
                    if status == "Success":
                        logger.info(f"SSM succeeded. output={output[:300]}")
                    else:
                        logger.error(f"SSM failed status={status} error={error[:300]}")
                    return {
                        "success": status == "Success",
                        "command_id": command_id,
                        "status": status,
                        "output": output,
                        "error": error,
                    }

            logger.warning(f"SSM command {command_id} did not complete in 90 s")
            return {
                "success": False,
                "command_id": command_id,
                "status": "Timeout",
                "output": "",
                "error": "Command did not complete within 90 seconds",
            }

        except ssm_client.exceptions.InvalidInstanceInformationException:
            logger.warning(f"Instance {instance_id} not SSM-ready (attempt {attempt})")
            if attempt < max_retries:
                time.sleep(10)
            else:
                return {
                    "success": False,
                    "command_id": "",
                    "status": "InvalidInstance",
                    "output": "",
                    "error": f"Instance {instance_id} not SSM-ready after {max_retries} retries",
                }

        except Exception as exc:
            logger.error(f"SSM error (attempt {attempt}): {exc}")
            if attempt < max_retries:
                time.sleep(5)
            else:
                return {
                    "success": False,
                    "command_id": "",
                    "status": "Error",
                    "output": "",
                    "error": str(exc),
                }

    return {
        "success": False,
        "command_id": "",
        "status": "Failed",
        "output": "",
        "error": f"Failed after {max_retries} retries",
    }


# ── Core provisioning logic ───────────────────────────────────────────────────

def _provision(request_id: str, student_id: str, workshop_name: str, student_password: str):
    logger.info(f"[{request_id}] provision student={student_id} workshop={workshop_name}")
    _update_status(
        request_id,
        "running",
        action="provision",
        student_id=student_id,
        workshop_name=workshop_name,
        created_at=_now_iso(),
    )

    instance_id = _get_shared_core_instance_id()
    if not instance_id:
        _update_status(request_id, "failed", error="Shared-core instance ID not found in SSM")
        return

    credentials = _get_shared_core_credentials()
    env_vars = {
        "GITEA_ADMIN_USER": credentials["gitea_admin_user"],
        "GITEA_ADMIN_PASSWORD": credentials["gitea_admin_password"],
        "GITEA_ORG_NAME": credentials["gitea_org_name"],
        "JENKINS_ADMIN_USER": credentials["jenkins_admin_user"],
        "JENKINS_ADMIN_PASSWORD": credentials["jenkins_admin_password"],
    }

    result = _invoke_ssm_command(
        instance_id=instance_id,
        script_path="/opt/scripts/provision-student.sh",
        parameters=[student_id, student_password or "fellowship123"],
        environment_vars=env_vars,
    )

    if result["success"]:
        _update_status(request_id, "success", ssm_command_id=result["command_id"])
    else:
        _update_status(
            request_id,
            "failed",
            ssm_command_id=result["command_id"],
            error=result["error"][:500],
        )


def _deprovision(request_id: str, student_id: str, workshop_name: str):
    logger.info(f"[{request_id}] deprovision student={student_id} workshop={workshop_name}")
    _update_status(
        request_id,
        "running",
        action="deprovision",
        student_id=student_id,
        workshop_name=workshop_name,
        created_at=_now_iso(),
    )

    instance_id = _get_shared_core_instance_id()
    if not instance_id:
        _update_status(request_id, "failed", error="Shared-core instance ID not found in SSM")
        return

    credentials = _get_shared_core_credentials()
    env_vars = {
        "GITEA_ADMIN_USER": credentials["gitea_admin_user"],
        "GITEA_ADMIN_PASSWORD": credentials["gitea_admin_password"],
        "GITEA_ORG_NAME": credentials["gitea_org_name"],
        "JENKINS_ADMIN_USER": credentials["jenkins_admin_user"],
        "JENKINS_ADMIN_PASSWORD": credentials["jenkins_admin_password"],
    }

    result = _invoke_ssm_command(
        instance_id=instance_id,
        script_path="/opt/scripts/deprovision-student.sh",
        parameters=[student_id, "--confirm"],
        environment_vars=env_vars,
    )

    if result["success"]:
        _update_status(request_id, "success", ssm_command_id=result["command_id"])
    else:
        _update_status(
            request_id,
            "failed",
            ssm_command_id=result["command_id"],
            error=result["error"][:500],
        )


# ── Lambda handler ────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    SQS-triggered Lambda. Processes one record per invocation (batch_size=1).
    Raises on unrecoverable errors so the message is returned to the queue
    (up to maxReceiveCount), then sent to the DLQ.
    """
    logger.info(f"Received {len(event.get('Records', []))} SQS record(s)")

    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        try:
            body = json.loads(record["body"])
        except (KeyError, json.JSONDecodeError) as exc:
            logger.error(f"[{message_id}] Malformed SQS message body: {exc}")
            # Do NOT raise — a malformed message will never succeed, let it DLQ
            continue

        request_id = body.get("request_id", message_id)
        action = body.get("action", "").lower()
        student_id = body.get("student_id", "")
        workshop_name = body.get("workshop_name", "")
        student_password = body.get("student_password", "fellowship123")

        if not student_id or not action:
            logger.error(f"[{request_id}] Missing student_id or action in message: {body}")
            _update_status(request_id, "failed", error="Missing student_id or action")
            continue

        try:
            if action == "provision":
                _provision(request_id, student_id, workshop_name, student_password)
            elif action == "deprovision":
                _deprovision(request_id, student_id, workshop_name)
            else:
                logger.error(f"[{request_id}] Unknown action: {action}")
                _update_status(request_id, "failed", error=f"Unknown action: {action}")
        except Exception as exc:
            logger.error(f"[{request_id}] Unhandled error processing {action}: {exc}", exc_info=True)
            _update_status(request_id, "failed", error=str(exc)[:500])
            # Re-raise so SQS retries (will DLQ after maxReceiveCount)
            raise
