"""
Product instruction/repair manual enrichment.

Flow (per product after listing isolation):
  SKU gate → search manuals (GCSE query strings + Gemini rule brief, separately)
  → URL filter/rank → fetch into temp buffer → validity+relevance check
  → only if valid manual AND same variant: attach + append claims.

Product listings / PDPs are never treated as manuals. If no valid manual is
found, nothing is attached (no listing fallback).
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

MAX_MANUAL_URLS_PER_KIND = 3
MAX_SEARCH_CANDIDATES = 8
MAX_PREVIEW_CHARS = 6000
MAX_CLAIM_SOURCE_CHARS = 24000
MAX_PDF_BYTES = 12 * 1024 * 1024

# Third-party hosts that publish instruction/repair manuals (not storefronts).
KNOWN_MANUAL_HOSTS = (
    "ifixit.com",
    "manualslib.com",
    "manualsonline.com",
    "manuals.plus",
    "device.report",
)

# Category / portfolio names that are not a single product variant.
_GENERIC_PRODUCT_NAMES = frozenset(
    {
        "hinges",
        "switch",
        "switches",
        "network switches",
        "network cameras",
        "connectivity solutions",
        "products",
        "product catalog",
        "samsung dishwashers",
        "laser product finder",
        "kitchen & home appliances",
        "kitchen and home appliances",
        "professional power solutions",
        "cyberpower professional power solutions",
    }
)

_MODEL_TOKEN_RE = re.compile(
    r"\b("
    r"[A-Z]{1,6}\d{2,}[A-Z0-9\-]{0,16}"  # TPS2372, DW80R9950US, DLP4710
    r"|[A-Z]{2,}[-_][A-Z0-9]{2,}(?:[-_][A-Z0-9]+){0,4}"  # USW-Pro-48-PoE
    r"|\d{2,}[A-Z]{1,6}\d{0,8}[A-Z]{0,6}"  # 38dBA style mixed
    r")\b",
    re.I,
)

_MANUAL_URL_HINTS = (
    ".pdf",
    "manual",
    "guide",
    "instruction",
    "repair",
    "service",
    "support",
    "datasheet",
    "data-sheet",
    "download",
    "downloads",
    "documentation",
    "technician",
    "ifixit",
    "user-guide",
    "userguide",
    "owner-manual",
    "installation",
)

_LISTING_URL_HINTS = (
    "/cart",
    "/buy",
    "/checkout",
    "/wishlist",
    "/compare",
    "/category/",
    "/categories/",
    "/collections/",
    "/browse/",
    "/search?",
    "/s?k=",
    "/dp/",
    "/gp/product",
)

_ALLOWED_DOC_TYPES = frozenset(
    {
        "instruction_manual",
        "user_manual",
        "user_guide",
        "repair_manual",
        "service_manual",
        "technician_guide",
        "installation_guide",
        "datasheet",
    }
)

_REJECT_DOC_TYPES = frozenset(
    {
        "product_listing",
        "marketing",
        "solutions_overview",
        "category_page",
        "storefront",
        "finder_tool",
        "other",
    }
)


def manuals_enrichment_enabled() -> bool:
    raw = (os.environ.get("PRODUCT_MANUAL_ENRICHMENT") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def Gemini():
    return _get_ai_client()


class ManualValidityRelevanceResult(BaseModel):
    """Validity (document type) + relevance (same product variant)."""

    valid_document: bool = False
    document_type: str = "other"
    relevant: bool = False
    confidence: float = 0.0
    reason: str = ""
    matched_features: list[str] = Field(default_factory=list)
    mismatched_features: list[str] = Field(default_factory=list)


# Backward-compatible alias for older imports/MCP callers.
class ManualRelevanceResult(ManualValidityRelevanceResult):
    pass


class ManualClaimsResult(BaseModel):
    claims: list[str] = Field(default_factory=list)


class ManualSearchHit(BaseModel):
    title: str = ""
    url: str = ""
    website_name: str = ""
    description: str = ""


class ManualSearchHitList(BaseModel):
    results: list[ManualSearchHit] = Field(default_factory=list)


def _host_from_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url.strip()}")
    return (parsed.netloc or "").lower().lstrip("www.")


def _looks_like_pdf_url(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    return path.endswith(".pdf") or ".pdf?" in (url or "").lower()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower().lstrip("www.")
    path = (parsed.path or "").rstrip("/").lower()
    return f"{host}{path}"


def _path_from_url(url: str) -> str:
    return (urlparse(url or "").path or "").lower()


def extract_model_tokens(*texts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in _MODEL_TOKEN_RE.finditer(str(text)):
            token = match.group(1).strip()
            key = token.lower()
            if key in seen or len(token) < 4:
                continue
            # Skip pure years / tiny numbers
            if re.fullmatch(r"\d{4}", token):
                continue
            seen.add(key)
            found.append(token)
    return found


def product_has_concrete_sku(
    product_name: str = "",
    listing_features: list[str] | None = None,
    product_url: str = "",
) -> dict[str, Any]:
    """
    Require a concrete model/SKU before manuals enrichment.
    Category / finder / portfolio listings return ok=False.
    """
    name = (product_name or "").strip()
    name_l = name.lower()
    if not name:
        return {"ok": False, "reason": "empty_product_name", "tokens": []}

    if name_l in _GENERIC_PRODUCT_NAMES:
        return {"ok": False, "reason": "generic_product_name", "tokens": []}

    # Soft generic patterns (category hubs)
    generic_patterns = (
        r"^samsung\s+dishwashers?$",
        r"^.*\bproduct finder\b.*$",
        r"^.*\bproduct catalog\b.*$",
        r"^.*\bsolutions?\b$",
        r"^network\s+cameras?$",
        r"^kitchen\b.*\bappliances?\b$",
    )
    for pat in generic_patterns:
        if re.search(pat, name_l):
            return {"ok": False, "reason": "generic_product_pattern", "tokens": []}

    feature_blob = " ".join(
        f.strip()
        for f in (listing_features or [])[:12]
        if isinstance(f, str) and f.strip()
    )
    path = _path_from_url(product_url)
    tokens = extract_model_tokens(name, feature_blob, path.replace("/", " ").replace("-", " "))
    if tokens:
        return {"ok": True, "reason": "model_token", "tokens": tokens[:8]}

    # Hyphenated product slug with digit often encodes SKU (usw-pro-max-24-poe)
    slug = path.rstrip("/").split("/")[-1] if path else ""
    if slug and re.search(r"\d", slug) and len(slug) >= 6 and slug.count("-") >= 1:
        if not any(
            x in slug
            for x in ("category", "collection", "all-", "products", "solutions")
        ):
            return {"ok": True, "reason": "url_slug_with_digits", "tokens": [slug]}

    return {"ok": False, "reason": "no_concrete_sku", "tokens": []}


def official_sites_for_product(
    product_url: str = "",
    source: str = "",
    extra_sites: list[str] | None = None,
) -> list[str]:
    """
    Prefer brand host, support.<brand>, and caller extras.
    Known third-party manual hosts are appended for search (not as product sites).
    """
    sites: list[str] = []

    def _add(host: str) -> None:
        host = (host or "").strip().lower().lstrip("www.")
        if host and host not in sites and "." in host:
            sites.append(host)

    brand = _host_from_url(product_url)
    if brand:
        _add(brand)
        # Common OEM support subdomain
        if not brand.startswith("support."):
            _add(f"support.{brand}")
            # support.hp.com style already covered; also downloads.
            _add(f"downloads.{brand}")

    if "://" in (source or ""):
        _add(_host_from_url(source))
    elif source and "." in source and " " not in source:
        _add(source)

    for candidate in extra_sites or []:
        if "://" in (candidate or ""):
            _add(_host_from_url(candidate))
        else:
            _add(candidate)

    for host in KNOWN_MANUAL_HOSTS:
        _add(host)

    return sites


def url_manual_score(url: str, product_url: str = "") -> int:
    """Higher is better. Negative means hard-reject."""
    if not url:
        return -100
    ul = url.lower()
    if product_url and _normalize_url(url) == _normalize_url(product_url):
        return -100
    if any(h in ul for h in _LISTING_URL_HINTS):
        return -50
    score = 0
    if _looks_like_pdf_url(ul):
        score += 50
    for hint in _MANUAL_URL_HINTS:
        if hint in ul:
            score += 8
    host = _host_from_url(ul)
    if host in KNOWN_MANUAL_HOSTS or any(
        host.endswith("." + h) for h in KNOWN_MANUAL_HOSTS
    ):
        score += 20
    if host.startswith("support.") or host.startswith("downloads."):
        score += 15
    # Pure product/solutions PDP without manual hints
    path = _path_from_url(ul)
    listing_path = any(
        p in path
        for p in ("/product/", "/products/", "/solutions/", "/shop/", "/store/")
    )
    if listing_path and score < 8:
        return -20
    return score


def is_plausible_manual_url(url: str, product_url: str = "") -> bool:
    return url_manual_score(url, product_url=product_url) >= 0


def rank_manual_candidates(
    hits: list[dict[str, str]],
    *,
    product_url: str = "",
    max_results: int = MAX_MANUAL_URLS_PER_KIND,
) -> list[dict[str, str]]:
    scored: list[tuple[int, dict[str, str]]] = []
    seen: set[str] = set()
    for hit in hits:
        url = (hit.get("url") or "").strip()
        if not url:
            continue
        key = _normalize_url(url)
        if key in seen:
            continue
        score = url_manual_score(url, product_url=product_url)
        if score < 0:
            continue
        seen.add(key)
        scored.append((score, hit))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [hit for _, hit in scored[:max_results]]


def build_gcse_manual_queries(
    product_name: str,
    listing_features: list[str],
    *,
    official_sites: list[str] | None = None,
    kind: str = "instruction",
    model_tokens: list[str] | None = None,
) -> list[str]:
    """Traditional GCSE operator strings for manuals/PDFs (not product discovery)."""
    name = (product_name or "").strip()
    if not name:
        return []
    tokens = list(model_tokens or [])[:3]
    token_clause = " ".join(tokens)
    feature_bits = [
        f.strip()
        for f in (listing_features or [])[:4]
        if isinstance(f, str) and f.strip()
    ]
    feature_clause = " ".join(feature_bits)[:120]
    if kind == "repair":
        doc_terms = ['"service manual"', '"repair manual"', '"technician guide"']
    else:
        doc_terms = [
            '"instruction manual" OR "user manual" OR "user guide"',
            "filetype:pdf",
            '"installation guide" OR "owner manual"',
        ]

    negatives = (
        "-inurl:cart -inurl:checkout -inurl:wishlist "
        "-inurl:amazon -inurl:ebay -inurl:walmart"
    )
    sites = [
        s
        for s in (official_sites or [])
        if s and s not in ("amazon.com", "ebay.com", "walmart.com", "bestbuy.com")
    ][:5]

    queries: list[str] = []
    for term in doc_terms:
        core = f"{name} {token_clause} {feature_clause} {term} {negatives}".strip()
        if sites:
            site_or = " OR ".join(f"site:{s}" for s in sites)
            queries.append(re.sub(r"\s+", " ", f"({site_or}) {core}"))
        else:
            queries.append(re.sub(r"\s+", " ", core))
    return list(dict.fromkeys(queries))


# Keep old name as alias for GCSE-oriented callers.
build_manual_search_queries = build_gcse_manual_queries


def build_gemini_manual_brief(
    product_name: str,
    listing_features: list[str],
    *,
    official_sites: list[str] | None = None,
    kind: str = "instruction",
    model_tokens: list[str] | None = None,
    max_results: int = MAX_MANUAL_URLS_PER_KIND,
) -> str:
    """Natural-language rule brief for Gemini manuals search (not product PDPs)."""
    name = (product_name or "").strip()
    tokens = ", ".join(model_tokens or []) or "(none extracted)"
    features = [
        f.strip()
        for f in (listing_features or [])[:10]
        if isinstance(f, str) and f.strip()
    ]
    sites = official_sites or []
    kind_label = (
        "repair/service/technician manuals"
        if kind == "repair"
        else "instruction/user/owner/installation manuals"
    )
    return f"""
