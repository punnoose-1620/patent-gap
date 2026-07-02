from datetime import datetime
import json
import re
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, field_validator

from web_search import match_runtime_block_keyword

_URL_CHECK_TIMEOUT = 10
_PRODUCT_URL_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

_ALLOWED_CLAIM_TYPES = frozenset({
    "asserted_claim",
    "independent_claim",
    "core_claim",
    "pivotal_claim",
})

_CLAIM_TYPE_ALIASES = {
    "asserted": "asserted_claim",
    "independent": "independent_claim",
    "core": "core_claim",
    "pivotal": "pivotal_claim",
}

def validate_string(value):
    if value is None:
        return False
    if not isinstance(value, str):
        return False
    if str(value).strip() == "":
        return False
    return True

def validate_list(value):
    if value is None:
        return False
    if not isinstance(value, list):
        return False
    if len(value) == 0:
        return False
    return True

class OtherIdData(BaseModel):
    title: str
    value: list[str]

    def validate_other_id_data(self):
        if self.title is None:
            return False, "Title is required"
        if self.value is None:
            return False, "Value is required"
        return True, ""

class DocumentsData(BaseModel):
    url: str
    source: str

    def validate_documents_data(self):
        if self.url is None:
            return False, "URL is required"
        if self.source is None:
            return False, "Source is required"
        return True, ""

class AttorneysData(BaseModel):
    name: str
    registrationNumber: str
    contact: list[str]

    def validate_attorneys_data(self):
        if self.name is None:
            return False, "Name is required"
        if self.registrationNumber is None:
            return False, "Registration number is required"
        if self.contact is None:
            return False, "Contact is required"
        return True, ""

def empty_live_search_results(source: str | None = None) -> "LiveSearchResults":
    """Blank metadata accumulator for incremental Gemini merge (not valid until filled)."""
    return LiveSearchResults(
        title="",
        status="",
        description="",
        currentStatusCode=0,
        currentStatusDate="",
        filingDate="",
        documents=[],
        document_urls=[],
        keywords=[],
        claims=[],
        attorneys=[],
        inventors=[],
        applicant="",
        current_assignee=[],
        other_ids=[],
        source=source,
    )


