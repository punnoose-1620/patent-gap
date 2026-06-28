import copy
import json
import time
from google import genai
from google.genai import types
from env_controller import getEnvKey

from llm_brain.static_prompts import *
from models.live_search_results import *

# Keys the legacy SDK doesn't accept as *schema annotations*.
# IMPORTANT: Do NOT include field names like "title" or "description" here,
# or they will be stripped from the properties we want Gemini to fill.
_SCHEMA_STRIP_KEYS = {"examples", "default", "$defs"}
MAX_ATTEMPTS = 5
DEFAULT_LLM_DELAY = 3       # Delay between processing 2 consecutive LLM calls (in seconds)

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
        default_source:str = None
        ):
        count = 0
        count_429 = 0
        error_message = ""

        schema = _rename_schema_keys_for_api(
            _strip_unsupported_schema_keys(_schema_without_defs(LiveSearchResults.model_json_schema()))
        )

        finalData = empty_live_search_results(source=default_source)

        while count < MAX_ATTEMPTS:
            final_prompt = PATENT_METADATA_EXTRACTOR + "\nHere's the content : \n" + str(patent_content)
            if error_message != "":
                final_prompt += "\n\nYour previous response failed validation with the error message: " + error_message + "\n"
                final_prompt += "Do not repeat the same mistake and try again."

            response = self._client.models.generate_content(
                model=model_name,
                contents=final_prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": schema,
                },
            )
            if "429 RESOURCE_EXHAUSTED" in response.text:
                if count_429 < MAX_ATTEMPTS:
                    count_429 += 1
                    time.sleep(DEFAULT_LLM_DELAY * (count_429 + 1))
                    error_message = response.text+"...A fixed delay has been applied before the next attempt."
                    continue
                else:
                    break
            
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
                "applicant": "",
                "current_assignee": [],
                "other_ids": [],
                "source": default_source,
            }
            for key, default in _defaults.items():
                if key not in data or data[key] is None:
                    data[key] = default
            class_data = LiveSearchResults.model_validate(data)
            merged, merge_error_message = finalData.merge_with_existing(class_data)
            print(f"LOG: Extracting patent metadata try {count}... Merged with existing data: {merged}\n\tMessage:{merge_error_message}")
            validated, e_message = finalData.validate_metadata()

            if not validated:
                count += 1
                error_message = e_message
                if count >= MAX_ATTEMPTS:
                    break
                time.sleep(DEFAULT_LLM_DELAY)
                continue
            else:
                break
        validated, e_message = finalData.validate_metadata()
        if not validated:
            error_message = e_message
            raise Exception(f"Patent_Metadata_Error: Failed to extract patent metadata after {MAX_ATTEMPTS} attempts.\n\t{e_message}")
        return finalData

    def extract_claims(
        self, 
        patent_content:str, 
        model_name:str = 'gemini-2.5-flash',
        count:int = 0,
        error_message:str = ""
        ):
        if count >= MAX_ATTEMPTS:
            raise Exception(f"Claims_Isolation_Error: Failed to extract claims after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
        final_prompt = CLAIM_ISOLATOR.replace("<ISOLATED_CLAIMS_RETURN_FORMAT>", IsolatedClaims.get_isolated_claims_description())
        final_prompt = final_prompt + "\nHere's the content : \n" + str(patent_content)
        if error_message != "":
            final_prompt += "\n\nYour previous response failed validation with the error message: " + error_message + "\n"
            final_prompt += "Do not repeat the same mistake and try again."

        schema = _strip_unsupported_schema_keys(_schema_without_defs(IsolatedClaims.model_json_schema()))
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            },
        )
        wrapper = IsolatedClaims.model_validate_json(response.text)
        validated, error_message = wrapper.verify_isolated_claims()
        if not validated:
            if count >= MAX_ATTEMPTS:
                raise Exception(f"Claims_Isolation_Error: Failed to extract claims after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
            time.sleep(DEFAULT_LLM_DELAY)
            return self.extract_claims(
                patent_content=patent_content,
                model_name=model_name,
                count=count + 1,
                error_message=error_message
            )
        return wrapper

    def extract_documented_claims(
        self,
        patent_content: str,
        model_name: str = 'gemini-2.5-flash',
        count:int = 0,
        error_message:str = ""
    ):
        """Extract numbered documented claims only (for live-search infringement candidates)."""
        if count >= MAX_ATTEMPTS:
            raise Exception(f"Documented_Claims_Isolation_Error: Failed to extract documented claims after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
        final_prompt = (
            DOCUMENTED_CLAIMS_ISOLATOR
            + "\nHere's the content:\n"
            + str(patent_content)
        )
        if error_message != "":
            final_prompt += "\n\nYour previous response failed validation with the error message: " + error_message + "\n"
            final_prompt += "Do not repeat the same mistake and try again."
        schema = _strip_unsupported_schema_keys(
            _schema_without_defs(DocumentedClaims.model_json_schema())
        )
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            },
        )
        wrapper = DocumentedClaims.model_validate_json(response.text)
        validated, error_message = wrapper.verify_documented_claims()
        if not validated:
            if count >= MAX_ATTEMPTS:
                raise Exception(f"Documented_Claims_Isolation_Error: Failed to extract documented claims after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
            time.sleep(DEFAULT_LLM_DELAY)
            return self.extract_documented_claims(
                patent_content=patent_content,
                model_name=model_name,
                count=count + 1,
                error_message=error_message
            )
        return wrapper

    def analyze_infringements(
        self, 
        reference_claims:list[str], 
        infringing_claims:list[str], 
        context:str,
        model_name:str = 'gemini-2.5-flash',
        count:int = 0,
        error_message:str = ""
        ):
        if count >= MAX_ATTEMPTS:
            raise Exception(f"Infringement_Analysis_Error: Failed to analyze infringements after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
        final_prompt = INFRINGEMENT_ANALYZER.replace("<reference_claims_replacement>", "\n".join(reference_claims))
        final_prompt = final_prompt.replace("<infringing_claims_replacement>", "\n".join(infringing_claims))
        final_prompt = final_prompt.replace("<context_of_reference_claims_replacement>", context)
        if error_message != "":
            final_prompt += "\n\nYour previous response failed validation with the error message: " + error_message + "\n"
            final_prompt += "Do not repeat the same mistake and try again."

        schema = _strip_unsupported_schema_keys(_schema_without_defs(InfringementAnalysis.model_json_schema()))
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": schema,
            },
        )

        wrapper = InfringementAnalysis.model_validate_json(response.text)
        validated, error_message = wrapper.validate_infringement_analysis()
        if not validated:
            if count >= MAX_ATTEMPTS:
                raise Exception(f"Infringement_Analysis_Error: Failed to analyze infringements after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
            time.sleep(DEFAULT_LLM_DELAY)
            return self.analyze_infringements(
                reference_claims=reference_claims, 
                infringing_claims=infringing_claims, 
                context=context,
                model_name=model_name,
                count=count + 1,
                error_message=error_message
            )
        return wrapper

    def get_search_string(
        self, 
        keywords: list[str], 
        owners: list[str], 
        search_limitations: dict,
        model_name:str = 'gemini-2.5-flash',
        ):
        
        companies = search_limitations.get('companies', [])
        websites = search_limitations.get('urls', [])
        priority_sources = search_limitations.get('priority_target_sources', [])
        priority_lines = []
        for entry in priority_sources:
            if isinstance(entry, dict):
                title = entry.get('title', '')
                url = entry.get('url', '')
                if title or url:
                    priority_lines.append(f"- {title}: {url}".strip())
            elif isinstance(entry, str) and entry.strip():
                priority_lines.append(f"- {entry.strip()}")
        if not priority_lines and websites:
            priority_lines = [f"- {url}" for url in websites if isinstance(url, str) and url.strip()]
        final_prompt = SEARCH_STRING_GENERATOR.replace("<keywords_replacement>", "\n".join(keywords))
        final_prompt = final_prompt.replace("<owners_replacement>", "\n".join(owners))
        final_prompt = final_prompt.replace("<search_limitations_companies>", "\n".join(companies))
        final_prompt = final_prompt.replace("<search_limitations_websites>", "\n".join(websites))
        final_prompt = final_prompt.replace(
            "<priority_target_sources_replacement>",
            "\n".join(priority_lines) if priority_lines else "(none specified)",
        )
        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
        )
        return response.text
    
    def perform_google_search(
        self, 
        search_string: str,
        max_results: int = 30,
        priority_target_sources: list | None = None,
        model_name:str = 'gemini-2.5-flash',
        count:int = 0,
        error_message:str = ""
        ):
        if count >= MAX_ATTEMPTS:
            raise Exception(f"Google_Search_Error: Failed to perform Google search after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
        priority_lines = []
        for entry in priority_target_sources or []:
            if isinstance(entry, dict):
                title = entry.get('title', '')
                url = entry.get('url', '')
                if title or url:
                    priority_lines.append(f"- {title}: {url}".strip())
            elif isinstance(entry, str) and entry.strip():
                priority_lines.append(f"- {entry.strip()}")
        final_prompt = PERFORM_GOOGLE_SEARCH_PROMPT.replace("<search_string_replacement>", search_string)
        final_prompt = final_prompt.replace("<max_results_replacement>", str(max_results))
        final_prompt = final_prompt.replace(
            "<priority_target_sources_replacement>",
            "\n".join(priority_lines) if priority_lines else "(none specified)",
        )
        if error_message != "":
            final_prompt += "\n\nYour previous response failed validation with the error message: " + error_message + "\n"
            final_prompt += "Do not repeat the same mistake and try again."

        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": GoogleSearchResultsList.model_json_schema(),
            },
        )
        wrapper = GoogleSearchResultsList.model_validate_json(response.text)
        validated, error_message = wrapper.validate_google_search_results_list()
        if not validated:
            if count >= MAX_ATTEMPTS:
                raise Exception(f"Google_Search_Error: Failed to perform Google search after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
            time.sleep(DEFAULT_LLM_DELAY)
            return self.perform_google_search(
                search_string=search_string,
                max_results=max_results,
                priority_target_sources=priority_target_sources,
                model_name=model_name,
                count=count + 1,
                error_message=error_message
            )
        return wrapper.results

    def perform_google_search_from_claims(
        self,
        product_name: str,
        reference_claims: list[str],
        owners: list[str] | None = None,
        search_limitations: dict | None = None,
        max_results: int = 30,
        model_name: str = 'gemini-2.5-flash',
        count: int = 0,
        error_message: str = "",
    ):
        if count >= MAX_ATTEMPTS:
            raise Exception(
                f"Google_Search_Error: Failed to perform Google search after {MAX_ATTEMPTS} attempts.\n\t{error_message}"
            )
        limitations = search_limitations or {}
        claims_text = "\n".join(
            claim.strip()
            for claim in (reference_claims or [])
            if isinstance(claim, str) and claim.strip()
        )
        if not claims_text:
            return []

        companies = limitations.get("companies", [])
        websites = limitations.get("urls", [])
        priority_sources = limitations.get("priority_target_sources", [])
        priority_lines = []
        for entry in priority_sources:
            if isinstance(entry, dict):
                title = entry.get("title", "")
                url = entry.get("url", "")
                if title or url:
                    priority_lines.append(f"- {title}: {url}".strip())
            elif isinstance(entry, str) and entry.strip():
                priority_lines.append(f"- {entry.strip()}")
        if not priority_lines and websites:
            priority_lines = [
                f"- {url}" for url in websites if isinstance(url, str) and url.strip()
            ]

        final_prompt = PERFORM_GOOGLE_SEARCH_FROM_CLAIMS_PROMPT.replace(
            "<reference_claims_replacement>", claims_text
        )
        final_prompt = final_prompt.replace(
            "<product_name_replacement>", product_name
            )
        final_prompt = final_prompt.replace(
            "<owners_replacement>",
            "\n".join(owners or []) or "(none specified)",
        )
        final_prompt = final_prompt.replace(
            "<search_limitations_companies>",
            "\n".join(companies) if companies else "(none specified)",
        )
        final_prompt = final_prompt.replace(
            "<search_limitations_websites>",
            "\n".join(websites) if websites else "(none specified)",
        )
        final_prompt = final_prompt.replace(
            "<priority_target_sources_replacement>",
            "\n".join(priority_lines) if priority_lines else "(none specified)",
        )
        final_prompt = final_prompt.replace("<max_results_replacement>", str(max_results))
        if error_message != "":
            final_prompt += (
                "\n\nYour previous response failed validation with the error message: "
                + error_message
                + "\n"
            )
            final_prompt += "Do not repeat the same mistake and try again."

        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": GoogleSearchResultsList.model_json_schema(),
            },
        )
        wrapper = GoogleSearchResultsList.model_validate_json(response.text)
        validated, error_message = wrapper.validate_google_search_results_list()
        if not validated:
            if count >= MAX_ATTEMPTS:
                raise Exception(
                    f"Google_Search_Error: Failed to perform Google search after {MAX_ATTEMPTS} attempts.\n\t{error_message}"
                )
            time.sleep(DEFAULT_LLM_DELAY)
            return self.perform_google_search_from_claims(
                product_name=product_name,
                reference_claims=reference_claims,
                owners=owners,
                search_limitations=search_limitations,
                max_results=max_results,
                model_name=model_name,
                count=count + 1,
                error_message=error_message,
            )
        return wrapper.results

    def isolate_product_target_sources(
        self,
        reference_claims: list[str],
        catalog: ProductTargetSources | None = None,
        model_name: str = 'gemini-2.5-flash',
        count: int = 0,
        error_message: str = "",
    ) -> ProductTargetSources:
        if count >= MAX_ATTEMPTS:
            raise Exception(
                f"Isolate_Product_Target_Sources_Error: Failed after {MAX_ATTEMPTS} attempts.\n\t{error_message}"
            )
        catalog = catalog or ProductTargetSources.default_catalog()
        claims_text = "\n".join(
            claim.strip() for claim in (reference_claims or []) if isinstance(claim, str) and claim.strip()
        )
        if not claims_text:
            return catalog.filter_reachable()

        available_lines = [
            f"- {source.title} | {source.url} | scope={', '.join(source.scope or [])}"
            for source in catalog.target_sources
        ]
        final_prompt = ISOLATE_TARGET_SOURCES.replace("<reference_claims_replacement>", claims_text)
        final_prompt = final_prompt.replace(
            "<target_source_structure_replacement>",
            "\n".join(available_lines),
        )
        final_prompt = final_prompt.replace(
            "<response_structure_replacement>",
            ProductTargetSources.get_description(),
        )
        if error_message:
            final_prompt += (
                "\n\nYour previous response failed validation with the error message: "
                + error_message
                + "\nDo not repeat the same mistake and try again."
            )

        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ProductTargetSources.model_json_schema(),
            },
        )
        isolated = ProductTargetSources.model_validate_json(response.text)
        schema_ok, schema_err = isolated.validate_against_catalog(catalog)
        if not schema_ok:
            time.sleep(DEFAULT_LLM_DELAY)
            return self.isolate_product_target_sources(
                reference_claims=reference_claims,
                catalog=catalog,
                model_name=model_name,
                count=count + 1,
                error_message=schema_err,
            )

        reachable = isolated.filter_reachable()
        if not reachable.target_sources:
            time.sleep(DEFAULT_LLM_DELAY)
            return self.isolate_product_target_sources(
                reference_claims=reference_claims,
                catalog=catalog,
                model_name=model_name,
                count=count + 1,
                error_message="No selected target sources passed URL validation",
            )
        return reachable
    
    def get_product_details(
        self, 
        product_content: str, 
        model_name:str = 'gemini-2.5-flash',
        count:int = 0,
        error_message:str = ""
        ):
        if count >= MAX_ATTEMPTS:
            raise Exception(f"Product_Details_Extraction_Error: Failed to extract product details after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
        final_prompt = PRODUCT_DETAILS_EXTRACTOR + "\nHere's the content : \n" + product_content
        if error_message != "":
            final_prompt += "\n\nYour previous response failed validation with the error message: " + error_message + "\n"
            final_prompt += "Do not repeat the same mistake and try again."

        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": InfringingProductDetail.model_json_schema(),
            },
        )
        wrapper = InfringingProductDetail.model_validate_json(response.text)
        validated, error_message = wrapper.validate_infringing_product_detail()
        if not validated:
            if count >= MAX_ATTEMPTS:
                raise Exception(f"Product_Details_Extraction_Error: Failed to extract product details after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
            time.sleep(DEFAULT_LLM_DELAY)
            return self.get_product_details(
                product_content=product_content,
                model_name=model_name,
                count=count + 1,
                error_message=error_message
            )
        return wrapper

    def get_patent_sources(
        self, 
        patent_ids: list[str], 
        model_name:str = 'gemini-2.5-flash',
        count:int = 0,
        error_message:str = ""
        ):
        if count >= MAX_ATTEMPTS:
            raise Exception(f"Patent_Sources_Error: Failed to extract patent sources after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
        final_prompt = SOURCE_LISTER.replace('<ids_replacement>', '\n'.join(patent_ids))
        if error_message != "":
            final_prompt += "\n\nYour previous response failed validation with the error message: " + error_message + "\n"
            final_prompt += "Do not repeat the same mistake and try again."

        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": PatentSourceList.model_json_schema(),
            },
        )
        wrapper = PatentSourceList.model_validate_json(response.text)
        validated, error_message = wrapper.validate_patent_source_list()
        if not validated:
            if count >= MAX_ATTEMPTS:
                raise Exception(f"Patent_Sources_Error: Failed to extract patent sources after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
            time.sleep(DEFAULT_LLM_DELAY)
            return self.get_patent_sources(
                patent_ids=patent_ids,
                model_name=model_name,
                count=count + 1,
                error_message=error_message
            )
        return wrapper

    def analyze_product_infringements(
            self, 
            reference_claims:list[str], 
            infringing_claims:list[str],
            model_name:str = 'gemini-2.5-flash',
            count:int = 0,
            error_message:str = ""
        ):
        if count >= MAX_ATTEMPTS:
            raise Exception(f"Product_InfringementAnalysis_Error: Failed to analyze product infringements after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
        final_prompt = PRODUCT_INFRINGEMENT_ANALYZER.replace("<reference_claims_replacement>", "\n".join(reference_claims))
        final_prompt = final_prompt.replace("<infringing_claims_replacement>", "\n".join(infringing_claims))
        if error_message != "":
            final_prompt += "\n\nYour previous response failed validation with the error message: " + error_message + "\n"
            final_prompt += "Do not repeat the same mistake and try again."

        response = self._client.models.generate_content(
            model=model_name,
            contents=final_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ProductSimilarityClaimList.model_json_schema(),
            },
        )
        wrapper = ProductSimilarityClaimList.model_validate_json(response.text)
        validated, error_message = wrapper.validate_product_similarity_claim_list()
        if not validated:
            if count >= MAX_ATTEMPTS:
                raise Exception(f"Product_InfringementAnalysis_Error: Failed to analyze product infringements after {MAX_ATTEMPTS} attempts.\n\t{error_message}")
            time.sleep(DEFAULT_LLM_DELAY)
            return self.analyze_product_infringements(
                reference_claims=reference_claims, 
                infringing_claims=infringing_claims, 
                model_name=model_name,
                count=count + 1,
                error_message=error_message
            )
        return wrapper.items