"""Testes de contrato do whatsapp_client: valida payload exato enviado à API da Meta."""
import pytest
import respx
import httpx

from app.whatsapp_client import send_text_message

PHONE_NUMBER_ID = "123456789"
TO = "5511999999999"
TEXT = "Olá, como posso ajudar?"
GRAPH_URL = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"


@pytest.mark.asyncio
@respx.mock
async def test_send_text_message_payload_contract():
    """Valida que o payload enviado à API da Meta tem os campos obrigatórios corretos."""
    captured = {}

    def capture_request(request):
        import json
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.mock"}]})

    respx.post(GRAPH_URL).mock(side_effect=capture_request)

    await send_text_message(PHONE_NUMBER_ID, TO, TEXT)

    payload = captured["payload"]
    assert payload["messaging_product"] == "whatsapp"
    assert payload["recipient_type"] == "individual"
    assert payload["to"] == TO
    assert payload["type"] == "text"
    assert payload["text"]["body"] == TEXT
    assert "preview_url" in payload["text"]


@pytest.mark.asyncio
@respx.mock
async def test_send_text_message_raises_on_4xx():
    """raise_for_status deve propagar erros HTTP 4xx da API da Meta."""
    respx.post(GRAPH_URL).mock(return_value=httpx.Response(401, json={"error": "Unauthorized"}))

    with pytest.raises(httpx.HTTPStatusError):
        await send_text_message(PHONE_NUMBER_ID, TO, TEXT)


@pytest.mark.asyncio
@respx.mock
async def test_send_text_message_raises_on_5xx():
    """Falhas transitórias (500) devem ser propagadas para retry externo."""
    respx.post(GRAPH_URL).mock(return_value=httpx.Response(500, json={"error": "Server Error"}))

    with pytest.raises(httpx.HTTPStatusError):
        await send_text_message(PHONE_NUMBER_ID, TO, TEXT)


@pytest.mark.asyncio
@respx.mock
async def test_send_text_message_uses_correct_endpoint():
    """URL da requisição deve incluir o phone_number_id correto."""
    route = respx.post(GRAPH_URL).mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.x"}]})
    )
    await send_text_message(PHONE_NUMBER_ID, TO, TEXT)
    assert route.called
