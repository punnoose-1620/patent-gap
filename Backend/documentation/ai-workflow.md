# AI workflow

How LLM calls, RAG indexing/retrieval, scoring shortlists, and audit interact. Code lives under [`ai_workflow/`](../ai_workflow/), [`llm_brain/`](../llm_brain/), [`scorer.py`](../scorer.py), and analysis in [`controller.py`](../controller.py) / [`live_search/`](../live_search/).

## Modes

Controlled by `AI_WORKFLOW_MODE` ([`ai_workflow/config.py`](../ai_workflow/config.py)):

| Mode | Client | Claim matrix behavior |
|------|--------|------------------------|
| `rag` (default) | [`GeminiWorkflow`](../ai_workflow/orchestration.py) wrapping `llm_brain.gemini.Gemini` | Large matrices shortlisted via hybrid retrieve when `user_id`+`case_id` present |
| `legacy` | Raw `Gemini()` | Full Cartesian product (still threshold-filtered) |

Factory: [`get_ai_client()`](../ai_workflow/orchestration.py).

## “Agents” — what exists in code today

There is **no** multi-agent runtime with named agent ACLs (no separate “researcher / scorer / attach” processes with per-role tool allowlists). What exists:

| Role (conceptual) | Implementation | Can touch |
|-------------------|----------------|-----------|
| HTTP analysis worker | Flask background thread calling `start_patent_analysis` / `start_product_analysis` | Full live search, Mongo case/infringement updates, audit `analysis_*`, optional manuals enrichment |
| Gemini LLM client | `Gemini` / `GeminiWorkflow` | Structured extract, search briefs, product details, infringement narrative analysis; pacing via `DEFAULT_LLM_DELAY` |
| RAG indexer / retriever | `ai_workflow.indexing` + `hybrid_retrieve` | Per-user Chroma collection; reads/writes vectors only |
| Claim scorer | `scorer.score_infringement_matrix_entry` | Embeddings cosine; optional RAG shortlist; writes row shapes for Mongo |
| MCP tool caller | External client over stdio → [`mcp_tools/mcp.py`](../mcp_tools/mcp.py) | Only the registered tools; every tool requires `user_id` + `case_id`; mutating tools write `kind=mcp_action` audit |

**Access rule that is implemented:** `_require_ids(user_id, case_id)` on every MCP tool. There is no further per-tool ACL matrix in-repo. Folder/case ownership checks apply on HTTP folder/case routes, not inside MCP tools (MCP trusts the caller-supplied ids). Treat MCP as **local/trusted** (module docstring: in-process / not a public networked product API in this phase).

## Pipeline pieces

### 1. Extract / search (LLM)

`GeminiWorkflow` delegates to `llm_brain.gemini.Gemini` methods such as:

- `extract_patent_metadata`, `extract_claims`, `extract_documented_claims`
- `perform_google_search`, `perform_google_search_from_claims`
- `get_product_details`, `get_patent_sources`
- `analyze_infringements`, `analyze_product_infringements`
- `generate_product_retail_search_params` (when present)

[`index_claims_for_case`](../ai_workflow/orchestration.py) is available when RAG mode is on, but extract_* wrappers do **not** auto-index — indexing is explicit (MCP `index_case_claims`, scorer shortlist lazy path, or calling `index_claims_for_case`).

### 2. Index (vector)

[`index_claim_texts`](../ai_workflow/indexing.py) → parent/child chunks (~600 tokens, ~12% overlap) → embed → Chroma upsert. Lazy path: [`ensure_case_claims_indexed`](../ai_workflow/indexing.py) (only if case has no `chunk_type=="claim"` yet).

### 3. Retrieve + shortlist

[`retrieve_similar_texts`](../ai_workflow/hybrid_retrieve.py) (BM25 + dense + RRF + cross-encoder).  
[`shortlist_claim_pairs`](../ai_workflow/hybrid_retrieve.py) used from [`scorer.py`](../scorer.py) when RAG on and pair count > 200.

### 4. Score

[`score_infringement_matrix_entry`](../scorer.py): cache by `scoring_input_hash`; keep pairs above caller threshold (MCP default `0.5`). Downstream UI/API filters may also apply `CLAIM_SIMILARITY_THRESHOLD` (`0.10`) via [`infringement_score_filters.py`](../infringement_score_filters.py).

### 5. Product manuals (specialized AI+search path)

[`live_search/product_manuals.py`](../live_search/product_manuals.py):

1. SKU gate (`product_has_concrete_sku`) — no concrete model → skip.
2. Split search: GCSE operator queries + Gemini **manuals-only** brief.
3. URL filter/rank (OEM/support/manual hosts; demote PDPs / listing URL).
4. Fetch to temp cache → validity+relevance (`assess_manual_relevance`) — listings invalid even if features match.
5. Attach only after accept (`attach_cached_manual_to_case`); optional claim extract.

Env kill switch: `PRODUCT_MANUAL_ENRICHMENT=0`.

### 6. Audit

Append-only Mongo via [`structures/audit.py`](../structures/audit.py). Allowed `kind` values:

`patent_fetch`, `analysis_start`, `analysis_complete`, `analysis_failed`, `clarification`, `chat_message`, `case_update_via_ai`, `mcp_action`, `manual_relevance`.

No update/delete helpers — immutable history by design.

## End-to-end (product analysis, simplified)

```text
POST /api/similarity-analysis-live/<case_id>
  → thread: start_product_analysis
      → audit analysis_start
      → __complete_product_search / live_search
          → discover products (Apify/GCSE/etc. per search_limitations)
          → isolate / relevance gate
          → optional enrich_product_with_manuals
          → claim compare / store infringements
      → refresh_case_infringement_scores (RAG shortlist if large)
      → update flags completed | error + audit as wired in controller
```

Patent analysis mirrors this with `start_patent_analysis` and claim-bucket loops (`asserted` / `independent` / `core` / `pivotal`).

Numbers and env defaults: [`constants.md`](constants.md). MCP tool catalog: [`mcp.md`](mcp.md).
