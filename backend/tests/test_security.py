"""
Comprehensive Security & Input Validation Tests for RepoPilot.

Validates SSRF prevention, command injection guards, protocol enforcement,
and input boundary conditions.
"""

import pytest
from fastapi.testclient import TestClient
from app.api import app
from app.ingest.loader import validate_git_repo_url

client = TestClient(app)


# ── URL Validation & SSRF Guard Tests ─────────────────────

def test_valid_github_urls():
    """Verify standard legitimate repository URLs pass validation."""
    valid_urls = [
        "https://github.com/langchain-ai/langchain",
        "https://github.com/fastapi/fastapi.git",
        "https://gitlab.com/gitlab-org/gitlab",
        "https://bitbucket.org/atlassian/sample-repo",
        "http://github.com/owner/repo",
    ]
    for url in valid_urls:
        validated = validate_git_repo_url(url)
        assert validated.startswith("http")
        assert len(validated) > 0


def test_reject_ssrf_and_private_ips():
    """Verify loopback, link-local, and internal cloud metadata IPs are rejected."""
    malicious_urls = [
        "http://169.254.169.254/latest/meta-data",
        "https://127.0.0.1/private/repo.git",
        "http://localhost/repo",
        "http://0.0.0.0/test/repo",
        "http://10.0.0.1/internal/repo",
        "http://192.168.1.1/secret/repo",
    ]
    for url in malicious_urls:
        with pytest.raises(ValueError):
            validate_git_repo_url(url)


def test_reject_dangerous_schemes():
    """Verify non-HTTP(S) schemes such as file:// and ssh:// are blocked."""
    unsafe_schemes = [
        "file:///etc/passwd",
        "file:///Users/mayank/rag/secret.txt",
        "ssh://git@github.com:owner/repo.git",
        "ftp://example.com/repo.git",
        "git://github.com/owner/repo.git",
        "javascript:alert(1)",
    ]
    for url in unsafe_schemes:
        with pytest.raises(ValueError):
            validate_git_repo_url(url)


def test_reject_command_injection_and_characters():
    """Verify shell metacharacters and injection strings are blocked."""
    injection_urls = [
        "https://github.com/owner/repo; rm -rf /",
        "https://github.com/owner/repo && whoami",
        "https://github.com/owner/repo | cat /etc/passwd",
        "https://github.com/owner/`id`",
        "https://github.com/owner/$(whoami)",
        "https://github.com/owner/repo\nhttp://evil.com",
    ]
    for url in injection_urls:
        with pytest.raises(ValueError):
            validate_git_repo_url(url)


def test_reject_incomplete_repo_paths():
    """Verify bare domains or root URLs without owner/repo are rejected."""
    incomplete_urls = [
        "https://github.com",
        "https://github.com/",
        "https://gitlab.com/onlyowner",
        "",
        "   ",
    ]
    for url in incomplete_urls:
        with pytest.raises(ValueError):
            validate_git_repo_url(url)


# ── API Endpoint Security & Validation Tests ──────────────

def test_api_ingest_rejects_ssrf():
    """Verify /ingest returns HTTP 400 when given an SSRF URL."""
    response = client.post("/ingest", json={"repo_url": "http://169.254.169.254/latest/meta-data"})
    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()


def test_api_ingest_rejects_file_protocol():
    """Verify /ingest returns HTTP 400 when given a file:// URL."""
    response = client.post("/ingest", json={"repo_url": "file:///etc/passwd"})
    assert response.status_code == 400


def test_api_ask_rejects_malformed_url():
    """Verify /ask returns HTTP 400 for unsafe repository URLs."""
    response = client.post("/ask", json={
        "question": "Explain this code",
        "repo_url": "https://github.com/owner/repo; rm -rf /"
    })
    assert response.status_code == 400
