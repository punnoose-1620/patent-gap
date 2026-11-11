"""
Product instruction/repair manual enrichment.

Flow (per product after listing isolation):
  search manuals (Gemini + GCSE) → fetch into temp buffer → AI relevance check
  → only if relevant: attach to case.documents + append claims.

Non-relevant manuals are never written to cases/documents.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, Field

from ai_workflow.orchestration import get_ai_client as _get_ai_client
from env_controller import getEnvKey
from file_controller import readFromPdfUrl
from live_search.googleSearch import (
    SESSION_HEADERS,
    SEARCH_TIMEOUT,
    __initialSearch,
    is_google_custom_search_configured,
)
from structures.audit import add_audit_entry
from structures.cases import get_case_by_id, update_case
from structures.documents import createDocument
from web_search import check_html_for_runtime_errors, convertHtmlToString

# In-memory inspect cache: cache_id -> {url, text, raw_bytes, content_type, ...}
_MANUAL_CACHE: dict[str, dict[str, Any]] = {}

MAX_MANUAL_URLS_PER_KIND = 2
MAX_PREVIEW_CHARS = 6000
MAX_CLAIM_SOURCE_CHARS = 24000
MAX_PDF_BYTES = 12 * 1024 * 1024


def manuals_enrichment_enabled() -> bool:
    raw = (os.environ.get("PRODUCT_MANUAL_ENRICHMENT") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def Gemini():
    return _get_ai_client()


class ManualRelevanceResult(BaseModel):
    relevant: bool = False
    confidence: float = 0.0
    reason: str = ""
    matched_features: list[str] = Field(default_factory=list)
    mismatched_features: list[str] = Field(default_factory=list)


class ManualClaimsResult(BaseModel):
    claims: list[str] = Field(default_factory=list)


def _host_from_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url.strip()}")
    return (parsed.netloc or "").lower().lstrip("www.")


def _looks_like_pdf_url(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    return path.endswith(".pdf") or ".pdf?" in (url or "").lower()


def official_sites_for_product(
    product_url: str = "",
    source: str = "",
    extra_sites: list[str] | None = None,
) -> list[str]:
    """Prefer the product's own host + any caller-supplied official sites."""
    sites: list[str] = []
    for candidate in (
        _host_from_url(product_url),
        _host_from_url(source) if "://" in (source or "") else "",
        *(extra_sites or []),
    ):
        host = (candidate or "").strip().lower().lstrip("www.")
        if host and host not in sites and "." in host:
            sites.append(host)
    return sites


def build_manual_search_queries(
    product_name: str,
    listing_features: list[str],
    *,
    official_sites: list[str] | None = None,
    kind: str = "instruction",
) -> list[str]:
    """
    Build site-scoped queries. kind: instruction | repair.
    Uses listing feature snippets so variant SKUs (e.g. Ryzen vs i5) stay distinct.
    """
    name = (product_name or "").strip()
    if not name:
        return []
    feature_bits = [
        f.strip()
        for f in (listing_features or [])[:6]
        if isinstance(f, str) and f.strip()
    ]
    feature_clause = " ".join(feature_bits)[:180]
    if kind == "repair":
        doc_terms = ['"service manual"', '"repair manual"', '"technician guide"']
    else:
        doc_terms = ['"instruction manual"', '"user guide"', '"user manual"', "filetype:pdf"]

    queries: list[str] = []
    sites = official_sites or []
    for term in doc_terms[:3]:
        if sites:
            site_or = " OR ".join(f"site:{s}" for s in sites[:4])
            q = f"({site_or}) {name} {feature_clause} {term}".strip()
        else:
            q = f"{name} {feature_clause} {term}".strip()
        queries.append(re.sub(r"\s+", " ", q))
    return list(dict.fromkeys(queries))


