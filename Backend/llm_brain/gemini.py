import copy
import json
import google.generativeai as genai
from env_controller import getEnvKey

from llm_brain.static_prompts import *
from Backend.models.live_search_results import *

# Keys the legacy SDK doesn't accept (remove these, keep everything else)
_SCHEMA_STRIP_KEYS = {"title", "description", "examples", "default", "$defs"}

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
        schema = _rename_schema_keys_for_api(
            _strip_unsupported_schema_keys(_schema_without_defs(LiveSearchResults.model_json_schema()))
        )
        response = gemini_client.generate_content(
            final_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=schema
            )
        )
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
        return LiveSearchResults.model_validate(data)

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
                response_schema=_strip_unsupported_schema_keys(_schema_without_defs(IsolatedClaims.model_json_schema()))
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
                response_schema=_strip_unsupported_schema_keys(_schema_without_defs(InfringementAnalysis.model_json_schema()))
            )
        )
        return InfringementAnalysis.model_validate_json(response.text)