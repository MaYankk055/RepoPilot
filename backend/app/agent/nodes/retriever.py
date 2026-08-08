"""
Retriever node — fetches relevant codebase documents and architecture context from Chroma vector store.
"""

import logging
from typing import List
from langchain_core.documents import Document
from app.agent.state import GraphState
from app.ingest.embedder import get_vector_store
from app.config import settings

logger = logging.getLogger(__name__)


def extract_repo_name(repo_url: str) -> str:
    """Extract the base repository name from various URL formats."""
    clean_url = repo_url.rstrip("/")
    repo_name = clean_url.split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return repo_name


def retrieve(state: GraphState) -> dict:
    """
    Retrieve documents and architecture context relevant to the user's question.

    Args:
        state: Current graph state containing the question and repo_url.

    Returns:
        Updated state with retrieved documents and citations.
    """
    question = state["question"]
    repo_url = state.get("repo_url", "")
    repo_name = extract_repo_name(repo_url) if repo_url else ""

    logger.info(f"Retrieving codebase context for '{repo_name}': {question[:100]}...")

    vector_store = get_vector_store()
    
    search_filter = {"repo": repo_name} if repo_name else None
    
    # Retrieve top K documents from similarity search
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": settings.retriever_top_k,
            **({"filter": search_filter} if search_filter else {}),
        },
    )

    documents: List[Document] = retriever.invoke(question)

    # For high-level architectural / structural questions, retrieve the architecture summary if not already included
    arch_keywords = [
        "architecture", "structure", "how it works", "overview", "what does",
        "entry point", "modules", "components", "stack", "features", "layout"
    ]
    is_arch_query = any(k in question.lower() for k in arch_keywords)
    
    has_arch_doc = any(
        doc.metadata.get("type") == "architecture" or doc.metadata.get("source") == "_REPO_ARCHITECTURE.md"
        for doc in documents
    )

    if is_arch_query and not has_arch_doc and search_filter:
        try:
            arch_retriever = vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={
                    "k": 2,
                    "filter": {"repo": repo_name, "type": "architecture"},
                },
            )
            arch_docs = arch_retriever.invoke(f"{repo_name} architecture directory structure overview")
            if arch_docs:
                documents = arch_docs[:1] + documents
                logger.info("Added repository architecture overview to retrieved documents")
        except Exception as e:
            logger.debug(f"Could not fetch dedicated architecture doc: {e}")

    # Build structured citations
    citations = []
    seen_sources = set()
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        if source not in seen_sources:
            citations.append(
                {
                    "source": source,
                    "url": doc.metadata.get("url", ""),
                    "type": doc.metadata.get("type", "unknown"),
                    "lines": doc.metadata.get("line_count", 0),
                }
            )
            seen_sources.add(source)

    logger.info(
        f"Retrieved {len(documents)} context chunks across {len(citations)} source files "
        f"(types: {[c['type'] for c in citations]})"
    )

    return {
        "documents": documents,
        "citations": citations,
    }