class LiveSearchResults(BaseModel):
    _id: str                # Format : source_userid_patentid
    title: str
    status: str
    description: str
    currentStatusCode: int
    currentStatusDate: str
    # Set Created By to 'Gemini'
    # Set Created Date to current date
    filingDate: str
    documents: list[DocumentsData]
    document_urls: list[str]
    # Set References to an empty list
    keywords: list[str]
    claims: list[str]
    # Set Infringement Details to an empty list
    # Set Infringements to an empty list
    attorneys: list[AttorneysData]
    inventors: list[str]
    applicant: str = None
    current_assignee: list[str]=[]
    other_ids: list[OtherIdData] = []
    source: str = None
    # Set Mailing Addresses to an empty list

    def created(self, creator: str):
        self.created_date = str(datetime.now().isoformat())
        self.created_by = creator

        self.references = []
        self.infringement_details = []
        self.infringements = []
        self.mailing_addresses = []
        return self

    def validate_metadata(self):
        if self.source is None:
            return False, "Source is required"
        if self.filingDate is None:
            return False, "Filing date is required"
        if self.keywords is None:
            return False, "Keywords are required"
        if self.claims is None:
            return False, "Claims are required"
        if self.attorneys is None:
            return False, "Attorneys are required"
        if self.inventors is None:
            return False, "Inventors are required"
        if self.applicant is None:
            return False, "Applicant is required"
        if not validate_string(self.title):
            return False, "Title is required"
        if self.status is None:
            return False, "Status is required"
        if self.description is None:
            return False, "Description is required"
        if self.currentStatusCode is None:
            return False, "Current status code is required"
        if not validate_string(self.filingDate):
            return False, "Filing date is required"
        return True, ""

    def merge_with_existing(self, existing_results: 'LiveSearchResults'):
        if existing_results is None:
            return False, "Existing results are required and cannot be None"
        # Case _id is set after portfolio import; not part of LiveSearchResults fields.
        if not validate_string(self.status) and validate_string(existing_results.status):
            self.status = existing_results.status
        
        if validate_string(self.description) and validate_string(existing_results.description):
            if len(self.description.strip()) < len(existing_results.description.strip()):
                self.description = existing_results.description
        if not validate_string(self.description) and validate_string(existing_results.description):
            self.description = existing_results.description
        
        if not validate_string(self.title) and validate_string(existing_results.title):
            self.title = existing_results.title
        
        if not validate_string(self.filingDate) and validate_string(existing_results.filingDate):
            self.filingDate = existing_results.filingDate
        
        if validate_list(self.keywords) and validate_list(existing_results.keywords):
            for word in existing_results.keywords:
                if validate_string(word):
                    if word.strip().lower() not in self.keywords:
                        self.keywords.append(word.strip())
        if not validate_list(self.keywords) and validate_list(existing_results.keywords):
            self.keywords = existing_results.keywords
        
        if not validate_list(self.claims) and validate_list(existing_results.claims):
            self.claims = existing_results.claims
        
        if validate_list(self.attorneys) and validate_list(existing_results.attorneys):
            for attorney in existing_results.attorneys:
                if attorney is not None:
                    validated, error_message = attorney.validate_attorneys_data()
                    if validated:
                        a_names = [a.name.strip().lower() for a in self.attorneys]
                        a_registration_numbers = [a.registrationNumber.strip().lower() for a in self.attorneys]
                        if (attorney.name.strip().lower() not in a_names) and (attorney.registrationNumber.strip().lower() not in a_registration_numbers):
                            self.attorneys.append(attorney)
        if not validate_list(self.attorneys) and validate_list(existing_results.attorneys):
            self.attorneys = existing_results.attorneys
        
        if validate_list(self.inventors) and validate_list(existing_results.inventors):
            for inventor in existing_results.inventors:
                if validate_string(inventor):
                    if inventor.strip().lower() not in self.inventors:
                        self.inventors.append(inventor.strip())
        if not validate_list(self.inventors) and validate_list(existing_results.inventors):
            self.inventors = existing_results.inventors
        
        if not validate_string(self.applicant) and validate_string(existing_results.applicant):
            self.applicant = existing_results.applicant
        
        if validate_list(self.current_assignee) and validate_list(existing_results.current_assignee):
            for assignee in existing_results.current_assignee:
                if assignee is not None:
                    if assignee.strip() not in self.current_assignee:
                        self.current_assignee.append(assignee.strip())
        if not validate_list(self.current_assignee) and validate_list(existing_results.current_assignee):
            self.current_assignee = existing_results.current_assignee
        
        if validate_list(self.other_ids) and validate_list(existing_results.other_ids):
            for other_id in existing_results.other_ids:
                if other_id is not None:
                    validated, error_message = other_id.validate_other_id_data()
                    if validated:
                        if other_id.title.strip() not in [o.title for o in self.other_ids]:
                            self.other_ids.append(other_id)
        if not validate_list(self.other_ids) and validate_list(existing_results.other_ids):
            self.other_ids = existing_results.other_ids
        
        if not validate_string(self.source) and validate_string(existing_results.source):
            self.source = existing_results.source
        
        if validate_list(self.documents) and validate_list(existing_results.documents):
            for document in existing_results.documents:
                if document is not None:
                    validated, error_message = document.validate_documents_data()
                    if validated:
                        if document.url.strip() not in [d.url for d in self.documents]:
                            self.documents.append(document)
        if not validate_list(self.documents) and validate_list(existing_results.documents):
            self.documents = existing_results.documents
        
        if validate_list(self.document_urls) and validate_list(existing_results.document_urls):
            for document_url in existing_results.document_urls:
                if document_url is not None:
                    if document_url.strip() not in self.document_urls:
                        self.document_urls.append(document_url.strip())
        if not validate_list(self.document_urls) and validate_list(existing_results.document_urls):
                self.document_urls = existing_results.document_urls
        return True, ""

