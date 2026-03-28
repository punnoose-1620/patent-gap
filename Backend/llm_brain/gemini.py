import copy
import json
from google import genai
from google.genai import types
from env_controller import getEnvKey

from llm_brain.static_prompts import *
from models.live_search_results import *

# Keys the legacy SDK doesn't accept as *schema annotations*.
# IMPORTANT: Do NOT include field names like "title" or "description" here,
# or they will be stripped from the properties we want Gemini to fill.
_SCHEMA_STRIP_KEYS = {"examples", "default", "$defs"}

def _strip_unsupported_schema_keys(obj):
    if isinstance(obj, dict):
        cleaned = {
            k: _strip_unsupported_schema_keys(v)
            for k, v in obj.items()
            if k not in _SCHEMA_STRIP_KEYS
        }
        return cleaned
    if isinstance(obj, list):
        return [_strip_unsupported_schema_keys(v) for v in obj]
    return obj

def _schema_without_defs(schema: dict) -> dict:
    """Remove $defs and inline $ref so legacy Gemini SDK accepts the schema."""
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})

    def inline_refs(obj):
        if isinstance(obj, dict):
            if "$ref" in obj and len(obj) == 1:
                ref = obj["$ref"]
                if ref.startswith("#/$defs/"):
                    name = ref.split("/")[-1]
                    if name in defs:
                        return inline_refs(defs[name])
            return {k: inline_refs(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [inline_refs(v) for v in obj]
        return obj

    return inline_refs(schema)

# Rename schema keys the API rejects; map back when parsing response
_SCHEMA_RENAME_FOR_API = {"_id": "id", "status": "case_status"}

def _rename_schema_keys_for_api(schema: dict) -> dict:
    """Rename _id -> id, status -> case_status and drop required so legacy API accepts schema."""
    schema = copy.deepcopy(schema)
    props = schema.get("properties", {})
    for old_name, new_name in _SCHEMA_RENAME_FOR_API.items():
        if old_name in props:
            props[new_name] = props.pop(old_name)
    # Remove required array so API does not validate required[0], required[2], etc.
    schema.pop("required", None)
    return schema

class Gemini:
    instance: 'Gemini' = None
    apiKey:str

    def __init__(self):
        self.apiKey = getEnvKey('gemini')
        self._client = genai.Client(api_key=self.apiKey)

    def extract_patent_metadata(
        self, 
        patent_content:str, 
        model_name:str = 'gemini-2.5-flash', 
        count:int = 0
        ):
        final_prompt = PATENT_METADATA_EXTRACTOR + "\nHere's the content : \n" + str(patent_content)
        if count > 0:
            final_prompt += "\n\nPlease try again. You haven't extracted valid patent metadata yet."

        schema = _rename_schema_keys_for_api(
            _strip_unsupported_schema_keys(_schema_without_defs(LiveSearchResults.model_json_schema()))
        )
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            },
        )
        if "429 RESOURCE_EXHAUSTED" in response.text:
            raise Exception("Error: Gemini rate limit exceeded")
        data = json.loads(response.text)
        data["_id"] = data.pop("id", data.get("_id", ""))
        data["status"] = data.pop("case_status", data.get("status", ""))
        # Fill missing required fields so validation does not fail when LLM omits them
        _defaults = {
            "title": "",
            "description": "",
            "currentStatusCode": 0,
            "currentStatusDate": "",
            "filingDate": "",
            "documents": [],
            "document_urls": [],
            "keywords": [],
            "claims": [],
            "attorneys": [],
            "inventors": [],
        }
        for key, default in _defaults.items():
            if key not in data or data[key] is None:
                data[key] = default
        title = data.get("title", "")
        filing_date = data.get("filingDate", "")
        if (title.strip() == "") or (filing_date.strip() == ""):
            if count >= 3:
                raise Exception("Error: Failed to extract patent metadata after 3 attempts")
            return LiveSearchResults.model_validate(self.extract_patent_metadata(patent_content, model_name, count + 1))
        return LiveSearchResults.model_validate(data)

    def extract_claims(
        self, 
        patent_content:str, 
        model_name:str = 'gemini-2.5-flash'
        ):
        final_prompt = CLAIM_ISOLATOR + "\nHere's the content : \n" + str(patent_content)

        schema = _strip_unsupported_schema_keys(_schema_without_defs(IsolatedClaims.model_json_schema()))
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            },
        )
        return IsolatedClaims.model_validate_json(response.text)

    def analyze_infringements(
        self, 
        reference_claims:list[str], 
        infringing_claims:list[str], 
        context:str,
        model_name:str = 'gemini-2.5-flash'
        ):
        
        final_prompt = INFRINGEMENT_ANALYZER.replace("<reference_claims_replacement>", "\n".join(reference_claims))
        final_prompt = final_prompt.replace("<infringing_claims_replacement>", "\n".join(infringing_claims))
        final_prompt = final_prompt.replace("<context_of_reference_claims_replacement>", context)

        schema = _strip_unsupported_schema_keys(_schema_without_defs(InfringementAnalysis.model_json_schema()))
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            },
        )
        return InfringementAnalysis.model_validate_json(response.text)

    def get_search_string(
        self, 
        keywords: list[str], 
        owners: list[str], 
        model_name:str = 'gemini-2.5-flash'
        ):
        final_prompt = SEARCH_STRING_GENERATOR.replace("<keywords_replacement>", "\n".join(keywords))
        final_prompt = final_prompt.replace("<owners_replacement>", "\n".join(owners))
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
        )
        return response.text
    
    def perform_google_search(
        self, 
        search_string: str, 
        model_name:str = 'gemini-2.5-flash'
        ):
        final_prompt = PERFORM_GOOGLE_SEARCH_PROMPT.replace("<search_string_replacement>", search_string)
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": GoogleSearchResultsList.model_json_schema(),
            },
        )
        wrapper = GoogleSearchResultsList.model_validate_json(response.text)
        return wrapper.results
    
    def get_product_details(self, product_content: str, model_name:str = 'gemini-2.5-flash'):
        final_prompt = PRODUCT_DETAILS_EXTRACTOR + "\nHere's the content : \n" + product_content
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": InfringingProductDetail.model_json_schema(),
            },
        )
        return InfringingProductDetail.model_validate_json(response.text)

    def analyze_product_infringements(
        self, 
        reference_claims:list[str], 
        infringing_claims:list[str],
        model_name:str = 'gemini-2.5-flash'
        ):
        final_prompt = PRODUCT_INFRINGEMENT_ANALYZER.replace("<reference_claims_replacement>", "\n".join(reference_claims))
        final_prompt = final_prompt.replace("<infringing_claims_replacement>", "\n".join(infringing_claims))
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ProductSimilarityClaimList.model_json_schema(),
            },
        )
        wrapper = ProductSimilarityClaimList.model_validate_json(response.text)
        return wrapper.items