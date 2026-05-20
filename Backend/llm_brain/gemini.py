import copy
import json
from datetime import datetime as dt
from google import genai
from google.genai import types
from env_controller import getEnvKey

from llm_brain.static_prompts import *
from models.live_search_results import *
from models.infringement_report import InfringementLitigationReport

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
            "applicant": "",
            "current_assignee": [],
            "other_ids": [],
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
        search_limitations: dict,
        model_name:str = 'gemini-2.5-flash'
        ):
        
        companies = search_limitations.get('companies', [])
        websites = search_limitations.get('urls', [])
        final_prompt = SEARCH_STRING_GENERATOR.replace("<keywords_replacement>", "\n".join(keywords))
        final_prompt = final_prompt.replace("<owners_replacement>", "\n".join(owners))
        final_prompt = final_prompt.replace("<search_limitations_companies>", "\n".join(companies))
        final_prompt = final_prompt.replace("<search_limitations_websites>", "\n".join(websites))
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

    def _trim_report_text(self, value, limit: int = 1200):
        """Keep LLM report inputs small enough to avoid truncated JSON responses."""
        value = str(value or "").strip()
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + "..."

    def _as_plain_dict(self, value):
        if hasattr(value, 'model_dump'):
            return value.model_dump()
        if hasattr(value, 'dict'):
            return value.dict()
        if isinstance(value, dict):
            return value
        return {}

    def _top_scored_items(self, items, score_key: str, limit: int):
        items = [item for item in (items or []) if isinstance(item, dict)]
        return sorted(
            items,
            key=lambda item: item.get(score_key, 0) or 0,
            reverse=True
        )[:limit]

    def _normalize_infringements_for_report(self, infringements: list, max_entries: int = 10, max_comparisons_per_entry: int = 5):
        """
        Convert the stored infringement-analysis shape into a compact report input.

        Stored case records can be very large: each outer infringement candidate may contain
        hundreds of nested `infringements` claim-comparison rows. The report only needs the
        strongest evidence, so this method keeps candidate metadata plus the top scored
        comparisons and drops bulky fields such as full claim lists, attorneys, other_ids, etc.
        """
        normalized = []
        for inf in (infringements or [])[:max_entries]:
            inf = self._as_plain_dict(inf)
            if not inf:
                continue

            nested_comparisons = self._top_scored_items(
                inf.get('infringements', []),
                'calculated_similarity_score',
                max_comparisons_per_entry
            )

            # Backward compatibility with older records that used `similar_claims`.
            similar_claims = self._top_scored_items(
                inf.get('similar_claims', []),
                'similarity_score',
                max_comparisons_per_entry
            )

            entry = {
                'source': self._trim_report_text(inf.get('source', ''), 120),
                'entry_id': self._trim_report_text(inf.get('entry_id', inf.get('case_id', inf.get('_id', ''))), 220),
                'entry_title': self._trim_report_text(inf.get('entry_title', inf.get('title', '')), 300),
                'entry_url': self._trim_report_text(inf.get('entry_url', inf.get('url', '')), 500),
                'description': self._trim_report_text(inf.get('description', ''), 700),
                'top_claim_comparisons': [
                    {
                        'reference_claim': self._trim_report_text(item.get('ref_claim', ''), 900),
                        'infringing_claim': self._trim_report_text(item.get('claim', ''), 900),
                        'similarity_score': item.get('calculated_similarity_score', 0),
                        'score_method': self._trim_report_text(item.get('score_method', ''), 80),
                        'last_scored_at': self._trim_report_text(item.get('last_scored_at', ''), 80),
                    }
                    for item in nested_comparisons
                ],
                'similar_claims': [
                    {
                        'claim': self._trim_report_text(item.get('claim', ''), 900),
                        'similarity_score': item.get('similarity_score', 0),
                        'source': self._trim_report_text(item.get('source', inf.get('source', '')), 120),
                        'url_to_claim': self._trim_report_text(item.get('url_to_claim', ''), 500),
                    }
                    for item in similar_claims
                ]
            }
            normalized.append(entry)
        return normalized

    def _build_complete_claim_evidence_for_report(self, infringements: list):
        """
        Build the complete, deterministic evidence payload for the final report object.

        This captures every stored claim-level comparison under each candidate patent. Gemini
        writes narrative sections; this method preserves the legal review evidence exactly
        from the stored infringement analysis.
        """
        report_infringements = []
        claim_analysis = []
        source_traceability = []

        for inf in (infringements or []):
            inf = self._as_plain_dict(inf)
            if not inf:
                continue

            source = str(inf.get('source', '') or 'unknown')
            entry_id = str(inf.get('entry_id', inf.get('case_id', inf.get('_id', 'unknown'))) or 'unknown')
            entry_title = str(inf.get('entry_title', inf.get('title', 'Untitled infringement candidate')) or 'Untitled infringement candidate')
            entry_url = str(inf.get('entry_url', inf.get('url', '')) or '')

            nested_matches = [item for item in (inf.get('infringements', []) or []) if isinstance(item, dict)]
            if not nested_matches:
                nested_matches = [item for item in (inf.get('similar_claims', []) or []) if isinstance(item, dict)]

            nested_matches = sorted(
                nested_matches,
                key=lambda item: item.get('calculated_similarity_score', item.get('similarity_score', 0)) or 0,
                reverse=True
            )

            similar_claims = []
            for item in nested_matches:
                reference_claim = str(item.get('ref_claim', item.get('reference_claim', '')) or '')
                candidate_claim = str(item.get('claim', item.get('infringing_claim', '')) or '')
                if candidate_claim.strip() == '':
                    continue
                score = item.get('calculated_similarity_score', item.get('similarity_score', 0))
                if not isinstance(score, (int, float)):
                    try:
                        score = float(score)
                    except Exception:
                        score = 0

                similar_claims.append({
                    'reference_claim': reference_claim,
                    'claim': candidate_claim,
                    'similarity_score': float(score),
                    'source': source,
                    'url_to_claim': str(item.get('url_to_claim', entry_url) or entry_url),
                })
                claim_analysis.append({
                    'reference_claim': reference_claim,
                    'infringing_claim': candidate_claim,
                    'source': source,
                    'entry_id': entry_id,
                    'entry_title': entry_title,
                    'entry_url': entry_url,
                    'similarity_score': float(score),
                    'commentary': str(item.get('commentary', item.get('justification', '')) or ''),
                })

            report_infringements.append({
                'source': source,
                'entry_id': entry_id,
                'entry_title': entry_title,
                'entry_url': entry_url,
                'similar_claims': similar_claims,
            })

            if entry_url:
                source_traceability.append(f'{entry_id} - {entry_title} - {entry_url}')
            else:
                source_traceability.append(f'{entry_id} - {entry_title} - {source}')

        return {
            'infringements': report_infringements,
            'claim_analysis': claim_analysis,
            'source_traceability': source_traceability,
        }

    def generate_infringement_report(self,
        ref_case: dict,
        infringements: list,
        model_name: str = 'gemini-2.5-flash'
        ):
        
        """
        Generate a structured infringement litigation report.
        Returns an InfringementLitigationReport object, or None on failure.
        """

        # Normalize reference case data for report input.
        if ref_case is None:
            ref_case = {}
        reference_case_normalized = {
            'case_id': str(ref_case.get('_id', ref_case.get('case_id', '')) or ''),
            'title': self._trim_report_text(ref_case.get('title', ''), 300),
            'description': self._trim_report_text(ref_case.get('description', ''), 1000),
            'claims': [
                self._trim_report_text(claim, 1000)
                for claim in (ref_case.get('claims', []) or [])[:10]
                ],
            'document_urls': (ref_case.get('document_urls', []) or [])[:5]
        }
        reference_case_complete = {
            'case_id': str(ref_case.get('_id', ref_case.get('case_id', '')) or ''),
            'title': str(ref_case.get('title', '') or ''),
            'description': str(ref_case.get('description', '') or ''),
            'claims': ref_case.get('claims', []) or [],
            'document_urls': ref_case.get('document_urls', []) or []
        }

        # Trimmed data is used only for Gemini narrative generation.
        normalized_infringements = self._normalize_infringements_for_report(infringements)
        # Complete evidence is merged into the final report after Gemini returns.
        complete_evidence = self._build_complete_claim_evidence_for_report(infringements)

        # Generate the report using Gemini by providing the appropriate prompt and normalized data.
        description = InfringementLitigationReport.getDescription()
        prompt = INFRINGEMENT_REPORT_PROMPT.replace('<Description>', description)
        prompt = prompt.replace('<referenceCase>', json.dumps(reference_case_normalized, indent=2, default=str))
        prompt = prompt.replace('<infringements>', json.dumps(normalized_infringements, indent=2, default=str))

        schema = _strip_unsupported_schema_keys(
            _schema_without_defs(InfringementLitigationReport.model_json_schema())
        )
        try:
            response = self._client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_json_schema': schema,
                }
            )
            response_text = response.text if response else '{}'
            try:
                report_data = json.loads(response_text)
            except Exception as e:
                print('\nERROR: Gemini returned invalid JSON for infringement report')
                print(f'JSON parse error: {str(e)}')
                print(f'Response length: {len(response_text)}')
                print(f'Response tail: {response_text[-1000:]}')
                raise
            # Fill defaults for fields the LLM may omit
            if not report_data.get('report_title', '').strip():
                report_data['report_title'] = f"Infringement Report for {reference_case_normalized.get('title', 'Reference Case')}"
            if not report_data.get('generated_at', '').strip():
                report_data['generated_at'] = dt.now().isoformat()
            # Preserve complete deterministic evidence from the stored analysis. Gemini is
            # used for narrative sections, not as the source of truth for claim-pair rows.
            report_data['reference_case'] = reference_case_complete
            report_data['infringements'] = complete_evidence['infringements']
            report_data['claim_analysis'] = complete_evidence['claim_analysis']
            existing_sources = report_data.get('source_traceability', [])
            if not isinstance(existing_sources, list):
                existing_sources = []
            report_data['source_traceability'] = list(dict.fromkeys(existing_sources + complete_evidence['source_traceability']))

            risk_assessment = report_data.get('risk_assessment')
            if isinstance(risk_assessment, dict):
                risk_level = str(risk_assessment.get('level', '') or '').strip().lower()
                # Gemini sometimes returns display-case values like "Medium". The
                # report validator expects the canonical enum values below.
                if risk_level in ['low', 'medium', 'high']:
                    risk_assessment['level'] = risk_level

            return InfringementLitigationReport.model_validate(report_data)
        except Exception as e:
            print(f'\nERROR: Error generating infringement report: {str(e)}')
            return None
