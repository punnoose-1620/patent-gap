"""
Parent-child hierarchical chunking for claims, descriptions, and product text.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional


def _approx_tokens(text: str) -> int:
    # Rough heuristic: ~4 chars/token
    return max(1, len(text or "") // 4)


def _split_windows(text: str, target_tokens: int = 600, overlap_ratio: float = 0.12) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if _approx_tokens(text) <= target_tokens:
        return [text]

    # Prefer sentence-ish splits, then hard char windows
    parts = re.split(r"(?<=[.:;!?])\s+|\n+", text)
    parts = [p.strip() for p in parts if p and p.strip()]
    if not parts:
        parts = [text]

    windows: List[str] = []
    current: List[str] = []
    current_tokens = 0
    overlap_tokens = max(20, int(target_tokens * overlap_ratio))

    for part in parts:
        pt = _approx_tokens(part)
        if current and current_tokens + pt > target_tokens:
            windows.append(" ".join(current).strip())
            # overlap: keep trailing bits
            overlap: List[str] = []
            ot = 0
            for piece in reversed(current):
                overlap.insert(0, piece)
                ot += _approx_tokens(piece)
                if ot >= overlap_tokens:
                    break
            current = overlap
            current_tokens = sum(_approx_tokens(x) for x in current)
        current.append(part)
        current_tokens += pt

    if current:
        windows.append(" ".join(current).strip())
    return [w for w in windows if w]


def _stable_id(*parts: str) -> str:
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def build_parent_child_chunks(
    *,
    user_id: str,
    case_id: str,
    record_id: str,
    source: str,
    chunk_type: str,
    parents: List[str],
    target_child_tokens: int = 600,
) -> List[Dict[str, Any]]:
    """
    Returns list of chunk dicts ready for embedding + Chroma upsert:
    id, document, metadata (includes parent_id, chunk_type, etc.)
    """
    chunks: List[Dict[str, Any]] = []
    for p_idx, parent_text in enumerate(parents or []):
        parent_text = (parent_text or "").strip()
        if not parent_text:
            continue
        parent_id = _stable_id(user_id, case_id, record_id, chunk_type, "parent", str(p_idx), parent_text[:200])
        # Parent row
        chunks.append(
            {
                "id": parent_id,
                "document": parent_text,
                "metadata": {
                    "user_id": user_id,
                    "case_id": case_id,
                    "record_id": record_id or case_id,
                    "chunk_id": parent_id,
                    "parent_id": parent_id,
                    "chunk_type": chunk_type,
                    "source": source or "",
                    "is_parent": True,
                    "parent_index": p_idx,
                },
            }
        )
        children = _split_windows(parent_text, target_tokens=target_child_tokens)
        # If only one window equal to parent, skip duplicate children
        if len(children) == 1 and children[0] == parent_text:
            continue
        for c_idx, child_text in enumerate(children):
            child_id = _stable_id(parent_id, "child", str(c_idx), child_text[:120])
            chunks.append(
                {
                    "id": child_id,
                    "document": child_text,
                    "metadata": {
                        "user_id": user_id,
                        "case_id": case_id,
                        "record_id": record_id or case_id,
                        "chunk_id": child_id,
                        "parent_id": parent_id,
                        "chunk_type": chunk_type,
                        "source": source or "",
                        "is_parent": False,
                        "parent_index": p_idx,
                        "child_index": c_idx,
                    },
                }
            )
    return chunks


def claims_to_parents(claims: Optional[List[str]]) -> List[str]:
    return [c.strip() for c in (claims or []) if isinstance(c, str) and c.strip()]