class SingleClaim(BaseModel):
    documented_claim: str
    market_language_claim: str
    claim_type:str

    @field_validator("claim_type", mode="before")
    @classmethod
    def normalize_claim_type(cls, value):
        if value is None:
            return value
        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        if normalized in _CLAIM_TYPE_ALIASES:
            return _CLAIM_TYPE_ALIASES[normalized]
        if normalized in _ALLOWED_CLAIM_TYPES:
            return normalized
        if normalized.endswith("_claim") and normalized in _ALLOWED_CLAIM_TYPES:
            return normalized
        return normalized

    def get_single_claim_description(self):
        return """
        {
            'documented_claim': str: The claim as documented in the patent.
            'market_language_claim': str: Claim translated in to market language using relevant wordings..
            'claim_type': str: The type of claim.
        }
        """

    def __verify_original_claim(self):
        temp = str(self.documented_claim).strip().lower()
        temp = temp.replace(" ", "")
        temp = temp.replace("\n", "")
        temp = temp.replace("\t", "")
        temp = temp.replace("\r", "")
        temp = temp.replace("\f", "")
        temp = temp.replace("\v", "")
        temp = temp.replace("\b", "")
        temp = temp.replace("\a", "")
        temp = temp.replace("\0", "")
        if len(temp) == 0:
            return False, "Documented claim is empty"
        return True, ""
    
    def __verify_market_language_claim(self):
        temp = str(self.market_language_claim).strip().lower()
        temp = temp.replace(" ", "")
        temp = temp.replace("\n", "")
        temp = temp.replace("\t", "")
        temp = temp.replace("\r", "")
        temp = temp.replace("\f", "")
        temp = temp.replace("\v", "")
        temp = temp.replace("\b", "")
        temp = temp.replace("\a", "")
        temp = temp.replace("\0", "")
        if len(temp) == 0:
            return False, "Market language claim is empty"
        return True, ""
    
    def __verify_claim_type(self):
        temp = str(self.claim_type).strip().lower()
        if temp in ["asserted_claim", "independent_claim", "core_claim", "pivotal_claim"]:
            return True, ""
        return False, "Invalid claim type"

    def verify_single_claim(self):
        original_validated, original_error_message = self.__verify_original_claim()
        if not original_validated:
            return False, original_error_message
        market_language_validated, market_language_error_message = self.__verify_market_language_claim()
        if not market_language_validated:
            return False, market_language_error_message
        claim_type_validated, claim_type_error_message = self.__verify_claim_type()
        if not claim_type_validated:
            return False, claim_type_error_message
        return True, ""

class DocumentedClaims(BaseModel):
    """Plain documented claim text for infringing patents (no types or market language)."""
    claims: list[str]

    def verify_documented_claims(self):
        if not self.claims:
            return False, "No claims extracted"
        for i, claim in enumerate(self.claims):
            if not isinstance(claim, str) or not claim.strip():
                return False, f"Claim {i + 1} is empty"
        return True, ""

class IsolatedClaims(BaseModel):
    claims: list[SingleClaim]

    @classmethod
    def get_isolated_claims_description(cls):
        return """
        {
            'claims': list[SingleClaim]: The claims that are isolated from the patent.
        }

        Structure of SingleClaim:
        {
            'documented_claim': str: The claim as documented in the patent. Translated to english if in foreign language.
            'market_language_claim': str: Claim translated in to market language using relevant wordings..
            'claim_type': str: The type of claim.
        }
        """
    
    def verify_isolated_claims(self):
        for i in range(len(self.claims)):
            claim = self.claims[i]
            validated, error_message = claim.verify_single_claim()
            if not validated:
                message = "For claim "+str(i+1)+": "+error_message
                return False, message
        return True, ""

class InfringementAnalysis(BaseModel):
    claim: str
    similarity_score: float

    def validate_infringement_analysis(self):
        if self.claim is None:
            return False, "Claim is required"
        if self.claim.strip() == "":
            return False, "Claim is empty"
        if self.similarity_score is None:
            return False, "Similarity score is required"
        if self.similarity_score < 0 or self.similarity_score > 1:
            return False, "Similarity score must be between 0 and 1"
        return True, ""

