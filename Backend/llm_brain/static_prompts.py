PATENT_METADATA_EXTRACTOR = """
I am providing a full patent document below.
Extract the metadata of the patent in the following format:
{
  "_id": "<string: Unique identifier for the patent>",
  "title": "<string: Title of the patent>",
  "status": "<string: Status of the patent shows the current status of the patent>",
  "description": "<string: Description of the patent>",
  "currentStatusCode": "<number: Current status code of the patent shows the current status of the patent>",
  "currentStatusDate": "<string: Current status date of the patent shows when the patent was last updated>",
  "filingDate": "<string: Filing date of the patent shows when the patent was filed>",
  "documents": "<list[DocumentsData]: List of documents of the patent>",
  "document_urls": "<list[str]: List of document urls of the patent>",
  "keywords": "<list[str]: List of keywords of the patent>",
  "claims": "<list[str]: List of claims of the patent>",
  "attorneys": "<list[AttorneysData]: List of attorneys of the patent>",
  "inventors": "<list[str]: List of inventors of the patent>"
}
DocumentsData is a dictionary with the following keys:
{
  "url": "<string: URL of the document>",
  "source": "<string: Source of the document>",
}
AttorneysData is a dictionary with the following keys:
{
  "name": "<string: Name of the attorney>",
  "registrationNumber": "<string: Registration number of the attorney in the country in which they are registered>",
}
"""

CLAIM_ISOLATOR = """
I am providing all the content from all documents related to a patent below.
Extract all the claims from the documents.
Return the claims in the following format:
{
  "claims": "<list[str]: List of claims of the patent>",
}
Do not include any other text or comments.
"""

INFRINGEMENT_ANALYZER = """
I am providing you with 2 sets of claims :
Reference Claims: <list[str]: List of claims of the patent>
Infringing Claims: <list[str]: List of claims of the patent>
Analyze the claims and determine if the infringing claims are similar to the reference claims.
Return the analysis in the following format:
{
  "claim": "<string: Claim that is similar to the reference claims>",
  "similarity_score": "<number: Similarity score between 0 and 1>",
}
Similarity score is a number between 0 and 1 that represents the similarity between the infringing claim and the reference claim.
The higher the similarity score, the more similar the claims are.
The similarity score is calculated using the cosine similarity algorithm.
Do not include any other text or comments.

Reference Claims : 
<reference_claims_replacement>

Infringing Claims : 
<infringing_claims_replacement>
"""

