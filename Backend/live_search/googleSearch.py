import re
from collections import Counter
from urllib.parse import urlparse

import requests

from env_controller import getEnvKey
from llm_brain.gemini import Gemini
from models.live_search_results import (
    GoogleSearchResults,
    InfringingProductDetail,
    blocked_product_url_reason,
)
from web_search import check_html_for_runtime_errors, convertHtmlToString

CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
CSE_PAGE_SIZE = 10
SEARCH_TIMEOUT = 10
MAX_CSE_QUERIES_PER_BUCKET = 3
TERMS_PER_QUERY = 6
MAX_TERMS_TOTAL = 18
SESSION_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_ENGLISH_STOPWORDS = frozenset(
    """
    a an the and or of to in for on with by at from as is are was were be been being
    this that these those it its they them their we our your you he she his her not no
    nor but if then than so such into over under between through during before after
    about above below up down out off all any each both few more most other some
    same can will just don should now only also very
    """.split()
)

_PATENT_STOPWORDS = frozenset(
    """
    comprising wherein thereof therein according claim claims characterized
    plurality configured adapted arranged disposed provided includes including
    respective one least first second third plurality means method apparatus
    system device member portion surface adapted coupled connected configured
    said wherein thereof therein hereby herein
    """.split()
)

_STOPWORDS = _ENGLISH_STOPWORDS | _PATENT_STOPWORDS


def is_google_custom_search_configured() -> bool:
    return bool(getEnvKey("google") and getEnvKey("google_cse"))


def _host_from_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url.strip()}")
    return (parsed.netloc or "").lower()


def _hosts_from_focus_urls(focus_urls: list[str]) -> list[str]:
    hosts = []
    for entry in focus_urls or []:
        host = _host_from_url(entry)
        if host:
            hosts.append(host)
    return list(dict.fromkeys(hosts))


def extract_search_terms_from_claims(
    reference_claims: list[str],
    max_terms: int = MAX_TERMS_TOTAL,
) -> list[str]:
    """Deterministic terms from claim text (no LLM)."""
    counts: Counter[str] = Counter()
    token_pattern = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{2,}")

    for claim in reference_claims or []:
        if not isinstance(claim, str) or not claim.strip():
            continue
        for token in token_pattern.findall(claim.lower()):
            if token in _STOPWORDS:
                continue
            if token.isdigit():
                continue
            if len(token) < 3:
                continue
            counts[token] += 1

    ranked = [term for term, _ in counts.most_common(max_terms)]
    return ranked


def _owner_exclusions(owners: list[str]) -> str:
    parts = []
    for owner in owners or []:
        if not isinstance(owner, str):
            continue
        cleaned = re.sub(r"[^\w\s-]", " ", owner).strip()
        if len(cleaned) < 3:
            continue
        if " " in cleaned:
            parts.append(f'-"{cleaned}"')
        else:
            parts.append(f"-{cleaned}")
    return " ".join(parts[:5])


def build_cse_queries_from_claims(
    reference_claims: list[str],
    focus_urls: list[str],
    owners: list[str] | None = None,
    max_queries: int = MAX_CSE_QUERIES_PER_BUCKET,
    terms_per_query: int = TERMS_PER_QUERY,
) -> list[str]:
    terms = extract_search_terms_from_claims(reference_claims)
    if not terms:
        return []

    hosts = _hosts_from_focus_urls(focus_urls)
    site_prefix = ""
    if hosts:
        site_clause = " OR ".join(f"site:{host}" for host in hosts)
        site_prefix = f"({site_clause}) "

    exclusions = _owner_exclusions(owners or [])
    exclusion_suffix = f" {exclusions}" if exclusions else ""

    queries = []
    for start in range(0, len(terms), terms_per_query):
        chunk = terms[start : start + terms_per_query]
        if not chunk:
            continue
        queries.append(f"{site_prefix}{' '.join(chunk)}{exclusion_suffix}".strip())
        if len(queries) >= max_queries:
            break

    return queries


