"""
Append-only AI activity audit log (Mongo).

Immutable history: add + read only. No update/delete helpers.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from database import addDataById, connect_to_database, getDataById, paginateDataByQuery
from env_controller import getAuditDatabaseName

AUDIT_KINDS = frozenset(
    {
        "patent_fetch",
        "analysis_start",
        "analysis_complete",
        "analysis_failed",
        "clarification",
        "chat_message",
        "case_update_via_ai",
        "mcp_action",
        "manual_relevance",
    }
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_audit_entry(
    *,
    user_id: str,
    case_id: str,
    kind: str,
) -> tuple[bool, str]:
    if not isinstance(user_id, str) or not user_id.strip():
        return False, "user_id is required"
    if not isinstance(case_id, str) or not case_id.strip():
        return False, "case_id is required"
    if kind not in AUDIT_KINDS:
        return False, f"kind must be one of: {', '.join(sorted(AUDIT_KINDS))}"
    return True, ""


def add_audit_entry(
    user_id: str,
    case_id: str,
    kind: str,
    *,
    text: str = "",
    payload: Optional[dict] = None,
    status: str = "",
    request_id: str = "",
    source: str = "",
) -> str | bool:
    """
    Insert one immutable audit row. Returns new _id, or False on validation/write failure.
    Never raises to callers (logging failures must not break product flows).
    """
    try:
        ok, error = validate_audit_entry(user_id=user_id, case_id=case_id, kind=kind)
        if not ok:
            print(f"LOG: audit entry rejected: {error}")
            return False

        entry: dict[str, Any] = {
            "_id": str(uuid.uuid4()),
            "user_id": user_id.strip(),
            "case_id": case_id.strip(),
            "kind": kind,
            "text": text or "",
            "payload": payload if isinstance(payload, dict) else {},
            "status": status or "",
            "request_id": request_id or "",
            "source": source or "",
            "created_at": _now_iso(),
        }
        added_id = addDataById(connect_to_database(), getAuditDatabaseName(), entry)
        if not added_id or "DocumentCreationError" in str(added_id):
            print(f"LOG: audit insert failed: {added_id}")
            return False
        return str(added_id)
    except Exception as e:
        print(f"LOG: add_audit_entry failed ({type(e).__name__}: {e})")
        return False


def get_audit_by_user_id(
    user_id: str,
    page: int = 1,
    kind: Optional[str] = None,
) -> dict:
    """Paginated audit rows for an attorney/user (newest first)."""
    if not isinstance(user_id, str) or not user_id.strip():
        return {
            "items": [],
            "pagination": {
                "page": 1,
                "page_size": 0,
                "total": 0,
                "total_pages": 0,
                "has_next": False,
            },
        }
    query: dict[str, Any] = {"user_id": user_id.strip()}
    if kind:
        if kind not in AUDIT_KINDS:
            print(f"LOG: get_audit_by_user_id ignored unknown kind={kind!r}")
        else:
            query["kind"] = kind
    return paginateDataByQuery(
        connect_to_database(),
        getAuditDatabaseName(),
        query=query,
        page=page,
        sort_field="created_at",
        sort_direction=-1,
    )


def get_audit_by_case_id(
    case_id: str,
    page: int = 1,
    kind: Optional[str] = None,
) -> dict:
    """Paginated audit rows for a Mongo case id (newest first)."""
    if not isinstance(case_id, str) or not case_id.strip():
        return {
            "items": [],
            "pagination": {
                "page": 1,
                "page_size": 0,
                "total": 0,
                "total_pages": 0,
                "has_next": False,
            },
        }
    query: dict[str, Any] = {"case_id": case_id.strip()}
    if kind:
        if kind not in AUDIT_KINDS:
            print(f"LOG: get_audit_by_case_id ignored unknown kind={kind!r}")
        else:
            query["kind"] = kind
    return paginateDataByQuery(
        connect_to_database(),
        getAuditDatabaseName(),
        query=query,
        page=page,
        sort_field="created_at",
        sort_direction=-1,
    )


def get_audit_by_id(audit_id: str) -> Optional[dict]:
    """Read a single audit row by id (read-only)."""
    if not isinstance(audit_id, str) or not audit_id.strip():
        return None
    try:
        return getDataById(connect_to_database(), getAuditDatabaseName(), audit_id.strip())
    except Exception as e:
        print(f"LOG: get_audit_by_id failed ({type(e).__name__}: {e})")
        return None
