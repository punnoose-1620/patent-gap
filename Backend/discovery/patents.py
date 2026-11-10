"""
Patent fetching and scrapers — thin facade over existing sources/web_scraper.
"""
from __future__ import annotations


def scrape_google_patents(*args, **kwargs):
    from web_scraper import google_patents as gp
    # Prefer common callables; otherwise expose module for callers that know APIs.
    for name in ("scrape_google_patent", "get_patent_data", "fetch_patent", "scrape"):
        fn = getattr(gp, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    return gp


def scrape_free_patents_online(*args, **kwargs):
    from web_scraper import free_patents_online as fpo
    for name in ("scrape_patent", "get_patent_data", "fetch_patent", "scrape"):
        fn = getattr(fpo, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    return fpo


def fetch_uspto(*args, **kwargs):
    from sources import USPTO as uspto_mod
    for name in ("fetch_patent", "get_patent", "search_patent", "getPatentData"):
        fn = getattr(uspto_mod, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    return uspto_mod


def fetch_openalex(*args, **kwargs):
    from sources import OpenAlex as oa
    for name in ("fetch", "search", "get_work"):
        fn = getattr(oa, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    return oa