def search_manual_urls(
    *,
    user_id: str,
    case_id: str,
    product_name: str,
    listing_features: list[str],
    official_sites: list[str] | None = None,
    kind: str = "instruction",
    max_results: int = MAX_MANUAL_URLS_PER_KIND,
) -> list[dict[str, str]]:
    """
    Gemini grounded search + optional GCSE. Returns [{title, url, website_name, description, via}].
    """
    queries = build_manual_search_queries(
        product_name,
        listing_features,
        official_sites=official_sites,
        kind=kind,
    )
    if not queries:
        return []

    seen: set[str] = set()
    out: list[dict[str, str]] = []

    # Gemini path (reuse existing search helper)
    try:
        priority = [{"title": s, "url": f"https://{s}"} for s in (official_sites or [])]
        for query in queries[:2]:
            if len(out) >= max_results:
                break
            try:
                results = Gemini().perform_google_search(
                    search_string=query,
                    max_results=max_results,
                    priority_target_sources=priority or None,
                )
            except Exception as exc:
                print(f"LOG: manual Gemini search failed ({type(exc).__name__}: {exc})")
                continue
            for item in results or []:
                url = (getattr(item, "url", None) or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                out.append(
                    {
                        "title": (getattr(item, "title", None) or url).strip(),
                        "url": url,
                        "website_name": (
                            getattr(item, "website_name", None) or _host_from_url(url)
                        ),
                        "description": (getattr(item, "description", None) or "").strip(),
                        "via": "gemini",
                        "kind": kind,
                    }
                )
                if len(out) >= max_results:
                    break
    except Exception as exc:
        print(f"LOG: manual Gemini search block failed ({type(exc).__name__}: {exc})")

    # GCSE backup / complement
    if is_google_custom_search_configured() and len(out) < max_results:
        for query in queries:
            if len(out) >= max_results:
                break
            try:
                cse_hits = __initialSearch(query, max_results=max_results)
            except Exception as exc:
                print(f"LOG: manual CSE search failed ({type(exc).__name__}: {exc})")
                continue
            for item in cse_hits or []:
                url = (getattr(item, "url", None) or "").strip()
                if not url or url in seen:
                    continue
                # Soft prefer official hosts when provided
                if official_sites:
                    host = _host_from_url(url)
                    if host and not any(
                        host == s or host.endswith("." + s) for s in official_sites
                    ):
                        # keep as fallback only if we still have room later
                        pass
                seen.add(url)
                out.append(
                    {
                        "title": (getattr(item, "title", None) or url).strip(),
                        "url": url,
                        "website_name": (
                            getattr(item, "website_name", None) or _host_from_url(url)
                        ),
                        "description": (getattr(item, "description", None) or "").strip(),
                        "via": "gcse",
                        "kind": kind,
                    }
                )
                if len(out) >= max_results:
                    break

    try:
        add_audit_entry(
            user_id=user_id,
            case_id=case_id,
            kind="mcp_action",
            text=f"Manual {kind} search for {product_name!r}",
            payload={
                "tool": "search_manual_urls",
                "kind": kind,
                "query_count": len(queries),
                "result_count": len(out),
                "official_sites": official_sites or [],
            },
            status="completed",
            source="product_manuals",
        )
    except Exception:
        pass

    return out[:max_results]


def fetch_url_for_inspection(
    *,
    user_id: str,
    case_id: str,
    url: str,
) -> dict[str, Any]:
    """
    Download URL into a temp cache for agent/pipeline inspection.
    Does NOT write to cases or documents.
    """
    url = (url or "").strip()
    if not url:
        return {"success": False, "error": "url is required"}

    cache_id = str(uuid.uuid4())
    content_type = ""
    raw_bytes: bytes | None = None
    text = ""
    is_pdf = _looks_like_pdf_url(url)

    try:
        response = requests.get(
            url,
            headers=SESSION_HEADERS,
            timeout=SEARCH_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").lower()
        raw_bytes = response.content or b""
        final_url = str(response.url or url)
        if "pdf" in content_type or _looks_like_pdf_url(final_url):
            is_pdf = True
        if is_pdf:
            if len(raw_bytes) > MAX_PDF_BYTES:
                return {
                    "success": False,
                    "error": f"PDF exceeds {MAX_PDF_BYTES} bytes",
                    "url": final_url,
                }
            # Extract text via existing helper (re-fetch is ok; also try bytes path)
            text = readFromPdfUrl(final_url, headers=SESSION_HEADERS) or ""
            if not text and raw_bytes:
                try:
                    import io
                    import PyPDF2

                    reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
                    parts = []
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            parts.append(extracted)
                    text = "\n".join(parts)
                except Exception as exc:
                    print(f"LOG: PDF bytes extract failed ({type(exc).__name__}: {exc})")
        else:
            html = raw_bytes.decode(response.encoding or "utf-8", errors="replace")
            blocked, keyword = check_html_for_runtime_errors(html, url=final_url)
            if blocked:
                return {
                    "success": False,
                    "error": f"Blocked/error page: {keyword}",
                    "url": final_url,
                }
            try:
                text = convertHtmlToString(html) or html
            except Exception:
                text = html
            raw_bytes = None  # don't keep large HTML blobs for attach
            url = final_url
    except Exception as exc:
        return {"success": False, "error": f"{type(exc).__name__}: {exc}", "url": url}

    text = (text or "").strip()
    if not text:
        return {"success": False, "error": "No extractable text", "url": url}

    preview = text[:MAX_PREVIEW_CHARS]
    _MANUAL_CACHE[cache_id] = {
        "url": url,
        "text": text[:MAX_CLAIM_SOURCE_CHARS],
        "raw_bytes": raw_bytes if is_pdf else None,
        "content_type": "application/pdf" if is_pdf else (content_type or "text/html"),
        "is_pdf": is_pdf,
        "user_id": user_id,
        "case_id": case_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    return {
        "success": True,
        "cache_id": cache_id,
        "url": url,
        "is_pdf": is_pdf,
        "content_type": "application/pdf" if is_pdf else content_type,
        "preview": preview,
        "char_count": len(text),
        "attached": False,
    }


def assess_manual_relevance(
    *,
    user_id: str,
    case_id: str,
    product_name: str,
    listing_features: list[str],
    manual_text: str,
    manual_url: str = "",
    cache_id: str = "",
) -> dict[str, Any]:
    """AI relevance check: does this manual match THIS product variant? Audited; no case write."""
    features = [
        f.strip()
        for f in (listing_features or [])[:20]
        if isinstance(f, str) and f.strip()
    ]
    body = (manual_text or "")[:MAX_PREVIEW_CHARS]
    prompt = f"""
You compare a product listing to a candidate instruction/repair manual.
Decide if the manual is for the SAME specific product variant (not a sibling SKU).

Product name: {product_name}
Listing features / claims:
{chr(10).join(f'- {f}' for f in features) or '(none)'}

Manual URL: {manual_url or '(unknown)'}
Manual excerpt:
{body}

Return JSON with:
- relevant (bool): true only if the manual clearly covers this product/variant
- confidence (0-1)
- reason (short)
- matched_features (list of listing features found in the manual)
- mismatched_features (list of listing features that contradict the manual)

Reject sponsored pages, wrong brand, wrong model family, or variants that differ on
distinguishing features (e.g. Ryzen 5 vs Intel i5 of the same Pavilion line).
""".strip()

    relevant = False
    confidence = 0.0
    reason = ""
    matched: list[str] = []
    mismatched: list[str] = []
    try:
        from llm_brain.gemini import Gemini as _GeminiCore

        api = _GeminiCore()._client
        response = api.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ManualRelevanceResult.model_json_schema(),
            },
        )
        parsed = ManualRelevanceResult.model_validate_json(response.text)
        relevant = bool(parsed.relevant)
        confidence = float(parsed.confidence or 0.0)
        reason = (parsed.reason or "").strip()
        matched = list(parsed.matched_features or [])
        mismatched = list(parsed.mismatched_features or [])
    except Exception as exc:
        reason = f"relevance_check_failed: {type(exc).__name__}: {exc}"
        print(f"LOG: {reason}")
        relevant = False

    try:
        add_audit_entry(
            user_id=user_id,
            case_id=case_id,
            kind="manual_relevance",
            text=f"Manual relevance {'accepted' if relevant else 'rejected'} for {product_name!r}",
            payload={
                "product_name": product_name,
                "manual_url": manual_url,
                "cache_id": cache_id,
                "relevant": relevant,
                "confidence": confidence,
                "reason": reason,
                "matched_features": matched[:10],
                "mismatched_features": mismatched[:10],
            },
            status="accepted" if relevant else "rejected",
            source="product_manuals",
        )
    except Exception:
        pass

    # Drop rejected cache entries so they cannot be attached later
    if not relevant and cache_id and cache_id in _MANUAL_CACHE:
        _MANUAL_CACHE.pop(cache_id, None)

    return {
        "relevant": relevant,
        "confidence": confidence,
        "reason": reason,
        "matched_features": matched,
        "mismatched_features": mismatched,
        "cache_id": cache_id if relevant else "",
    }


def extract_claims_from_manual_text(
    *,
    product_name: str,
    manual_text: str,
) -> list[str]:
    """Extract technical claim-like strings from a verified manual excerpt."""
    body = (manual_text or "")[:MAX_CLAIM_SOURCE_CHARS]
    if not body.strip():
        return []
    prompt = f"""
Extract technical product capabilities, specifications, procedures, and hardware/
software features from this instruction or repair manual for "{product_name}".
Prefer concrete specs over marketing language.
Return JSON: {{"claims": ["...", "..."]}}
Rules:
- Each claim is one clear capability or spec statement
- Skip empty, generic, or unrelated lines
- Max 25 claims
Manual:
{body}
""".strip()
    try:
        from llm_brain.gemini import Gemini as _GeminiCore

        api = _GeminiCore()._client
        response = api.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ManualClaimsResult.model_json_schema(),
            },
        )
        parsed = ManualClaimsResult.model_validate_json(response.text)
        claims = []
        for c in parsed.claims or []:
            if isinstance(c, str) and c.strip():
                claims.append(c.strip())
        return claims[:25]
    except Exception as exc:
        print(f"LOG: manual claim extract failed ({type(exc).__name__}: {exc})")
        return []


