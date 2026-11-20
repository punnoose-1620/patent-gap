"""
Index claims / product text into local Chroma for a user+case.
"""
from __future__ import annotations

from typing import List, Optional

from ai_workflow.chunking import build_parent_child_chunks, claims_to_parents
from ai_workflow.embeddings import embed_texts
from database import chroma


def index_claim_texts(
    *,
    user_id: str,
    case_id: str,
    claims: List[str],
    record_id: Optional[str] = None,
    source: str = "",
    chunk_type: str = "claim",
    replace_case_chunks: bool = False,
) -> int:
    """Chunk + embed + upsert claim (or description/product) texts. Returns upsert count."""
    if not user_id or not case_id:
        return 0
    parents = claims_to_parents(claims)
    if not parents:
        return 0

    if replace_case_chunks:
        # Only delete same chunk_type for this case to avoid wiping other types
        existing = chroma.list_documents_for_case(user_id, case_id)
        ids_to_delete = []
        for i, meta in enumerate(existing.get("metadatas") or []):
            if not meta:
                continue
            if meta.get("chunk_type") == chunk_type and existing.get("ids"):
                ids_to_delete.append(existing["ids"][i])
        if ids_to_delete:
            chroma.delete_ids(user_id, ids_to_delete)

    chunks = build_parent_child_chunks(
        user_id=user_id,
        case_id=case_id,
        record_id=record_id or case_id,
        source=source,
        chunk_type=chunk_type,
        parents=parents,
    )
    if not chunks:
        return 0

    documents = [c["document"] for c in chunks]
    ids = [c["id"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    # Chroma metadata values must be scalar
    for meta in metadatas:
        for k, v in list(meta.items()):
            if isinstance(v, bool):
                meta[k] = bool(v)
            elif v is None:
                meta[k] = ""
            elif not isinstance(v, (str, int, float, bool)):
                meta[k] = str(v)

    embeddings = embed_texts(documents)
    if embeddings is None:
        # Store documents without embeddings; hybrid can still use BM25 + query_texts
        print("LOG: indexing without dense embeddings (embed_texts returned None)")
        return chroma.upsert_chunks(user_id, ids, documents, embeddings=None, metadatas=metadatas)

    return chroma.upsert_chunks(user_id, ids, documents, embeddings=embeddings, metadatas=metadatas)


def ensure_case_claims_indexed(user_id: str, case_id: str, claims: List[str], source: str = "") -> int:
    """Lazy index: upsert if case has no claim chunks yet."""
    existing = chroma.list_documents_for_case(user_id, case_id)
    metas = existing.get("metadatas") or []
    has_claims = any((m or {}).get("chunk_type") == "claim" for m in metas)
    if has_claims:
        return 0
    return index_claim_texts(
        user_id=user_id,
        case_id=case_id,
        claims=claims,
        source=source,
        chunk_type="claim",
    )
