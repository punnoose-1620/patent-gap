from __future__ import annotations

import re

from live_search.integrations.base import BaseProductIntegration, quote_query


class AmazonProductIntegration(BaseProductIntegration):
    source_name = "Amazon"
    source_hosts = ("amazon.com", "amazon.co.uk")

    def _search_urls(self, query: str) -> list[str]:
        encoded = quote_query(query)
        return [
            f"https://www.amazon.com/s?k={encoded}",
            f"https://www.amazon.co.uk/s?k={encoded}",
        ]

    def _is_allowed_product_url(self, url: str) -> bool:
        if not super()._is_allowed_product_url(url):
            return False
        return bool(re.search(r"/(?:dp|gp/product)/[A-Z0-9]{8,14}", url, re.IGNORECASE))

    def _product_id(self, product_url: str, title: str) -> str:
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{8,14})", product_url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return super()._product_id(product_url, title)
