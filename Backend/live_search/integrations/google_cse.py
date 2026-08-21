from __future__ import annotations

from live_search.googleSearch import is_google_custom_search_configured, productGoogleSearch


class GoogleCseIntegration:
    """Thin adapter for the existing Google Custom Search implementation."""

    source_name = "Google Custom Search"

    def search(self, reference_claims, focus_urls, owners=None, max_results=30):
        if not is_google_custom_search_configured():
            return []
        return productGoogleSearch(
            reference_claims,
            focus_urls,
            owners=owners or [],
            max_results=max_results,
        )