def __initialSearch(
    query: str,
    max_results: int = 30,
) -> list[GoogleSearchResults]:
    api_key = getEnvKey("google")
    cse_id = getEnvKey("google_cse")
    if not api_key or not cse_id:
        print(
            "WARN: Google Custom Search not configured "
            "(GOOGLE_API_KEY and GOOGLE_CSE_ID required)"
        )
        return []

    if not (query or "").strip():
        print("WARN: Empty Google Custom Search query")
        return []

    max_results = max(1, min(int(max_results or CSE_PAGE_SIZE), 100))
    results: list[GoogleSearchResults] = []
    start = 1

    while len(results) < max_results and start <= 91:
        num = min(CSE_PAGE_SIZE, max_results - len(results))
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query.strip(),
            "num": num,
            "start": start,
        }
        try:
            response = requests.get(CSE_ENDPOINT, params=params, timeout=SEARCH_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            print(f"\nERROR: Google Custom Search request failed: {exc}")
            break

        items = payload.get("items") or []
        if not items:
            break

        for item in items:
            url = (item.get("link") or "").strip()
            if not url:
                continue
            title = (item.get("title") or "").strip() or url
            description = (item.get("snippet") or "").strip() or title
            website_name = item.get("displayLink") or _host_from_url(url) or "unknown"
            results.append(
                GoogleSearchResults(
                    title=title,
                    url=url,
                    website_name=website_name,
                    description=description,
                )
            )
            if len(results) >= max_results:
                break

        if len(items) < num:
            break
        start += num

    return results


def __getSearchContent(result_url: str) -> str | None:
    if not result_url or not str(result_url).strip():
        return None
    try:
        response = requests.get(
            result_url,
            headers=SESSION_HEADERS,
            timeout=SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        html_content = response.text
    except requests.RequestException as exc:
        print(f"\nERROR: Error getting HTML content for URL: {result_url} — {exc}")
        return None

    if not html_content or not html_content.strip():
        return None

    is_error_page, error_keyword = check_html_for_runtime_errors(
        html_content, url=result_url
    )
    if is_error_page:
        print(f"\nERROR: Blocked page content for URL: {result_url} — {error_keyword}")
        return None

    return html_content


def __isolateProductDetails(search_content: str) -> InfringingProductDetail:
    return Gemini().get_product_details(search_content)


def productGoogleSearch(
    reference_claims: list[str],
    focus_urls: list[str],
    owners: list[str] | None = None,
    max_results: int = 30,
) -> list[InfringingProductDetail]:
    """
    Search Google Custom Search using claim-derived terms (no LLM before search),
    then fetch pages and extract product details with Gemini.
    """
    queries = build_cse_queries_from_claims(
        reference_claims,
        focus_urls,
        owners=owners,
    )
    if not queries:
        print("WARN: No CSE queries built from reference claims")
        return []

    for index, query in enumerate(queries, 1):
        print(f"LOG: CSE query {index}/{len(queries)}: {query}")

    product_details: list[InfringingProductDetail] = []
    seen_urls: set[str] = set()
    seen_result_urls: set[str] = set()
    per_query_budget = max(1, max_results // len(queries))

    for query in queries:
        if len(seen_result_urls) >= max_results:
            break
        remaining = max_results - len(seen_result_urls)
        search_results = __initialSearch(query, max_results=min(per_query_budget, remaining))
        print(
            f"LOG: Google Custom Search returned {len(search_results)} result(s) "
            f"for query: {query[:80]}..."
        )

        for result in search_results:
            url = (result.url or "").strip()
            if not url or url in seen_result_urls:
                continue
            blocked = blocked_product_url_reason(url)
            if blocked:
                print(f"LOG: Skipping blocked product URL: {url} — {blocked}")
                seen_result_urls.add(url)
                continue
            seen_result_urls.add(url)

            content = __getSearchContent(url)
            if not content:
                continue

            try:
                product_data = __isolateProductDetails(content)
            except Exception as exc:
                print(f"\nERROR: Product details extraction failed for {url}: {exc}")
                continue

            product_url = (product_data.product_url or url).strip()
            if product_url in seen_urls:
                continue
            seen_urls.add(product_url)

            if not product_data.product_url:
                product_data.product_url = url
            product_details.append(product_data)

    print(f"LOG: productGoogleSearch extracted {len(product_details)} product(s)")
    return product_details
