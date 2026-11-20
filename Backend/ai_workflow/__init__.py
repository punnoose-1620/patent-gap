"""
Vectorized RAG + Gemini agent workflow.
Toggle with AI_WORKFLOW_MODE=legacy|rag (env).
"""
from ai_workflow.config import get_workflow_mode, is_rag_mode  # noqa: F401
from ai_workflow.orchestration import GeminiWorkflow  # noqa: F401