Find official {kind_label} for ONE specific product variant.

Product name: {name}
Model / SKU tokens (must match when present): {tokens}
Listing features:
{chr(10).join(f'- {f}' for f in features) or '(none)'}

Preferred domains (use when relevant):
{chr(10).join(f'- {s}' for s in sites) or '(any official support/manual host)'}

Return up to {max_results} distinct real web results as JSON:
{{
  "results": [
    {{
      "title": "...",
      "url": "...",
      "website_name": "...",
      "description": "..."
    }}
  ]
}}

HARD RULES:
- Return ONLY instruction manuals, user guides, service/repair manuals, installation
  guides, technician docs, or technical datasheets (PDF preferred).
- Do NOT return product listing pages, shop/cart pages, category hubs, solutions
  marketing overviews, "product finder" tools, or retailer storefronts.
- Do NOT return Amazon, eBay, Walmart, Best Buy, Home Depot, Lowe's product pages.
- Prefer manufacturer support/download/PDF URLs and known manual hosts (iFixit, ManualsLib).
- Prefer documents that explicitly name the same model/SKU tokens when available.
- Every URL must be a real link you can justify from search — never invent paths.
- If no qualifying manual is found, return {{"results": []}}.
""".strip()


def _search_manuals_via_gemini(
    *,
    product_name: str,
    listing_features: list[str],
    official_sites: list[str] | None,
    kind: str,
    model_tokens: list[str] | None,
    max_results: int,
) -> list[dict[str, str]]:
    brief = build_gemini_manual_brief(
        product_name,
        listing_features,
        official_sites=official_sites,
        kind=kind,
        model_tokens=model_tokens,
        max_results=max_results,
    )
    out: list[dict[str, str]] = []
    try:
        from llm_brain.gemini import Gemini as _GeminiCore

        api = _GeminiCore()._client
        response = api.models.generate_content(
            model="gemini-2.5-flash",
            contents=brief,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ManualSearchHitList.model_json_schema(),
            },
        )
        wrapper = ManualSearchHitList.model_validate_json(response.text)
        for item in wrapper.results or []:
            url = (item.url or "").strip()
            if not url:
                continue
            out.append(
                {
                    "title": (item.title or url).strip(),
                    "url": url,
                    "website_name": (item.website_name or _host_from_url(url)).strip(),
                    "description": (item.description or "").strip(),
                    "via": "gemini_manuals",
                    "kind": kind,
                }
            )
            if len(out) >= max_results:
                break
    except Exception as exc:
        print(f"LOG: manual Gemini rule-search failed ({type(exc).__name__}: {exc})")
    return out


def _search_manuals_via_gcse(
    *,
    product_name: str,
    listing_features: list[str],
    official_sites: list[str] | None,
    kind: str,
    model_tokens: list[str] | None,
    max_results: int,
) -> list[dict[str, str]]:
    if not is_google_custom_search_configured():
        return []
    queries = build_gcse_manual_queries(
        product_name,
        listing_features,
        official_sites=official_sites,
        kind=kind,
        model_tokens=model_tokens,
    )
    out: list[dict[str, str]] = []
    seen: set[str] = set()
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
    return out


def search_manual_urls(
    *,
    user_id: str,
    case_id: str,
    product_name: str,
    listing_features: list[str],
    official_sites: list[str] | None = None,
    kind: str = "instruction",
    max_results: int = MAX_MANUAL_URLS_PER_KIND,
    product_url: str = "",
    require_sku: bool = True,
) -> list[dict[str, str]]:
    """
    GCSE (operator strings) + Gemini (manuals-only rule brief), then URL filter/rank.
    Does not attach anything. Skips search when require_sku and no concrete SKU.
    """
    sku = product_has_concrete_sku(
        product_name, listing_features, product_url=product_url
    )
    if require_sku and not sku.get("ok"):
        try:
            add_audit_entry(
                user_id=user_id,
                case_id=case_id,
                kind="mcp_action",
                text=f"Manual search skipped for {product_name!r} (no concrete SKU)",
                payload={
                    "tool": "search_manual_urls",
                    "kind": kind,
                    "skipped": True,
                    "sku_gate": sku,
                },
                status="skipped",
                source="product_manuals",
            )
        except Exception:
            pass
        print(
            f"LOG: Manual search skipped for {product_name!r}: {sku.get('reason')}"
        )
        return []

    model_tokens = list(sku.get("tokens") or [])
    sites = official_sites or []

    # Prefer GCSE PDFs when configured; always also try Gemini manuals brief.
    raw: list[dict[str, str]] = []
    raw.extend(
        _search_manuals_via_gcse(
            product_name=product_name,
            listing_features=listing_features,
            official_sites=sites,
            kind=kind,
            model_tokens=model_tokens,
            max_results=MAX_SEARCH_CANDIDATES,
        )
    )
    raw.extend(
        _search_manuals_via_gemini(
            product_name=product_name,
            listing_features=listing_features,
            official_sites=sites,
            kind=kind,
            model_tokens=model_tokens,
            max_results=MAX_SEARCH_CANDIDATES,
        )
    )

    ranked = rank_manual_candidates(
        raw, product_url=product_url, max_results=max_results
    )

    try:
        add_audit_entry(
            user_id=user_id,
            case_id=case_id,
            kind="mcp_action",
            text=f"Manual {kind} search for {product_name!r}",
            payload={
                "tool": "search_manual_urls",
                "kind": kind,
                "raw_count": len(raw),
                "result_count": len(ranked),
                "official_sites": sites,
                "sku_tokens": model_tokens[:8],
                "filtered_out": max(0, len(raw) - len(ranked)),
            },
            status="completed",
            source="product_manuals",
        )
    except Exception:
        pass

    return ranked


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
        "accepted": False,
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


def _normalize_doc_type(value: str) -> str:
    normalized = (
        (value or "other")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )
    aliases = {
        "instruction": "instruction_manual",
        "instructions": "instruction_manual",
        "user": "user_manual",
        "owners_manual": "user_manual",
        "owner_manual": "user_manual",
        "service": "service_manual",
        "repair": "repair_manual",
        "install_guide": "installation_guide",
        "installation": "installation_guide",
        "product_page": "product_listing",
        "pdp": "product_listing",
        "listing": "product_listing",
        "marketing_page": "marketing",
        "solutions": "solutions_overview",
        "solution_page": "solutions_overview",
        "category": "category_page",
        "store": "storefront",
        "shop": "storefront",
        "finder": "finder_tool",
        "product_finder": "finder_tool",
        "data_sheet": "datasheet",
        "spec_sheet": "datasheet",
    }
    return aliases.get(normalized, normalized)


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
    """
    Validity + relevance check (audited; no case write).
    Accept only if the page is a real manual-like document AND matches this variant.
    Product listings / marketing pages are invalid even if they describe the product.
    """
    features = [
        f.strip()
        for f in (listing_features or [])[:20]
        if isinstance(f, str) and f.strip()
    ]
    body = (manual_text or "")[:MAX_PREVIEW_CHARS]
    model_tokens = extract_model_tokens(product_name, " ".join(features), manual_url)
    prompt = f"""
