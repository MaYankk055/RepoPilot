"""
Hallucination checker node — verifies the answer is grounded in retrieved context.
"""

import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.agent.state import GraphState
from app.agent.llm import get_chat_llm
from app.config import settings

logger = logging.getLogger(__name__)

HALLUCINATION_SYSTEM_PROMPT = """You are a hallucination detector for a RAG system.
Given a set of source documents and a generated answer, determine if the answer
is grounded in (supported by) the source documents.

An answer is grounded if:
- Its key claims can be traced back to information in the documents
- It doesn't make up facts not present in the documents
- It doesn't contradict the documents

Respond with ONLY "grounded" or "not_grounded". Nothing else."""

HALLUCINATION_USER_PROMPT = """Source documents:
{documents}

Generated answer:
{generation}

Is the answer grounded in the source documents? (grounded/not_grounded):"""


def check_hallucination(state: GraphState) -> dict:
    """
    Check if the generated answer is grounded in the retrieved documents.

    If not grounded and retries remain, increment retry_count to trigger
    re-generation.

    Args:
        state: Current graph state with documents, generation, and retry_count.

    Returns:
        Updated state with retry_count incremented if hallucination detected and is_grounded flag.
    """
    documents = state["documents"]
    generation = state["generation"]
    retry_count = state.get("retry_count", 0)

    # Format documents for the check
    docs_text = "\n\n".join(
        [
            f"[{doc.metadata.get('source', 'unknown')}]: {doc.page_content[:1500]}"
            for doc in documents
        ]
    )

    llm = get_chat_llm(temperature=0.0)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", HALLUCINATION_SYSTEM_PROMPT),
            ("human", HALLUCINATION_USER_PROMPT),
        ]
    )

    chain = prompt | llm | StrOutputParser()

    result = chain.invoke(
        {"documents": docs_text, "generation": generation}
    ).strip().lower()

    is_grounded = "grounded" in result and "not_grounded" not in result

    if is_grounded:
        logger.info("Hallucination check: PASSED (answer is grounded)")
        return {"retry_count": retry_count, "is_grounded": True}
    else:
        new_count = retry_count + 1
        logger.warning(
            f"Hallucination check: FAILED (retry {new_count}/{settings.max_retries})"
        )
        return {"retry_count": new_count, "is_grounded": False}

