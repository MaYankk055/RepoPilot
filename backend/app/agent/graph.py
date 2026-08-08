"""
LangGraph state machine — the agentic RAG workflow.

Graph structure:
    START → router
      ├─ out_of_scope → guardrail → END
      └─ retrieval → retrieve → grader
           ├─ relevant → generate → hallucination_check
           │    ├─ grounded → END
           │    └─ not_grounded → generate (retry, max 2)
           └─ not_relevant → web_search → generate → ...
"""

import logging
from langgraph.graph import StateGraph, END

from app.agent.state import GraphState
from app.agent.nodes.router import route_question
from app.agent.nodes.retriever import retrieve
from app.agent.nodes.grader import grade_documents
from app.agent.nodes.generator import generate
from app.agent.nodes.web_search import web_search
from app.agent.nodes.hallucination_checker import check_hallucination
from app.agent.nodes.guardrail import guardrail
from app.agent.edges import (
    route_after_router,
    route_after_grader,
    route_after_hallucination_check,
)

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """
    Build and compile the full agentic RAG state machine.

    Returns:
        A compiled LangGraph that can be invoked with a GraphState.
    """
    workflow = StateGraph(GraphState)

    # ── Add nodes ────────────────────────────────────────
    workflow.add_node("router", route_question)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("generate", generate)
    workflow.add_node("web_search", web_search)
    workflow.add_node("hallucination_check", check_hallucination)
    workflow.add_node("guardrail", guardrail)

    # ── Set entry point ──────────────────────────────────
    workflow.set_entry_point("router")

    # ── Conditional edges ────────────────────────────────

    # Router → retrieve or guardrail
    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "retrieve": "retrieve",
            "guardrail": "guardrail",
        },
    )

    # Guardrail → END
    workflow.add_edge("guardrail", END)

    # Retrieve → grade
    workflow.add_edge("retrieve", "grade_documents")

    # Grader → generate or web_search
    workflow.add_conditional_edges(
        "grade_documents",
        route_after_grader,
        {
            "generate": "generate",
            "web_search": "web_search",
        },
    )

    # Web search → generate
    workflow.add_edge("web_search", "generate")

    # Generate → hallucination check
    workflow.add_edge("generate", "hallucination_check")

    # Hallucination check → END or retry generate
    workflow.add_conditional_edges(
        "hallucination_check",
        route_after_hallucination_check,
        {
            "generate": "generate",
            "end": END,
        },
    )

    # ── Compile ──────────────────────────────────────────
    app = workflow.compile()
    logger.info("LangGraph agent compiled successfully")

    return app


# Singleton compiled graph
agent_graph = None


def get_agent():
    """Get or create the compiled agent graph."""
    global agent_graph
    if agent_graph is None:
        agent_graph = build_graph()
    return agent_graph
