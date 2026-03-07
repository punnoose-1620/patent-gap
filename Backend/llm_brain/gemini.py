import google.generativeai as genai
from env_controller import getEnvKey

from static_prompts import *
from Backend.models.live_search_results import *


class Gemini:
    instance: 'Gemini' = None
    apiKey:str

    def __init__(self):
        self.apiKey = getEnvKey('gemini')
        instance = genai.configure(api_key=self.apiKey)

    def extract_patent_metadata(
        self, 
        patent_content:str, 
        model_name:str = 'gemini-2.5-flash'
        ):
        final_prompt = PATENT_METADATA_EXTRACTOR + "\nHere's the content : \n" + patent_content

        # Example (pseudo) setup for API client (replace with actual Gemini SDK/client):
        gemini_client = genai.GenerativeModel(model_name)

        # To actually call the model and use the prompt:
        response = gemini_client.generate_content(
            final_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=LiveSearchResults.model_json_schema()
            )
        )
        return LiveSearchResults.model_validate_json(response.text)

    def extract_claims(
        self, 
        patent_content:str, 
        model_name:str = 'gemini-2.5-flash'
        ):
        final_prompt = CLAIM_ISOLATOR + "\nHere's the content : \n" + patent_content

        # Example (pseudo) setup for API client (replace with actual Gemini SDK/client):
        gemini_client = genai.GenerativeModel(model_name)

        # To actually call the model and use the prompt:
        response = gemini_client.generate_content(
            final_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=IsolatedClaims.model_json_schema()
            )
        )
        return IsolatedClaims.model_validate_json(response.text)

    def analyze_infringements(
        self, 
        reference_claims:list[str], 
        infringing_claims:list[str], 
        model_name:str = 'gemini-2.5-flash'
        ):
        final_prompt = INFRINGEMENT_ANALYZER.replace("<reference_claims_replacement>", "\n".join(reference_claims)).replace("<infringing_claims_replacement>", "\n".join(infringing_claims))

        # Example (pseudo) setup for API client (replace with actual Gemini SDK/client):
        gemini_client = genai.GenerativeModel(model_name)

        # To actually call the model and use the prompt:
        response = gemini_client.generate_content(
            final_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=InfringementAnalysis.model_json_schema()
            )
        )
        return InfringementAnalysis.model_validate_json(response.text)