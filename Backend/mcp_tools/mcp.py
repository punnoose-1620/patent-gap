"""
FastMCP / MCPServer tools wrapping internal patent-gap functions.
In-process / local use — not a public networked product API in this phase.
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


def _build_mcp():
    if FastMCP is None:
        return None
    mcp = FastMCP("patent-gap")

    @mcp.tool()
    def extract_patent_metadata(patent_content: str, default_source: str = "") -> Any:
        """Extract structured patent metadata from raw patent HTML/text via Gemini."""
        from ai_workflow.orchestration import get_ai_client

        return get_ai_client().extract_patent_metadata(
            patent_content=patent_content,
            default_source=default_source or None,
        )

    @mcp.tool()
    def extract_claims(patent_content: str) -> Any:
        """Extract claims from patent content."""
        from ai_workflow.orchestration import get_ai_client

        return get_ai_client().extract_claims(patent_content=patent_content)

    @mcp.tool()
    def index_case_claims(
        user_id: str,
        case_id: str,
        claims: List[str],
        source: str = "",
        chunk_type: str = "claim",
    ) -> int:
        """Chunk and upsert claim texts into the local Chroma index for a user/case."""
        from ai_workflow.indexing import index_claim_texts

        return index_claim_texts(
            user_id=user_id,
            case_id=case_id,
            claims=claims,
            source=source,
            chunk_type=chunk_type,
            replace_case_chunks=True,
        )

    @mcp.tool()
    def hybrid_retrieve(
        user_id: str,
        case_id: str,
        query_text: str,
        chunk_type: str = "claim",
    ) -> List[Dict[str, Any]]:
        """BM25 + dense + rerank retrieval over a user's case chunks."""
        from ai_workflow.hybrid_retrieve import retrieve_similar_texts

        return retrieve_similar_texts(
            user_id=user_id,
            case_id=case_id,
            query_text=query_text,
            chunk_type=chunk_type or None,
        )

    @mcp.tool()
    def analyze_infringements(
        reference_claims: List[str],
        infringing_claims: List[str],
        context: str = "",
    ) -> Any:
        """Run Gemini infringement analysis on claim sets."""
        from ai_workflow.orchestration import get_ai_client

        return get_ai_client().analyze_infringements(
            reference_claims, infringing_claims, context
        )

    @mcp.tool()
    def get_case_context(case_id: str) -> Optional[Dict[str, Any]]:
        """Load a case document from Mongo by id."""
        from structures.cases import get_case_by_id

        return get_case_by_id(case_id)

    @mcp.tool()
    def score_claim_matrix(
        reference_claims: List[str],
        infringing_claims: List[str],
        threshold: float = 0.5,
        user_id: str = "",
        case_id: str = "",
    ) -> Dict[str, Any]:
        """Score reference x infringing claims (RAG shortlist when enabled)."""
        from scorer import score_infringement_matrix_entry

        stored, chart = score_infringement_matrix_entry(
            reference_claims,
            infringing_claims,
            None,
            threshold=threshold,
            user_id=user_id or None,
            case_id=case_id or None,
        )
        return {"stored_rows": stored, "chart_rows": chart}

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
