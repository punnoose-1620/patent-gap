import json
from Prompts import *
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
    entry_title: str
    entry_url: str
    similar_claims: list[SimilarityClaim]

def get_claim_model_client():
    genai.configure(api_key=getEnvKey('gemini'))
    return genai.GenerativeModel(claim_model_name)

def get_summary_model_client():
    genai.configure(api_key=getEnvKey('gemini'))
    return genai.GenerativeModel(summary_model_name)

def get_infringement_model_client():
    genai.configure(api_key=getEnvKey('gemini'))
    return genai.GenerativeModel(infringement_model_name)

def get_claims(document_contents: str):
    """
    This function is used to get the claims from the document contents.
    It will return the list of claims if they are valid, otherwise it will return an empty list.
    """
    complete_claim_isolation_prompt = claim_isolation_propmt.replace("<DOCUMENT_CONTENTS_REPLACEMENT>", document_contents)
    try:
        claims_response = get_claim_model_client().generate_content(complete_claim_isolation_prompt)
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
        infringements_response = get_infringement_model_client().generate_content(
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

def get_complete_infringements(claims: list[str]):
    """
    This function is used to get the complete infringements from the document contents.
    It will return the infringements if they are valid, otherwise it will return an empty list.
    It will try to get the infringements 3 times if they are not valid.
    """
    attempts = 0
    similar_infringements = get_similar_infringements(claims)
    if not check_infringement_results(similar_infringements):
        print('\nERROR: Failed to get the complete infringements after 1 attempt')
        return []
    return similar_infringements

def get_patent_summary(document_contents: str):
    """
    This function is used to get the summary of the patent from the document contents.
    It will return the summary if it is valid, otherwise it will return an empty string.
    """
    complete_summary_prompt = summary_prompt.replace("<DOCUMENT_CONTENTS_REPLACEMENT>", document_contents)
    try:
        summary_response = get_summary_model_client().generate_content(complete_summary_prompt)
        return summary_response._result.candidates[0].content.parts[0].text
    except Exception as e:
        print('\nERROR: Error in get_patent_summary: ', e)
        return ''
