import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

TEST_SECRET = "test_secret"
TEST_TOKEN = "test_verify_token"


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", TEST_SECRET)
    monkeypatch.setenv("META_VERIFY_TOKEN", TEST_TOKEN)


client = TestClient(app)


def make_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class TestWebhookVerification:
    def test_valid_token_returns_challenge(self):
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": TEST_TOKEN,
                "hub.challenge": "abc123",
            },
        )
        assert response.status_code == 200
        assert response.text == "abc123"

    def test_invalid_token_returns_403(self):
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "abc123",
            },
        )
        assert response.status_code == 403


class TestWebhookReceive:
    def test_missing_signature_returns_403(self):
        response = client.post("/webhook", json={"entry": []})
        assert response.status_code == 403

    def test_invalid_signature_returns_403(self):
        body = json.dumps({"entry": []}).encode()
        response = client.post(
            "/webhook",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=invalidsignature"},
        )
        assert response.status_code == 403

    @patch("app.main.publish_message", new_callable=AsyncMock)
    def test_valid_message_returns_200(self, mock_publish):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "123456"},
                                "messages": [
                                    {
                                        "id": "wamid.abc",
                                        "from": "5511999999999",
                                        "type": "text",
                                        "text": {"body": "Qual a taxa de juros?"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        body = json.dumps(payload).encode()
        sig = make_signature(body, TEST_SECRET)
        response = client.post(
            "/webhook",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_publish.assert_awaited_once()
