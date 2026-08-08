"""
Agent state definition — the TypedDict that flows through the LangGraph state machine.
"""

from typing import TypedDict, Annotated
from langchain_core.documents import Document


def add_to_list(existing: list, new: list) -> list:
    """Reducer that appends new items to existing list."""
    return existing + new


class GraphState(TypedDict):
    """
    State object that flows through every node in the LangGraph agent.

    Attributes:
        question: The user's original question.
        documents: Retrieved/filtered documents from the vector store or web search.
        generation: The LLM-generated answer.
        web_search_needed: Whether the grader determined web search is needed.
        confidence_score: Self-assessed confidence (0.0 to 1.0) of the generated answer.
        citations: Source references for the answer.
        trace_events: List of decision-trace events emitted during this run.
        retry_count: Number of hallucination-check retries so far.
        route_decision: Router's classification of the question.
    """

    question: str
    repo_url: str
    documents: list[Document]
    generation: str
    web_search_needed: bool
    confidence_score: float
    citations: list[dict]
    trace_events: list[dict]
    retry_count: int
    route_decision: str
    session_id: str
    is_grounded: bool
    chat_history: list[dict]