class ProductTargetSource(BaseModel):
    title: str
    url: str
    scope: list[str] = []

    @classmethod
    def get_description(cls) -> str:
        return json.dumps(
            {
                "title": "Human-readable name of the retailer, marketplace, or manufacturer storefront",
                "url": "Homepage or canonical shopping URL (must be real and reachable; do not invent URLs)",
                "scope": "List of country/region codes where products ship (e.g. US, UK, EU)",
            },
            indent=2,
        )

    @staticmethod
    def normalize_hostname(url: str) -> str:
        try:
            host = urlparse(url.strip()).netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return ""

    def validate_url_exists(self, session: requests.Session | None = None) -> tuple[bool, str]:
        if not self.url or not str(self.url).strip():
            return False, "URL is empty"
        owns_session = session is None
        if owns_session:
            session = requests.Session()
            session.headers.update(_PRODUCT_URL_HEADERS)
        try:
            response = session.head(
                self.url.strip(),
                timeout=_URL_CHECK_TIMEOUT,
                allow_redirects=True,
            )
            if response.status_code >= 400:
                response = session.get(
                    self.url.strip(),
                    timeout=_URL_CHECK_TIMEOUT,
                    allow_redirects=True,
                )
            if response.status_code < 400:
                return True, ""
            return False, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)
        finally:
            if owns_session:
                session.close()

    def validate_product_target_source(self) -> tuple[bool, str]:
        if not validate_string(self.title):
            return False, "Title is required"
        if not validate_string(self.url):
            return False, "URL is required"
        if self.scope is None:
            return False, "Scope is required"
        if not isinstance(self.scope, list):
            return False, "Scope must be a list"
        return True, ""


class ProductTargetSources(BaseModel):
    target_sources: list[ProductTargetSource]

    @classmethod
    def get_description(cls) -> str:
        return json.dumps(
            {
                "target_sources": [
                    json.loads(ProductTargetSource.get_description()),
                ],
            },
            indent=2,
        )

    @classmethod
    def default_catalog(cls) -> "ProductTargetSources":
        return cls(
            target_sources=[
                ProductTargetSource(title="Amazon US", url="https://www.amazon.com", scope=["US"]),
                ProductTargetSource(title="Amazon UK", url="https://www.amazon.co.uk", scope=["UK"]),
                ProductTargetSource(title="Walmart", url="https://www.walmart.com", scope=["US"]),
                ProductTargetSource(title="eBay US", url="https://www.ebay.com", scope=["US"]),
                ProductTargetSource(title="Target", url="https://www.target.com", scope=["US"]),
                ProductTargetSource(title="Best Buy", url="https://www.bestbuy.com", scope=["US"]),
                ProductTargetSource(title="Home Depot", url="https://www.homedepot.com", scope=["US"]),
                ProductTargetSource(title="Lowe's", url="https://www.lowes.com", scope=["US"]),
            ]
        )

    def catalog_urls(self) -> list[str]:
        return [source.url.strip() for source in self.target_sources if source.url]

    def filter_reachable(self, session: requests.Session | None = None) -> "ProductTargetSources":
        kept = []
        owns_session = session is None
        if owns_session:
            session = requests.Session()
            session.headers.update(_PRODUCT_URL_HEADERS)
        try:
            for source in self.target_sources:
                ok, err = source.validate_url_exists(session=session)
                if ok:
                    kept.append(source)
                else:
                    print(f"WARN: Unreachable product target source {source.url}: {err}")
        finally:
            if owns_session:
                session.close()
        return ProductTargetSources(target_sources=kept)

    def validate_against_catalog(
        self,
        catalog: "ProductTargetSources",
    ) -> tuple[bool, str]:
        if self.target_sources is None:
            return False, "target_sources is required"
        allowed_hosts = {
            ProductTargetSource.normalize_hostname(url)
            for url in catalog.catalog_urls()
        }
        for index, source in enumerate(self.target_sources):
            valid, message = source.validate_product_target_source()
            if not valid:
                return False, f"For target source {index + 1}: {message}"
            host = ProductTargetSource.normalize_hostname(source.url)
            if host not in allowed_hosts:
                return False, (
                    f"For target source {index + 1}: URL host {host!r} is not in the allowed catalog"
                )
        return True, ""

    def merge_urls_into_search_limitations(self, search_limitations: dict) -> dict:
        merged = dict(search_limitations or {})
        existing = merged.get("urls") or []
        if not isinstance(existing, list):
            existing = [existing] if existing else []
        isolated_urls = self.catalog_urls()
        merged["urls"] = list(dict.fromkeys([*existing, *isolated_urls]))
        merged["priority_target_sources"] = [
            source.model_dump() for source in self.target_sources
        ]
        return merged


