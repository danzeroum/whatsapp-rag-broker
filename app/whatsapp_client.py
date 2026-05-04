import os
import logging
import httpx

GRAPH_API_URL = "https://graph.facebook.com/v20.0"
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")

logger = logging.getLogger(__name__)


async def send_text_message(phone_number_id: str, to: str, text: str) -> dict:
    """
    Envia uma mensagem de texto via WhatsApp Cloud API (Meta).
    Documentação: https://developers.facebook.com/docs/whatsapp/cloud-api/messages
    """
    url = f"{GRAPH_API_URL}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"[whatsapp] Mensagem enviada para {to} — status {response.status_code}")
        return response.json()
