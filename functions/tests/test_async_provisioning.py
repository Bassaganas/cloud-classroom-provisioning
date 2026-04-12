"""
Unit tests for async shared-core provisioning.

Coverage:
  - _enqueue_provisioning_request: happy path, SQS failure
  - provision_student_on_shared_core: async path, sync fallback (no queue), no instance
  - deprovision_student_on_shared_core: async path, sync fallback (no queue)
  - shared_core_provisioner.lambda_handler: provision, deprovision, malformed message,
      unknown action, missing fields, SSM success, SSM failure, DynamoDB status tracking
"""

import json
import os
import uuid
from unittest.mock import MagicMock, patch, call

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sqs_record(body: dict, message_id: str = "msg-001") -> dict:
    return {"messageId": message_id, "body": json.dumps(body)}


# ─────────────────────────────────────────────────────────────────────────────
# Tests for classroom_instance_manager — async enqueue path
# ─────────────────────────────────────────────────────────────────────────────

class TestEnqueueProvisioningRequest:
    """_enqueue_provisioning_request sends the correct SQS message."""

    def setup_method(self):
        # Reset module-level state
        import importlib
        import functions.common.classroom_instance_manager as mgr
        importlib.reload(mgr)

    def test_provision_enqueues_when_queue_url_set(self, monkeypatch):
        import functions.common.classroom_instance_manager as mgr

        mock_sqs = MagicMock()
        monkeypatch.setattr(mgr, "sqs", mock_sqs)
        monkeypatch.setattr(mgr, "SHARED_CORE_PROVISIONING_QUEUE_URL", "https://sqs.eu-west-1.amazonaws.com/123/test-queue")

        result = mgr.provision_student_on_shared_core(
            "frodo", workshop_name="fellowship", student_password="shire123"
        )

        assert result["success"] is True
        assert result["async"] is True
        assert "request_id" in result
        mock_sqs.send_message.assert_called_once()
        call_kwargs = mock_sqs.send_message.call_args[1]
        body = json.loads(call_kwargs["MessageBody"])
        assert body["action"] == "provision"
        assert body["student_id"] == "frodo"
        assert body["student_password"] == "shire123"

    def test_deprovision_enqueues_when_queue_url_set(self, monkeypatch):
        import functions.common.classroom_instance_manager as mgr

        mock_sqs = MagicMock()
        monkeypatch.setattr(mgr, "sqs", mock_sqs)
        monkeypatch.setattr(mgr, "SHARED_CORE_PROVISIONING_QUEUE_URL", "https://sqs.eu-west-1.amazonaws.com/123/test-queue")

        result = mgr.deprovision_student_on_shared_core("frodo", workshop_name="fellowship")

        assert result["success"] is True
        assert result["async"] is True
        body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
        assert body["action"] == "deprovision"
        assert body["student_id"] == "frodo"

    def test_enqueue_failure_returns_success_false(self, monkeypatch):
        import functions.common.classroom_instance_manager as mgr

        mock_sqs = MagicMock()
        mock_sqs.send_message.side_effect = Exception("SQS unavailable")
        monkeypatch.setattr(mgr, "sqs", mock_sqs)
        monkeypatch.setattr(mgr, "SHARED_CORE_PROVISIONING_QUEUE_URL", "https://sqs.eu-west-1.amazonaws.com/123/test-queue")

        result = mgr.provision_student_on_shared_core("frodo")

        assert result["success"] is False
        assert result["async"] is True
        assert "SQS unavailable" in result["details"]["error"]

    def test_provision_falls_back_to_sync_when_no_queue(self, monkeypatch):
        """No queue URL → synchronous SSM path (instance not found → success:True skip)."""
        import functions.common.classroom_instance_manager as mgr

        monkeypatch.setattr(mgr, "SHARED_CORE_PROVISIONING_QUEUE_URL", "")
        monkeypatch.setattr(mgr, "get_shared_core_instance_id", lambda *a, **k: None)

        result = mgr.provision_student_on_shared_core("frodo")

        assert result["success"] is True
        assert result.get("async") is False
        assert "skipped" in result["message"]

    def test_deprovision_falls_back_to_sync_when_no_queue(self, monkeypatch):
        import functions.common.classroom_instance_manager as mgr

        monkeypatch.setattr(mgr, "SHARED_CORE_PROVISIONING_QUEUE_URL", "")
        monkeypatch.setattr(mgr, "get_shared_core_instance_id", lambda *a, **k: None)

        result = mgr.deprovision_student_on_shared_core("frodo")

        assert result["success"] is True
        assert result.get("async") is False

    def test_request_id_is_valid_uuid(self, monkeypatch):
        import functions.common.classroom_instance_manager as mgr

        mock_sqs = MagicMock()
        monkeypatch.setattr(mgr, "sqs", mock_sqs)
        monkeypatch.setattr(mgr, "SHARED_CORE_PROVISIONING_QUEUE_URL", "https://sqs.eu-west-1.amazonaws.com/123/test-queue")

        result = mgr.provision_student_on_shared_core("frodo")

        # Must be a valid UUID-4
        parsed = uuid.UUID(result["request_id"], version=4)
        assert str(parsed) == result["request_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Tests for shared_core_provisioner Lambda handler
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_provisioner_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("CLASSROOM_REGION", "eu-west-1")
    monkeypatch.setenv("PROVISIONING_STATUS_TABLE", "test-provisioning-status")


class TestSharedCoreProvisionerHandler:
    """lambda_handler for the shared_core_provisioner Lambda."""

    def _import(self):
        import importlib
        import functions.aws.shared_core_provisioner as mod
        importlib.reload(mod)
        return mod

    def test_provision_success(self, monkeypatch):
        mod = self._import()

        monkeypatch.setattr(mod, "_get_shared_core_instance_id", lambda: "i-shared-001")
        monkeypatch.setattr(mod, "_get_shared_core_credentials", lambda: {
            "gitea_admin_user": "admin",
            "gitea_admin_password": "pass",
            "gitea_org_name": "org",
            "jenkins_admin_user": "admin",
            "jenkins_admin_password": "pass",
        })
        monkeypatch.setattr(mod, "_invoke_ssm_command", lambda **kw: {
            "success": True, "command_id": "cmd-001", "status": "Success",
            "output": "done", "error": "",
        })
        mock_table = MagicMock()
        monkeypatch.setattr(mod, "_get_status_table", lambda: mock_table)

        event = {"Records": [_sqs_record({
            "request_id": "req-001",
            "action": "provision",
            "student_id": "frodo",
            "workshop_name": "fellowship",
            "student_password": "shire123",
        })]}
        mod.lambda_handler(event, {})

        # DynamoDB should have been called: once with running, once with success
        assert mock_table.put_item.call_count == 2
        final_call = mock_table.put_item.call_args_list[-1][1]["Item"]
        assert final_call["status"] == "success"
        assert final_call["request_id"] == "req-001"
        assert final_call["ssm_command_id"] == "cmd-001"

    def test_deprovision_success(self, monkeypatch):
        mod = self._import()

        monkeypatch.setattr(mod, "_get_shared_core_instance_id", lambda: "i-shared-001")
        monkeypatch.setattr(mod, "_get_shared_core_credentials", lambda: {
            "gitea_admin_user": "admin",
            "gitea_admin_password": "pass",
            "gitea_org_name": "org",
            "jenkins_admin_user": "admin",
            "jenkins_admin_password": "pass",
        })
        monkeypatch.setattr(mod, "_invoke_ssm_command", lambda **kw: {
            "success": True, "command_id": "cmd-002", "status": "Success",
            "output": "removed", "error": "",
        })
        mock_table = MagicMock()
        monkeypatch.setattr(mod, "_get_status_table", lambda: mock_table)

        event = {"Records": [_sqs_record({
            "request_id": "req-002",
            "action": "deprovision",
            "student_id": "frodo",
            "workshop_name": "fellowship",
        })]}
        mod.lambda_handler(event, {})

        final_item = mock_table.put_item.call_args_list[-1][1]["Item"]
        assert final_item["status"] == "success"

    def test_ssm_failure_marks_status_failed(self, monkeypatch):
        mod = self._import()

        monkeypatch.setattr(mod, "_get_shared_core_instance_id", lambda: "i-shared-001")
        monkeypatch.setattr(mod, "_get_shared_core_credentials", lambda: {
            "gitea_admin_user": "a", "gitea_admin_password": "b",
            "gitea_org_name": "o", "jenkins_admin_user": "a", "jenkins_admin_password": "b",
        })
        monkeypatch.setattr(mod, "_invoke_ssm_command", lambda **kw: {
            "success": False, "command_id": "cmd-003", "status": "Failed",
            "output": "", "error": "script error",
        })
        mock_table = MagicMock()
        monkeypatch.setattr(mod, "_get_status_table", lambda: mock_table)

        event = {"Records": [_sqs_record({
            "request_id": "req-003",
            "action": "provision",
            "student_id": "sam",
            "workshop_name": "fellowship",
        })]}
        mod.lambda_handler(event, {})

        final_item = mock_table.put_item.call_args_list[-1][1]["Item"]
        assert final_item["status"] == "failed"
        assert "script error" in final_item["error"]

    def test_instance_id_not_found_marks_failed(self, monkeypatch):
        mod = self._import()

        monkeypatch.setattr(mod, "_get_shared_core_instance_id", lambda: None)
        mock_table = MagicMock()
        monkeypatch.setattr(mod, "_get_status_table", lambda: mock_table)

        event = {"Records": [_sqs_record({
            "request_id": "req-004",
            "action": "provision",
            "student_id": "pippin",
            "workshop_name": "fellowship",
        })]}
        mod.lambda_handler(event, {})

        statuses = [c[1]["Item"]["status"] for c in mock_table.put_item.call_args_list]
        assert "failed" in statuses

    def test_malformed_json_is_skipped_without_exception(self, monkeypatch):
        mod = self._import()
        mock_table = MagicMock()
        monkeypatch.setattr(mod, "_get_status_table", lambda: mock_table)

        event = {"Records": [{"messageId": "m1", "body": "{not valid json"}]}
        # Should NOT raise — bad messages are skipped to avoid retry loops
        mod.lambda_handler(event, {})

    def test_unknown_action_marks_failed(self, monkeypatch):
        mod = self._import()
        mock_table = MagicMock()
        monkeypatch.setattr(mod, "_get_status_table", lambda: mock_table)

        event = {"Records": [_sqs_record({
            "request_id": "req-005",
            "action": "teleport",
            "student_id": "merry",
            "workshop_name": "fellowship",
        })]}
        mod.lambda_handler(event, {})

        items = [c[1]["Item"] for c in mock_table.put_item.call_args_list]
        assert any(i["status"] == "failed" for i in items)

    def test_missing_student_id_marks_failed(self, monkeypatch):
        mod = self._import()
        mock_table = MagicMock()
        monkeypatch.setattr(mod, "_get_status_table", lambda: mock_table)

        event = {"Records": [_sqs_record({
            "request_id": "req-006",
            "action": "provision",
            # student_id intentionally missing
        })]}
        mod.lambda_handler(event, {})

        items = [c[1]["Item"] for c in mock_table.put_item.call_args_list]
        assert any(i["status"] == "failed" for i in items)

    def test_ttl_set_on_status_record(self, monkeypatch):
        import time as time_mod
        mod = self._import()

        monkeypatch.setattr(mod, "_get_shared_core_instance_id", lambda: "i-001")
        monkeypatch.setattr(mod, "_get_shared_core_credentials", lambda: {
            "gitea_admin_user": "a", "gitea_admin_password": "b",
            "gitea_org_name": "o", "jenkins_admin_user": "a", "jenkins_admin_password": "b",
        })
        monkeypatch.setattr(mod, "_invoke_ssm_command", lambda **kw: {
            "success": True, "command_id": "cmd-ttl", "status": "Success",
            "output": "", "error": "",
        })
        mock_table = MagicMock()
        monkeypatch.setattr(mod, "_get_status_table", lambda: mock_table)

        event = {"Records": [_sqs_record({
            "request_id": "req-ttl",
            "action": "provision",
            "student_id": "gandalf",
            "workshop_name": "fellowship",
        })]}
        mod.lambda_handler(event, {})

        for call_obj in mock_table.put_item.call_args_list:
            item = call_obj[1]["Item"]
            assert "expire_at" in item
            # expire_at should be roughly now + 7 days
            assert item["expire_at"] > int(time_mod.time())


# ─────────────────────────────────────────────────────────────────────────────
# Tests for _build_env_exports in shared_core_provisioner
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildEnvExports:
    def test_basic_export(self):
        import importlib
        import functions.aws.shared_core_provisioner as mod
        importlib.reload(mod)

        exports = mod._build_env_exports({"FOO": "bar", "NUM": "42"})
        assert "export FOO='bar'" in exports
        assert "export NUM='42'" in exports

    def test_single_quote_in_value_is_escaped(self):
        import importlib
        import functions.aws.shared_core_provisioner as mod
        importlib.reload(mod)

        exports = mod._build_env_exports({"PASS": "it's a secret"})
        # The value should have ' escaped as '\''
        assert "it'\\''s" in exports

    def test_empty_env_returns_empty_string(self):
        import importlib
        import functions.aws.shared_core_provisioner as mod
        importlib.reload(mod)

        assert mod._build_env_exports({}) == ""
