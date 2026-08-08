"""
Generator node — produces deep, contextual, and comprehensive codebase answers using the LLM.
Synthesizes architecture, code files, functions, configurations, and documentation.
"""

import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.agent.state import GraphState
from app.agent.llm import get_chat_llm
from app.config import settings

logger = logging.getLogger(__name__)

GENERATE_SYSTEM_PROMPT = """You are RepoPilot, an elite GitHub Codebase Architect and Technical Support Agent.
Your objective is to provide comprehensive, in-depth, and highly contextual answers about the target repository by analyzing its full codebase, architecture, source files, configurations, and documentation.

CORE PRINCIPLES:
1. **Full-Codebase Context**: Combine insights from source code, architecture summaries, module directories, dependency configs, and docs to give rich, multi-layered explanations.
2. **Deep Technical Detail**: Explain how classes, functions, modules, and services interact. Walk through the data flow or execution sequence when asked about features.
3. **Precise File Citations**: Always reference the exact files and paths where logic lives (e.g. `[Source: app/agent/graph.py]`).
4. **Code & Configuration Snippets**: Provide clear markdown code snippets with syntax highlighting to illustrate how components are implemented or configured.
5. **Architectural Clarity**: If the user asks about the project structure, design patterns, or setup, explain the roles of key directories and entry points.
6. **Honesty on Gaps**: If a specific file or implementation detail is not present in the provided context, state what is known from the architecture and suggest where it resides.

FORMATTING REQUIREMENTS:
- Structure answers logically with markdown headings (`###`), bullet points, and code blocks.
- End your response with a confidence assessment on the final line in this exact format:
CONFIDENCE: <score>
where <score> is a float between 0.0 and 1.0 (e.g., 0.95 for complete codebase clarity, 0.75 for solid partial context, < 0.5 if context was minimal)."""

GENERATE_USER_PROMPT = """{history}Context Documents & Codebase Extracts:
{context}

User Question: {question}

Provide your detailed, contextual answer with source citations and confidence score:"""


def generate(state: GraphState) -> dict:
    """
    Generate an in-depth codebase answer using the LLM with retrieved code & doc context.

    Args:
        state: Current graph state with question and documents.

    Returns:
        Updated state with generation and confidence_score.
    """
    question = state["question"]
    documents = state.get("documents", [])
    chat_history = state.get("chat_history", [])

    # Format prior conversation history
    history_str = ""
    if chat_history:
        history_lines = ["=== Prior Conversation Turns ==="]
        for msg in chat_history[-6:]:
            role = "User" if msg.get("role") == "user" else "RepoPilot"
            content = msg.get("content", "").strip()
            if len(content) > 600:
                content = content[:600] + "..."
            history_lines.append(f"{role}: {content}")
        history_str = "\n".join(history_lines) + "\n\n"

    # Format documents into context string
    context_parts = []
    for i, doc in enumerate(documents, 1):
        source = doc.metadata.get("source", "unknown")
        doc_type = doc.metadata.get("type", "unknown")
        repo = doc.metadata.get("repo", "")
        context_parts.append(
            f"=== Document {i} [File: {source}] [Type: {doc_type}] [Repo: {repo}] ===\n"
            f"{doc.page_content}\n"
        )
    context = "\n".join(context_parts) if context_parts else "No specific documents found."

    llm = get_chat_llm(temperature=settings.llm_temperature)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", GENERATE_SYSTEM_PROMPT),
            ("human", GENERATE_USER_PROMPT),
        ]
    )

    chain = prompt | llm | StrOutputParser()

    logger.info(f"Generating detailed codebase answer for: {question[:100]}...")
    result = chain.invoke({"history": history_str, "context": context, "question": question})

    # Parse confidence score from the response
    generation = result
    confidence_score = 0.85  # default baseline

    if "CONFIDENCE:" in result:
        parts = result.rsplit("CONFIDENCE:", 1)
        generation = parts[0].strip()
        try:
            score_str = parts[1].strip().split()[0]
            confidence_score = float(score_str)
            confidence_score = max(0.0, min(1.0, confidence_score))
        except (ValueError, IndexError):
            logger.warning("Could not parse confidence score from response, defaulting to 0.85")

    logger.info(f"Generated answer (length: {len(generation)} chars, confidence: {confidence_score})")

    return {
        "generation": generation,
        "confidence_score": confidence_score,
    }
