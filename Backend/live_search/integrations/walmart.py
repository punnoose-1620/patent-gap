from __future__ import annotations

import re

from live_search.integrations.base import BaseProductIntegration, quote_query


class WalmartProductIntegration(BaseProductIntegration):
    source_name = "Walmart"
    source_hosts = ("walmart.com",)

    def _search_urls(self, query: str) -> list[str]:
        return [f"https://www.walmart.com/search?q={quote_query(query)}"]

    def _is_allowed_product_url(self, url: str) -> bool:
        if not super()._is_allowed_product_url(url):
            return False
        return "/ip/" in url.lower()

    def _product_id(self, product_url: str, title: str) -> str:
        match = re.search(r"/ip/(?:[^/]+/)?(\d+)", product_url)
        if match:
            return match.group(1)
        return super()._product_id(product_url, title)
