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

# Modelo multilingual — suporta PT-BR, EN e +100 idiomas
MULTILINGUAL_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Distância máxima aceita (ChromaDB usa distância L2: menor = mais similar)
# 0.0 = idêntico, 1.5 = pouco relacionado. Ajuste conforme necessidade.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "1.2"))


def _get_client():
    """Retorna o cliente ChromaDB com telemetria desabilitada."""
    return chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )


def _get_embedding_fn():
    """
    Retorna a função de embedding adequada ao provider.

    - openai  : OpenAIEmbeddingFunction com text-embedding-3-small
    - deepseek: SentenceTransformerEmbeddingFunction multilingual (local, gratuito)
      paraphrase-multilingual-MiniLM-L12-v2 suporta PT-BR e +100 idiomas.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "deepseek":
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=MULTILINGUAL_MODEL
        )

    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model_name="text-embedding-3-small",
    )


def _get_collection():
    client = _get_client()
    emb_fn = _get_embedding_fn()
    return client.get_or_create_collection(COLLECTION_NAME, embedding_function=emb_fn)


def ingest_documents() -> None:
    """
    Lê arquivos .txt e .md da pasta DOCS_PATH, divide em chunks e indexa no ChromaDB.
    Apaga a coleção anterior para garantir que os embeddings sejam recriados com o modelo correto.
    """
    client = _get_client()
    emb_fn = _get_embedding_fn()

    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info("[rag] Coleção anterior removida para reindexação limpa.")
    except Exception:
        pass

    collection = client.create_collection(COLLECTION_NAME, embedding_function=emb_fn)

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
    Filtra chunks com distância acima de SIMILARITY_THRESHOLD (irrelevantes).
    """
    collection = _get_collection()
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    retrieved = []
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, dist in zip(docs, metas, distances):
        if dist > SIMILARITY_THRESHOLD:
            logger.info(
                f"[rag] Chunk DESCARTADO de '{meta.get('source')}' "
                f"(chunk {meta.get('chunk')}) — distância={dist:.4f} > threshold={SIMILARITY_THRESHOLD}"
            )
            continue
        retrieved.append({"text": doc, "source": meta.get("source"), "chunk": meta.get("chunk")})
        logger.info(
            f"[rag] Chunk ACEITO de '{meta.get('source')}' "
            f"(chunk {meta.get('chunk')}) — distância={dist:.4f}"
        )

    return retrieved
