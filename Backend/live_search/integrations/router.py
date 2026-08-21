from __future__ import annotations

from env_controller import getEnvKey
from live_search.integrations.amazon import AmazonProductIntegration
from live_search.integrations.base import ProductSearchContext
from live_search.integrations.bestbuy import BestBuyProductIntegration
from live_search.integrations.ebay import EbayProductIntegration
from live_search.integrations.generic_vendor import GenericVendorIntegration
from live_search.integrations.http_client import ProductHttpClient
from live_search.integrations.walmart import WalmartProductIntegration
from models.live_search_results import InfringingProductDetail


def use_apify_fallback_enabled(search_limitations: dict | None = None) -> bool:
    limitations = search_limitations or {}
    explicit = limitations.get("use_apify_fallback")
    if explicit is not None:
        return explicit is True or str(explicit).strip().lower() in {"1", "true", "yes"}
    env_value = getEnvKey("use_apify_fallback")
    return str(env_value or "").strip().lower() in {"1", "true", "yes"}


class ProductIntegrationRouter:
    """Run low-cost product integrations in a fixed, normalized order."""

    def __init__(self, client: ProductHttpClient | None = None):
        self.client = client or ProductHttpClient()
        self.integrations = [
            AmazonProductIntegration(self.client),
            WalmartProductIntegration(self.client),
            EbayProductIntegration(self.client),
            BestBuyProductIntegration(self.client),
            GenericVendorIntegration(self.client),
        ]

    def search(
        self,
        *,
        product_name: str,
        keywords: list[str],
        reference_claims: list[str],
        owners: list[str] | None = None,
        search_limitations: dict | None = None,
        max_results: int = 30,
    ) -> list[InfringingProductDetail]:
        context = ProductSearchContext(
            product_name=product_name,
            keywords=keywords or [],
            reference_claims=reference_claims or [],
            owners=owners or [],
            search_limitations=search_limitations or {},
            max_results=max_results,
        )
        products: list[InfringingProductDetail] = []
        seen_urls: set[str] = set()
        per_source_limit = max(1, min(max_results, max_results // 2 or 1))
        for integration in self.integrations:
            if len(products) >= max_results:
                break
            source_context = ProductSearchContext(
                product_name=context.product_name,
                keywords=context.keywords,
                reference_claims=context.reference_claims,
                owners=context.owners,
                search_limitations=context.search_limitations,
                max_results=min(per_source_limit, max_results - len(products)),
            )
            try:
                found = integration.search(source_context)
            except Exception as exc:
                print(f"LOG: {integration.source_name} integration failed: {exc}")
                continue
            print(f"LOG: {integration.source_name} integration returned {len(found)} product(s)")
            for product in found:
                if product.product_url in seen_urls:
                    continue
                seen_urls.add(product.product_url)
                products.append(product)
                if len(products) >= max_results:
                    break
        return products[:max_results]
