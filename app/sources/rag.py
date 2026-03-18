"""ChromaDB vector search for repair manual documentation."""
from __future__ import annotations

import chromadb
from openai import OpenAI

from ..config import settings

_chroma_client: chromadb.PersistentClient | None = None
_openai_client: OpenAI | None = None


def _get_chroma() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _embed(text: str) -> list[float]:
    response = _get_openai().embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def search(
    query: str,
    locomotive_model: str | None = None,
    n_results: int = 5,
) -> list[dict]:
    """Search repair manuals in the vector store.

    Returns list of dicts with keys: text, metadata, distance.
    """
    collection = _get_chroma().get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    query_embedding = _embed(query)

    where_filter = None
    if locomotive_model:
        where_filter = {"locomotive_model": locomotive_model.strip()}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    output: list[dict] = []
    if results["documents"] and results["documents"][0]:
        for i in range(len(results["documents"][0])):
            output.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
    return output
