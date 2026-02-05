claim_model_name = "gemini-2.5-flash"
summary_model_name = "gemini-2.5-flash"
infringement_model_name = "gemini-3-flash-preview"

infringement_keys = ['source', 'entry_id', 'similar_claims']
similarity_claim_keys = ['claim', 'similarity_score', 'source', 'url_to_claim']
sources = ['USPTO Open Data Portal', 'Google Patents', 'Espacenet', 'WIPO Patentscope', 'The Lens']
model_name = "gemini-3-flash-preview"

claim_isolation_propmt = """
I am providing a full patent document below. 
Locate the section titled 'Claims' or 'What is claimed is:'. 
Extract all numbered claims starting from Claim 1 until the end of the document. 
Ignore all other sections like 'Detailed Description', 'Abstract', or 'Background'. 
Return only the raw text of the claims, preserving their original numbering and hierarchical structure.
Avoid incomplete claims.
Do not include any other text or comments.

<DOCUMENT_CONTENTS_REPLACEMENT>
"""

search_prompts = """
I am providing a list of claims below.
<CLAIMS_LIST_REPLACEMENT>
I want you to search for similar claims in the following sources:
<SOURCES_LIST_REPLACEMENT>
Return the similar claims in the following format:
<RESPONSE_FORMAT_REPLACEMENT>
Note that entry_title is the title of the patent infringing upon this claim.
"""

response_format = """
{
  "source": "<string: Name of the patent data source (e.g., 'USPTO Open Data Portal')>",
  "entry id": "<string: Unique identifier for the matched document or entry>",
  "similar claims": [
    {
        "claim" : "<string: Text of the similar claim>",
        "similarity_score" : "<number: Similarity score between 0 and 1>"
    }
  ]
}
"""

complete_summary_prompt = """
I am providing a full patent document below.
<DOCUMENT_CONTENTS_REPLACEMENT>
Generate a summary of the patent in 100 words or fewer.
Return only the raw text of the summary.
Do not include any other text or comments.
"""