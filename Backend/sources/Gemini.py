import json
from env_controller import getEnvKey
import google.generativeai as genai
from typing_extensions import TypedDict

"""
This file contains the functions to get the similar infringements from the document contents using the Gemini model.
It will return the list of similar infringements if they are valid, otherwise it will return an empty list.
It will try to get the similar infringements 3 times if they are not valid.

This is the flow of the process:
1. Get the claims from the document contents.
2. Get the similar infringements from the claims.
3. Check if the similar infringements are valid.
4. Return the similar infringements if they are valid, otherwise return an empty list.
"""

class SimilarityClaim(TypedDict):
    claim: str
    similarity_score: float
    source: str
    url_to_claim: str

class InfringementSource(TypedDict):
    source: str
    entry_id: str
    similar_claims: list[SimilarityClaim]

infringement_keys = ['source', 'entry_id', 'similar_claims']
similarity_claim_keys = ['claim', 'similarity_score', 'source', 'url_to_claim']

claim_isolation_propmt = """
I am providing a full patent document below. 
Locate the section titled 'Claims' or 'What is claimed is:'. 
Extract all numbered claims starting from Claim 1 until the end of the document. 
Ignore all other sections like 'Detailed Description', 'Abstract', or 'Background'. 
Return only the raw text of the claims, preserving their original numbering and hierarchical structure.

<DOCUMENT_CONTENTS_REPLACEMENT>
"""

search_prompts = """
I am providing a list of claims below.
<CLAIMS_LIST_REPLACEMENT>
I want you to search for similar claims in the following sources:
<SOURCES_LIST_REPLACEMENT>
Return the similar claims in the following format:
<RESPONSE_FORMAT_REPLACEMENT>
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

sources = ['USPTO Open Data Portal', 'Google Patents', 'Espacenet', 'WIPO Patentscope', 'The Lens']
model_name = "gemini-3-flash-preview"

def get_model_client():
    """
    This function is used to get the model client for the given model name.
    It will return the model client if it is valid, otherwise it will return None.
    """
    genai.configure(api_key=getEnvKey('gemini'))
    return genai.GenerativeModel(model_name)

def get_claims(document_contents: str):
    """
    This function is used to get the claims from the document contents.
    It will return the list of claims if they are valid, otherwise it will return an empty list.
    """
    complete_claim_isolation_prompt = claim_isolation_propmt.replace("<DOCUMENT_CONTENTS_REPLACEMENT>", document_contents)
    try:
        claims_response = get_model_client().generate_content(complete_claim_isolation_prompt)
        claims_list_string = claims_response._result.candidates[0].content.parts[0].text
        claims_lists = []
        for claim in claims_list_string.split("\n"):
            if (claim.strip() != "") and (claim.strip()[0].isdigit()):
                claims_lists.append(claim.strip())
        return claims_lists
    except Exception as e:
        print('Error in get_claims: ', e)
        if '429' in str(e):
            return ['Rate Exceeded Error']
        elif '403' in str(e):
            return ['Access Forbidden Error']
        elif '401' in str(e):
            return ['Authentication Error']
        elif '400' in str(e):
            return ['Bad Request Error']
        else:
            return []

def check_infringement_keys(entry):
    """
    This function is used to check if the infringement keys are valid.
    It will return True if the infringement keys are valid, otherwise it will return False.
    """
    try:
        print('TEST: Infringement entry keys: ', entry.keys())
        for key in infringement_keys:
            if key not in entry.keys():
                return False
        return True
    except Exception as e:
        print('\nERROR: Error in check_infringement_keys: ', e)
        return False

def check_similarity_claim_keys(entry):
    """
    This function is used to check if the similarity claim keys are valid.
    It will return True if the similarity claim keys are valid, otherwise it will return False.
    """
    try:
        print('TEST: Similarity claim entry keys: ', entry.keys())
        for key in similarity_claim_keys:
            if key not in entry.keys():
                return False
        return True
    except Exception as e:
        print('\nERROR: Error in check_similarity_claim_keys: ', e)
        return False

def get_similar_infringements(claims: list[str]):
    """
    This function is used to get the similar infringements from the claims.
    It will return the similar infringements if they are valid, otherwise it will return an empty list.
    """
    infringements_list = []
    claims_text = ""
    sources_text = ""
    for claim in claims:
        claims_text = f"{claims_text}\n{claim.strip()}"
    for source in sources:
        sources_text = f"{sources_text},{source.strip()}"
    complete_infringement_search_prompt = search_prompts.replace("<CLAIMS_LIST_REPLACEMENT>", claims_text)
    complete_infringement_search_prompt = complete_infringement_search_prompt.replace("<SOURCES_LIST_REPLACEMENT>", sources_text)
    complete_infringement_search_prompt = complete_infringement_search_prompt.replace("<RESPONSE_FORMAT_REPLACEMENT>", response_format)
    if ('<CLAIMS_LIST_REPLACEMENT>' in complete_infringement_search_prompt) or ('<SOURCES_LIST_REPLACEMENT>' in complete_infringement_search_prompt) or ('<RESPONSE_FORMAT_REPLACEMENT>' in complete_infringement_search_prompt):
        print('\nTEST: complete_infringement_search_prompt is missing some placeholders: ', complete_infringement_search_prompt)
        return []
    try:
        infringements_response = get_model_client().generate_content(
            complete_infringement_search_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=list[InfringementSource]
            )
        )
        infringements = json.loads(infringements_response._result.candidates[0].content.parts[0].text)
        if len(infringements) > 0:
            for infringement in infringements:
                infringements_list.append(infringement)
        return infringements_list

    except Exception as e:
        print('\nERROR: Error in get_similar_infringements: ', e)
        return []

def check_infringement_results(infringements: list):
    """
    This function is used to check if the infringements are valid.
    It will return True if the infringements are valid, otherwise it will return False.
    """
    for infringement in infringements:
        print('\nTEST: infringement (',type(infringement),'): ', json.dumps(infringement, indent=4))
        if not check_infringement_keys(infringement):
            return False
        if 'similar_claims' in infringement:
            similar_claims_entries = infringement['similar_claims']
            print('TEST: similar_claims_entry (',type(similar_claims_entries),'): ', json.dumps(similar_claims_entries, indent=4))
            for similar_claims_entry in similar_claims_entries:
                if not check_similarity_claim_keys(similar_claims_entry):
                    return False
    return True

def get_complete_infringements(document_contents: str):
    """
    This function is used to get the complete infringements from the document contents.
    It will return the infringements if they are valid, otherwise it will return an empty list.
    It will try to get the infringements 3 times if they are not valid.
    """
    claims = get_claims(document_contents)
    if (len(claims) == 0) or (claims is None):
        return []
    if (claims[0] == 'Rate Exceeded Error') or (claims[0] == 'Access Forbidden Error') or (claims[0] == 'Authentication Error') or (claims[0] == 'Bad Request Error'):
        return claims
    attempts = 0
    similar_infringements = get_similar_infringements(claims)
    if not check_infringement_results(similar_infringements):
        print('\nERROR: Failed to get the complete infringements after 1 attempt')
        return []
    return similar_infringements
