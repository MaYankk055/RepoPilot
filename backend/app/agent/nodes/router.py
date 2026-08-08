"""
Router node — classifies the question to decide the next step.
"""

import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.agent.state import GraphState
from app.agent.llm import get_chat_llm
from app.config import settings

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are an expert router for a GitHub repository support agent.
Your job is to route user questions to the correct destination. EXACTLY one of these categories:
- "retrieval" — the question is about the repository (setup, usage, configuration, bugs, features, API, etc.) and should be answered by searching the repo's documentation and issues.
- "out_of_scope" — the question is completely unrelated to the repository (e.g., weather, sports, personal questions, general coding questions not about this repo).

Respond with ONLY the category name, nothing else. No explanation, no punctuation."""

ROUTER_USER_PROMPT = """Question: {question}

Category:"""


def route_question(state: GraphState) -> dict:
    """
    Classify the user question to determine the agent's path.

    Args:
        state: Current graph state with the question and chat_history.

    Returns:
        Updated state with route_decision.
    """
    question = state["question"]
    chat_history = state.get("chat_history", [])

    history_context = ""
    if chat_history:
        last_turn = chat_history[-1]
        history_context = f"Previous context: [{last_turn.get('role', 'agent')}]: {last_turn.get('content', '')[:200]}\n"

    llm = get_chat_llm(temperature=0.0)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ROUTER_SYSTEM_PROMPT),
            ("human", "Context:\n{history}\nQuestion: {question}\n\nCategory:"),
        ]
    )

    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({"history": history_context, "question": question}).strip().lower()

    # Normalize the response
    if "retrieval" in result:
        decision = "retrieval"
    elif "out_of_scope" in result or "out" in result:
        decision = "out_of_scope"
    else:
        # Default to retrieval if unclear
        decision = "retrieval"

    logger.info(f"Routed question to: {decision}")

    return {"route_decision": decision}
