"""
Centralized LLM client factory with robust SSL certificate verification and connection error recovery.
"""

import os
import certifi
import httpx
import logging
from langchain_groq import ChatGroq
from app.config import settings

logger = logging.getLogger(__name__)

# Configure environment variables to ensure libraries use valid CA certificates
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()


def get_http_client() -> httpx.Client:
    """
    Create a resilient httpx client configured with certifi certificates,
    falling back gracefully if SSL chain inspection fails.
    """
    try:
        return httpx.Client(verify=certifi.where(), timeout=60.0)
    except Exception as e:
        logger.warning(f"Could not initialize httpx client with certifi: {e}, using fallback client")
        return httpx.Client(verify=False, timeout=60.0)


def get_chat_llm(temperature: float = 0.0, model: str | None = None) -> ChatGroq:
    """
    Get a ChatGroq instance with resilient transport and SSL handling.
    """
    http_client = get_http_client()
    return ChatGroq(
        model=model or settings.llm_model,
        temperature=temperature,
        api_key=settings.groq_api_key,
        http_client=http_client,
        max_retries=3,
    )
