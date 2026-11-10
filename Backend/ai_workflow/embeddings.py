"""
Embedding helpers for RAG index.
Primary: Gemini. Fallback: OpenAI text-embedding-3-small. Then None (BM25-only).
"""
from __future__ import annotations

from typing import List, Optional

from ai_workflow.config import get_gemini_embedding_model
from env_controller import getEnvKey


def embed_texts_gemini(texts: List[str]) -> Optional[List[List[float]]]:
    if not texts:
        return []
    api_key = getEnvKey("gemini")
    if not api_key:
        return None
    model = get_gemini_embedding_model()
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        out: List[List[float]] = []
        for text in texts:
            content = (text or " ").strip() or " "
            result = client.models.embed_content(model=model, contents=content)
            # google-genai response shapes vary by version
            emb = None
            if hasattr(result, "embeddings") and result.embeddings:
                first = result.embeddings[0]
                emb = getattr(first, "values", None) or getattr(first, "embedding", None)
            if emb is None and hasattr(result, "embedding"):
                emb = getattr(result.embedding, "values", None) or result.embedding
            if emb is None:
                return None
            out.append(list(emb))
        return out
    except Exception as e:
        print(f"LOG: embed_texts_gemini failed ({type(e).__name__}: {e})")
        return None


def embed_texts_openai(texts: List[str], model: str = "text-embedding-3-small") -> Optional[List[List[float]]]:
    if not texts:
        return []
    api_key = getEnvKey("openai")
    if not api_key:
        # Empty / none / null OPENAI_API_KEY → skip; caller uses local/BM25 backup.
        return None
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        out: List[List[float]] = []
        for text in texts:
            content = (text or " ").strip() or " "
            response = client.embeddings.create(model=model, input=content)
            out.append(list(response.data[0].embedding))
        return out
    except Exception as e:
        print(f"LOG: embed_texts_openai failed ({type(e).__name__}: {e})")
        return None


def embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """Primary Gemini → OpenAI fallback (if configured) → None."""
    vectors = embed_texts_gemini(texts)
    if vectors is not None:
        return vectors
    return embed_texts_openai(texts)


def embed_query(text: str) -> Optional[List[float]]:
    vectors = embed_texts([text or " "])
    if not vectors:
        return None
    return vectors[0]
