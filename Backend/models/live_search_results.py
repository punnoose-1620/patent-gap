from pydantic import BaseModel

class DocumentsData(BaseModel):
    url: str
    source: str

class AttorneysData(BaseModel):
    name: str
    registrationNumber: str
    contact: list[str]

class LiveSearchResults(BaseModel):
    _id: str
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
    # Set Mailing Addresses to an empty list

    def created(self, creator: str):
        self.created_date = str(datetime.now().isoformat())
        self.created_by = creator

        self.references = []
        self.infringement_details = []
        self.infringements = []
        self.mailing_addresses = []
        return self

class IsolatedClaims(BaseModel):
    claims: list[str]

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