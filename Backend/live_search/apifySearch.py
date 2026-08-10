"""
Apify retail product discovery - JSON-driven actor config, single public search() entry.
"""
from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from urllib.parse import urlparse

from env_controller import getEnvKey
from models.live_search_results import (
    ApifyRuntimeParams,
    ApifySearchStrategy,
    ApifySources,
    InfringingProductDetail,
    blocked_product_url_reason,
    is_dummy_product_value,
)

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")
_MAX_SEARCH_STRINGS = 6
_MAX_SOURCES_PER_RUN = 6
_MAX_RESULTS_PER_ACTOR_CALL = 15
_MAX_TITLE_TERMS = 4
_MAX_QUERY_WORDS = 6

_TITLE_PREFIX_RE = re.compile(
    r"^(?:a|an|the)\s+"
    r"(?:method|system|apparatus|device|assembly|article|composition|process|use)\s+"
    r"(?:(?:for|of|to|involving)\s+|performed\s+by\s+)",
    re.IGNORECASE,
)

_PATENT_QUERY_STOPWORDS = frozenset({
    "comprising",
    "wherein",
    "thereof",
    "thereby",
    "according",
    "embodiment",
    "method",
    "system",
    "apparatus",
    "device",
    "process",
    "performed",
})

_SOURCES_DIR = os.path.join(os.path.dirname(__file__), "..", "sources")
_CATALOG_PATH = os.path.join(_SOURCES_DIR, "apify_retail_catalog.json")
_ACTOR_CONFIG_PATH = os.path.join(_SOURCES_DIR, "apify_actor_config.json")

_APIFY_LIMIT_HIT = "hit"


def _clean_patent_title(title: str) -> str:
    text = (title or "").strip()
    if not text:
        return ""
    text = _TITLE_PREFIX_RE.sub("", text).strip()
    text = re.sub(r"^(?:a|an|the)\s+", "", text, flags=re.IGNORECASE).strip()
    # Drop trailing claim-style clause after first sentence fragment.
    if " comprising " in text.lower():
        text = re.split(r"\s+comprising\s+", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if text.endswith("."):
        text = text[:-1].strip()
    return text


def _is_retail_friendly_search_string(text: str) -> bool:
    cleaned = (text or "").strip()
    if len(cleaned) < 3:
        return False
    if len(cleaned.split()) > _MAX_QUERY_WORDS:
        return False
    words = cleaned.lower().split()
    if all(word in _PATENT_QUERY_STOPWORDS for word in words):
        return False
    if words and words[0] in _PATENT_QUERY_STOPWORDS:
        return False
    return True


def _extract_title_search_terms(title: str, max_terms: int = _MAX_TITLE_TERMS) -> list[str]:
    cleaned = _clean_patent_title(title)
    if not cleaned or len(cleaned) < 4:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(
            stop_words="english",
            lowercase=True,
            ngram_range=(1, 2),
            max_features=20,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9-]{2,}\b",
        )
        matrix = vectorizer.fit_transform([cleaned])
        feature_names = vectorizer.get_feature_names_out()
        scores = matrix.toarray()[0]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        terms: list[str] = []
        for idx in ranked:
            if scores[idx] <= 0:
                break
            term = str(feature_names[idx])
            if not _is_retail_friendly_search_string(term):
                continue
            terms.append(term)
            if len(terms) >= max_terms:
                break
        return terms
    except Exception as exc:
        print(f"WARN: Apify title term extraction failed: {exc}")
        return []


