from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

from models.live_search_results import (
    InfringingProductDetail,
    blocked_product_url_reason,
    is_dummy_product_value,
    is_product_listing_url,
    is_valid_product_url,
)


MAX_CLAIMS_PER_PRODUCT = 12
MAX_CLAIM_CHARS = 280


@dataclass
class ProductSearchContext:
    product_name: str
    keywords: list[str]
    reference_claims: list[str]
    owners: list[str] = field(default_factory=list)
    search_limitations: dict = field(default_factory=dict)
    max_results: int = 30


class BaseProductIntegration:
    source_name = "Generic"
    source_hosts: tuple[str, ...] = ()
    max_queries = 4
    max_urls_per_query = 8

    def __init__(self, client):
        self.client = client

    def search(self, context: ProductSearchContext) -> list[InfringingProductDetail]:
        products: list[InfringingProductDetail] = []
        seen_urls: set[str] = set()
        queries = self._build_queries(context)
        for query in queries[: self.max_queries]:
            if len(products) >= context.max_results:
                break
            for url in self._discover_product_urls(query, context):
                normalized_url = normalize_url(url)
                if (
                    not normalized_url
                    or normalized_url in seen_urls
                    or not self._is_allowed_product_url(normalized_url)
                ):
                    continue
                seen_urls.add(normalized_url)
                product = self._fetch_product(normalized_url, context)
                if product:
                    products.append(product)
                    if len(products) >= context.max_results:
                        break
        return products[: context.max_results]

    def _build_queries(self, context: ProductSearchContext) -> list[str]:
        candidates = [context.product_name]
        candidates.extend(context.keywords or [])
        candidates.extend(extract_terms_from_claims(context.reference_claims, max_terms=8))
        queries: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = clean_query(candidate)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            queries.append(text)
            if len(queries) >= self.max_queries:
                break
        return queries

    def _discover_product_urls(
        self,
        query: str,
        context: ProductSearchContext,
    ) -> list[str]:
        del context
        urls: list[str] = []
        for search_url in self._search_urls(query):
            html = self.client.fetch_text(search_url, source=self.source_name)
            if not html:
                continue
            urls.extend(self._extract_product_urls(html, search_url))
            if len(urls) >= self.max_urls_per_query:
                break
        return list(dict.fromkeys(urls))[: self.max_urls_per_query]

    def _search_urls(self, query: str) -> list[str]:
        raise NotImplementedError

    def _extract_product_urls(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for link in soup.select("a[href]"):
            href = link.get("href") or ""
            absolute = normalize_url(urljoin(base_url, href))
            if self._is_allowed_product_url(absolute):
                urls.append(absolute)
        return list(dict.fromkeys(urls))

    def _fetch_product(
        self,
        product_url: str,
        context: ProductSearchContext,
    ) -> InfringingProductDetail | None:
        del context
        html = self.client.fetch_text(product_url, source=self.source_name)
        if not html:
            return None
        return self._product_from_html(product_url, html)

    def _product_from_html(
        self,
        product_url: str,
        html: str,
    ) -> InfringingProductDetail | None:
        soup = BeautifulSoup(html, "html.parser")
        title = first_non_empty(
            meta_content(soup, "og:title"),
            meta_content(soup, "twitter:title"),
            text_of_first(soup, ["h1", "[data-testid='product-title']", "#productTitle"]),
            soup.title.string if soup.title else "",
        )
        title = clean_text(title)
        description = first_non_empty(
            meta_content(soup, "og:description"),
            meta_content(soup, "description", attr="name"),
            meta_content(soup, "twitter:description"),
        )
        claims = collect_claims_from_html(soup, description)
        if not title or is_dummy_product_value(title):
            return None
        product_id = self._product_id(product_url, title)
        try:
            product = InfringingProductDetail(
                source=self.source_name,
                product_id=product_id,
                product_url=product_url,
                product_name=title,
                claims=claims or [title],
                similar_claims=[],
            )
            valid, message = product.validate_infringing_product_detail()
            if not valid:
                print(f"LOG: {self.source_name} skipped invalid product {product_url}: {message}")
                return None
            return product
        except Exception as exc:
            print(f"LOG: {self.source_name} product normalization failed for {product_url}: {exc}")
            return None

    def _product_id(self, product_url: str, title: str) -> str:
        parsed = urlparse(product_url)
        path_tail = parsed.path.rstrip("/").split("/")[-1]
        if path_tail and len(path_tail) >= 3:
            return path_tail[:80]
        digest = hashlib.sha1(f"{self.source_name}:{product_url}:{title}".encode("utf-8")).hexdigest()
        return digest[:16]

    def _is_allowed_product_url(self, url: str) -> bool:
        if not url or not is_valid_product_url(url):
            return False
        if blocked_product_url_reason(url):
            return False
        if is_product_listing_url(url):
            return False
        if not self.source_hosts:
            return True
        host = normalized_host(url)
        return any(host == source_host or host.endswith("." + source_host) for source_host in self.source_hosts)


def normalized_host(url: str) -> str:
    host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def normalize_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        return ""
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}{query}".rstrip("/")


def clean_text(value: str) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]


def first_non_empty(*values: str) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def text_of_first(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            return tag.get_text(" ", strip=True)
    return ""


def meta_content(soup: BeautifulSoup, name: str, attr: str = "property") -> str:
    tag = soup.find("meta", attrs={attr: name})
    if not tag and attr == "property":
        tag = soup.find("meta", attrs={"name": name})
    if not tag:
        return ""
    return tag.get("content") or ""


def collect_claims_from_html(soup: BeautifulSoup, description: str = "") -> list[str]:
    claims: list[str] = []
    for value in _json_ld_claims(soup):
        add_claim(claims, value)
    add_claim(claims, description)
    selectors = [
        "#feature-bullets li",
        ".feature li",
        ".features li",
        ".specs li",
        ".product-features li",
        "[class*='feature'] li",
        "[class*='spec'] li",
        "table tr",
    ]
    for selector in selectors:
        for tag in soup.select(selector):
            add_claim(claims, tag.get_text(" ", strip=True))
            if len(claims) >= MAX_CLAIMS_PER_PRODUCT:
                return claims
    return claims[:MAX_CLAIMS_PER_PRODUCT]


def _json_ld_claims(soup: BeautifulSoup) -> list[str]:
    values: list[str] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for product in _iter_json_products(payload):
            for key in ("description", "name", "sku", "model"):
                if isinstance(product.get(key), str):
                    values.append(product[key])
    return values


def _iter_json_products(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_json_products(item)
    elif isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_json_products(item)
        types = payload.get("@type")
        if types == "Product" or (isinstance(types, list) and "Product" in types):
            yield payload


def add_claim(claims: list[str], value: str):
    text = clean_text(value)
    if len(text) < 12:
        return
    if text.lower() in {"add to cart", "buy now", "shop now"}:
        return
    text = text[:MAX_CLAIM_CHARS]
    if text not in claims:
        claims.append(text)


def clean_query(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"[^\w\s+.-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    return " ".join(words[:8])


def extract_terms_from_claims(claims: list[str], max_terms: int = 8) -> list[str]:
    stopwords = {
        "comprising",
        "wherein",
        "thereof",
        "method",
        "system",
        "device",
        "apparatus",
        "configured",
        "plurality",
        "claim",
        "claims",
        "first",
        "second",
    }
    counts: dict[str, int] = {}
    for claim in claims or []:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", str(claim).lower()):
            if token in stopwords:
                continue
            counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts, key=lambda item: counts[item], reverse=True)
    return ranked[:max_terms]


def quote_query(query: str) -> str:
    return quote_plus(query.strip())