class GoogleSearchResults(BaseModel):
    title: str
    url: str
    website_name: str
    description: str

    def validate_google_search_results(self):
        if self.title is None:
            return False, "Title is required"
        if self.url is None:
            return False, "URL is required"
        if self.website_name is None:
            return False, "Website name is required"
        if self.description is None:
            return False, "Description is required"
        return True, ""

class GoogleSearchResultsList(BaseModel):
    """Wrapper so Gemini receives an object schema (required), not an array."""
    results: list[GoogleSearchResults]

    def validate_google_search_results_list(self):
        if self.results is None:
            return False, "Results are required"
        for index in range(len(self.results)):
            result = self.results[index]
            validated, error_message = result.validate_google_search_results()
            if not validated:
                return False, "For result "+str(index+1)+": "+error_message
        return True, ""

def _reject_error_page_text(field_label: str, text: str):
    keyword = match_runtime_block_keyword(text)
    if keyword:
        return False, f"{field_label} indicates a blocked page ({keyword!r})"
    return True, ""


_DUMMY_SENTINELS = frozenset({
    "not available",
    "not found",
    "unknown",
    "n/a",
    "na",
    "none",
    "null",
    "not extractable",
    "url not found",
    "url not found in corrupted content",
    "not extractable due to data corruption",
    "product name unreadable due to data corruption",
})

_SCHEMA_PLACEHOLDER_RE = re.compile(
    r"<\s*(?:string|list\s*\[\s*str\s*\]|int|float|bool)\s*:",
    re.IGNORECASE,
)


def _normalize_dummy_token(value: str) -> str:
    return re.sub(r"[_\s]+", " ", str(value).strip().lower())


def is_dummy_product_value(value) -> bool:
    """True for empty values, LLM schema placeholders, or sentinel not-available strings."""
    if value is None:
        return True
    if not isinstance(value, str) or not value.strip():
        return True
    text = value.strip()
    if _SCHEMA_PLACEHOLDER_RE.search(text):
        return True
    if _normalize_dummy_token(text) in _DUMMY_SENTINELS:
        return True
    return False


def is_valid_product_url(value) -> bool:
    if is_dummy_product_value(value):
        return False
    text = str(value).strip().lower()
    return text.startswith("http://") or text.startswith("https://")


_PDP_URL_MARKERS = (
    "/dp/",
    "/gp/product/",
    "/ip/",
    "/pd/",
    "/en/product/",
    "/product/",
    "/site/",
)

_LISTING_URL_MARKERS = (
    "/browse/",
    "/category/",
    "/categories/",
    "/collections/",
    "/search",
    "/s?",
    "/music/",
    "/books/",
    "/clothing/",
    "/b/",
    "/sch/",
)

_LISTING_URL_PATTERNS = (
    re.compile(r"/dishwashers/?$", re.IGNORECASE),
    re.compile(r"/[a-z]{2}(?:-[a-z]{2})?/dishwashers/?$", re.IGNORECASE),
    re.compile(r"/home-appliances/dishwashers/?$", re.IGNORECASE),
)

_TARGET_PDP_PATTERN = re.compile(r"/p/.+/-/a-\d+", re.IGNORECASE)


def is_product_listing_url(url: str) -> bool:
    """True when URL looks like a category, search, or browse page — not a single product PDP."""
    if not isinstance(url, str) or not url.strip():
        return True
    normalized = url.strip().lower()
    parsed = urlparse(normalized)
    path = parsed.path or ""
    query = parsed.query or ""

    if query and any(token in query for token in ("k=", "keywords=", "search=", "q=")):
        if "/s?" in normalized or "/search" in path:
            return True

    for marker in _PDP_URL_MARKERS:
        if marker in normalized:
            return False
    if _TARGET_PDP_PATTERN.search(normalized):
        return False
    if "samsung.com" in normalized and "/dishwashers/" in normalized:
        if len([segment for segment in path.strip("/").split("/") if segment]) >= 4:
            return False

    for marker in _LISTING_URL_MARKERS:
        if marker in normalized:
            return True
    for pattern in _LISTING_URL_PATTERNS:
        if pattern.search(path):
            return True
    return False


