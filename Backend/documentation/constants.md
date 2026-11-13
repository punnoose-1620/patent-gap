# Fixed values, thresholds, and filters

Canonical numeric and boolean controls used by the Backend. Prefer reading the cited modules if behavior changes.

## Linking convention

Flow docs reference functions as ``[`name`](../path.py)``. Details live in that function’s docstring in source — there is no separate `functions.md`.

---

## Similarity and scoring

| Constant | Value | Where | Meaning |
|----------|-------|--------|---------|
| `CLAIM_SIMILARITY_THRESHOLD` | `0.10` | [`infringement_score_filters.py`](../infringement_score_filters.py) | Claim-pair / chart rows kept only if score **>** this value when filters are applied on read/update |
| Default matrix `threshold` | `0.5` | [`scorer.py`](../scorer.py) `score_infringement_matrix_entry` | Pairs with cosine score ≤ threshold are omitted from stored/chart rows (caller can override; MCP tool default is `0.5`) |
| `PRODUCT_TITLE_SIMILARITY_THRESHOLD` | `0.10` | [`live_search/liveSearchController.py`](../live_search/liveSearchController.py) | Product title relevance gate vs reference title |
| `_FUZZY_DEDUP_THRESHOLD` | `0.9` | [`structures/cases.py`](../structures/cases.py) | Fuzzy string dedup when merging case fields |
| Product low-relevance skip | `0.1` | Live product isolation logs / extract path | Products with relevance score `< 0.1` are skipped (see product isolation in live search) |

Score method identity: `SCORE_METHOD = "embedding_cosine"`, `SCORE_VERSION = "v1"` in [`scorer.py`](../scorer.py).

---

## RAG / vector

| Constant / env | Default | Where | Meaning |
|----------------|---------|--------|---------|
| `AI_WORKFLOW_MODE` | `rag` | [`ai_workflow/config.py`](../ai_workflow/config.py) | `rag` or `legacy` |
| `RAG_TOP_K` | `50` | same | Hybrid retrieve candidate pool size |
| `RAG_RERANK_K` | `15` | same | After cross-encoder rerank |
| RRF `k` | `60` | [`ai_workflow/hybrid_retrieve.py`](../ai_workflow/hybrid_retrieve.py) | Reciprocal rank fusion constant |
| Full matrix cutoff | `200` pairs | `shortlist_claim_pairs` | If `\|refs\|×\|infs\| ≤ 200`, use full Cartesian product |
| Child chunk target tokens | `~600` | [`ai_workflow/chunking.py`](../ai_workflow/chunking.py) | Window size (~4 chars/token heuristic) |
| Chunk overlap ratio | `0.12` | same | Overlap between child windows |
| `GEMINI_EMBEDDING_MODEL` | `text-embedding-004` | config / env | Primary embedding model name |
| OpenAI embedding fallback | `text-embedding-3-small` | [`ai_workflow/embeddings.py`](../ai_workflow/embeddings.py) | Used only if Gemini fails and OpenAI key is set |
| Chroma space | `cosine` | [`database/chroma.py`](../database/chroma.py) | Collection metadata `hnsw:space` |
| Null / local embed dim | `32` | chroma upsert without dense vectors | Deterministic filler vectors so Chroma does not download ONNX |

---

## Live search / LLM pacing

| Constant | Value | Where | Meaning |
|----------|-------|--------|---------|
| `DEFAULT_LLM_DELAY` | `3` seconds | [`live_search/liveSearchController.py`](../live_search/liveSearchController.py), [`llm_brain/gemini.py`](../llm_brain/gemini.py) | Sleep between consecutive LLM calls / retries |
| `MAX_ATTEMPTS` | (gemini module) | [`llm_brain/gemini.py`](../llm_brain/gemini.py) | Retry budget for structured Gemini calls |
| Apify retail | on unless `use_apify_retail is False` | [`live_search/apifySearch.py`](../live_search/apifySearch.py) | Case `search_limitations` can disable Apify retail |

---

## Product manuals enrichment

| Constant / env | Default | Where | Meaning |
|----------------|---------|--------|---------|
| `PRODUCT_MANUAL_ENRICHMENT` | enabled (`1`) | [`live_search/product_manuals.py`](../live_search/product_manuals.py) | Set `0`/`false`/`off` to disable |
| `MAX_MANUAL_URLS_PER_KIND` | `3` | same | Max ranked URLs fetched per instruction/repair kind |
| `MAX_SEARCH_CANDIDATES` | `8` | same | Raw search pool before URL filter/rank |
| `MAX_PREVIEW_CHARS` | `6000` | same | Relevance preview size |
| `MAX_CLAIM_SOURCE_CHARS` | `24000` | same | Claim extract source size |
| `MAX_PDF_BYTES` | `12 MiB` | same | PDF attach size cap |
| SKU gate | required | `product_has_concrete_sku` | No concrete model/SKU → skip enrichment |
| Validity gate | instruction/repair/datasheet only | `assess_manual_relevance` | Product listings are invalid even if features match |

---

## Documents / uploads

| Rule | Value | Where |
|------|-------|--------|
| Blob size helper | 12 MB | [`controller.py`](../controller.py) `is_blob_under_12mb` |

---

## Auth / session

| Item | Behavior | Where |
|------|----------|--------|
| User id resolution | `X-User-ID` header first, else Flask `session['user_id']` | [`app.py`](../app.py) `get_user_id` |
| Password storage | Plain comparison in `login_user` (legacy) | [`structures/users.py`](../structures/users.py) |

---

## Known operational caveats (as of docs authoring)

- Dense Chroma queries that pass a `where` with **two** top-level keys (`case_id` + `chunk_type`) can fail with Chroma’s “exactly one operator” error; hybrid retrieve logs `dense retrieve failed` and continues with BM25. See [`ai_workflow/hybrid_retrieve.py`](../ai_workflow/hybrid_retrieve.py).
- Default Gemini embedding model name `text-embedding-004` may 404 on some API versions; embeddings then fall through to OpenAI or BM25-only paths.
