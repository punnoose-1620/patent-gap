# Endpoint flows

Primary HTTP paths in [`app.py`](../app.py). Auth: [`get_user_id()`](../app.py) — `X-User-ID` then session. Details live in linked `.py` docstrings (no `functions.md`). Operational live path is `controller.py` + `live_search/`; [`discovery/`](../discovery/) is a thin re-export facade only.

---

## Case intake (no live analysis)

| Route | Behavior |
|-------|----------|
| `POST /api/create-patent` | [`create_case`](../structures/cases.py) — persists to Mongo; rejects duplicate `_id`. **Preferred.** |
| `POST /api/add-patent` | Legacy [`create_patent`](../controller.py) — stamps `local_` id / `created_by`; **does not persist** (in-memory success only). |
| `POST /api/fetch-patent-from-uspto` | Daemon thread → [`fetchById`](../controller.py): similar-case merge or USPTO → `create_case` → description → Gemini `extract_claims`; Google/FPO fallbacks. |
| `POST /api/bulk-fetch` | Multiple patent ids |
| `GET /api/check-fetching-thread-status/<patent_id>` | Poll user `fetching_patents` / thread status |

Fetch may audit `patent_fetch`. Does not start similarity-analysis-live.

---

## Live similarity analysis (patent + product)

**Route:** `POST /api/similarity-analysis-live/<case_id>` → [`live_similarity_analysis`](../app.py)

1. Auth + existing case; require keywords, claims, owners (owners fall back to assignee/applicant/inventors).
2. Bucket claims:
   - List → `search_type='generic'`, asserted-style texts.
   - Dict → `search_type='bucketed'` by `claim_type` with `documented_claim` and `market_language_claim`.
3. Clear timing fields on case.
4. Start **two** non-daemon threads in parallel:
   - [`start_patent_analysis`](../controller.py)
   - [`start_product_analysis`](../controller.py)
5. Return `patent_thread_id` / `product_thread_id` immediately. Progress via case flags, infringements, audit — not this response. Patent/product detail merges use `_merge_infringement_details`.

### Patent thread

```text
audit analysis_start → flags(category=patent) → reset status
→ per bucket (asserted → independent → core → pivotal):
     searchPatentSources → FPO + Google Patents scrape
     → Gemini metadata/claims (claims_mode=infringement_candidate)
     → sleep(DEFAULT_LLM_DELAY=3s) between detail fetches
     → Gemini get_patent_sources / analyze → create_infringement
→ dedupe; update_infringements; refresh_case_infringement_scores
→ completed | error flags + infringement_details.patent_ids
```

### Product thread

```text
audit analysis_start
→ __complete_product_search
     → normalize_search_limitations
     → resolve_product_target_sources_for_analysis (retailer catalog; no LLM)
     → Gemini.generate_product_retail_search_params (or fallback)
     → per claim bucket × retail params:
          searchProductSources(ref_claim_flag=original|market)
→ update_infringements → refresh_case_infringement_scores
→ case.infringement_details + completed | error flags
```

**`searchProductSources` order:**

1. **Gemini primary** — claim-driven search → HTML → `get_product_details` → `_persist_extracted_products`
2. **Apify** — if configured and enabled for the case (Gemini/CSE limitations strip Apify hosts when appropriate)
3. **GCSE fallback** — only if still empty and CSE configured (`productGoogleSearch`)

Inside `_persist_extracted_products` (before claim compare): relevance gate → optional [`enrich_product_with_manuals`](../live_search/product_manuals.py) → Gemini `analyze_product_infringements` → `create_infringement`.

---

## USPTO keyword similarity (legacy synchronous)

**Route:** `POST /api/trigger-similarity-analysis`

Auth + keywords → [`getKeywordDocumentsUSPTO`](../sources/USPTO.py) → references → [`generateReports`](../controller.py) → update case → create alert. Separate from live threads.

---

## Cases and infringements

| Route | Notes |
|-------|--------|
| `GET/POST /api/cases/<case_id>` | Read / update |
| `POST /api/cases/<case_id>/update-status` | Status transitions |
| `GET /api/cases/<case_id>/patents` | Related patents |
| `GET /api/get-claims/<case_id>` | Claims payload |
| `GET /api/infringement-details/<case_id>` | Details blob |
| `GET /api/infringement-chart/<case_id>` | Chart rows; score filter may apply |
| `GET/PUT/DELETE .../infringements[/<id>]` | Infringement CRUD |

Score filter: [`infringement_score_filters.py`](../infringement_score_filters.py) (`CLAIM_SIMILARITY_THRESHOLD = 0.10`).

---

## Auth, folders, documents, misc

| Area | Routes |
|------|--------|
| Auth | `/api/login`, `/logout`, `/profile`, password + attorney create/update |
| Folders | `/api/folders/*` — list/get/create/rename/delete; viewers/editors/cases ([`structures/folders.py`](../structures/folders.py) ACL) |
| Documents | upload ≤12MB PDF/XML; `GET /api/document/<id>`; `POST /api/proxy-document` |
| Search / alerts / demo | search-history APIs; `/api/alerts`; create-demo-request |

---

## MCP (non-HTTP)

Stdio tools — [`mcp.md`](mcp.md). Manuals: search → fetch → assess → attach.
