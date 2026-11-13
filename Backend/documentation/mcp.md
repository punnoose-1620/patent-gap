# MCP tools

Server: [`mcp_tools/mcp.py`](../mcp_tools/mcp.py). Builds a FastMCP (or fallback MCPServer) named `patent-gap`. Run with `run_stdio()` / `python -m`-style entry when MCP libraries are installed.

**Scope:** in-process / local agent use — not exposed as a public HTTP product API in this phase.

## Hard requirements

- Every tool calls `_require_ids(user_id, case_id)` — both non-empty strings.
- **Processing** tools append audit `kind="mcp_action"` via [`structures.audit.add_audit_entry`](../structures/audit.py).
- **Read/get** tools do **not** write audit entries (documented in module docstring).

There is no separate agent-role ACL beyond requiring ids. MCP does **not** call folder `has_edit_permission` / `has_delete_permission`. Callers are trusted to pass the correct user/case (local/trusted use only).

**Important:** `get_case_context` loads by `case_id` only — it does **not** verify that `user_id` owns or can view the case.

## Tool catalog (13)

| Tool | Mutates? | Audit | Behavior |
|------|----------|-------|----------|
| `extract_patent_metadata` | No (LLM only) | Yes (`mcp_action`) | `get_ai_client().extract_patent_metadata` |
| `extract_claims` | No (LLM only) | Yes | `get_ai_client().extract_claims` |
| `index_case_claims` | Yes (Chroma) | Yes | `index_claim_texts(..., replace_case_chunks=True)` |
| `hybrid_retrieve` | No | No | `retrieve_similar_texts` |
| `analyze_infringements` | No (LLM only) | Yes | `get_ai_client().analyze_infringements` |
| `get_case_context` | No | No | `get_case_by_id(case_id)` — no user filter |
| `score_claim_matrix` | No* | Yes | `score_infringement_matrix_entry` (default threshold `0.5`); returns rows (*caller must persist) |
| `get_audit_by_case_id` | No | No | Paginated audit for case |
| `get_audit_by_user_id` | No | No | Paginated by user (`case_id` still required for MCP consistency) |
| `search_product_manuals` | No | Via callee | `search_manual_urls(..., require_sku=True)`; may write `mcp_action` from manuals module |
| `fetch_manual_for_inspection` | Temp cache only | Yes | Preview only; no case documents |
| `assess_manual_relevance` | May drop bad cache | Via assess (`manual_relevance`) | Listings invalid even if features match |
| `attach_verified_manual_to_case` | Yes (case docs) | Via attach | Accepted cache only; optional claim extract |

## Manuals agent sequence (intended)

1. `search_product_manuals` — candidates only.
2. `fetch_manual_for_inspection` — cache + preview.
3. `assess_manual_relevance` — accept/reject.
4. `attach_verified_manual_to_case` — only if accepted.

Skipping assess/attach gates will fail or refuse attach for non-accepted cache entries (enforced in [`product_manuals.py`](../live_search/product_manuals.py)).

## Library dependency

Import order tries: `fastmcp.FastMCP` → `mcp.server.mcpserver.MCPServer` → `mcp.server.fastmcp.FastMCP`. If none import, `mcp` is `None` and `run_stdio()` raises.

## Related audit kinds

See `AUDIT_KINDS` in [`structures/audit.py`](../structures/audit.py). MCP processing uses `mcp_action`; manuals assessment uses `manual_relevance`; analysis threads use `analysis_start` / `analysis_complete` / `analysis_failed`.
