"""
Hybrid retrieval: BM25 + dense (Chroma) → RRF fuse → optional cross-encoder rerank.
Used to shortlist candidates and avoid full O(N×M) when corpus is large.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ai_workflow.config import get_cross_encoder_model, get_rag_rerank_k, get_rag_top_k
from ai_workflow.embeddings import embed_query
from database import chroma

_cross_encoder = None


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is not None:
        return _cross_encoder
    try:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(get_cross_encoder_model())
        return _cross_encoder
    except Exception as e:
        print(f"LOG: cross-encoder unavailable ({type(e).__name__}: {e})")
        _cross_encoder = False
        return None


def _rrf_fuse(rank_lists: List[List[str]], k: int = 60) -> List[str]:
    scores: Dict[str, float] = {}
    for ranked in rank_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def _bm25_rank(query: str, doc_ids: List[str], documents: List[str], top_k: int) -> List[str]:
    if not documents:
        return []
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        print("LOG: rank_bm25 not installed; skipping BM25")
        return []

    tokenized_corpus = [(d or "").lower().split() for d in documents]
    tokenized_query = (query or "").lower().split()
    if not tokenized_query:
        return []
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(tokenized_query)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [doc_ids[i] for i in ranked]


def retrieve_similar_texts(
    *,
    user_id: str,
    case_id: str,
    query_text: str,
    chunk_type: Optional[str] = None,
    top_k: Optional[int] = None,
    rerank_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Return shortlisted chunks: [{id, document, metadata, score}, ...]
    Parents preferred when child hits.
    """
    top_k = top_k or get_rag_top_k()
    rerank_k = rerank_k or get_rag_rerank_k()
    query_text = (query_text or "").strip()
    if not user_id or not case_id or not query_text:
        return []

    where: Dict[str, Any] = {"case_id": case_id}
    if chunk_type:
        where["chunk_type"] = chunk_type

    stored = chroma.list_documents_for_case(user_id, case_id)
    ids = list(stored.get("ids") or [])
    documents = list(stored.get("documents") or [])
    metadatas = list(stored.get("metadatas") or [])

    # Filter by chunk_type in-memory if needed
    if chunk_type:
        filtered = [
            (i, d, m)
            for i, d, m in zip(ids, documents, metadatas)
            if (m or {}).get("chunk_type") == chunk_type
        ]
        if filtered:
            ids, documents, metadatas = map(list, zip(*filtered))
        else:
            ids, documents, metadatas = [], [], []

    if not ids:
        return []

    id_to_doc = {i: d for i, d in zip(ids, documents)}
    id_to_meta = {i: (m or {}) for i, m in zip(ids, metadatas)}

    bm25_ranked = _bm25_rank(query_text, ids, documents, top_k)

    dense_ranked: List[str] = []
    q_emb = embed_query(query_text)
    try:
        if q_emb is not None:
            result = chroma.query_chunks(
                user_id,
                query_embeddings=[q_emb],
                n_results=min(top_k, len(ids)),
                where=where,
            )
        else:
            result = chroma.query_chunks(
                user_id,
                query_texts=[query_text],
                n_results=min(top_k, len(ids)),
                where=where,
            )
        dense_ranked = list((result.get("ids") or [[]])[0] or [])
    except Exception as e:
        print(f"LOG: dense retrieve failed ({type(e).__name__}: {e})")

    fused = _rrf_fuse([bm25_ranked, dense_ranked])[:top_k]
    if not fused:
        fused = bm25_ranked or dense_ranked or ids[:top_k]

    # Map children → parent documents when available
    candidates: List[Dict[str, Any]] = []
    seen_parents = set()
    for doc_id in fused:
        meta = id_to_meta.get(doc_id) or {}
        parent_id = meta.get("parent_id") or doc_id
        if parent_id in seen_parents:
            continue
        seen_parents.add(parent_id)
        parent_doc = id_to_doc.get(parent_id) or id_to_doc.get(doc_id) or ""
        parent_meta = id_to_meta.get(parent_id) or meta
        candidates.append(
            {
                "id": parent_id,
                "document": parent_doc,
                "metadata": parent_meta,
                "score": 0.0,
            }
        )

    # Cross-encoder rerank
    encoder = _get_cross_encoder()
    if encoder and candidates:
        try:
            pairs = [[query_text, c["document"]] for c in candidates]
            scores = encoder.predict(pairs)
            for c, s in zip(candidates, scores):
                c["score"] = float(s)
            candidates.sort(key=lambda x: x["score"], reverse=True)
        except Exception as e:
            print(f"LOG: rerank failed ({type(e).__name__}: {e})")

    return candidates[:rerank_k]


def shortlist_claim_pairs(
    reference_claims: List[str],
    infringing_claims: List[str],
    *,
    user_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """
    When RAG mode + index available: for each ref claim, retrieve top infringing
    candidates instead of full Cartesian product.
    Falls back to full product if retrieval cannot run.
    """
    from itertools import product

    refs = [c.strip() for c in (reference_claims or []) if isinstance(c, str) and c.strip()]
    infs = [c.strip() for c in (infringing_claims or []) if isinstance(c, str) and c.strip()]
    if not refs or not infs:
        return []

    # Small matrices: full product is fine and preserves legacy behavior
    if len(refs) * len(infs) <= 200:
        return list(product(refs, infs))

    if not user_id or not case_id:
        return list(product(refs, infs))

    try:
        from ai_workflow.indexing import ensure_case_claims_indexed

        ensure_case_claims_indexed(user_id, case_id, infs, source="infringing")
        pairs = []
        seen = set()
        rerank_k = get_rag_rerank_k()
        for ref in refs:
            hits = retrieve_similar_texts(
                user_id=user_id,
                case_id=case_id,
                query_text=ref,
                chunk_type="claim",
                rerank_k=rerank_k,
            )
            hit_texts = {h["document"] for h in hits if h.get("document")}
            # Match retrieved parent texts back to infringing claim list
            for inf in infs:
                if inf in hit_texts or any(inf in h or h in inf for h in hit_texts):
                    key = (ref, inf)
                    if key not in seen:
                        seen.add(key)
                        pairs.append(key)
            # Ensure at least some pairs per ref if retrieval miss
            if not any(r == ref for r, _ in pairs):
                for inf in infs[:rerank_k]:
                    key = (ref, inf)
                    if key not in seen:
                        seen.add(key)
                        pairs.append(key)
        return pairs or list(product(refs, infs))
    except Exception as e:
        print(f"LOG: shortlist_claim_pairs failed ({type(e).__name__}: {e}); full matrix")
        return list(product(refs, infs))
