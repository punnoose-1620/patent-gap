# MongoDB

Operational document store. **Source of truth for shapes:** [`structures/`](../structures/) (Pydantic/dict builders + CRUD). [`models/`](../models/) are thin re-export shims (`from structures.X import *`).

Access: PyMongo via `connect_to_database()` and helpers `getDataById`, `getAllData`, `getDataByKeyValue`, `addDataById`, `updateDataById`, `deleteDataById`.

There is **no** formal Mongo schema validator in-repo. Most writers pass opaque dicts; stronger checks exist for audit kinds, folder names, demo fields, live-search product Pydantic models, and infringement score filters.

## Collection names (env)

`get*DatabaseName()` returns the **collection** name for the active environment (`PROD` / `DEV` / `TEST`). Only audit has hardcoded fallbacks.

| Getter | Env keys | Fallback |
|--------|----------|----------|
| `getCaseDatabaseName` | `CASE_DATABASE_NAME_*` | none |
| `getUserDatabaseName` | `USERS_DATABASE_NAME_*` | none |
| `getAlertDatabaseName` | `ALERT_DATABASE_NAME_*` | none |
| `getDocumentDatabaseName` | `DOCUMENTS_DATABASE_NAME_*` | none |
| `getInfringementDatabaseName` | `INFRINGEMENT_DATABASE_NAME_*` | none |
| `getSearchHistoryDatabaseName` | `SEARCH_HISTORY_DATABASE_NAME_*` | none |
| `getFolderDatabaseName` | `FOLDER_DATABASE_NAME_*` | none |
| `getDemoDatabaseName` | `DEMO_DATABASE_NAME_*` | none |
| `getAuditDatabaseName` | `AUDIT_DATABASE_NAME_*` | `audit` / `audit_dev` / `audit_test` |

Typical local names look like `cases_*`, `users_*`, `infringements_*`, `audit*`, etc. (from `.env`).

---

## Cases — `getCaseDatabaseName()`

**Code:** [`structures/cases.py`](../structures/cases.py) → `create_case`  
**Id:** often `{source}_{userId}_{patentId}` so Mongo and Chroma `case_id` align. `_id` required on create.

| Field | Type | Notes |
|-------|------|--------|
| `_id` | str | Primary key |
| `title`, `description`, `status` / `current_status` | str | `Completed` special-cased in open/list filters |
| `created_by`, `owner`, `assigned_to`, `accepted_by`, `assigned_editors` | str / list | ACL-ish fields |
| `source` | str | `uspto`, `google_patents`, `free_patents_online`, … |
| `keywords` | list[str] | Live analysis requires these |
| `claims` | list[str] **or** dict | Portfolio dict: `{ "0": {documented_claim, market_language_claim, claim_type} }`; candidates often list[str] |
| `documents` | list[{url, source, …}] | Pointers; `source=='local'` → documents collection |
| `document_urls` | list[str] | Flat URLs |
| `infringements` | list | Legacy/inline; full hits usually in infringements collection |
| `folders` | list[str] | Denormalized folder ids |
| `search_limitations` | dict | Companies, URLs, sources, Apify toggle, max results |
| `excluded_case_ids` / `excluded_case_titles` | list | Search exclusions |
| `country`, `inventors`, `applicant`, `current_assignee`, `attorneys`, `other_ids`, `references` | various | Patent metadata |
| `filingDate` / `filing_date` | str | Both casings appear across sources |
| Analysis fields | various | `infringement_analysis_status`, `*_time_taken`, `infringement_details`, … |

Claim dict `claim_type` ∈ `{asserted_claim, independent_claim, core_claim, pivotal_claim}` (see `structures/live_search_results.SingleClaim`). Fuzzy merge uses `_FUZZY_DEDUP_THRESHOLD = 0.9`.

**Create paths:** `POST /api/create-patent`; `controller.fetchById` (USPTO / Google / FPO); live-search Gemini dumps; keyword USPTO bulk; dummy seed. Prefer `create-patent` over legacy `add-patent` (in-memory only).

---

## Users — `getUserDatabaseName()`

**Code:** [`structures/users.py`](../structures/users.py)

| Field | Type | Notes |
|-------|------|--------|
| `_id` | str | |
| `email`, `password` | str | Login; **plaintext** compare today |
| `full_name`, `title`, `role` | str | Create-attorney forces `role='attorney'` |
| `created_date` / `created_on`, `deleted_on`, `last_updated` | str/datetime | |
| `cases`, `patents` | list[str] | Optional soft refs |
| `fetching_patents`, `error_patents` | list[str] | Bulk USPTO import progress |

---

