from __future__ import annotations

import re

from live_search.integrations.base import BaseProductIntegration, quote_query


class BestBuyProductIntegration(BaseProductIntegration):
    source_name = "Best Buy"
    source_hosts = ("bestbuy.com",)

    def _search_urls(self, query: str) -> list[str]:
        return [f"https://www.bestbuy.com/site/searchpage.jsp?st={quote_query(query)}"]

    def _is_allowed_product_url(self, url: str) -> bool:
        if not super()._is_allowed_product_url(url):
            return False
        return "/site/" in url.lower() and re.search(r"/\d+\.p", url)

    def _product_id(self, product_url: str, title: str) -> str:
        match = re.search(r"/(\d+)\.p", product_url)
        if match:
            return match.group(1)
        return super()._product_id(product_url, title)
