"""
Web search node — fallback when retrieved documents aren't relevant enough.
"""

import logging
from langchain_core.documents import Document
from tavily import TavilyClient

from app.agent.state import GraphState
from app.config import settings

logger = logging.getLogger(__name__)


def web_search(state: GraphState) -> dict:
    """
    Search the web using Tavily when repo docs don't cover the question.

    Args:
        state: Current graph state with the question.

    Returns:
        Updated state with web search results appended to documents.
    """
    question = state["question"]
    documents = state.get("documents", [])

    logger.info(f"Web search fallback for: {question[:100]}...")

    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        search_results = client.search(
            query=f"{question} github documentation",
            max_results=3,
            search_depth="advanced",
        )

        web_docs = []
        web_citations = []
        for result in search_results.get("results", []):
            doc = Document(
                page_content=result.get("content", ""),
                metadata={
                    "source": result.get("title", "Web Search"),
                    "url": result.get("url", ""),
                    "type": "web_search",
                    "type": "web_search",
                },
            )
            web_docs.append(doc)
            web_citations.append(
                {
                    "source": result.get("title", "Web Search"),
                    "url": result.get("url", ""),
                    "type": "web_search",
                }
            )

        logger.info(f"Web search returned {len(web_docs)} results")

        # Combine existing relevant docs with web results
        combined_docs = documents + web_docs
        existing_citations = state.get("citations", [])

        return {
            "documents": combined_docs,
            "citations": existing_citations + web_citations,
            "web_search_needed": False,
        }

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        # If web search fails, continue with whatever docs we have
        return {
            "documents": documents,
            "web_search_needed": False,
        }
