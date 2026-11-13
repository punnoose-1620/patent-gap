"""
FastMCP / MCPServer tools wrapping internal patent-gap functions.
In-process / local use — not a public networked product API in this phase.

Processing tools require user_id + case_id and append an audit row.
Read/get tools do not write audit entries.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

FastMCP = None
_MCP_IMPL = None

try:
    from fastmcp import FastMCP as _FM

    FastMCP = _FM
    _MCP_IMPL = "fastmcp"
except Exception:
    try:
        from mcp.server.mcpserver import MCPServer as _FM

        FastMCP = _FM
        _MCP_IMPL = "mcp.server.mcpserver"
    except Exception:
        try:
            from mcp.server.fastmcp import FastMCP as _FM

            FastMCP = _FM
            _MCP_IMPL = "mcp.server.fastmcp"
        except Exception as e:
            print(f"LOG: MCP server library unavailable ({type(e).__name__}: {e})")
            FastMCP = None
            _MCP_IMPL = None


def _require_ids(user_id: str, case_id: str) -> None:
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id is required")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id is required")


def _audit_mcp_action(
    user_id: str,
    case_id: str,
    tool_name: str,
    *,
    text: str = "",
    payload: Optional[Dict[str, Any]] = None,
    status: str = "completed",
) -> None:
    """Append mcp_action audit for processing tools only (never for getters)."""
    try:
        from structures.audit import add_audit_entry

        add_audit_entry(
            user_id=user_id,
            case_id=case_id,
            kind="mcp_action",
            text=text or f"MCP tool {tool_name}",
            payload={"tool": tool_name, **(payload or {})},
            status=status,
            source="mcp",
        )
    except Exception as e:
        print(f"LOG: MCP audit skipped ({type(e).__name__}: {e})")


def _build_mcp():
    if FastMCP is None:
        return None
    mcp = FastMCP("patent-gap")

    @mcp.tool()
    def extract_patent_metadata(
        user_id: str,
        case_id: str,
        patent_content: str,
        default_source: str = "",
    ) -> Any:
        """Extract structured patent metadata from raw patent HTML/text via Gemini."""
        _require_ids(user_id, case_id)
        from ai_workflow.orchestration import get_ai_client

        result = get_ai_client().extract_patent_metadata(
            patent_content=patent_content,
            default_source=default_source or None,
        )
        _audit_mcp_action(
            user_id,
            case_id,
            "extract_patent_metadata",
            text="Extracted patent metadata via MCP",
            payload={"default_source": default_source or ""},
        )
        return result

    @mcp.tool()
    def extract_claims(user_id: str, case_id: str, patent_content: str) -> Any:
        """Extract claims from patent content."""
        _require_ids(user_id, case_id)
        from ai_workflow.orchestration import get_ai_client

        result = get_ai_client().extract_claims(patent_content=patent_content)
        _audit_mcp_action(
            user_id,
            case_id,
            "extract_claims",
            text="Extracted patent claims via MCP",
        )
        return result

    @mcp.tool()
    def index_case_claims(
        user_id: str,
        case_id: str,
        claims: List[str],
        source: str = "",
        chunk_type: str = "claim",
    ) -> int:
        """Chunk and upsert claim texts into the local Chroma index for a user/case."""
        _require_ids(user_id, case_id)
        from ai_workflow.indexing import index_claim_texts

        count = index_claim_texts(
            user_id=user_id,
            case_id=case_id,
            claims=claims,
            source=source,
            chunk_type=chunk_type,
            replace_case_chunks=True,
        )
        _audit_mcp_action(
            user_id,
            case_id,
            "index_case_claims",
            text="Indexed case claims into vector store via MCP",
            payload={"chunk_type": chunk_type, "claim_count": len(claims or []), "upserted": count},
        )
        return count

    @mcp.tool()
    def hybrid_retrieve(
        user_id: str,
        case_id: str,
        query_text: str,
        chunk_type: str = "claim",
    ) -> List[Dict[str, Any]]:
        """BM25 + dense + rerank retrieval over a user's case chunks (read-only; no audit)."""
        _require_ids(user_id, case_id)
        from ai_workflow.hybrid_retrieve import retrieve_similar_texts

        return retrieve_similar_texts(
            user_id=user_id,
            case_id=case_id,
            query_text=query_text,
            chunk_type=chunk_type or None,
        )

    @mcp.tool()
    def analyze_infringements(
        user_id: str,
        case_id: str,
        reference_claims: List[str],
        infringing_claims: List[str],
        context: str = "",
    ) -> Any:
        """Run Gemini infringement analysis on claim sets."""
        _require_ids(user_id, case_id)
        from ai_workflow.orchestration import get_ai_client

        result = get_ai_client().analyze_infringements(
            reference_claims, infringing_claims, context
        )
        _audit_mcp_action(
            user_id,
            case_id,
            "analyze_infringements",
            text="Ran infringement analysis via MCP",
            payload={
                "reference_claim_count": len(reference_claims or []),
                "infringing_claim_count": len(infringing_claims or []),
            },
        )
        return result

    @mcp.tool()
    def get_case_context(user_id: str, case_id: str) -> Optional[Dict[str, Any]]:
        """Load a case document from Mongo by id (read-only; no audit)."""
        _require_ids(user_id, case_id)
        from structures.cases import get_case_by_id

        return get_case_by_id(case_id)

    @mcp.tool()
    def score_claim_matrix(
        user_id: str,
        case_id: str,
        reference_claims: List[str],
        infringing_claims: List[str],
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Score reference x infringing claims (RAG shortlist when enabled)."""
        _require_ids(user_id, case_id)
        from scorer import score_infringement_matrix_entry

        stored, chart = score_infringement_matrix_entry(
            reference_claims,
            infringing_claims,
            None,
            threshold=threshold,
            user_id=user_id,
            case_id=case_id,
        )
        _audit_mcp_action(
            user_id,
            case_id,
            "score_claim_matrix",
            text="Scored claim matrix via MCP",
            payload={
                "threshold": threshold,
                "reference_claim_count": len(reference_claims or []),
                "infringing_claim_count": len(infringing_claims or []),
            },
        )
        return {"stored_rows": stored, "chart_rows": chart}

    @mcp.tool()
    def get_audit_by_case_id(
        user_id: str,
        case_id: str,
        page: int = 1,
        kind: str = "",
    ) -> Dict[str, Any]:
        """Fetch immutable AI audit history for a case (read-only; no audit)."""
        _require_ids(user_id, case_id)
        from structures.audit import get_audit_by_case_id as _get

        return _get(case_id, page=page, kind=kind or None)

    @mcp.tool()
    def get_audit_by_user_id(
        user_id: str,
        case_id: str,
        page: int = 1,
        kind: str = "",
    ) -> Dict[str, Any]:
        """
        Fetch immutable AI audit history for a user (read-only; no audit).
        case_id is required for MCP consistency / ACL context even though the
        query is keyed by user_id.
        """
        _require_ids(user_id, case_id)
        from structures.audit import get_audit_by_user_id as _get

        return _get(user_id, page=page, kind=kind or None)

    @mcp.tool()
    def search_product_manuals(
        user_id: str,
        case_id: str,
        product_name: str,
        listing_features: List[str],
        official_sites: Optional[List[str]] = None,
        kind: str = "instruction",
        max_results: int = 3,
        product_url: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Search instruction/repair manuals only (not product listings).
        Uses GCSE operator queries + a Gemini manuals-only rule brief, then
        filters/ranks out PDPs and the product's own listing URL.
        Skips search when the listing has no concrete model/SKU.
        Does not attach anything to the case.
        """
        _require_ids(user_id, case_id)
        from live_search.product_manuals import search_manual_urls

        return search_manual_urls(
            user_id=user_id,
            case_id=case_id,
            product_name=product_name,
            listing_features=listing_features or [],
            official_sites=official_sites or [],
            kind=kind,
            max_results=max_results,
            product_url=product_url or "",
            require_sku=True,
        )

    @mcp.tool()
    def fetch_manual_for_inspection(
        user_id: str,
        case_id: str,
        url: str,
    ) -> Dict[str, Any]:
        """
        Download a manual URL (HTML or PDF) into a temp cache and return a text
        preview for agent inspection. Does NOT write to cases/documents.
        """
        _require_ids(user_id, case_id)
        from live_search.product_manuals import fetch_url_for_inspection

        result = fetch_url_for_inspection(user_id=user_id, case_id=case_id, url=url)
        _audit_mcp_action(
            user_id,
            case_id,
            "fetch_manual_for_inspection",
            text=f"Fetched manual candidate for inspection: {url}",
            payload={
                "url": url,
                "success": bool(result.get("success")),
                "cache_id": result.get("cache_id") or "",
                "is_pdf": bool(result.get("is_pdf")),
            },
            status="completed" if result.get("success") else "failed",
        )
        return result

    @mcp.tool()
    def assess_manual_relevance(
        user_id: str,
        case_id: str,
        product_name: str,
        listing_features: List[str],
        cache_id: str = "",
        manual_text: str = "",
        manual_url: str = "",
    ) -> Dict[str, Any]:
        """
        Validity + relevance check for a candidate manual.
        Product listings / marketing pages are invalid even if features match.
        Accept only instruction/repair/service-style docs for the SAME SKU/variant.
        Audited. Rejected candidates are not attachable and are dropped from cache.
        """
        _require_ids(user_id, case_id)
        from live_search.product_manuals import (
            assess_manual_relevance as _assess,
            get_manual_cache_entry,
        )

        text = manual_text
        url = manual_url
        cached = get_manual_cache_entry(cache_id) if cache_id else None
        if cached:
            text = text or cached.get("text") or ""
            url = url or cached.get("url") or ""
        return _assess(
            user_id=user_id,
            case_id=case_id,
            product_name=product_name,
            listing_features=listing_features or [],
            manual_text=text,
            manual_url=url,
            cache_id=cache_id,
        )

    @mcp.tool()
    def attach_verified_manual_to_case(
        user_id: str,
        case_id: str,
        cache_id: str,
        source_tag: str = "instruction_manual",
        file_name: str = "",
        append_claims: bool = True,
        product_name: str = "",
    ) -> Dict[str, Any]:
        """
        Attach a previously inspected+accepted manual to case.documents.
        Only works for cache entries that passed assess_manual_relevance.
        Optionally returns extracted claims to append to the product claims list.
        """
        _require_ids(user_id, case_id)
        from live_search.product_manuals import (
            attach_cached_manual_to_case,
            extract_claims_from_manual_text,
            get_manual_cache_entry,
        )

        attached = attach_cached_manual_to_case(
            user_id=user_id,
            case_id=case_id,
            cache_id=cache_id,
            source_tag=source_tag,
            file_name=file_name,
        )
        claims: List[str] = []
        if append_claims and attached.get("success"):
            cached = get_manual_cache_entry(cache_id) or {}
            claims = extract_claims_from_manual_text(
                product_name=product_name or file_name or "product",
                manual_text=cached.get("text") or "",
            )
            attached["extracted_claims"] = claims
        return attached

    return mcp


mcp = _build_mcp()


def run_stdio():
    """Run MCP server over stdio if a server library is installed."""
    if mcp is None:
        raise RuntimeError(
            "MCP server library not available. Install fastmcp (and mcp<2) or mcp>=2."
        )
    mcp.run()


if __name__ == "__main__":
    run_stdio()
