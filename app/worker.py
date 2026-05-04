import os
import asyncio
import logging
from openai import AsyncOpenAI
from app.broker import consume_message
from app.rag import retrieve
from app.whatsapp_client import send_text_message

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_response(question: str, context_chunks: list[dict]) -> str:
    """
    Gera resposta com LLM usando o contexto recuperado pelo RAG.
    Cada resposta é fundamentada em documentos reais — rastreável e auditável.
    """
    context_text = "\n\n".join(
        f"[Fonte: {c['source']} | Chunk {c['chunk']}]\n{c['text']}" for c in context_chunks
    )

    prompt = f"""Você é um assistente especializado. Responda a pergunta do usuário \
baseando-se EXCLUSIVAMENTE no contexto abaixo. Se a informação não estiver no contexto, \
diga que não possui essa informação.

## Contexto
{context_text}

## Pergunta
{question}

## Resposta"""

    response = await openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


async def process_event(event: dict) -> None:
    msg_id = event["msg_id"]
    phone = event["phone"]
    text = event["text"]
    phone_number_id = event["phone_number_id"]

    logger.info(f"[worker] Processando msg {msg_id} de {phone}")

    # 1. RAG: recupera chunks relevantes
    chunks = retrieve(text, top_k=3)
    logger.info(f"[worker] {len(chunks)} chunks recuperados para a query.")

    # 2. LLM: gera resposta fundamentada
    answer = await generate_response(text, chunks)
    logger.info(f"[worker] Resposta gerada: {answer[:80]}...")

    # 3. WhatsApp: envia resposta ao usuário
    await send_text_message(phone_number_id, phone, answer)
    logger.info(f"[worker] Resposta enviada para {phone}.")


async def run_worker() -> None:
    """
    Loop principal do worker: consome eventos da fila e processa continuamente.
    Em produção, isso seria uma AWS Lambda acionada por SQS trigger.
    """
    logger.info("[worker] Worker iniciado. Aguardando mensagens na fila...")
    while True:
        event = await consume_message()
        if event:
            try:
                await process_event(event)
            except Exception as exc:
                logger.exception(f"[worker] Erro ao processar evento {event.get('msg_id')}: {exc}")


if __name__ == "__main__":
    asyncio.run(run_worker())
