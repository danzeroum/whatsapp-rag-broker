"""Testes do broker Redis usando fakeredis (sem container)."""
import json

import fakeredis.aioredis
import pytest

import app.broker as broker_module
from app.broker import consume_message, publish_message


@pytest.fixture(autouse=True)
async def fake_redis(monkeypatch):
    """Substitui a conexão Redis real por um fake in-memory."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(broker_module, "_redis_client", fake)
    yield fake
    await fake.flushall()
    await fake.aclose()


@pytest.mark.asyncio
async def test_publish_serializes_event():
    """publish_message deve serializar o evento completo como JSON na fila."""
    event = {
        "msg_id": "wamid.test123",
        "phone": "5511999999999",
        "text": "olá",
        "phone_number_id": "987654321",
    }
    await publish_message(event)

    client = await broker_module.get_redis()
    raw = await client.rpop("whatsapp:messages")
    assert raw is not None
    payload = json.loads(raw)
    assert payload["msg_id"] == "wamid.test123"
    assert payload["phone"] == "5511999999999"
    assert payload["text"] == "olá"
    assert payload["phone_number_id"] == "987654321"


@pytest.mark.asyncio
async def test_publish_then_consume_returns_event():
    """Publicar e consumir deve retornar o mesmo evento (FIFO)."""
    event = {
        "msg_id": "wamid.fifo",
        "phone": "5511988888888",
        "text": "teste fifo",
        "phone_number_id": "111",
    }
    await publish_message(event)
    result = await consume_message()
    assert result is not None
    assert result["msg_id"] == "wamid.fifo"
    assert result["phone"] == "5511988888888"
    assert result["text"] == "teste fifo"
    assert result["phone_number_id"] == "111"


@pytest.mark.asyncio
async def test_consume_empty_queue_returns_none():
    """consume_message deve retornar None quando a fila está vazia."""
    result = await consume_message()
    assert result is None


@pytest.mark.asyncio
async def test_publish_multiple_fifo_order():
    """Múltiplas mensagens devem ser consumidas na ordem de publicação."""
    for i in range(3):
        await publish_message({"msg_id": f"msg_{i}", "phone": "55", "text": str(i), "phone_number_id": "0"})

    results = []
    for _ in range(3):
        r = await consume_message()
        assert r is not None
        results.append(r["msg_id"])

    assert results == ["msg_0", "msg_1", "msg_2"]
