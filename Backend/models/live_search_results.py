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

class DocumentsData(BaseModel):
    url: str
    source: str

class AttorneysData(BaseModel):
    name: str
    registrationNumber: str
    contact: list[str]