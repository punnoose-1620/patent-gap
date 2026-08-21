from __future__ import annotations

import itertools
import random
import time

import requests

from env_controller import getEnvKey
from web_search import check_html_for_runtime_errors


DEFAULT_TIMEOUT = 12
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


class ProductHttpClient:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.proxies = self._load_proxies()
        self._proxy_cycle = itertools.cycle(self.proxies) if self.proxies else None

    def fetch_text(self, url: str, source: str = "product") -> str | None:
        html = self._fetch_with_requests(url, source=source, use_proxy=False)
        if self._looks_usable(html, url):
            return html
        html = self._fetch_with_requests(url, source=source, use_proxy=True)
        if self._looks_usable(html, url):
            return html
        return self._fetch_with_playwright(url, source=source)

    def _fetch_with_requests(
        self,
        url: str,
        source: str,
        use_proxy: bool,
    ) -> str | None:
        proxy_url = self._next_proxy() if use_proxy else None
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                proxies=proxies,
                allow_redirects=True,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            mode = "proxy" if proxy_url else "direct"
            print(f"LOG: {source} {mode} fetch failed for {url}: {exc}")
            return None

    def _fetch_with_playwright(self, url: str, source: str) -> str | None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        proxy_url = self._next_proxy()
        launch_kwargs = {"headless": True}
        if proxy_url:
            launch_kwargs["proxy"] = {"server": proxy_url}

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    user_agent=DEFAULT_HEADERS["User-Agent"],
                    locale="en-US",
                    viewport={"width": 1365, "height": 900},
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                time.sleep(random.uniform(0.3, 0.8))
                html = page.content()
                context.close()
                browser.close()
                if self._looks_usable(html, url):
                    return html
        except Exception as exc:
            print(f"LOG: {source} Playwright fetch failed for {url}: {exc}")
        return None

    def _looks_usable(self, html: str | None, url: str) -> bool:
        if not html or len(html.strip()) < 300:
            return False
        is_error, keyword = check_html_for_runtime_errors(html, url=url)
        if is_error:
            print(f"LOG: Product page blocked/error for {url}: {keyword}")
            return False
        return True

    def _load_proxies(self) -> list[str]:
        raw = getEnvKey("proxy_urls") or ""
        proxies = []
        for item in raw.replace("\n", ",").split(","):
            value = item.strip()
            if value:
                proxies.append(value)
        return proxies

    def _next_proxy(self) -> str | None:
        if not self._proxy_cycle:
            return None
        return next(self._proxy_cycle)
