"""Testes do webhook: verificação, HMAC e recebimento de mensagens."""
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


def make_payload(phone_number_id="123456", phone="5511999999999", text="Qual a taxa de juros?", msg_id="wamid.abc"):
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": phone_number_id},
                    "messages": [{
                        "id": msg_id,
                        "from": phone,
                        "type": "text",
                        "text": {"body": text},
                    }],
                }
            }]
        }]
    }


class TestWebhookVerification:
    def test_valid_token_returns_challenge(self):
        response = client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": TEST_TOKEN, "hub.challenge": "abc123"},
        )
        assert response.status_code == 200
        assert response.text == "abc123"

    def test_invalid_token_returns_403(self):
        response = client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong_token", "hub.challenge": "abc123"},
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
        payload = make_payload()
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

    @patch("app.main.publish_message", new_callable=AsyncMock)
    def test_publishes_correct_phone_number_id(self, mock_publish):
        """O evento publicado deve conter o phone_number_id extraído do metadata."""
        payload = make_payload(phone_number_id="87654321", phone="5511988888888", text="Teste metadata")
        body = json.dumps(payload).encode()
        sig = make_signature(body, TEST_SECRET)
        client.post(
            "/webhook",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        event_published = mock_publish.await_args[0][0]
        assert event_published["phone_number_id"] == "87654321"
        assert event_published["phone"] == "5511988888888"
        assert event_published["text"] == "Teste metadata"

    @patch("app.main.publish_message", new_callable=AsyncMock)
    def test_ignores_non_text_messages(self, mock_publish):
        """Mensagens de tipo não-text (imagem, áudio) não devem ser publicadas na fila."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123"},
                        "messages": [{"id": "wamid.img", "from": "55119", "type": "image"}],
                    }
                }]
            }]
        }
        body = json.dumps(payload).encode()
        sig = make_signature(body, TEST_SECRET)
        client.post(
            "/webhook",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        mock_publish.assert_not_awaited()

    @patch("app.main.publish_message", new_callable=AsyncMock)
    def test_payload_without_messages_returns_200(self, mock_publish):
        """Payloads sem 'messages' (status updates) devem retornar 200 sem publicar."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "123"},
                        "statuses": [{"id": "wamid.status", "status": "delivered"}],
                    }
                }]
            }]
        }
        body = json.dumps(payload).encode()
        sig = make_signature(body, TEST_SECRET)
        response = client.post(
            "/webhook",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        mock_publish.assert_not_awaited()