def _build_apify_search_strings(
    keywords: list[str] | None = None,
    product_name: str = "",
) -> list[str]:
    """Retail queries from TF-IDF title terms + case keywords (no Gemini, no search_limitations)."""
    strings: list[str] = []
    strings.extend(_extract_title_search_terms(product_name))
    for kw in keywords or []:
        if isinstance(kw, str) and kw.strip():
            strings.append(kw.strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in strings:
        text = candidate.strip()
        key = text.lower()
        if key in seen or not _is_retail_friendly_search_string(text):
            continue
        seen.add(key)
        deduped.append(text)
    return deduped[:_MAX_SEARCH_STRINGS]


def _is_apify_limit_error(exc: Exception) -> bool:
    try:
        from apify_client.errors import ApifyApiError
    except ImportError:
        return False
    if isinstance(exc, ApifyApiError):
        status = getattr(exc, "status_code", None)
        if status in (402, 429):
            return True
    msg = str(exc).lower()
    return any(
        phrase in msg
        for phrase in ("limit", "quota", "usage", "insufficient", "rate limit")
    )

def is_apify_configured() -> bool:
    return bool((getEnvKey("apify") or "").strip())


def _normalize_host(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url.strip()}")
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


class Apify:
    """Facade for Apify retail product search. Only search() is public."""

    def __init__(self):
        self._api_key = (getEnvKey("apify") or "").strip()
        self._client = None
        self._catalog: list[dict] | None = None
        self._actor_config: dict | None = None

    def search(
        self,
        reference_claims: list[str],
        search_limitations: dict | None = None,
        keywords: list[str] | None = None,
        product_name: str = "",
        max_results: int = 30,
        seen_runs: set | None = None,
        limit_flag: set | None = None,
    ) -> list[InfringingProductDetail]:
        """
        Discover products from configured retail Apify actors.

        Sources come from the JSON catalog; search strings from TF-IDF title terms
        and case keywords (no Gemini, no search_limitations).
        """
        if not self._api_key:
            print("WARN: Apify not configured (APIFY_API_KEY missing)")
            return []

        if not is_apify_enabled_for_case(search_limitations):
            print("LOG: Apify retail search skipped (use_apify_retail is false)")
            return []

        if limit_flag is not None and _APIFY_LIMIT_HIT in limit_flag:
            print("LOG: Apify skipped - account limit already reached this run")
            return []

        strategy = self._build_search_strategy(
            keywords=keywords,
            product_name=product_name,
        )
        if not strategy.sources or not strategy.search_strings:
            print("LOG: Apify search strategy empty - skipping")
            return []

        per_call_cap = max(1, min(_MAX_RESULTS_PER_ACTOR_CALL, max_results))
        seen = seen_runs if seen_runs is not None else set()
        products: list[InfringingProductDetail] = []

        print(
            f"LOG: Apify search - {len(strategy.sources)} source(s), "
            f"{len(strategy.search_strings)} search string(s)"
        )

        limit_reached = False
        for source in strategy.sources:
            catalog_entry = self._catalog_entry_by_id(source.catalog_id)
            if not catalog_entry:
                catalog_entry = self._catalog_entry_for_source(source)
            if not catalog_entry:
                print(f"WARN: No catalog entry for source {source.source_title!r}")
                continue

            catalog_id = catalog_entry.get("catalog_id", "")
            actor_config = self._actor_config_for_catalog(catalog_id)
            if not actor_config:
                print(f"WARN: No actor config for catalog_id {catalog_id!r}")
                continue

            for search_string in strategy.search_strings:
                run_key = (catalog_id, search_string.strip().lower())
                if run_key in seen:
                    print(f"LOG: Apify skipping duplicate run: {catalog_id} / {search_string!r}")
                    continue
                seen.add(run_key)

                try:
                    params = self._build_runtime_params(
                        catalog_entry,
                        actor_config,
                        search_string,
                        max_results=per_call_cap,
                    )
                    items = self._run_actor(params)
                    mapped = self._map_dataset_items(
                        items,
                        source_title=source.source_title,
                        field_map=actor_config.get("field_map") or {},
                        flatten_path=actor_config.get("flatten_path"),
                    )
                    print(
                        f"LOG: Apify {source.source_title} / {search_string!r} "
                        f"-> {len(mapped)} product(s)"
                    )
                    products.extend(mapped)
                except Exception as exc:
                    if _is_apify_limit_error(exc):
                        print(
                            f"\nWARN: Apify limit reached - stopping further runs: {exc}"
                        )
                        limit_reached = True
                        if limit_flag is not None:
                            limit_flag.add(_APIFY_LIMIT_HIT)
                    else:
                        print(
                            f"\nERROR: Apify run failed for {source.source_title} "
                            f"/ {search_string!r}: {exc}"
                        )

                if limit_reached or len(products) >= max_results:
                    break
            if limit_reached or len(products) >= max_results:
                break

        return products[:max_results]

    # ------------------------------------------------------------------ private

    def _get_client(self):
        if self._client is None:
            from apify_client import ApifyClient

            self._client = ApifyClient(self._api_key)
        return self._client

    def _load_catalog(self) -> list[dict]:
        if self._catalog is None:
            with open(_CATALOG_PATH, encoding="utf-8") as handle:
                self._catalog = json.load(handle)
        return self._catalog

    def _load_actor_config(self) -> dict:
        if self._actor_config is None:
            with open(_ACTOR_CONFIG_PATH, encoding="utf-8") as handle:
                self._actor_config = json.load(handle)
        return self._actor_config

    def _catalog_entry_by_id(self, catalog_id: str) -> dict | None:
        if not catalog_id:
            return None
        for entry in self._load_catalog():
            if entry.get("catalog_id") == catalog_id:
                return entry
        return None

    def _catalog_entry_for_source(self, source: ApifySources) -> dict | None:
        identifier = (source.source_identifier or "").strip()
        for entry in self._load_catalog():
            if entry.get("source_identifier") == identifier:
                host = _normalize_host(source.source_url)
                entry_hosts = entry.get("hosts") or []
                if not host or host in entry_hosts or _normalize_host(entry.get("source_url", "")) == host:
                    return entry
        return None

    def _actor_config_for_catalog(self, catalog_id: str) -> dict | None:
        config = self._load_actor_config()
        return config.get(catalog_id)

    def _build_search_strategy(
        self,
        keywords: list[str] | None = None,
        product_name: str = "",
    ) -> ApifySearchStrategy:
        sources = self._resolve_sources()
        search_strings = _build_apify_search_strings(
            keywords=keywords,
            product_name=product_name,
        )
        return ApifySearchStrategy(sources=sources, search_strings=search_strings)

    def _resolve_sources(self) -> list[ApifySources]:
        matched: list[ApifySources] = []
        for entry in self._load_catalog():
            matched.append(self._catalog_entry_to_source(entry))
            if len(matched) >= _MAX_SOURCES_PER_RUN:
                break
        return matched

    def _catalog_entry_to_source(self, entry: dict) -> ApifySources:
        return ApifySources(
            source_title=entry.get("source_title", ""),
            source_identifier=entry.get("source_identifier", ""),
            source_url=entry.get("source_url", ""),
            country=entry.get("country", ""),
            countryCode=entry.get("countryCode", ""),
            catalog_id=entry.get("catalog_id", ""),
        )

    def _build_runtime_params(
        self,
        catalog_entry: dict,
        actor_config: dict,
        search_string: str,
        max_results: int,
    ) -> ApifyRuntimeParams:
        placeholders = {
            "search_string": search_string.strip(),
            "max_results": max_results,
            "marketplace": actor_config.get("body", {}).get("marketplace", "com"),
            "domain": actor_config.get("body", {}).get("domain", "com"),
        }
        body_template = actor_config.get("body") or {}
        body = self._substitute_value(deepcopy(body_template), placeholders)
        query_template = actor_config.get("query")
        query = search_string.strip()
        if query_template:
            if isinstance(query_template, str):
                query = self._substitute_value(query_template, placeholders)
            elif isinstance(query_template, dict):
                query = json.dumps(self._substitute_value(deepcopy(query_template), placeholders))

        return ApifyRuntimeParams(
            query=query,
            body=body,
            source_identifier=catalog_entry.get("source_identifier", ""),
            catalog_id=catalog_entry.get("catalog_id", ""),
        )

    def _substitute_value(self, value, placeholders: dict):
        if isinstance(value, str):
            def replacer(match):
                key = match.group(1)
                return str(placeholders.get(key, match.group(0)))

            text = _PLACEHOLDER_RE.sub(replacer, value)
            if text.isdigit():
                return int(text)
            return text
        if isinstance(value, list):
            return [self._substitute_value(item, placeholders) for item in value]
        if isinstance(value, dict):
            return {k: self._substitute_value(v, placeholders) for k, v in value.items()}
        return value

    def _run_actor(self, params: ApifyRuntimeParams) -> list[dict]:
        client = self._get_client()
        print(
            f"LOG: Apify actor run {params.source_identifier} "
            f"(catalog={params.catalog_id}, query={params.query[:80]!r})"
        )
        run = client.actor(params.source_identifier).call(run_input=params.body)
        dataset_id = self._dataset_id_from_run(run)
        if not dataset_id:
            return []
        items = list(client.dataset(dataset_id).iterate_items())
        return items

    @staticmethod
    def _dataset_id_from_run(run) -> str:
        if run is None:
            return ""
        if isinstance(run, dict):
            return run.get("defaultDatasetId") or run.get("default_dataset_id") or ""
        return getattr(run, "default_dataset_id", "") or getattr(run, "defaultDatasetId", "") or ""

    def _map_dataset_items(
        self,
        items: list,
        source_title: str,
        field_map: dict,
        flatten_path: str | None = None,
    ) -> list[InfringingProductDetail]:
        rows = self._flatten_items(items, flatten_path)
        products: list[InfringingProductDetail] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            product = self._map_item_to_product(row, source_title, field_map)
            if product:
                products.append(product)
        return products

    def _flatten_items(self, items: list, flatten_path: str | None) -> list[dict]:
        if not items:
            return []
        if flatten_path:
            rows = []
            for item in items:
                if isinstance(item, dict):
                    nested = item.get(flatten_path)
                    if isinstance(nested, list):
                        rows.extend(n for n in nested if isinstance(n, dict))
            if rows:
                return rows
        rows: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("results"), list):
                rows.extend(n for n in item["results"] if isinstance(n, dict))
            else:
                rows.append(item)
        return rows

    def _map_item_to_product(
        self,
        item: dict,
        source_title: str,
        field_map: dict,
    ) -> InfringingProductDetail | None:
        product_url = self._first_field(item, field_map.get("product_url") or ["url"])
        product_name = self._first_field(item, field_map.get("product_name") or ["title"])
        product_id = self._first_field(
            item, field_map.get("product_id") or ["id", "asin", "itemId"]
        )

        if is_dummy_product_value(product_url) or is_dummy_product_value(product_name):
            return None
        if blocked_product_url_reason(str(product_url or "")):
            return None

        claims: list[str] = []
        for field in field_map.get("claims_from") or []:
            raw = item.get(field)
            if raw is None:
                continue
            text = str(raw).strip()
            if text and text not in claims:
                claims.append(text)

        if not product_name and claims:
            product_name = claims[0][:200]
        if not product_id and product_url:
            product_id = product_url.rstrip("/").split("/")[-1][:80]
        if not product_url or not product_name:
            return None

        if not claims:
            claims = [product_name]

        return InfringingProductDetail(
            source=source_title,
            product_id=str(product_id),
            product_url=str(product_url).strip(),
            product_name=str(product_name).strip(),
            claims=claims,
            similar_claims=[],
        )

    def _first_field(self, item: dict, keys: list[str]) -> str:
        for key in keys:
            value = item.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""


def is_apify_enabled_for_case(search_limitations: dict | None) -> bool:
    """True when Apify is configured and retail search is not explicitly disabled."""
    if not is_apify_configured():
        return False
    limitations = search_limitations or {}
    return limitations.get("use_apify_retail") is not False
