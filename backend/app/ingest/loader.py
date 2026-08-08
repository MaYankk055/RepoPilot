"""
Git repository document loader and comprehensive codebase architecture profiler.

Clones a public GitHub repository using a Git URL into a temporary directory,
analyzes the codebase structure, extracts architecture and dependency maps,
and loads all code, config, and documentation files as LangChain Document objects
with rich metadata for deep RAG indexing.
"""

import os
import re
import shutil
import tempfile
import logging
from urllib.parse import urlparse
import ipaddress
from typing import List, Dict, Set, Tuple
from git import Repo
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Disallowed internal IP ranges for SSRF prevention
BLOCKED_HOSTNAMES: Set[str] = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254", # AWS/GCP/Azure instance metadata
    "metadata.google.internal",
}

def validate_git_repo_url(url: str) -> str:
    """
    Strictly validate and sanitize a Git repository URL.
    Ensures safe protocols (https/http), blocks internal IP subnets (SSRF),
    and rejects malformed strings or command injection payloads.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL must be a non-empty string.")
    
    clean_url = url.strip().rstrip("/")
    
    # Check for forbidden control characters or shell injection artifacts
    if any(char in clean_url for char in [";", "&", "|", "`", "$", "\n", "\r", "<", ">", '"', "'", "\\"]):
        raise ValueError("Repository URL contains invalid or potentially dangerous characters.")
        
    parsed = urlparse(clean_url)
    
    if parsed.scheme.lower() not in {"https", "http"}:
        raise ValueError(f"Invalid URL protocol '{parsed.scheme}'. Only HTTPS/HTTP repository URLs are supported.")
        
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("Repository URL must include a valid hostname.")
        
    if hostname in BLOCKED_HOSTNAMES:
        raise ValueError(f"Access to host '{hostname}' is blocked for security reasons.")
        
    # Check for private or loopback IP addresses
    parsed_ip = None
    try:
        parsed_ip = ipaddress.ip_address(hostname)
    except ValueError:
        # Not a raw IP address, which is good for public hostnames (e.g., github.com)
        pass

    if parsed_ip is not None:
        if (
            parsed_ip.is_private
            or parsed_ip.is_loopback
            or parsed_ip.is_link_local
            or parsed_ip.is_reserved
            or parsed_ip.is_multicast
            or parsed_ip.is_unspecified
        ):
            raise ValueError(f"Access to private or local IP '{hostname}' is blocked for security.")

    # Ensure path has at least an owner/organization and a repository name
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise ValueError("Repository URL must include owner and repository name (e.g., https://github.com/owner/repo).")

    return clean_url


# Folders to skip entirely
IGNORED_DIRECTORIES: Set[str] = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    ".next",
    ".nuxt",
    ".turbo",
    ".docusaurus",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    "out",
    "target",
    "bin",
    "obj",
    "venv",
    ".venv",
    "env",
    "virtualenv",
    "vendor",
    "pods",
    "coverage",
    ".coverage",
    "htmlcov",
    "site-packages",
}

# Large or noisy files to ignore
IGNORED_FILENAMES: Set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "cargo.lock",
    "poetry.lock",
    "gemfile.lock",
    "composer.lock",
    ".ds_store",
    "thumbs.db",
}

# Valid extensions by category
CODE_EXTENSIONS: Set[str] = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".c", ".cpp", ".cc", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php", ".cs",
    ".swift", ".kt", ".scala", ".sql", ".sh", ".bash", ".zsh",
}

DOC_EXTENSIONS: Set[str] = {
    ".md", ".mdx", ".rst", ".txt", ".adoc"
}

CONFIG_EXTENSIONS: Set[str] = {
    ".json", ".yml", ".yaml", ".toml", ".xml", ".ini", ".env.example"
}

KEY_CONFIG_FILES: Set[str] = {
    "package.json", "pyproject.toml", "requirements.txt", "cargo.toml",
    "go.mod", "pom.xml", "build.gradle", "dockerfile", "docker-compose.yml",
    "docker-compose.yaml", "tsconfig.json", "makefile"
}


class GitRepoLoader:
    """Loads and profiles documents from a cloned Git repository."""

    def __init__(self, repo_url: str):
        self.repo_url = validate_git_repo_url(repo_url)
        # Extract owner and repo_name
        parts = self.repo_url.split("/")
        self.repo_name = parts[-1]
        if self.repo_name.endswith(".git"):
            self.repo_name = self.repo_name[:-4]
        self.owner = parts[-2] if len(parts) >= 2 else ""

    def _should_skip_dir(self, dir_name: str) -> bool:
        """Determine if a directory should be skipped."""
        lower = dir_name.lower()
        return lower in IGNORED_DIRECTORIES or lower.startswith(".")

    def _should_skip_file(self, filename: str) -> bool:
        """Determine if a file should be skipped."""
        lower = filename.lower()
        if lower.startswith(".") and lower not in {".env.example"}:
            return True
        if lower in IGNORED_FILENAMES:
            return True
        if any(lower.endswith(sfx) for sfx in [".min.js", ".min.css", ".bundle.js", ".map"]):
            return True
        return False

    def _classify_file(self, rel_path: str, filename: str, ext: str) -> str:
        """Classify file type into architecture, code, documentation, or configuration."""
        lower_name = filename.lower()
        if lower_name in KEY_CONFIG_FILES or ext in CONFIG_EXTENSIONS:
            return "configuration"
        elif ext in DOC_EXTENSIONS:
            return "documentation"
        elif ext in CODE_EXTENSIONS:
            return "code"
        return "other"

    def _build_repo_architecture_document(
        self, file_tree: List[str], dir_map: Dict[str, List[str]], key_configs: Dict[str, str]
    ) -> Document:
        """
        Generate a synthetic repository architectural overview document.
        This provides the LLM with the global structure, tech stack, and module map.
        """
        lines = [
            f"# Repository Architecture & Codebase Map: {self.repo_name}",
            f"**Repository URL:** {self.repo_url}",
            f"**Total Source/Doc Files Analyzed:** {len(file_tree)}",
            "",
            "## 1. Directory Structure & File Hierarchy",
            "```text",
        ]

        # Pretty print file tree (up to first 150 items to keep concise)
        for path in file_tree[:150]:
            lines.append(f"- {path}")
        if len(file_tree) > 150:
            lines.append(f"... and {len(file_tree) - 150} more files")
        lines.append("```")
        lines.append("")

        # Module / Directory summaries
        lines.append("## 2. Codebase Modules & Directory Contents")
        for directory, files in sorted(dir_map.items()):
            if directory == ".":
                dir_label = "Root Directory (`/`)"
            else:
                dir_label = f"`{directory}/`"
            file_sample = ", ".join(f"`{f}`" for f in files[:8])
            if len(files) > 8:
                file_sample += f" (+{len(files) - 8} more)"
            lines.append(f"- **{dir_label}**: {len(files)} files ({file_sample})")
        lines.append("")

        # Key configuration and dependency highlights
        if key_configs:
            lines.append("## 3. Key Configuration & Project Entry Points")
            for cfg_name, cfg_snippet in key_configs.items():
                lines.append(f"### `{cfg_name}`")
                lines.append("```text")
                lines.append(cfg_snippet[:1500])
                lines.append("```")
                lines.append("")

        architecture_content = "\n".join(lines)
        return Document(
            page_content=architecture_content,
            metadata={
                "source": "_REPO_ARCHITECTURE.md",
                "filename": "_REPO_ARCHITECTURE.md",
                "type": "architecture",
                "repo": self.repo_name,
                "url": f"{self.repo_url}",
            },
        )

    def load_all(self) -> List[Document]:
        """
        Clone the repository, analyze architecture, and load all code and documentation files.
        """
        logger.info(f"Cloning and deeply analyzing repository from {self.repo_url}...")

        docs: List[Document] = []
        file_tree: List[str] = []
        dir_map: Dict[str, List[str]] = {}
        key_configs: Dict[str, str] = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                logger.info(f"Cloning {self.repo_url} into temporary directory {temp_dir}...")
                Repo.clone_from(self.repo_url, temp_dir, depth=1)

                for root, dirs, files in os.walk(temp_dir):
                    # Filter out ignored directories in place
                    dirs[:] = [d for d in dirs if not self._should_skip_dir(d)]

                    rel_root = os.path.relpath(root, temp_dir)
                    current_dir = "." if rel_root == "." else rel_root

                    for file in sorted(files):
                        if self._should_skip_file(file):
                            continue

                        ext = os.path.splitext(file)[1].lower()
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, temp_dir)
                        lower_name = file.lower()

                        # Classify file
                        file_type = self._classify_file(rel_path, file, ext)
                        if file_type == "other" and lower_name not in KEY_CONFIG_FILES:
                            continue

                        file_tree.append(rel_path)
                        dir_map.setdefault(current_dir, []).append(file)

                        # Read file content
                        try:
                            # Skip excessively large files (> 500KB) to prevent bloat
                            if os.path.getsize(file_path) > 500 * 1024:
                                logger.debug(f"Skipping oversized file {rel_path}")
                                continue

                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()

                            if not content.strip():
                                continue

                            # Save key configuration snippets for the architecture summary
                            if lower_name in KEY_CONFIG_FILES and len(key_configs) < 5:
                                key_configs[rel_path] = content[:1500]

                            line_count = len(content.splitlines())

                            docs.append(
                                Document(
                                    page_content=content,
                                    metadata={
                                        "source": rel_path,
                                        "filename": file,
                                        "extension": ext,
                                        "type": file_type,
                                        "repo": self.repo_name,
                                        "line_count": line_count,
                                        "url": f"{self.repo_url}/blob/main/{rel_path}",
                                    },
                                )
                            )
                        except Exception as e:
                            logger.warning(f"Error reading file {rel_path}: {e}")

                # Build and prepend the repo architecture document
                if file_tree:
                    arch_doc = self._build_repo_architecture_document(file_tree, dir_map, key_configs)
                    docs.insert(0, arch_doc)

            except Exception as e:
                logger.error(f"Failed to clone or process {self.repo_url}: {e}", exc_info=True)
                return []

        logger.info(
            f"Successfully indexed {len(docs)} documents from {self.repo_name} "
            f"(including architecture overview, code, configs, and docs)"
        )
        return docs