def attach_cached_manual_to_case(
    *,
    user_id: str,
    case_id: str,
    cache_id: str,
    source_tag: str = "instruction_manual",
    file_name: str = "",
) -> dict[str, Any]:
    """
    Persist a previously inspected+accepted manual onto the case.
    Requires cache entry (relevance accept keeps cache; reject clears it).
    """
    entry = _MANUAL_CACHE.get(cache_id)
    if not entry:
        return {
            "success": False,
            "error": "cache_id not found or was rejected — fetch and accept again",
        }
    if entry.get("case_id") != case_id:
        return {"success": False, "error": "cache_id does not belong to this case_id"}

    raw = entry.get("raw_bytes")
    is_pdf = bool(entry.get("is_pdf"))
    url = entry.get("url") or ""
    if is_pdf and raw:
        if len(raw) > MAX_PDF_BYTES:
            return {"success": False, "error": "PDF too large to attach"}
        name = file_name or os.path.basename(urlparse(url).path) or "manual.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        doc_payload = {
            "file_name": name,
            "file_type": "application/pdf",
            "file_size": len(raw),
            "created_at": datetime.utcnow().isoformat(),
            "created_by": user_id,
            "case_id": case_id,
            "file_content": raw,
            "source_url": url,
        }
        created = createDocument(doc_payload)
        if not created.get("success"):
            return {"success": False, "error": created.get("message") or "createDocument failed"}
        document_id = created.get("document_id")
        document_url = f"document/{document_id}"
    else:
        # HTML manuals: store a lightweight pointer document without binary
        document_id = None
        document_url = url

    case = get_case_by_id(case_id) or {}
    documents = list(case.get("documents") or [])
    documents.append(
        {
            "url": document_url,
            "source": source_tag or "instruction_manual",
            "source_url": url,
            "product_manual": True,
        }
    )
    update_result = update_case(case_id, {"documents": documents})
    if not update_result.get("success"):
        return {
            "success": False,
            "error": update_result.get("message") or "failed to update case documents",
        }

    try:
        add_audit_entry(
            user_id=user_id,
            case_id=case_id,
            kind="case_update_via_ai",
            text=f"Attached verified manual to case ({source_tag})",
            payload={
                "tool": "attach_cached_manual_to_case",
                "cache_id": cache_id,
                "document_id": document_id,
                "document_url": document_url,
                "source_tag": source_tag,
                "source_url": url,
            },
            status="completed",
            source="product_manuals",
        )
    except Exception:
        pass

    # Keep text for claim merge; drop raw bytes after attach
    entry["raw_bytes"] = None
    entry["attached"] = True

    return {
        "success": True,
        "document_id": document_id,
        "document_url": document_url,
        "source": source_tag,
        "source_url": url,
    }


