from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse

ERROR_PAGE_KEYWORDS = (
    "page not found",
    "error 404",
    "site not found",
    "404",
    "not found",
    "broken link",
    "internal server error",
    "500 error",
    "forbidden",
    "access denied",
)

BOT_CAPTCHA_PAGE_KEYWORDS = (
    "captcha",
    "recaptcha",
    "hcaptcha",
    "robot or human",
    "are you a robot",
    "verify you are human",
    "verify you're human",
    "security check",
    "unusual traffic",
    "automated access",
    "automated requests",
    "automated bots",
    "please verify",
    "not a robot",
    "click the button below to continue shopping",
    "enable javascript and cookies",
    "javascript is disabled",
    "access denied by security policy",
    "blocked request",
    "bot detection",
    "perimeterx",
    "datadome",
    "please complete the security check",
    "confirm you are human",
    "press & hold",
    "checking your browser",
    "cloudflare ray id",
    "px-captcha",
    "sorry, we just need to make sure you're not a robot",
    "to discuss automated access to amazon data",
)

HTML_BOT_SIGNALS = (
    'class="g-recaptcha"',
    "www.google.com/recaptcha",
    "hcaptcha.com",
    "cf-browser-verification",
    "challenge-platform",
    'id="captcha"',
    "px-captcha",
    "datadome",
    "geo.captcha-delivery.com",
)

RETAIL_HOST_MARKERS = (
    "amazon.",
    "walmart.",
    "lowes.",
    "homedepot.",
    "target.",
    "bestbuy.",
    "ebay.",
)

MIN_RETAIL_PRODUCT_PAGE_TEXT_CHARS = 400


def match_error_page_keyword(text):
    if not isinstance(text, str) or not text.strip():
        return None
    content_lower = text.lower()
    for keyword in ERROR_PAGE_KEYWORDS:
        if keyword in content_lower:
            return keyword
    return None


def match_bot_or_captcha_keyword(text):
    if not isinstance(text, str) or not text.strip():
        return None
    content_lower = text.lower()
    for keyword in BOT_CAPTCHA_PAGE_KEYWORDS:
        if keyword in content_lower:
            return keyword
    return None


def match_runtime_block_keyword(text):
    """Match error pages, bot walls, or captcha interstitials in plain text."""
    return match_error_page_keyword(text) or match_bot_or_captcha_keyword(text)


def _host_from_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url.strip()}")
    return (parsed.netloc or "").lower()


def is_known_retail_product_url(url: str) -> bool:
    host = _host_from_url(url)
    return any(marker in host for marker in RETAIL_HOST_MARKERS)


def match_html_bot_signal(html_content: str):
    if not isinstance(html_content, str) or not html_content.strip():
        return None
    html_lower = html_content.lower()
    for signal in HTML_BOT_SIGNALS:
        if signal.lower() in html_lower:
            return signal
    return None


def match_thin_retail_product_page(plain_text: str, url: str = ""):
    if not is_known_retail_product_url(url):
        return None
    cleaned = plain_text.strip() if isinstance(plain_text, str) else ""
    if len(cleaned) < MIN_RETAIL_PRODUCT_PAGE_TEXT_CHARS:
        return f"thin retail page ({len(cleaned)} chars)"
    return None


def check_content_for_runtime_errors(plain_string_content, url: str = ""):
    if not isinstance(plain_string_content, str):
        return True, None

    keyword = match_runtime_block_keyword(plain_string_content)
    if keyword:
        return True, keyword

    thin = match_thin_retail_product_page(plain_string_content, url)
    if thin:
        return True, thin

    return False, None


def check_html_for_runtime_errors(html_content, url: str = ""):
    if not isinstance(html_content, str) or not html_content.strip():
        return True, "empty html"

    html_signal = match_html_bot_signal(html_content)
    if html_signal:
        return True, html_signal

    plain_text = convertHtmlToString(html_content)
    return check_content_for_runtime_errors(plain_text, url=url)


def convertHtmlToString(content):
    if not isinstance(content, str):
        return ""
    soup = BeautifulSoup(content, "html.parser")
    return soup.get_text(separator=" ", strip=True)


html_to_string = convertHtmlToString


def get_content(url: str):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type")
        body = response.text

        if (content_type is not None) and ("html" in str(content_type).lower()):
            is_blocked, block_keyword = check_html_for_runtime_errors(body, url=url)
            if is_blocked:
                return None, None, "Runtime Error : " + str(block_keyword)
            convertedBody = html_to_string(body)
            content_type = "Text"
            return content_type, convertedBody, None
        return content_type, body, None
    except requests.exceptions.HTTPError as http_err:
        return None, None, "HTTP Error : " + str(http_err)
    except requests.exceptions.ConnectionError as conn_err:
        return None, None, "Connection Error : " + str(conn_err)
    except requests.exceptions.Timeout as timeout_err:
        return None, None, "Timeout Error : " + str(timeout_err)
    except requests.exceptions.RequestException as req_err:
        return None, None, "Request Error : " + str(req_err)
    except Exception as e:
        return None, None, "Unexpected Error : " + str(e)


def parse_urls(urls: list[str]):
    contents = []
    for url in urls:
        content_type, body, error = get_content(url)
        if error is not None:
            print("ERROR: Fetching Patent from url: ", url, "\nError: ", error, "\n\n")
        else:
            if "html" in str(content_type).lower():
                convertedBody = html_to_string(body)
                contents.append(convertedBody)
            else:
                contents.append(body)
