"""
Conditional edge functions — routing logic between nodes in the LangGraph state machine.
"""

import logging
from app.agent.state import GraphState
from app.config import settings

logger = logging.getLogger(__name__)


def route_after_router(state: GraphState) -> str:
    """
    After the router classifies the question, decide where to go.

    Returns:
        "retrieve" if the question is about the repo.
        "guardrail" if the question is out of scope.
    """
    decision = state.get("route_decision", "retrieval")

    if decision == "out_of_scope":
        logger.info("Edge: router → guardrail (out of scope)")
        return "guardrail"
    else:
        logger.info("Edge: router → retrieve (retrieval needed)")
        return "retrieve"


def route_after_grader(state: GraphState) -> str:
    """
    After the grader scores documents, decide whether to search the web.

    Returns:
        "web_search" if docs aren't relevant enough.
        "generate" if we have sufficient relevant docs.
    """
    if state.get("web_search_needed", False):
        logger.info("Edge: grader → web_search (insufficient relevant docs)")
        return "web_search"
    else:
        logger.info("Edge: grader → generate (docs are relevant)")
        return "generate"


def route_after_hallucination_check(state: GraphState) -> str:
    """
    After the hallucination check, decide whether to retry or finish.

    Returns:
        "generate" if hallucination detected and retries remain.
        "end" if the answer is grounded or retries are exhausted.
    """
    is_grounded = state.get("is_grounded", True)
    retry_count = state.get("retry_count", 0)

    if not is_grounded and retry_count <= settings.max_retries:
        logger.info(
            f"Edge: hallucination_check → generate "
            f"(retry {retry_count}/{settings.max_retries})"
        )
        return "generate"
    else:
        logger.info("Edge: hallucination_check → end (grounded or retries exhausted)")
        return "end"

