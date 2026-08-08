"""
Grader node — evaluates whether retrieved codebase documents and code snippets are relevant to the user's question.
Code-aware: recognizes source code, function/class signatures, configs, and architecture maps as valid context.
"""

import logging
import json
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from app.agent.state import GraphState
from app.agent.llm import get_chat_llm
from app.config import settings

logger = logging.getLogger(__name__)

BATCH_GRADER_SYSTEM_PROMPT = """You are an expert codebase relevance grader for an AI assistant.
Given a user question about a repository and a numbered list of retrieved code/documentation snippets,
evaluate which documents are relevant to answering or providing context for the question.

GUIDELINES FOR RELEVANCE:
- Architecture maps, directory trees, and project summaries ARE RELEVANT for general or architectural questions.
- Source code defining relevant functions, classes, interfaces, routes, variables, or logic ARE RELEVANT.
- Configuration files (package.json, pyproject.toml, Dockerfile, etc.) defining dependencies or setup ARE RELEVANT.
- Documentation explaining concepts, installation, or APIs ARE RELEVANT.
- Only reject snippets that are completely unrelated to the question's topic.

OUTPUT FORMAT:
Respond with ONLY a JSON array of the 1-based indices of relevant documents, e.g., [1, 2, 4].
If none are relevant, output []. No other text or markdown."""

BATCH_GRADER_USER_PROMPT = """Question: {question}

Retrieved Documents:
{documents}

JSON array of relevant document indices:"""


def grade_documents(state: GraphState) -> dict:
    """
    Evaluate retrieved documents for relevance in a fast batch evaluation.

    Args:
        state: Current graph state with question and documents.

    Returns:
        Updated state with filtered relevant documents and web_search_needed flag.
    """
    question = state["question"]
    documents: List[Document] = state.get("documents", [])

    if not documents:
        return {
            "documents": [],
            "web_search_needed": True,
            "citations": [],
        }

    # Format documents for batch grading
    doc_previews = []
    for i, doc in enumerate(documents, 1):
        source = doc.metadata.get("source", "unknown")
        doc_type = doc.metadata.get("type", "unknown")
        # Take snippet preview
        snippet = doc.page_content[:400].replace("\n", " ")
        doc_previews.append(f"[{i}] File: {source} ({doc_type}) -> {snippet}...")

    formatted_docs = "\n".join(doc_previews)

    llm = get_chat_llm(temperature=0.0)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", BATCH_GRADER_SYSTEM_PROMPT),
            ("human", BATCH_GRADER_USER_PROMPT),
        ]
    )

    chain = prompt | llm | StrOutputParser()

    relevant_docs: List[Document] = []

    try:
        raw_result = chain.invoke({"question": question, "documents": formatted_docs}).strip()
        # Parse JSON indices
        if "[" in raw_result and "]" in raw_result:
            json_str = raw_result[raw_result.find("[") : raw_result.rfind("]") + 1]
            indices = json.loads(json_str)
            for idx in indices:
                if isinstance(idx, int) and 1 <= idx <= len(documents):
                    relevant_docs.append(documents[idx - 1])
        else:
            # Fallback to keeping all if parsing is ambiguous
            relevant_docs = documents
    except Exception as e:
        logger.warning(f"Batch grading parsing failed ({e}), keeping all retrieved documents")
        relevant_docs = documents

    # If grading yielded zero docs, keep top 2 docs rather than losing all context
    if not relevant_docs and documents:
        relevant_docs = documents[:2]

    # Web search needed if fewer than 2 relevant documents
    web_search_needed = len(relevant_docs) < 1

    logger.info(
        f"Graded {len(documents)} codebase docs: {len(relevant_docs)} relevant kept, "
        f"web_search_needed={web_search_needed}"
    )

    # Reconstruct citations for relevant documents
    citations = []
    seen = set()
    for doc in relevant_docs:
        source = doc.metadata.get("source", "unknown")
        if source not in seen:
            citations.append(
                {
                    "source": source,
                    "url": doc.metadata.get("url", ""),
                    "type": doc.metadata.get("type", "unknown"),
                    "lines": doc.metadata.get("line_count", 0),
                }
            )
            seen.add(source)

    return {
        "documents": relevant_docs,
        "web_search_needed": web_search_needed,
        "citations": citations,
    }