def drop_manual_cache(cache_id: str) -> None:
    _MANUAL_CACHE.pop(cache_id or "", None)


def get_manual_cache_entry(cache_id: str) -> dict[str, Any] | None:
    """Return a shallow copy of cache metadata/text (no raw_bytes) for callers/MCP."""
    entry = _MANUAL_CACHE.get(cache_id or "")
    if not entry:
        return None
    return {
        "url": entry.get("url"),
        "text": entry.get("text"),
        "content_type": entry.get("content_type"),
        "is_pdf": entry.get("is_pdf"),
        "case_id": entry.get("case_id"),
        "attached": bool(entry.get("attached")),
    }


def enrich_product_with_manuals(
    product_details: Any,
    *,
    user_id: str,
    case_id: str,
    official_sites: list[str] | None = None,
) -> Any:
    """
    Pipeline helper: after listing isolation, search/verify manuals and append claims.
    Only attaches relevant manuals. Safe no-op on failure.
    """
    if not manuals_enrichment_enabled():
        return product_details
    if not user_id or not case_id:
        return product_details

    try:
        name = getattr(product_details, "product_name", None) or ""
        product_url = getattr(product_details, "product_url", None) or ""
        source = getattr(product_details, "source", None) or ""
        claims = list(getattr(product_details, "claims", None) or [])
        if not name:
            return product_details

        sites = official_sites_for_product(
            product_url=product_url,
            source=source,
            extra_sites=official_sites,
        )
        new_claims: list[str] = []

        for kind, source_tag in (
            ("instruction", "instruction_manual"),
            ("repair", "repair_manual"),
        ):
            hits = search_manual_urls(
                user_id=user_id,
                case_id=case_id,
                product_name=name,
                listing_features=claims,
                official_sites=sites,
                kind=kind,
                max_results=MAX_MANUAL_URLS_PER_KIND,
            )
            for hit in hits:
                url = hit.get("url") or ""
                fetched = fetch_url_for_inspection(
                    user_id=user_id, case_id=case_id, url=url
                )
                if not fetched.get("success"):
                    continue
                cache_id = fetched.get("cache_id") or ""
                preview = fetched.get("preview") or ""
                verdict = assess_manual_relevance(
                    user_id=user_id,
                    case_id=case_id,
                    product_name=name,
                    listing_features=claims,
                    manual_text=preview,
                    manual_url=url,
                    cache_id=cache_id,
                )
                if not verdict.get("relevant"):
                    print(
                        f"LOG: Manual rejected for {name!r}: {url} — {verdict.get('reason')}"
                    )
                    continue
                attach = attach_cached_manual_to_case(
                    user_id=user_id,
                    case_id=case_id,
                    cache_id=cache_id,
                    source_tag=source_tag,
                )
                if not attach.get("success"):
                    print(f"LOG: Manual attach failed: {attach.get('error')}")
                    # still allow claim extract from cache text if present
                cached = _MANUAL_CACHE.get(cache_id) or {}
                manual_claims = extract_claims_from_manual_text(
                    product_name=name,
                    manual_text=cached.get("text") or preview,
                )
                for mc in manual_claims:
                    if mc not in claims and mc not in new_claims:
                        new_claims.append(mc)
                # One good manual per kind is enough
                if manual_claims or attach.get("success"):
                    break

        if new_claims:
            product_details.claims = list(claims) + new_claims
            print(
                f"LOG: Appended {len(new_claims)} manual-derived claim(s) for {name!r}"
            )
    except Exception as exc:
        print(
            f"LOG: enrich_product_with_manuals failed ({type(exc).__name__}: {exc})"
        )
    return product_details
