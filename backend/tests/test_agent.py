"""
Unit and integration tests for LangGraph agent routing, edges, and state machine.
"""

import pytest
from langchain_core.documents import Document
from app.agent.state import GraphState
from app.agent.edges import (
    route_after_router,
    route_after_grader,
    route_after_hallucination_check,
)
from app.ingest.chunker import chunk_documents


def test_route_after_router_retrieval():
    """Test routing when decision is retrieval."""
    state: GraphState = {
        "question": "How does the backend authenticate?",
        "repo_url": "https://github.com/example/repo",
        "documents": [],
        "generation": "",
        "web_search_needed": False,
        "confidence_score": 0.0,
        "citations": [],
        "trace_events": [],
        "retry_count": 0,
        "route_decision": "retrieval",
        "session_id": "test-123",
        "is_grounded": True,
    }
    decision = route_after_router(state)
    assert decision == "retrieve"


def test_route_after_router_out_of_scope():
    """Test routing when question is out of scope."""
    state: GraphState = {
        "question": "What is the capital of France?",
        "repo_url": "https://github.com/example/repo",
        "documents": [],
        "generation": "",
        "web_search_needed": False,
        "confidence_score": 0.0,
        "citations": [],
        "trace_events": [],
        "retry_count": 0,
        "route_decision": "out_of_scope",
        "session_id": "test-123",
        "is_grounded": True,
    }
    decision = route_after_router(state)
    assert decision == "guardrail"


def test_route_after_grader_with_web_search():
    """Test routing to web search if grader flags context deficiency."""
    state: GraphState = {
        "question": "Explain dependency vulnerabilities",
        "repo_url": "https://github.com/example/repo",
        "documents": [],
        "generation": "",
        "web_search_needed": True,
        "confidence_score": 0.0,
        "citations": [],
        "trace_events": [],
        "retry_count": 0,
        "route_decision": "retrieval",
        "session_id": "test-123",
        "is_grounded": True,
    }
    decision = route_after_grader(state)
    assert decision == "web_search"


def test_route_after_grader_with_documents():
    """Test routing directly to generate when documents are relevant."""
    state: GraphState = {
        "question": "Explain model architecture",
        "repo_url": "https://github.com/example/repo",
        "documents": [Document(page_content="Model is a CNN", metadata={"source": "model.py"})],
        "generation": "",
        "web_search_needed": False,
        "confidence_score": 0.0,
        "citations": [],
        "trace_events": [],
        "retry_count": 0,
        "route_decision": "retrieval",
        "session_id": "test-123",
        "is_grounded": True,
    }
    decision = route_after_grader(state)
    assert decision == "generate"


def test_route_after_hallucination_check_grounded():
    """Test routing ends when answer is grounded."""
    state: GraphState = {
        "question": "What is the entry point?",
        "repo_url": "https://github.com/example/repo",
        "documents": [Document(page_content="Entry point is main.py", metadata={"source": "main.py"})],
        "generation": "The entry point is main.py",
        "web_search_needed": False,
        "confidence_score": 0.95,
        "citations": [],
        "trace_events": [],
        "retry_count": 0,
        "route_decision": "retrieval",
        "session_id": "test-123",
        "is_grounded": True,
    }
    decision = route_after_hallucination_check(state)
    assert decision == "end"


def test_route_after_hallucination_check_retry():
    """Test routing triggers re-generation when hallucination is detected."""
    state: GraphState = {
        "question": "What is the entry point?",
        "repo_url": "https://github.com/example/repo",
        "documents": [Document(page_content="Entry point is main.py", metadata={"source": "main.py"})],
        "generation": "The entry point is unknown.py",
        "web_search_needed": False,
        "confidence_score": 0.3,
        "citations": [],
        "trace_events": [],
        "retry_count": 1,
        "route_decision": "retrieval",
        "session_id": "test-123",
        "is_grounded": False,
    }
    decision = route_after_hallucination_check(state)
    assert decision == "generate"


def test_chunking_preserves_metadata():
    """Test that chunker splits documents and retains code-aware metadata."""
    sample_doc = Document(
        page_content="def authenticate(user):\n    pass\n" * 100,
        metadata={"source": "auth/service.py", "type": "code", "repo": "test-repo"},
    )
    chunks = chunk_documents([sample_doc])
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.metadata["source"] == "auth/service.py"
        assert chunk.metadata["type"] == "code"
        assert chunk.metadata["repo"] == "test-repo"
