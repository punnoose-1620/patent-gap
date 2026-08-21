from __future__ import annotations

import re

from live_search.integrations.base import BaseProductIntegration, quote_query


class EbayProductIntegration(BaseProductIntegration):
    source_name = "eBay"
    source_hosts = ("ebay.com",)

    def _search_urls(self, query: str) -> list[str]:
        return [f"https://www.ebay.com/sch/i.html?_nkw={quote_query(query)}"]

    def _is_allowed_product_url(self, url: str) -> bool:
        if not super()._is_allowed_product_url(url):
            return False
        return "/itm/" in url.lower()

    def _product_id(self, product_url: str, title: str) -> str:
        match = re.search(r"/itm/(?:[^/]+/)?(\d+)", product_url)
        if match:
            return match.group(1)
        return super()._product_id(product_url, title)
