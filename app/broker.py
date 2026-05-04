import json
import os
import logging
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
QUEUE_NAME = "whatsapp:messages"

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def publish_message(event: dict) -> None:
    """
    Publica o evento de mensagem na fila Redis (LPUSH).
    Equivalente a um SQS SendMessage em produção AWS.
    """
    client = await get_redis()
    await client.lpush(QUEUE_NAME, json.dumps(event))
    logger.info(f"[broker] Mensagem {event['msg_id']} publicada na fila '{QUEUE_NAME}'.")


async def consume_message() -> dict | None:
    """
    Consome bloqueante da fila Redis (BRPOP com timeout).
    Equivalente a SQS ReceiveMessage + DeleteMessage.
    """
    client = await get_redis()
    result = await client.brpop(QUEUE_NAME, timeout=5)
    if result:
        _, raw = result
        return json.loads(raw)
    return None
