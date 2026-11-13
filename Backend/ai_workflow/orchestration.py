"""
Gemini-backed workflow facade. Same method surface as llm_brain.gemini.Gemini.
When RAG mode is on, indexing hooks run after claim/metadata extraction.
"""
from __future__ import annotations

from typing import Any, List, Optional

from ai_workflow.config import is_rag_mode


class GeminiWorkflow:
    """Thin wrapper around llm_brain.gemini.Gemini with optional RAG side-effects."""

    def __init__(self):
        from llm_brain.gemini import Gemini

        self._gemini = Gemini()

    def extract_patent_metadata(self, *args, **kwargs):
        return self._gemini.extract_patent_metadata(*args, **kwargs)

    def extract_claims(self, *args, **kwargs):
        return self._gemini.extract_claims(*args, **kwargs)

    def extract_documented_claims(self, *args, **kwargs):
        return self._gemini.extract_documented_claims(*args, **kwargs)

    def analyze_infringements(self, *args, **kwargs):
        return self._gemini.analyze_infringements(*args, **kwargs)

    def perform_google_search(self, *args, **kwargs):
        return self._gemini.perform_google_search(*args, **kwargs)

    def perform_google_search_from_claims(self, *args, **kwargs):
        return self._gemini.perform_google_search_from_claims(*args, **kwargs)

    def get_product_details(self, *args, **kwargs):
        return self._gemini.get_product_details(*args, **kwargs)

    def get_patent_sources(self, *args, **kwargs):
        return self._gemini.get_patent_sources(*args, **kwargs)

    def analyze_product_infringements(self, *args, **kwargs):
        return self._gemini.analyze_product_infringements(*args, **kwargs)

    def generate_product_retail_search_params(self, *args, **kwargs):
        fn = getattr(self._gemini, "generate_product_retail_search_params", None)
        if callable(fn):
            return fn(*args, **kwargs)
        raise AttributeError("generate_product_retail_search_params not available on Gemini")

    def index_claims_for_case(
        self,
        user_id: str,
        case_id: str,
        claims: List[str],
        source: str = "",
        chunk_type: str = "claim",
    ) -> int:
        if not is_rag_mode():
            return 0
        try:
            from ai_workflow.indexing import index_claim_texts

            return index_claim_texts(
                user_id=user_id,
                case_id=case_id,
                claims=claims or [],
                source=source,
                chunk_type=chunk_type,
                replace_case_chunks=True,
            )
        except Exception as e:
            print(f"LOG: index_claims_for_case failed ({type(e).__name__}: {e})")
            return 0


def get_ai_client():
    """
    Factory for analysis/MCP LLM access.

    Returns GeminiWorkflow when AI_WORKFLOW_MODE=rag (Gemini + optional
    index_claims_for_case), otherwise raw llm_brain.gemini.Gemini.
    """
    if is_rag_mode():
        return GeminiWorkflow()
    from llm_brain.gemini import Gemini

    return Gemini()
