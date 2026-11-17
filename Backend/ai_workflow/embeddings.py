"""
Embedding helpers for RAG index.
Primary: Gemini → OpenAI text-embedding-3-small → local TF-IDF (HashingVectorizer).
Local TF-IDF is last-resort only so dense retrieve still has a shared vector space
when both APIs fail (same n_features for index and query).
"""
from __future__ import annotations

from typing import List, Optional

from ai_workflow.config import get_gemini_embedding_model
from env_controller import getEnvKey

# Fixed dim so index + query share a space without a persisted vocabulary.
_TFIDF_N_FEATURES = 384
_hashing_vectorizer = None
# Skip repeated Gemini calls after a hard failure (e.g. model 404).
_gemini_unavailable = False


def embed_texts_gemini(texts: List[str]) -> Optional[List[List[float]]]:
    global _gemini_unavailable
    if not texts:
        return []
    if _gemini_unavailable:
        return None
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
                _gemini_unavailable = True
                print(
                    f"LOG: embed_texts_gemini returned no embedding "
                    f"(model={model}); skipping further Gemini embed attempts"
                )
                return None
            out.append(list(emb))
        return out
    except Exception as e:
        _gemini_unavailable = True
        print(
            f"LOG: embed_texts_gemini failed ({type(e).__name__}: {e}); "
            "skipping further Gemini embed attempts"
        )
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


def _get_hashing_vectorizer():
    global _hashing_vectorizer
    if _hashing_vectorizer is None:
        from sklearn.feature_extraction.text import HashingVectorizer

        _hashing_vectorizer = HashingVectorizer(
            n_features=_TFIDF_N_FEATURES,
            alternate_sign=False,
            norm="l2",
            lowercase=True,
            ngram_range=(1, 2),
        )
    return _hashing_vectorizer


def embed_texts_tfidf(texts: List[str]) -> Optional[List[List[float]]]:
    """
    Last-resort local embeddings via HashingVectorizer (TF-IDF-style).
    Not a primary quality path — only used when Gemini and OpenAI both fail.
    """
    if not texts:
        return []
    try:
        docs = [(t or " ").strip() or " " for t in texts]
        matrix = _get_hashing_vectorizer().transform(docs)
        dense = matrix.toarray()
        return [row.tolist() for row in dense]
    except Exception as e:
        print(f"LOG: embed_texts_tfidf failed ({type(e).__name__}: {e})")
        return None


def embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """Primary Gemini → OpenAI → local TF-IDF → None."""
    vectors = embed_texts_gemini(texts)
    if vectors is not None:
        return vectors
    vectors = embed_texts_openai(texts)
    if vectors is not None:
        return vectors
    print("LOG: embed_texts falling back to local TF-IDF (HashingVectorizer)")
    return embed_texts_tfidf(texts)


def embed_query(text: str) -> Optional[List[float]]:
    vectors = embed_texts([text or " "])
    if not vectors:
        return None
    return vectors[0]
