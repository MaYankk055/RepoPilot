"""
Document chunker — splits loaded codebase documents into semantically coherent chunks for embedding.
Uses language-aware separators and injects rich context breadcrumbs into every chunk.
"""

import logging
from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_core.documents import Document

from app.config import settings

logger = logging.getLogger(__name__)

# Map file extensions to LangChain Language enums for syntax-aware splitting
EXTENSION_TO_LANGUAGE: Dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
    ".java": Language.JAVA,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".c": Language.CPP,
    ".h": Language.CPP,
    ".hpp": Language.CPP,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".rb": Language.RUBY,
    ".php": Language.PHP,
    ".cs": Language.CSHARP,
    ".swift": Language.SWIFT,
    ".kt": Language.KOTLIN,
    ".scala": Language.SCALA,
    ".html": Language.HTML,
    ".md": Language.MARKDOWN,
    ".mdx": Language.MARKDOWN,
    ".rst": Language.RST,
}


def get_splitter_for_doc(doc: Document) -> RecursiveCharacterTextSplitter:
    """Create a language-aware splitter or fallback to standard recursive splitter."""
    ext = doc.metadata.get("extension", "").lower()
    doc_type = doc.metadata.get("type", "")

    # Architecture summary uses larger chunks to preserve full system map
    if doc_type == "architecture":
        return RecursiveCharacterTextSplitter(
            chunk_size=min(settings.chunk_size * 2, 2500),
            chunk_overlap=settings.chunk_overlap,
            separators=["\n## ", "\n### ", "\n\n", "\n", " "],
            add_start_index=True,
        )

    # If extension is supported by Language enum
    if ext in EXTENSION_TO_LANGUAGE:
        try:
            return RecursiveCharacterTextSplitter.from_language(
                language=EXTENSION_TO_LANGUAGE[ext],
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                add_start_index=True,
            )
        except Exception:
            pass

    # Generic code/config splitter
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=[
            "\nclass ",
            "\ndef ",
            "\nfunction ",
            "\nexport ",
            "\ninterface ",
            "\ntype ",
            "\n\n",
            "\n",
            "; ",
            ". ",
            " ",
            "",
        ],
        add_start_index=True,
    )


def chunk_documents(documents: List[Document]) -> List[Document]:
    """
    Split codebase documents into chunks suitable for embedding and deep code retrieval.
    Appends rich metadata and context breadcrumbs to every chunk.
    """
    all_chunks: List[Document] = []

    for doc in documents:
        splitter = get_splitter_for_doc(doc)
        chunks = splitter.split_documents([doc])

        source = doc.metadata.get("source", "unknown")
        doc_type = doc.metadata.get("type", "code")
        repo = doc.metadata.get("repo", "repository")

        for idx, chunk in enumerate(chunks):
            # Inject rich breadcrumb header into the chunk's content for the embedding & LLM
            header = f"[Repository: {repo}] [File: {source}] [Type: {doc_type}] [Chunk: {idx + 1}/{len(chunks)}]"
            chunk.page_content = f"{header}\n---\n{chunk.page_content}"
            chunk.metadata["chunk_index"] = idx
            chunk.metadata["total_chunks"] = len(chunks)
            all_chunks.append(chunk)

    logger.info(
        f"Chunked {len(documents)} documents into {len(all_chunks)} semantic chunks "
        f"(chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap})"
    )

    return all_chunks