## Infringements — `getInfringementDatabaseName()`

**Code:** [`structures/infringements.py`](../structures/infringements.py)

| Field | Type | Notes |
|-------|------|--------|
| `_id` | str | e.g. `product_{id}_{ts}` / `patent_{id}_{ts}` |
| `parent_case_id` | str | **Required** |
| `created_at` | str | UTC ISO ending `Z` |
| Product: `source`, `product_id`, `product_url`, `product_name`, `claims` | | Validated URL; claims may include manual extracts |
| Product: `similar_claims[]` | | `claim`, `similarity_score`, `source`, `url_to_claim`, `justification`, `ref_claim_index`, `ref_claim_flag` (`market`\|`original`) |
| Patent shape | | Case-like dump + `similar_claims`; `gemini_infringement` stripped before insert |

Read/update filters ([`infringement_score_filters.py`](../infringement_score_filters.py)) drop rows with `similarity_score` ≤ `0.10`.

Matrix chart scoring (separate from Gemini similar_claims) uses [`scorer.py`](../scorer.py): `calculated_similarity_score`, `scoring_input_hash`, `score_method=embedding_cosine`, `score_version=v1`.

**Create:** `liveSearchController` product/patent persist → `create_infringement`.

---

## Documents — `getDocumentDatabaseName()`

**Code:** [`structures/documents.py`](../structures/documents.py)

| Field | Type | Notes |
|-------|------|--------|
| `_id`, `file_name`, `file_type`, `file_size` | | PDF/XML upload API ≤12MB |
| `created_at`, `created_by`, `case_id` | | |
| `file_content` | bytes | Binary **in Mongo** |
| `source_url` | str | Optional (manuals) |

Case gets pointer `{url: "document/{id}", source: "local"}` (+ manuals: `source_url`, `product_manual: true`).

---

## Folders — `getFolderDatabaseName()`

**Code:** [`structures/folders.py`](../structures/folders.py)

| Field | Type | Notes |
|-------|------|--------|
| `_id` | uuid4 str | |
| `name` | str | Non-empty required |
| `created_by`, `owner` | str | Delete permission |
| `viewers`, `editors`, `cases` | list[str] | Deduped; bidirectional with case `folders` |

---

## Alerts — `getAlertDatabaseName()`

**Code:** [`structures/alerts.py`](../structures/alerts.py) → `add_to_alerts`

| Field | Type | Notes |
|-------|------|--------|
| `_id` | str | Often `str(int(time.time()))` |
| `title`, `description` | str | |
| `triggered_by`, `triggered_at` | str | |
| `alert_users` | list[str] | |
| `opened_receipts`, `sent_receipts` | list | Init `[]` |

---

## Search history — `getSearchHistoryDatabaseName()`

**Code:** [`structures/search_history.py`](../structures/search_history.py)

| Field | Type | Notes |
|-------|------|--------|
| `created_by` | str | User id |
| `search_query` | str | Required on API |
| `search_results` | any | Required non-empty on API |

---

## Demo — `getDemoDatabaseName()`

**Code:** [`structures/demo.py`](../structures/demo.py)

| Field | Type | Notes |
|-------|------|--------|
| `_id` | str | `demo_req_{uuid8}` |
| `name`, `email`, `organization`, `role`, `date`, `time`, `timezone` | str | All required |
| `status` | str | `'pending'` on create |
| `created_at` | str | UTC ISO + `Z` |

---

## Audit — `getAuditDatabaseName()`

**Code:** [`structures/audit.py`](../structures/audit.py) — append-only (no update/delete helpers).

| Field | Type | Notes |
|-------|------|--------|
| `_id` | uuid4 str | |
| `user_id`, `case_id` | str | Required non-empty |
| `kind` | str | Must be in `AUDIT_KINDS` |
| `text`, `status`, `request_id`, `source` | str | |
| `payload` | dict | Default `{}` |
| `created_at` | str | UTC ISO |

**`AUDIT_KINDS`:** `patent_fetch`, `analysis_start`, `analysis_complete`, `analysis_failed`, `clarification`, `chat_message`, `case_update_via_ai`, `mcp_action`, `manual_relevance`.

Writers: `controller.py`, `mcp_tools/mcp.py`, `live_search/product_manuals.py`.

---

## Cross-cutting

1. Cases are schema-flexible (USPTO vs Gemini vs manual differ in casing and optional fields).
2. Infringements collection holds full hits with `parent_case_id`; case may still hold a legacy `infringements` list.
3. Documents store binary blobs; cases store URL pointers only.
4. Correlate Mongo case `_id` with Chroma metadata `case_id`.