You evaluate a candidate document for product-manual enrichment.

This is a TWO-PART decision:
1) VALIDITY (document type): Is this an instruction/user/service/repair/installation
   manual or technical datasheet?
2) RELEVANCE (variant): Is it for the SAME specific product variant / SKU
   (not a sibling model that differs by one digit or a feature set)?

Product name: {product_name}
Model/SKU tokens from listing (when present, prefer exact match): {', '.join(model_tokens) or '(none)'}
Listing features / claims:
{chr(10).join(f'- {f}' for f in features) or '(none)'}

Manual URL: {manual_url or '(unknown)'}
Manual excerpt:
{body}

Return JSON with:
- valid_document (bool): true ONLY for instruction/user/service/repair/installation
  manuals or datasheets. false for product listings, shop pages, category hubs,
  solutions marketing overviews, product finders, blogs, or general brand pages.
- document_type (string): one of instruction_manual, user_manual, user_guide,
  repair_manual, service_manual, technician_guide, installation_guide, datasheet,
  product_listing, marketing, solutions_overview, category_page, storefront,
  finder_tool, other
- relevant (bool): true only if the SAME specific product/variant is covered
- confidence (0-1)
- reason (short)
- matched_features (list)
- mismatched_features (list)

Reject if:
- The page is a product listing / PDP / marketing page (even if features match)
- Wrong brand, wrong model family, or sibling SKU (e.g. Pavilion Ryzen vs i5,
  Pro Max 24 vs Pro 48, cloud-native SDM vs SDM when listing is the other)
