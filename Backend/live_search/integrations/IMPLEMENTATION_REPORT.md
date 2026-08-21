# Product Scraping Integrations

## Goal

Replace Apify as the default retail product discovery path while keeping the existing Gemini extraction and infringement comparison pipeline intact.

## Flow

1. Existing Gemini product discovery runs first.
2. Existing Google Custom Search fallback runs when Gemini finds no usable product.
3. New integration router runs after that when no product has been persisted.
4. Apify is only called when `USE_APIFY_FALLBACK=true` or `search_limitations.use_apify_fallback=true`.
5. Products from all new integrations are normalized as `InfringingProductDetail`.
6. Existing `_persist_extracted_products` handles relevance filtering, Gemini product infringement scoring, DB persistence, and duplicate URL handling.

## New Files

- `Backend/live_search/integrations/base.py`
- `Backend/live_search/integrations/http_client.py`
- `Backend/live_search/integrations/router.py`
- `Backend/live_search/integrations/amazon.py`
- `Backend/live_search/integrations/walmart.py`
- `Backend/live_search/integrations/ebay.py`
- `Backend/live_search/integrations/bestbuy.py`
- `Backend/live_search/integrations/generic_vendor.py`
- `Backend/live_search/integrations/google_cse.py`
- `Backend/test_product_integrations.py`

## Runtime Strategy

- HTTP fetch is attempted first.
- Proxy HTTP fetch is attempted second when `PROXY_URLS` is configured.
- Playwright is attempted last for JavaScript-heavy or blocked pages.
- Each source has bounded query/result limits to reduce run time and cost.

## Required/Optional Env Vars

- `PROXY_URLS`
- `USE_APIFY_FALLBACK`
- `GOOGLE_API_KEY`
- `GOOGLE_CSE_ID`
- `SERPAPI_API_KEY`
- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`
- `BESTBUY_API_KEY`
- `WALMART_CLIENT_ID`
- `WALMART_CLIENT_SECRET`
- `APIFY_API_KEY`

## Limitations

- Marketplace search pages can still block automated traffic.
- Free or low-cost proxies may be inconsistent.
- Amazon is expected to be the least stable source.
- The generic vendor integration is intentionally simple and should be expanded source-by-source as customer needs appear.
