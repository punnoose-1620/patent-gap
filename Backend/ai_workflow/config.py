"""Runtime flags for RAG / AI workflow."""
from __future__ import annotations

import os
from dotenv import load_dotenv


def get_workflow_mode() -> str:
    load_dotenv()
    mode = (os.environ.get("AI_WORKFLOW_MODE") or "rag").strip().lower()
    if mode not in ("legacy", "rag"):
        return "rag"
    return mode


def is_rag_mode() -> bool:
    return get_workflow_mode() == "rag"


def get_chroma_persist_dir() -> str:
    load_dotenv()
    configured = os.environ.get("CHROMA_PERSIST_DIR")
    if configured:
        return configured
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend_root, "vector_store")


def get_gemini_embedding_model() -> str:
    load_dotenv()
    return os.environ.get("GEMINI_EMBEDDING_MODEL") or "text-embedding-004"


def get_rag_top_k() -> int:
    load_dotenv()
    try:
        return max(1, int(os.environ.get("RAG_TOP_K") or 50))
    except ValueError:
        return 50


def get_rag_rerank_k() -> int:
    load_dotenv()
    try:
        return max(1, int(os.environ.get("RAG_RERANK_K") or 15))
    except ValueError:
        return 15


def get_cross_encoder_model() -> str:
    load_dotenv()
    return (
        os.environ.get("RAG_CROSS_ENCODER_MODEL")
        or "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
