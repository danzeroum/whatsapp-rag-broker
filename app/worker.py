import asyncio
import logging
import os

from openai import AsyncOpenAI

from app.broker import consume_message
from app.rag import ingest_documents, retrieve
from app.whatsapp_client import send_text_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _build_llm_client() -> AsyncOpenAI:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "deepseek":
        return AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
        )
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


def _default_model() -> str:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    return "deepseek-chat" if provider == "deepseek" else "gpt-4o-mini"


async def generate_response(question: str, context_chunks: list[dict]) -> str:
    client = _build_llm_client()
    model = os.getenv("LLM_MODEL", _default_model())

    context_text = "\n\n".join(
        f"[Fonte: {c['source']} | Chunk {c['chunk']}]\n{c['text']}" for c in context_chunks
    )

    prompt = (
        "Você é um assistente especializado. Responda a pergunta do usuário "
        "baseando-se EXCLUSIVAMENTE no contexto abaixo. Se a informação não estiver no contexto, "
        "diga que não possui essa informação.\n\n"
        f"## Contexto\n{context_text}\n\n"
        f"## Pergunta\n{question}\n\n## Resposta"
    )

    response = await client.chat.completions.create(
        model=model,
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

    separator = "=" * 60
    logger.info(separator)
    logger.info("[worker] NOVA MENSAGEM RECEBIDA")
    logger.info(f"[worker]   msg_id  : {msg_id}")
    logger.info(f"[worker]   de      : {phone}")
    logger.info(f"[worker]   texto   : {text}")
    logger.info(separator)

    chunks = retrieve(text, top_k=3)
    logger.info(f"[worker] {len(chunks)} chunks recuperados para a query.")
    for i, chunk in enumerate(chunks):
        logger.info(f"[worker]   chunk[{i}] fonte={chunk.get('source')} | {chunk.get('text', '')[:100]}...")

    answer = await generate_response(text, chunks)

    logger.info(separator)
    logger.info("[worker] RESPOSTA GERADA")
    logger.info(f"[worker]   para    : {phone}")
    logger.info(f"[worker]   resposta: {answer}")
    logger.info(separator)

    await send_text_message(phone_number_id, phone, answer)
    logger.info(f"[worker] Mensagem enviada para {phone} com sucesso.")


async def run_worker() -> None:
    logger.info("[worker] Worker iniciado. Indexando documentos...")
    ingest_documents()
    logger.info("[worker] Indexação concluída. Aguardando mensagens na fila...")
    while True:
        event = await consume_message()
        if event:
            try:
                await process_event(event)
            except Exception as exc:
                logger.exception(f"[worker] Erro ao processar evento {event.get('msg_id')}: {exc}")


if __name__ == "__main__":
    asyncio.run(run_worker())
