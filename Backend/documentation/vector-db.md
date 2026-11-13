# Vector database (Chroma)

Local/persistent Chroma store used by the RAG path for claim (and related) chunk retrieval. Implementation: [`database/chroma.py`](../database/chroma.py). Indexing and retrieval: [`ai_workflow/indexing.py`](../ai_workflow/indexing.py), [`ai_workflow/hybrid_retrieve.py`](../ai_workflow/hybrid_retrieve.py), [`ai_workflow/chunking.py`](../ai_workflow/chunking.py), [`ai_workflow/embeddings.py`](../ai_workflow/embeddings.py).

## Layout

| Concept | Behavior |
|---------|----------|
| Client | Persistent Chroma client (path from env / default under Backend working tree) |
| Isolation | **One collection per user**: `get_user_collection(user_id)` |
| Distance | Collection metadata `hnsw:space = cosine` |
| Case scoping | Metadata field `case_id` on every chunk; delete via `delete_by_case(user_id, case_id)` |

Mongo remains system of record for case/product/infringement documents. Chroma holds **chunked text + embeddings** for retrieval only.

---

## Chunk schema

Built by [`build_parent_child_chunks`](../ai_workflow/chunking.py):

**Parent row**

| Metadata key | Value |
|--------------|--------|
| `user_id` | Owner |
| `case_id` | Composite case id |
| `record_id` | Record or case id |
| `chunk_id` / `id` | Stable hash id |
| `parent_id` | Same as parent id |
| `chunk_type` | e.g. `"claim"` |
| `source` | e.g. `"infringing"`, `"reference"` |
| `is_parent` | `True` |
| `parent_index` | int |

**Child row** — same keys plus `is_parent: False`, `child_index`, `parent_id` pointing at parent. Children are ~600-token windows with ~12% overlap. If a parent fits in one window, children are skipped to avoid duplicates.

Document text stored in Chroma is the claim (or chunk) string used for BM25 and dense search.

---

## Embeddings

Order in [`ai_workflow/embeddings.py`](../ai_workflow/embeddings.py) / indexing:

1. **Gemini** embedding API (`GEMINI_EMBEDDING_MODEL`, default `text-embedding-004`).
2. **OpenAI** `text-embedding-3-small` if Gemini fails and an OpenAI key is configured.
3. If neither produces vectors, upsert may use **deterministic 32-d filler** vectors in [`chroma.upsert_chunks`](../database/chroma.py) so Chroma does not download a default ONNX model. Dense quality then depends on BM25 + rerank.

Query embedding uses the same stack via `embed_query`.

---

## Hybrid retrieve

[`retrieve_similar_texts`](../ai_workflow/hybrid_retrieve.py):

1. Load case chunks (`list_documents_for_case`).
2. Optional filter intent: `case_id` + `chunk_type` (see caveat below).
3. **BM25** rank over documents.
4. **Dense** Chroma query (`query_embeddings` preferred).
5. **RRF** fuse (`k=60`).
6. Map hits to **parent** documents.
7. **Cross-encoder** rerank (`RAG_RERANK_K`, default 15).

Used by claim shortlisting in [`shortlist_claim_pairs`](../ai_workflow/hybrid_retrieve.py) when `AI_WORKFLOW_MODE=rag` and `|refs|×|infs| > 200`.

---

## Indexing entry points

| Function | Role |
|----------|------|
| [`index_claim_texts`](../ai_workflow/indexing.py) | Full chunk+embed+upsert; optional replace same `chunk_type` |
| [`ensure_case_claims_indexed`](../ai_workflow/indexing.py) | Lazy upsert only if case has no claim chunks yet |
| MCP `index_case_claims` | Explicit reindex (`replace_case_chunks=True`) — see [`mcp.md`](mcp.md) |
| Case delete / reindex | `delete_by_case` then re-upsert |

Extract/LLM helpers do not auto-index; callers must invoke indexing explicitly (or rely on scorer shortlist lazy index).

---

## Caveats (precise)

1. **Chroma `where` operators:** Passing a dict with two top-level equality keys (e.g. `{"case_id": …, "chunk_type": …}`) can raise *“Expected where to have exactly one operator”* on some Chroma versions. Hybrid retrieve catches this, logs `dense retrieve failed`, and continues with BM25. Prefer `$and` if tightening filters.
2. **Embedding model 404:** If `text-embedding-004` is unavailable on the configured Gemini endpoint, expect fallback logs and possible BM25-heavy behavior.
3. **Mode:** If `AI_WORKFLOW_MODE=legacy`, scoring uses full claim matrices without RAG shortlist (still subject to score thresholds).

Related numbers: [`constants.md`](constants.md).