def _reject_dummy_product_field(field_label: str, text: str):
    if is_dummy_product_value(text):
        return False, f"{field_label} is a dummy or placeholder value ({text!r})"
    return True, ""


class InfringingProductDetail(BaseModel):
    source: str
    product_id: str
    product_url: str
    product_name: str
    claims: list[str]
    similar_claims: list["ProductSimilarityClaim"] = []

    def validate_infringing_product_detail(self):
        if self.source is None:
            return False, "Source is required"
        if self.product_id is None:
            return False, "Product ID is required"
        if self.product_url is None:
            return False, "Product URL is required"
        if self.product_name is None:
            return False, "Product name is required"
        for field_label, value in (
            ("Product ID", self.product_id),
            ("Product URL", self.product_url),
            ("Product name", self.product_name),
            ("Source", self.source),
        ):
            validated, error_message = _reject_dummy_product_field(field_label, value)
            if not validated:
                return False, error_message
        if not is_valid_product_url(self.product_url):
            return False, f"Product URL is not a valid http(s) URL ({self.product_url!r})"
        if is_product_listing_url(self.product_url):
            return False, f"Product URL is a category or listing page ({self.product_url!r})"
        validated, error_message = _reject_error_page_text("Product name", self.product_name)
        if not validated:
            return False, error_message
        for index in range(len(self.claims)):
            claim = self.claims[index]
            if not isinstance(claim, str) or not claim.strip():
                return False, "For claim "+str(index+1)+": Claim is empty"
            validated, error_message = _reject_dummy_product_field(
                f"Claim {index + 1}", claim
            )
            if not validated:
                return False, error_message
            validated, error_message = _reject_error_page_text(
                f"Claim {index + 1}", claim
            )
            if not validated:
                return False, error_message
        for index in range(len(self.similar_claims)):
            claim = self.similar_claims[index]
            validated, error_message = claim.validate_product_similarity_claim()
            if not validated:
                return False, "For similar claim "+str(index+1)+": "+error_message
        return True, ""

class ProductSimilarityClaim(BaseModel):
    claim: str
    similarity_score: float
    source: str
    url_to_claim: str
    justification: str

    def validate_product_similarity_claim(self):
        if self.claim is None:
            return False, "Claim is required"
        if self.similarity_score is None:
            return False, "Similarity score is required"
        if self.source is None:
            return False, "Source is required"
        if self.url_to_claim is None:
            return False, "URL to claim is required"
        if self.justification is None:
            return False, "Justification is required"
        return True, ""

class ProductSimilarityClaimList(BaseModel):
    """Wrapper so Gemini receives an object schema (required), not an array."""
    items: list[ProductSimilarityClaim]

    def validate_product_similarity_claim_list(self):
        if self.items is None:
            return False, "Similarity claims are required"
        for index in range(len(self.items)):
            item = self.items[index]
            validated, error_message = item.validate_product_similarity_claim()
            if not validated:
                return False, "For claim item "+str(index+1)+": "+error_message
        return True, ""

class PatentSource(BaseModel):
    id: str
    source: str
    country: str

    def validate_patent_source(self):
        if self.id is None:
            return False, "Patent ID is required"
        if self.source is None:
            return False, "Source is required"
        if self.country is None:
            return False, "Country is required"
        return True, ""

class PatentSourceList(BaseModel):
    patents: list[PatentSource]

    def validate_patent_source_list(self):
        if self.patents is None:
            return False, "Patents are required"
        for index in range(len(self.patents)):
            patent = self.patents[index]
            validated, error_message = patent.validate_patent_source()
            if not validated:
                return False, "For patent "+str(index+1)+": "+error_message
        return True, ""

class ClaimTypes(BaseModel):
    asserted_claims: list[str]
    independent_claims: list[str]
    core_claims: list[str]
    pivotal_claims: list[str]

    def get_claim_types_description(self):
        return """
        {
          'asserted_claims': list<str>: The specific claims selected for a lawsuit because a competitor's product actively infringes them.
          'independent_claims': list<str>: Broad, standalone claims that don't rely on other claims, making them the primary targets for litigation.
          'core_claims': list<str>: Industry shorthand for the specific claims that capture the actual commercial value of the product.
          'pivotal_claims': list<str>: The claims that best survive "prior art" challenges while still catching the infringer.
        }
        """