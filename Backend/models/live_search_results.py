from pydantic import BaseModel, field_validator

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

class OtherIdData(BaseModel):
    title: str
    value: list[str]

class DocumentsData(BaseModel):
    url: str
    source: str

class AttorneysData(BaseModel):
    name: str
    registrationNumber: str
    contact: list[str]

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
    # Set Mailing Addresses to an empty list

    def created(self, creator: str):
        self.created_date = str(datetime.now().isoformat())
        self.created_by = creator

        self.references = []
        self.infringement_details = []
        self.infringements = []
        self.mailing_addresses = []
        return self

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
            'documented_claim': str: The claim as documented in the patent.
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

class GoogleSearchResults(BaseModel):
    title: str
    url: str
    website_name: str
    description: str

class GoogleSearchResultsList(BaseModel):
    """Wrapper so Gemini receives an object schema (required), not an array."""
    results: list[GoogleSearchResults]

class InfringingProductDetail(BaseModel):
    source: str
    product_id: str
    product_url: str
    product_name: str
    claims: list[str]
    similar_claims: list["ProductSimilarityClaim"] = []

class ProductSimilarityClaim(BaseModel):
    claim: str
    similarity_score: float
    source: str
    url_to_claim: str
    justification: str

class ProductSimilarityClaimList(BaseModel):
    """Wrapper so Gemini receives an object schema (required), not an array."""
    items: list[ProductSimilarityClaim]

class PatentSource(BaseModel):
    id: str
    source: str
    country: str

class PatentSourceList(BaseModel):
    patents: list[PatentSource]

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