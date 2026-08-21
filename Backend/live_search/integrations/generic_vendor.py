from __future__ import annotations

from urllib.parse import urlparse

from live_search.integrations.base import (
    BaseProductIntegration,
    ProductSearchContext,
    normalize_url,
    quote_query,
)


class GenericVendorIntegration(BaseProductIntegration):
    source_name = "Generic Vendor"
    source_hosts = ()
    max_queries = 3

    def search(self, context: ProductSearchContext):
        hosts = self._hosts_from_context(context)
        if not hosts:
            return []
        products = []
        seen = set()
        for host in hosts[:6]:
            self.source_hosts = (host,)
            for product in super().search(context):
                if product.product_url in seen:
                    continue
                seen.add(product.product_url)
                product.source = host
                products.append(product)
                if len(products) >= context.max_results:
                    return products
        return products

    def _search_urls(self, query: str) -> list[str]:
        host = self.source_hosts[0] if self.source_hosts else ""
        if not host:
            return []
        encoded = quote_query(query)
        return [
            f"https://{host}/search?q={encoded}",
            f"https://{host}/search?query={encoded}",
            f"https://{host}/?s={encoded}",
        ]

    def _hosts_from_context(self, context: ProductSearchContext) -> list[str]:
        urls = []
        for entry in (context.search_limitations or {}).get("urls") or []:
            if isinstance(entry, str):
                urls.append(entry)
        for entry in (context.search_limitations or {}).get("priority_target_sources") or []:
            if isinstance(entry, dict) and entry.get("url"):
                urls.append(entry["url"])
        hosts = []
        blocked = {"amazon.com", "amazon.co.uk", "walmart.com", "ebay.com", "bestbuy.com"}
        for url in urls:
            normalized = normalize_url(url if "://" in url else f"https://{url}")
            host = urlparse(normalized).netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            if host and host not in blocked and host not in hosts:
                hosts.append(host)
        return hosts
