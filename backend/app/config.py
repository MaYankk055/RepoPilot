import os
import certifi
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

# Ensure valid CA bundle is available globally across all HTTP/SSL operations
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()


class Settings(BaseSettings):

    """Central configuration for the RepoPilot agent core."""

    # ── LLM ──────────────────────────────────────────────
    groq_api_key: str = Field(default="", description="Groq API key for LLM calls")
    llm_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model name for generation and grading",
    )
    llm_temperature: float = Field(default=0.0, description="LLM temperature")

    # ── Embeddings ───────────────────────────────────────
    embedding_provider: str = Field(
        default="local",
        description="'local' for sentence-transformers, 'openai' for text-embedding-3-small",
    )
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    local_embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformers model name for local embeddings",
    )

    # ── Vector Store ─────────────────────────────────────
    chroma_persist_dir: str = Field(
        default="./chroma_db", description="Chroma persistence directory"
    )
    chroma_collection_name: str = Field(
        default="repo_docs", description="Chroma collection name"
    )

    # ── Tavily (Web Search) ──────────────────────────────
    tavily_api_key: str = Field(default="", description="Tavily API key for web search")

    # ── Redis ────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")

    # ── MongoDB ──────────────────────────────────────────
    mongodb_url: str = Field(
        default="mongodb://localhost:27017", description="MongoDB connection string"
    )
    mongodb_db: str = Field(default="repopilot", description="MongoDB database name")

    # ── Kafka ────────────────────────────────────────────
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092", description="Kafka bootstrap servers"
    )
    kafka_trace_topic: str = Field(
        default="repopilot.traces", description="Kafka topic for decision traces"
    )

    # ── Agent Behavior ───────────────────────────────────
    confidence_threshold: float = Field(
        default=0.7,
        description="Below this confidence, escalate to GitHub issue search/creation",
    )
    max_retries: int = Field(
        default=2, description="Max hallucination-check retries before giving up"
    )
    retriever_top_k: int = Field(
        default=8, description="Number of documents to retrieve from vector store"
    )
    chunk_size: int = Field(default=1200, description="Document chunk size in chars")
    chunk_overlap: int = Field(
        default=250, description="Overlap between consecutive chunks"
    )
    cors_origins: str = Field(
        default="*", description="Allowed CORS origins (comma-separated or '*')"
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton settings instance
settings = Settings()
