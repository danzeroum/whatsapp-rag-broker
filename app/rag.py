import logging
import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

DOCS_PATH = Path(os.getenv("DOCS_PATH", "data/docs"))
CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma_db")
COLLECTION_NAME = "knowledge_base"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

logger = logging.getLogger(__name__)


def _get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    emb_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
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
