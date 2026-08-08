"""
Guardrail node — refuses out-of-scope questions.
"""

import logging
from app.agent.state import GraphState

logger = logging.getLogger(__name__)


def guardrail(state: GraphState) -> dict:
    """
    Handle out-of-scope questions with a polite refusal.

    Args:
        state: Current graph state (routed here by the router).

    Returns:
        Updated state with a refusal message as the generation.
    """
    question = state["question"]
    repo_url = state.get("repo_url", "")
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "") if repo_url else "target"

    logger.info(f"Guardrail triggered for out-of-scope question: {question[:100]}...")

    refusal = (
        f"I'm RepoPilot, a technical codebase assistant specifically for the **{repo_name}** repository. "
        "Your question appears to be outside the scope of this repository.\n\n"
        "I can help you analyze:\n"
        "- 🏗️ Codebase architecture, entry points & directory structure\n"
        "- 💻 Functions, classes, services, and execution data flows\n"
        "- ⚙️ Configuration files, environment variables & build dependencies\n"
        "- 🐛 Bug diagnosis, stack traces, and implementation guidance\n"
        "- 📚 API routes, models, and technical documentation\n\n"
        f"Please ask a question related to the **{repo_name}** codebase."
    )

    return {
        "generation": refusal,
        "confidence_score": 1.0,  # We're confident this is out of scope
        "citations": [],
        "escalated": False,
    }
