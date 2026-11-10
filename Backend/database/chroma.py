"""
Local ChromaDB adapter (PersistentClient). No server auth in this mode.
Partition: one collection per user_id. Metadata maps back to Mongo record IDs.
Cloud Chroma switch is out of scope until explicitly requested.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

_client = None
_COLLECTION_PREFIX = "user_"


def _persist_dir() -> str:
    load_dotenv()
    configured = os.environ.get("CHROMA_PERSIST_DIR")
    if configured:
        return configured
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend_root, "vector_store")


def _sanitize_user_id(user_id: str) -> str:
    raw = (user_id or "anonymous").strip()
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw)
    return cleaned[:128] or "anonymous"


def collection_name_for_user(user_id: str) -> str:
    return f"{_COLLECTION_PREFIX}{_sanitize_user_id(user_id)}"


def _null_embedding_function():
    """
    Chroma still wants an EmbeddingFunction type, but we always pass embeddings
    from Gemini/OpenAI ourselves — never use Chroma's default ONNX downloader.
    """
    try:
        from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
    except Exception:
        return None

    class _NullEF(EmbeddingFunction):
        def __call__(self, input: Documents) -> Embeddings:
            # Deterministic tiny vectors if Chroma ever calls us without embeddings.
            out = []
            for text in input:
                raw = (text or "").encode("utf-8")
                seed = sum(raw) % 997
                out.append([((seed + i) % 100) / 100.0 for i in range(32)])
            return out

    return _NullEF()


def get_chroma_client():
    """Lazy PersistentClient singleton."""
    global _client
    if _client is not None:
        return _client
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError as e:
        raise ImportError(
            "chromadb is required for vector storage. Install with: pip install chromadb"
        ) from e

    path = _persist_dir()
    os.makedirs(path, exist_ok=True)
    _client = chromadb.PersistentClient(
        path=path,
        settings=Settings(anonymized_telemetry=False),
    )
    return _client


def get_user_collection(user_id: str):
    client = get_chroma_client()
    name = collection_name_for_user(user_id)
    # Prefer get without re-declaring embedding_function (avoids conflict with
    # collections created earlier under Chroma's default ONNX EF).
    try:
        return client.get_collection(name=name)
    except Exception:
        pass
    kwargs = {"name": name, "metadata": {"hnsw:space": "cosine"}}
    ef = _null_embedding_function()
    if ef is not None:
        kwargs["embedding_function"] = ef
    return client.get_or_create_collection(**kwargs)


def upsert_chunks(
    user_id: str,
    ids: List[str],
    documents: List[str],
    embeddings: Optional[List[List[float]]] = None,
    metadatas: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Upsert chunk texts (and optional precomputed embeddings) for a user."""
    if not ids:
        return 0
    if len(ids) != len(documents):
        raise ValueError("ids and documents length mismatch")
    if metadatas is not None and len(metadatas) != len(ids):
        raise ValueError("metadatas length mismatch")
    if embeddings is not None and len(embeddings) != len(ids):
        raise ValueError("embeddings length mismatch")

    collection = get_user_collection(user_id)
    if embeddings is None:
        # Avoid Chroma default model download: synthesize stable local vectors.
        embeddings = []
        for text in documents:
            raw = (text or "").encode("utf-8")
            seed = sum(raw) % 997
            embeddings.append([((seed + i) % 100) / 100.0 for i in range(32)])
    kwargs = {
        "ids": ids,
        "documents": documents,
        "metadatas": metadatas or [{"user_id": user_id} for _ in ids],
        "embeddings": embeddings,
    }
    collection.upsert(**kwargs)
    return len(ids)


def query_chunks(
    user_id: str,
    query_texts: Optional[List[str]] = None,
    query_embeddings: Optional[List[List[float]]] = None,
    n_results: int = 50,
    where: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Query a user's collection. Prefer query_embeddings when available."""
    collection = get_user_collection(user_id)
    kwargs: Dict[str, Any] = {"n_results": max(1, int(n_results))}
    if where:
        kwargs["where"] = where
    if query_embeddings is not None:
        kwargs["query_embeddings"] = query_embeddings
    elif query_texts is not None:
        kwargs["query_texts"] = query_texts
    else:
        raise ValueError("Provide query_embeddings or query_texts")
    return collection.query(**kwargs)


def delete_by_case(user_id: str, case_id: str) -> None:
    """Delete all chunks for a case in the user's collection."""
    if not case_id:
        return
    collection = get_user_collection(user_id)
    try:
        collection.delete(where={"case_id": case_id})
    except Exception as e:
        print(f"LOG: chroma delete_by_case failed ({type(e).__name__}: {e})")


def delete_ids(user_id: str, ids: List[str]) -> None:
    if not ids:
        return
    collection = get_user_collection(user_id)
    try:
        collection.delete(ids=ids)
    except Exception as e:
        print(f"LOG: chroma delete_ids failed ({type(e).__name__}: {e})")


def list_documents_for_case(user_id: str, case_id: str, limit: int = 10000) -> Dict[str, Any]:
    """Fetch stored chunks for BM25 rebuild / inspection."""
    collection = get_user_collection(user_id)
    try:
        return collection.get(
            where={"case_id": case_id},
            include=["documents", "metadatas", "embeddings"],
            limit=limit,
        )
    except TypeError:
        # Older chroma may not accept limit the same way
        return collection.get(
            where={"case_id": case_id},
            include=["documents", "metadatas", "embeddings"],
        )
    except Exception as e:
        print(f"LOG: chroma list_documents_for_case failed ({type(e).__name__}: {e})")
        return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
