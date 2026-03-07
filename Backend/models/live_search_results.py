from pydantic import BaseModel

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
    # Set Mailing Addresses to an empty list

    def created(self, creator: str):
        self.created_date = str(datetime.now().isoformat())
        self.created_by = creator

        self.references = []
        self.infringement_details = []
        self.infringements = []
        self.mailing_addresses = []
        return self

class DocumentsData(BaseModel):
    url: str
    source: str

class AttorneysData(BaseModel):
    name: str
    registrationNumber: str
    contact: list[str]

class IsolatedClaims(BaseModel):
    claims: list[str]

class InfringementAnalysis(BaseModel):
    claim: str
    similarity_score: float