# Backend architecture

Flask monolith that serves the HTML Frontend, REST JSON APIs, background analysis threads, live web/product search, Gemini/OpenAI LLM calls, Mongo persistence, and a local Chroma vector index. An optional MCP stdio server exposes the same core capabilities to external agents.

## Runtime entry

| Piece | Path | Role |
|-------|------|------|
| Flask app | [`app.py`](../app.py) | Routes, CORS, sessions, Swagger init, static/templates |
| Config | env via [`env_controller.py`](../env_controller.py), `PORT`/`DEBUG`/`SECRET_KEY` on app | Collection names, keys, feature flags |
| Templates / static | `../Frontend`, `../Assets` | Server-rendered pages + assets |
| Analysis orchestration | [`controller.py`](../controller.py) | `start_patent_analysis`, `start_product_analysis`, USPTO fetch threads |
| Live search | [`live_search/`](../live_search/) | Patent/product discovery, manuals enrichment |
| AI workflow | [`ai_workflow/`](../ai_workflow/) | RAG mode, embeddings, indexing, hybrid retrieve, LLM client factory |
| LLM wrappers | [`llm_brain/`](../llm_brain/), [`llm_processor.py`](../llm_processor.py), [`sources/Gemini.py`](../sources/Gemini.py) | Structured Gemini/OpenAI calls |
| Data access | [`database/`](../database/), [`structures/`](../structures/), [`models/`](../models/) | Mongo CRUD + thin HTTP model adapters |
| Scoring | [`scorer.py`](../scorer.py), [`infringement_score_filters.py`](../infringement_score_filters.py) | Claim-pair cosine scores + read filters |
| MCP | [`mcp_tools/mcp.py`](../mcp_tools/mcp.py) | FastMCP / MCPServer tool surface |
| Patent sources | [`sources/`](../sources/) | USPTO, OpenAlex, Gemini-assisted extract, aggregator |
| Discovery / scrapers | [`discovery/`](../discovery/), [`web_scraper/`](../web_scraper/), [`web_search.py`](../web_search.py) | Product/web helpers |

Default listen: `PORT` env or **5000**.

## Layering (request → storage)

```text
Browser / React client
        │  HTTP (+ X-User-ID or session)
        ▼
   app.py routes  ──► models/*  ──► structures/*  ──► database (Mongo)
        │
        ├── controller threads (patent/product analysis, patent fetch)
        │         │
        │         ├── live_search/*  (GCSE, Apify, manuals, isolation)
        │         ├── sources/*      (USPTO / OpenAlex / Gemini)
        │         ├── scorer / data_processor (embeddings similarity)
        │         └── ai_workflow/*  (index + shortlist when RAG on)
        │
        └── mcp_tools (stdio agents) ──► same structures / ai_workflow / live_search
                                              │
                                              ├── Mongo (cases, infringements, audit, …)
                                              └── Chroma per-user collections (vector_store/)
```

## Identity and case keys

- **User:** resolved by [`get_user_id`](../app.py) — header `X-User-ID`, else `session['user_id']`.
- **Case id:** `{source}_{userId}_{patentId}` pattern used so analysis, Mongo, audit, and Chroma `case_id` metadata stay aligned (see analysis start in controller / live search).
- **Permissions:** folder/case helpers check `created_by` / `owner` / `editors` / `viewers` in [`structures/folders.py`](../structures/folders.py) and related case helpers — not a full RBAC engine.

## Sync vs async work

| Kind | Mechanism |
|------|-----------|
| CRUD, charts, folders | Synchronous request/response |
| Patent/product infringement analysis | `threading` + Flask `app.app_context()` inside controller starters |
| USPTO / multi-source patent fetch | Background threads; status polled via `/api/check-fetching-thread-status/<patent_id>` |
| MCP | Separate process over stdio (`python -m mcp_tools.mcp` / `run_stdio`) |

Analysis progress is written onto the case (infringement analysis flags/status buckets) and into the **append-only** audit collection (`analysis_start`, `analysis_complete`, `analysis_failed`, …).

## Design invariants worth preserving

1. Mongo is system of record; Chroma is a retrieval cache for claims/chunks.
2. Processing MCP tools and analysis paths should pass **both** `user_id` and `case_id` and prefer writing audit rows for mutating AI actions.
3. Product **manual** enrichment must not treat retail PDPs as manuals (SKU gate + validity/relevance) — [`live_search/product_manuals.py`](../live_search/product_manuals.py).
4. Claim chart rows use `embedding_cosine` / `v1` hashing for cache reuse in [`scorer.py`](../scorer.py).

See also: [`mongo-db.md`](mongo-db.md), [`vector-db.md`](vector-db.md), [`ai-workflow.md`](ai-workflow.md), [`endpoint-flow.md`](endpoint-flow.md).
