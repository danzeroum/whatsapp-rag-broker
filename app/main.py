import os
import asyncio
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from app.security import verify_signature
from app.broker import publish_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "meu_token_secreto_123")

app = FastAPI(
    title="WhatsApp RAG Broker",
    description="Serverless-ready Webhook para API Oficial do WhatsApp com RAG e Broker assíncrono.",
    version="1.0.0",
)


@app.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    request: Request,
):
    """
    Endpoint obrigatório da Meta para validação inicial do Webhook (challenge-response).
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    challenge = params.get("hub.challenge")
    token = params.get("hub.verify_token")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso pela Meta.")
        return challenge

    raise HTTPException(status_code=403, detail="Falha na verificação do token.")


@app.post("/webhook", dependencies=[Depends(verify_signature)])
async def receive_message(request: Request):
    """
    Recebe eventos do WhatsApp Cloud API.
    Valida a assinatura HMAC e publica mensagens na fila para processamento assíncrono.
    Sempre retorna 200 OK rapidamente para evitar reenvio pela Meta.
    """
    payload = await request.json()

    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Ignora status de entrega (read, delivered) — foca só em mensagens reais
                if "messages" not in value:
                    continue

                for msg in value["messages"]:
                    if msg.get("type") != "text":
                        continue  # Extensível para áudio, imagem etc.

                    event = {
                        "msg_id": msg.get("id"),
                        "phone": msg.get("from"),
                        "text": msg["text"]["body"],
                        "phone_number_id": value["metadata"]["phone_number_id"],
                    }

                    logger.info(f"[{event['msg_id']}] Mensagem de {event['phone']}: {event['text']}")

                    # Publica na fila — desacopla recebimento do processamento
                    await publish_message(event)

    except Exception as exc:
        logger.exception(f"Erro ao processar payload: {exc}")

    # Meta exige 200 OK imediato — não bloquear aqui
    return {"status": "ok"}
