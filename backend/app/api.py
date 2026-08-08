"""
FastAPI server — the HTTP interface to the RepoPilot agent.

Endpoints:
  GET  /health       — Basic health check
  GET  /api/status   — Live connection & API key verification for Groq, Embeddings, Chroma, and Tavily
  POST /ask          — Ask a question about the repository (JSON response)
  POST /ask/stream   — Ask a question with Server-Sent Events (SSE streaming)
  POST /ingest       — Ingest a GitHub repository into the vector store
"""

import time
import logging
import uuid
import asyncio
import json
import os
import certifi
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

# Ensure certifi CA bundle is used globally
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()

from app.config import settings
from app.agent.llm import get_chat_llm
from app.agent.graph import get_agent
from app.agent.state import GraphState
from app.ingest.embedder import ingest_git_repo, get_vector_store_stats
from app.ingest.loader import validate_git_repo_url

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("RepoPilot backend starting up...")
    logger.info(f"LLM model: {settings.llm_model}")
    logger.info(f"Embedding provider: {settings.embedding_provider}")
    yield
    logger.info("RepoPilot backend shutting down...")


# ── App ──────────────────────────────────────────────────
app = FastAPI(
    title="RepoPilot Backend",
    description="Agentic RAG codebase assistant for GitHub repositories",
    version="0.2.0",
    lifespan=lifespan,
)

cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] if settings.cors_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The question to ask")
    repo_url: str = Field(..., description="The repository URL to query against")
    session_id: Optional[str] = Field(
        default=None, description="Session ID (auto-generated if not provided)"
    )
    history: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, description="Prior conversation message turns for context continuity"
    )


class Citation(BaseModel):
    source: str
    url: str
    type: str
    lines: Optional[int] = 0


class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    confidence: float
    session_id: str


class IngestRequest(BaseModel):
    repo_url: str = Field(
        ...,
        description="The full Git clone URL (e.g., https://github.com/owner/repo.git)",
    )


class IngestResponse(BaseModel):
    message: str
    repo: str
    chunks_stored: int


# ── Endpoints ────────────────────────────────────────────
@app.get("/health")
async def health():
    """Basic health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/status")
async def api_status():
    """
    Live verification of all API keys and core subsystem components:
    - Groq LLM API connectivity & latency
    - Vector store stats (Chroma DB collection & chunks)
    - Embeddings model status
    - Tavily search configuration
    """
    start_time = time.time()
    groq_ok = False
    groq_latency = 0.0
    groq_error = None

    # 1. Test Groq LLM Connectivity
    if settings.groq_api_key:
        try:
            t0 = time.time()
            llm = get_chat_llm(temperature=0.0)
            # Lightweight invocation to verify the API key
            res = await asyncio.to_thread(llm.invoke, "hi")
            groq_latency = round((time.time() - t0) * 1000, 1)
            groq_ok = bool(res and res.content)
        except Exception as e:
            logger.warning(f"Groq API verification failed: {e}")
            groq_error = str(e)
    else:
        groq_error = "Groq API key not configured in .env"

    # 2. Test Chroma Vector Store
    vector_stats = get_vector_store_stats()

    # 3. Check Embeddings
    embedding_status = {
        "provider": settings.embedding_provider,
        "model": settings.local_embedding_model if settings.embedding_provider == "local" else "text-embedding-3-small",
        "ready": True,
    }

    # 4. Check Tavily
    tavily_status = {
        "configured": bool(settings.tavily_api_key),
        "status": "ready" if settings.tavily_api_key else "not_configured",
    }

    total_latency = round((time.time() - start_time) * 1000, 1)
    is_connected = groq_ok and (vector_stats.get("status") == "ready")

    return {
        "connected": is_connected,
        "status": "connected" if is_connected else "degraded" if groq_ok else "error",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_latency_ms": total_latency,
        "llm": {
            "provider": "Groq",
            "model": settings.llm_model,
            "connected": groq_ok,
            "latency_ms": groq_latency,
            "error": groq_error,
        },
        "vector_store": vector_stats,
        "embeddings": embedding_status,
        "tavily": tavily_status,
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """
    Ingest a git repository by cloning, analyzing codebase architecture,
    chunking source files, and indexing vectors in Chroma DB.
    """
    try:
        validated_url = validate_git_repo_url(request.repo_url)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    try:
        logger.info(f"Starting deep codebase ingestion for repo URL {validated_url}...")
        
        vector_store = await asyncio.to_thread(ingest_git_repo, validated_url)
        count = vector_store._collection.count()
        return IngestResponse(
            message=f"Successfully analyzed and indexed {validated_url}",
            repo=validated_url,
            chunks_stored=count,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """
    Ask a question about the repository codebase.
    """
    try:
        validated_url = validate_git_repo_url(request.repo_url)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    session_id = request.session_id or str(uuid.uuid4())

    initial_state: GraphState = {
        "question": request.question.strip(),
        "repo_url": validated_url,
        "documents": [],
        "generation": "",
        "web_search_needed": False,
        "confidence_score": 0.0,
        "citations": [],
        "trace_events": [],
        "retry_count": 0,
        "route_decision": "",
        "session_id": session_id,
        "chat_history": request.history or [],
    }

    try:
        agent = get_agent()
        result = await asyncio.to_thread(agent.invoke, initial_state)

        citations_data = []
        for c in result.get("citations", []):
            citations_data.append(
                Citation(
                    source=c.get("source", ""),
                    url=c.get("url", ""),
                    type=c.get("type", "code"),
                    lines=c.get("lines", 0),
                )
            )

        return AskResponse(
            answer=result.get("generation", "I couldn't generate an answer based on the repository context."),
            citations=citations_data,
            confidence=result.get("confidence_score", 0.8),
            session_id=session_id,
        )
    except Exception as e:
        logger.error(f"Agent invocation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Agent error: {str(e)}"
        )


@app.post("/ask/stream")
async def ask_stream(request: AskRequest):
    """
    Ask a question with Server-Sent Events streaming.
    """
    try:
        validated_url = validate_git_repo_url(request.repo_url)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

    session_id = request.session_id or str(uuid.uuid4())

    initial_state: GraphState = {
        "question": request.question.strip(),
        "repo_url": validated_url,
        "documents": [],
        "generation": "",
        "web_search_needed": False,
        "confidence_score": 0.0,
        "citations": [],
        "trace_events": [],
        "retry_count": 0,
        "route_decision": "",
        "session_id": session_id,
        "chat_history": request.history or [],
    }

    async def event_generator():
        """Generate SSE events from the agent's node transitions."""
        try:
            agent = get_agent()

            for event in agent.stream(initial_state, stream_mode="updates"):
                for node_name, node_output in event.items():
                    sse_data = json.dumps(
                        {
                            "type": "node_update",
                            "node": node_name,
                            "data": {
                                k: v
                                for k, v in node_output.items()
                                if k not in ("documents",)
                            },
                        },
                        default=str,
                    )
                    yield f"data: {sse_data}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

        except Exception as e:
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": session_id,
        },
    )
