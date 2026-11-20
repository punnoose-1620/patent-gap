"""
Product fetching / search — facade over live_search helpers.
"""
from __future__ import annotations


def enrich_with_manuals(*args, **kwargs):
    """Optional instruction/repair manual enrichment after listing isolation."""
    try:
        from live_search.product_manuals import enrich_product_with_manuals

        return enrich_product_with_manuals(*args, **kwargs)
    except Exception as e:
        print(f"LOG: discovery.products.enrich_with_manuals failed ({type(e).__name__}: {e})")
        return args[0] if args else None


def google_product_search(*args, **kwargs):
    try:
        from live_search import googleSearch as gs
        for name in ("search", "google_search", "perform_search", "run_search"):
            fn = getattr(gs, name, None)
            if callable(fn):
                return fn(*args, **kwargs)
        return gs
    except Exception as e:
        print(f"LOG: discovery.products.google_product_search failed ({type(e).__name__}: {e})")
        return None


def apify_product_search(*args, **kwargs):
    try:
        from live_search import apifySearch as apify
        for name in ("search", "apify_search", "run_actor", "run_search"):
            fn = getattr(apify, name, None)
            if callable(fn):
                return fn(*args, **kwargs)
        return apify
    except Exception as e:
        print(f"LOG: discovery.products.apify_product_search failed ({type(e).__name__}: {e})")
        return None


def build_search_urls(*args, **kwargs):
    try:
        from live_search import searchUrlBuilder as builder
        for name in ("build", "build_urls", "build_search_urls", "get_urls"):
            fn = getattr(builder, name, None)
            if callable(fn):
                return fn(*args, **kwargs)
        return builder
    except Exception as e:
        print(f"LOG: discovery.products.build_search_urls failed ({type(e).__name__}: {e})")
        return None
