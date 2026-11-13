# Backend features

Capability map tied to real modules. Thresholds: [`constants.md`](constants.md).

## Patent infringement discovery

- Live multi-source patent search driven by claim buckets (asserted / independent / core / pivotal) or generic claim lists.
- Orchestrated by [`start_patent_analysis`](../controller.py); sources under [`sources/`](../sources/) and [`live_search/`](../live_search/).
- Results stored as infringements + case status flags; audited as analysis lifecycle events.

## Product infringement discovery

- Parallel with patent analysis from one live endpoint; original vs market claim language.
- Roles: **Gemini** (retail params, claim-driven search, HTML→details, infringement, manuals); **Apify** (marketplace actors when enabled); **GCSE** (product fallback if Gemini empty; primary manuals URL search).
- Owner + `search_limitations`; relevance/isolation gates (~0.10 floors where coded).
- [`start_product_analysis`](../controller.py) → update infringements → refresh scores. `discovery/` is a thin facade — live path uses `live_search` directly.

## Product manuals enrichment

- Optional (`PRODUCT_MANUAL_ENRICHMENT`).
- **Requires concrete SKU/model**; category hubs skipped.
- Manuals-only search (GCSE + Gemini brief); URL rank prefers OEM/support/manual hosts.
- Validity+relevance rejects product listings even when features match.
- Attach only after accept; can extract claims from manual text.
- Code: [`live_search/product_manuals.py`](../live_search/product_manuals.py); MCP tools in [`mcp.md`](mcp.md).

## Claim similarity scoring

- Cosine embedding similarity (`embedding_cosine` / `v1`) with hash cache.
- Matrix threshold (default `0.5` at score time); chart/API filter `0.10`.
- RAG shortlist for large matrices when `AI_WORKFLOW_MODE=rag`.

## RAG vector assist

- Per-user Chroma collections; parent/child claim chunks.
- Hybrid BM25 + dense + cross-encoder rerank.
- See [`vector-db.md`](vector-db.md), [`ai-workflow.md`](ai-workflow.md).

## Case / folder collaboration

- Cases owned/created by users; folders with owner, editors, viewers.
- Case membership via case `folders` array and folder APIs.

## Documents

- Upload to local storage / document collection; size helper ~12 MB.
- Proxy and download endpoints for viewing.

## Alerts and search history

- Alerts created on certain analysis paths; searchable history APIs.

## USPTO / patent ingest

- Fetch by id (USPTO and fallbacks), bulk fetch, thread status polling.
- Keyword USPTO similarity path (`/api/trigger-similarity-analysis`) distinct from live analysis.

## MCP agent interface

- Local stdio tools for extract, index, retrieve, score, audit read, manuals workflow.
- Immutable audit log for AI/MCP actions.

## Demo

- Demo request + show-demo pages; demo user/case ids used in test runs.