- Generic category listing matched to one specific SKU manual
""".strip()

    valid_document = False
    document_type = "other"
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
                "response_json_schema": ManualValidityRelevanceResult.model_json_schema(),
            },
        )
        parsed = ManualValidityRelevanceResult.model_validate_json(response.text)
        valid_document = bool(parsed.valid_document)
        document_type = _normalize_doc_type(parsed.document_type or "other")
        relevant = bool(parsed.relevant)
        confidence = float(parsed.confidence or 0.0)
        reason = (parsed.reason or "").strip()
        matched = list(parsed.matched_features or [])
        mismatched = list(parsed.mismatched_features or [])
    except Exception as exc:
        reason = f"relevance_check_failed: {type(exc).__name__}: {exc}"
        print(f"LOG: {reason}")
        valid_document = False
        relevant = False

    # Deterministic overrides
    if document_type in _REJECT_DOC_TYPES:
        valid_document = False
    if document_type in _ALLOWED_DOC_TYPES:
        # trust type when model marked allowed, but still require valid_document flag
        # unless model contradicted itself
        pass
    if manual_url and not is_plausible_manual_url(manual_url):
        # Soft signal: if URL looks like a listing, force invalid unless PDF
        if not _looks_like_pdf_url(manual_url):
            valid_document = False
            if document_type in _ALLOWED_DOC_TYPES:
                document_type = "product_listing"
            reason = (reason + " | url_looks_like_listing").strip(" |")

    accepted = bool(valid_document and relevant and document_type in _ALLOWED_DOC_TYPES)

    try:
        add_audit_entry(
            user_id=user_id,
            case_id=case_id,
            kind="manual_relevance",
            text=(
                f"Manual validity+relevance "
                f"{'accepted' if accepted else 'rejected'} for {product_name!r}"
            ),
            payload={
                "product_name": product_name,
                "manual_url": manual_url,
                "cache_id": cache_id,
                "valid_document": valid_document,
                "document_type": document_type,
                "relevant": relevant,
                "accepted": accepted,
                "confidence": confidence,
                "reason": reason,
                "matched_features": matched[:10],
                "mismatched_features": mismatched[:10],
            },
            status="accepted" if accepted else "rejected",
            source="product_manuals",
        )
    except Exception:
        pass

    if cache_id and cache_id in _MANUAL_CACHE:
        if accepted:
            _MANUAL_CACHE[cache_id]["accepted"] = True
        else:
            _MANUAL_CACHE.pop(cache_id, None)

    return {
        "relevant": accepted,  # backward compatible: "relevant" means attachable
        "accepted": accepted,
        "valid_document": valid_document,
        "document_type": document_type,
        "variant_relevant": relevant,
        "confidence": confidence,
        "reason": reason,
        "matched_features": matched,
        "mismatched_features": mismatched,
        "cache_id": cache_id if accepted else "",
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
    Requires cache entry that passed validity+relevance (accepted=True).
    """
    entry = _MANUAL_CACHE.get(cache_id)
    if not entry:
        return {
            "success": False,
            "error": "cache_id not found or was rejected — fetch and accept again",
        }
    if entry.get("case_id") != case_id:
        return {"success": False, "error": "cache_id does not belong to this case_id"}
    if not entry.get("accepted"):
        return {
            "success": False,
            "error": "cache entry was not validity+relevance accepted",
        }

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
        "accepted": bool(entry.get("accepted")),
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
    Only attaches validity+relevance accepted manuals. No product-listing fallback.
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

        sku = product_has_concrete_sku(name, claims, product_url=product_url)
        if not sku.get("ok"):
            print(
                f"LOG: Manual enrichment skipped for {name!r}: {sku.get('reason')}"
            )
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
                product_url=product_url,
                require_sku=True,
            )
            attached_this_kind = False
            for hit in hits:
                url = hit.get("url") or ""
                if not is_plausible_manual_url(url, product_url=product_url):
                    print(f"LOG: Manual URL filtered (listing/same-page): {url}")
                    continue
                fetched = fetch_url_for_inspection(
                    user_id=user_id, case_id=case_id, url=url
                )
                if not fetched.get("success"):
                    continue
                # Re-check final URL after redirects
                final_url = fetched.get("url") or url
                if not is_plausible_manual_url(final_url, product_url=product_url):
                    cache_id = fetched.get("cache_id") or ""
                    drop_manual_cache(cache_id)
                    print(
                        f"LOG: Manual URL filtered after fetch (listing/same-page): {final_url}"
                    )
                    continue

                cache_id = fetched.get("cache_id") or ""
                preview = fetched.get("preview") or ""
                verdict = assess_manual_relevance(
                    user_id=user_id,
                    case_id=case_id,
                    product_name=name,
                    listing_features=claims,
                    manual_text=preview,
                    manual_url=final_url,
                    cache_id=cache_id,
                )
                if not verdict.get("accepted"):
                    print(
                        f"LOG: Manual rejected for {name!r}: {final_url} — "
                        f"type={verdict.get('document_type')} "
                        f"valid={verdict.get('valid_document')} "
                        f"variant={verdict.get('variant_relevant')} — "
                        f"{verdict.get('reason')}"
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
                    # Do not extract claims from a non-attached / non-accepted path
                    continue

                cached = _MANUAL_CACHE.get(cache_id) or {}
                manual_claims = extract_claims_from_manual_text(
                    product_name=name,
                    manual_text=cached.get("text") or preview,
                )
                for mc in manual_claims:
                    if mc not in claims and mc not in new_claims:
                        new_claims.append(mc)
                attached_this_kind = True
                # One good valid manual per kind — no listing fallback after rejects
                break

            if not attached_this_kind and not hits:
                print(f"LOG: No valid {kind} manual candidates for {name!r}")

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
