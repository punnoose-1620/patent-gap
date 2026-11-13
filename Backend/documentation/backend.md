# Backend documentation index

Authoritative notes for the Flask Backend under `Backend/`. Prefer these docs + **source docstrings** over outdated comments elsewhere. There is no `functions.md` — cite ``[`fn`](../path.py)`` and read that function’s docstring.

## Doc map

| Doc | Contents |
|-----|----------|
| [`architecture.md`](architecture.md) | Layers, folders, sync vs threads, identity |
| [`mongo-db.md`](mongo-db.md) | Collections and field shapes |
| [`vector-db.md`](vector-db.md) | Chroma layout, embeddings, hybrid retrieve |
| [`ai-workflow.md`](ai-workflow.md) | RAG modes, conceptual roles, pipelines, audit kinds |
| [`mcp.md`](mcp.md) | MCP tool catalog and manuals sequence |
| [`endpoint-flow.md`](endpoint-flow.md) | Major HTTP flows |
| [`features.md`](features.md) | Product capability map |
| [`constants.md`](constants.md) | Thresholds, env defaults, known caveats |

## Integrations

| System | Use | Config touchpoints |
|--------|-----|--------------------|
| MongoDB | System of record | `env_controller` collection name getters; `database.connect_to_database` |
| Chroma | Per-user claim/chunk vectors | `CHROMA_PERSIST_DIR` (default `Backend/vector_store`); [`database/chroma.py`](../database/chroma.py) |
| Google Gemini | LLM extract/search/analyze + embeddings | Keys in env; `GEMINI_EMBEDDING_MODEL`; [`llm_brain/gemini.py`](../llm_brain/gemini.py) |
| OpenAI | Embedding fallback; some similarity embeds | Key in env; [`ai_workflow/embeddings.py`](../ai_workflow/embeddings.py), [`data_processor.py`](../data_processor.py) |
| Google CSE (GCSE) | Web/manual search | Live search / product_manuals |
| Apify | Retail product search | `search_limitations.use_apify_retail`; [`live_search/apifySearch.py`](../live_search/apifySearch.py) |
| USPTO / OpenAlex | Patent fetch & keyword docs | [`sources/`](../sources/) |
| FastMCP / mcp | Agent stdio tools | [`mcp_tools/mcp.py`](../mcp_tools/mcp.py) |
| Sentence-transformers cross-encoder | Rerank | `RAG_CROSS_ENCODER_MODEL` default `cross-encoder/ms-marco-MiniLM-L-6-v2` |

## Operations

- **Start API:** run Flask `app.py` (PORT default 5000, DEBUG from env).
- **Start MCP:** ensure `fastmcp` or compatible `mcp` installed; run `mcp_tools.mcp` `run_stdio`.
- **Env flags of note:** `AI_WORKFLOW_MODE`, `PRODUCT_MANUAL_ENRICHMENT`, `RAG_TOP_K`, `RAG_RERANK_K`, `CHROMA_PERSIST_DIR`, `GEMINI_EMBEDDING_MODEL`, `SECRET_KEY`.
- **Logs:** stdout `LOG:` / `ERROR:` prefixes; optional `Backend/logs/`.
- **Audit:** append-only; never “fix” history by mutating rows — insert a new kind if needed.
- **User auth:** header `X-User-ID` preferred for API clients; session for classic Frontend.

## Performance characteristics

| Area | Behavior |
|------|----------|
| Live analysis | Long-running threads (minutes–hours); LLM delay default **3s** between calls |
| Claim matrices | Full product if ≤200 pairs; else RAG shortlist in rag mode |
| Embeddings | Gemini first; OpenAI fallback; BM25-only if both fail |
| Manuals | Cap search candidates / URLs / PDF bytes (see constants); SKU skip avoids useless LLM |
| Chroma dense `where` | Two-key filters may fail on some versions — dense path degrades to BM25 (logged) |
| Cross-encoder | First use may download model weights |

## Accuracy note

These docs were written against the Backend tree as of the documentation pass. If code and docs disagree, **trust the Python source** and update the matching `.md` file.
