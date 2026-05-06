import logging
import os
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

DOCS_PATH = Path(os.getenv("DOCS_PATH", "data/docs"))
CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma_db")
COLLECTION_NAME = "knowledge_base"

logger = logging.getLogger(__name__)


def _get_client():
    """Retorna o cliente ChromaDB com telemetria desabilitada."""
    return chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )


def _get_collection():
    """
    Retorna a coleção ChromaDB usando a função de embedding adequada ao provider.

    - openai  : OpenAIEmbeddingFunction com text-embedding-3-small
    - deepseek: DefaultEmbeddingFunction (sentence-transformers local, gratuito)
      O DeepSeek não oferece API de embeddings; usar modelo local é a prática recomendada.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    client = _get_client()

    if provider == "deepseek":
        emb_fn = embedding_functions.DefaultEmbeddingFunction()
    else:
        emb_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_name="text-embedding-3-small",
        )

    return client.get_or_create_collection(COLLECTION_NAME, embedding_function=emb_fn)


def ingest_documents() -> None:
    """
    Lê arquivos .txt e .md da pasta DOCS_PATH, divide em chunks e indexa no ChromaDB.
    """
    collection = _get_collection()
    chunks, ids, metadatas = [], [], []

    for file_path in DOCS_PATH.glob("**/*"):
        if file_path.suffix not in (".txt", ".md"):
            continue

        content = file_path.read_text(encoding="utf-8")
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        for i, para in enumerate(paragraphs):
            chunk_id = f"{file_path.stem}_{i}"
            chunks.append(para)
            ids.append(chunk_id)
            metadatas.append({"source": file_path.name, "chunk": i})

    if chunks:
        collection.upsert(documents=chunks, ids=ids, metadatas=metadatas)
        logger.info(f"[rag] {len(chunks)} chunks indexados no ChromaDB.")
    else:
        logger.warning("[rag] Nenhum documento encontrado para ingestão.")


def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """
    Busca os top_k chunks mais relevantes para a query.
    """
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=top_k)

    retrieved = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        retrieved.append({"text": doc, "source": meta.get("source"), "chunk": meta.get("chunk")})
        logger.info(f"[rag] Chunk recuperado de '{meta.get('source')}' (chunk {meta.get('chunk')})")

    return retrieved
