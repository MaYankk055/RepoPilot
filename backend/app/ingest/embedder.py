"""
Chroma vector store setup — embeds, indexes, and stores codebase chunks with collection management.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)


class LocalSentenceTransformerEmbeddings(Embeddings):
    """
    Direct, robust local sentence-transformers embeddings implementing
    LangChain's Embeddings interface. Completely free, fast, and offline.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = SentenceTransformer(model_name, device=device)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search/document chunks."""
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Embed a single user query."""
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()


_embedding_instance = None
_vector_store_instance = None


def get_embedding_function():
    """Get or reuse the embedding function based on settings."""
    global _embedding_instance
    if _embedding_instance is not None:
        return _embedding_instance

    if settings.embedding_provider == "openai" and settings.openai_api_key:
        from langchain_openai import OpenAIEmbeddings

        _embedding_instance = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.openai_api_key,
        )
    else:
        # Direct local sentence-transformers (free, offline, no API key required)
        _embedding_instance = LocalSentenceTransformerEmbeddings(
            model_name=settings.local_embedding_model,
            device="cpu",
        )
    return _embedding_instance


def get_vector_store() -> Chroma:
    """Get or reuse the Chroma vector store instance."""
    global _vector_store_instance
    if _vector_store_instance is not None:
        return _vector_store_instance

    embedding_fn = get_embedding_function()
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    _vector_store_instance = Chroma(
        collection_name=settings.chroma_collection_name,
        embedding_function=embedding_fn,
        persist_directory=settings.chroma_persist_dir,
    )
    return _vector_store_instance


def get_vector_store_stats() -> Dict[str, Any]:
    """Retrieve statistics about the indexed collections in Chroma DB."""
    try:
        store = get_vector_store()
        count = store._collection.count()
        return {
            "collection_name": settings.chroma_collection_name,
            "total_chunks": count,
            "persist_dir": settings.chroma_persist_dir,
            "status": "ready",
        }
    except Exception as e:
        logger.warning(f"Error getting vector store stats: {e}")
        return {
            "collection_name": settings.chroma_collection_name,
            "total_chunks": 0,
            "persist_dir": settings.chroma_persist_dir,
            "status": "error",
            "error": str(e),
        }


def embed_and_store(chunks: List[Document], repo_name: Optional[str] = None) -> Chroma:
    """
    Embed document chunks and store them in Chroma.
    Cleans up any previous chunks from the same repo to ensure fresh indices.
    """
    vector_store = get_vector_store()

    if repo_name:
        try:
            # Delete old chunks for this repo if they exist
            logger.info(f"Removing any existing vectors for repository: {repo_name}")
            vector_store._collection.delete(where={"repo": repo_name})
        except Exception as e:
            logger.debug(f"No existing vectors to delete for {repo_name}: {e}")

    logger.info(
        f"Embedding {len(chunks)} chunks using {settings.embedding_provider} "
        f"provider, storing into Chroma at {settings.chroma_persist_dir}"
    )

    # Batch add documents in groups of 100 to avoid memory spikes
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vector_store.add_documents(batch)
        logger.debug(f"Stored batch {i // batch_size + 1}/{(len(chunks) + batch_size - 1) // batch_size}")

    logger.info(f"Successfully indexed {len(chunks)} chunks in Chroma")
    return vector_store


def ingest_git_repo(repo_url: str) -> Chroma:
    """
    Full ingestion pipeline for a git repository:
    clone → analyze architecture → load code & docs → chunk → embed → store.
    """
    from app.ingest.loader import GitRepoLoader
    from app.ingest.chunker import chunk_documents

    loader = GitRepoLoader(repo_url=repo_url)
    documents = loader.load_all()

    if not documents:
        raise ValueError(
            f"No valid source or documentation files could be loaded from {repo_url}. "
            "Please ensure the URL is a valid, public Git repository."
        )

    chunks = chunk_documents(documents)
    vector_store = embed_and_store(chunks, repo_name=loader.repo_name)
    return vector_store
