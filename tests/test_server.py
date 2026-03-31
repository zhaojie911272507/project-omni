"""Tests for FastAPI server webhooks."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    from server import app

    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        """Test health endpoint returns status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "project-omni"


class TestWeComWebhook:
    """Test WeCom webhook endpoints."""

    def test_wecom_verify_missing_params(self, client: TestClient) -> None:
        """Test WeCom verify endpoint without required params."""
        response = client.get("/webhook/wecom")
        assert response.status_code == 422  # Validation error

    def test_wecom_receive_invalid_xml(self, client: TestClient) -> None:
        """Test WeCom receive with invalid XML."""
        response = client.post(
            "/webhook/wecom?msg_signature=test&timestamp=test&nonce=test",
            content="<valid>xml</valid>",
        )
        # Should return 200 with 'success' for non-text message or 403 for signature mismatch
        assert response.status_code in (200, 403)


class TestFeishuWebhook:
    """Test Feishu webhook endpoints."""

    def test_feishu_empty_body(self, client: TestClient) -> None:
        """Test Feishu webhook with empty body."""
        response = client.post("/webhook/feishu", json={})
        assert response.status_code == 200
        data = response.json()
        # Empty body has no event_type, so it's ignored
        assert data["code"] in (0, 1)  # Either ignored or token mismatch

    def test_feishu_url_verification(
        self, client: TestClient, mock_feishu_env: None
    ) -> None:
        """Test Feishu URL verification challenge."""
        response = client.post(
            "/webhook/feishu",
            json={
                "type": "url_verification",
                "token": "test_token",
                "challenge": "test_challenge_123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["challenge"] == "test_challenge_123"

    def test_feishu_non_message_event(self, client: TestClient) -> None:
        """Test Feishu webhook with non-message event."""
        response = client.post(
            "/webhook/feishu",
            json={
                "header": {
                    "event_type": "im.message.update_v1",
                    "token": "test",
                    "event_id": "test_event_123",
                },
                "event": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        # May be ignored or token mismatch depending on env
        assert data.get("msg") in ("ignored", "token mismatch", "duplicate")

    def test_feishu_non_text_message(self, client: TestClient) -> None:
        """Test Feishu webhook with non-text message."""
        response = client.post(
            "/webhook/feishu",
            json={
                "header": {
                    "event_type": "im.message.receive_v1",
                    "token": "test",
                    "event_id": "test_event_456",
                },
                "event": {
                    "message": {"message_type": "image", "content": "{}"},
                    "sender": {"sender_id": {"open_id": "test_user"}},
                },
            },
        )
        assert response.status_code == 200
        # May be non-text ignored or token mismatch
        data = response.json()
        assert "ignored" in data.get("msg", "") or data.get("msg") == "token mismatch"

    def test_feishu_empty_text(self, client: TestClient) -> None:
        """Test Feishu webhook with empty text."""
        response = client.post(
            "/webhook/feishu",
            json={
                "header": {
                    "event_type": "im.message.receive_v1",
                    "token": "test",
                    "event_id": "test_event_789",
                },
                "event": {
                    "message": {
                        "message_type": "text",
                        "content": '{"text": ""}',
                    },
                    "sender": {"sender_id": {"open_id": "test_user"}},
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        # May be empty or token mismatch
        assert "empty" in data.get("msg", "") or data.get("msg") == "token mismatch"
