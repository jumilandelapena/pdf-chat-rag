"""Shared fixtures. Tests run offline with the mock provider and the fake embedder."""

from __future__ import annotations

import os

os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDINGS_PROVIDER"] = "fake"
os.environ.pop("ANTHROPIC_API_KEY", None)

import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import pymupdf  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PDFS = REPO_ROOT / "sample-pdfs"
TINY_PAGES = [
    "Alpha one. The crawler weighs six million pounds. Count is fine.\n\n"
    "A second paragraph talks about teapots and coffee brewing protocols.",
    "Soft­hyphen word here. Visit https://example.com/" + "a" * 290 + " for the long url. The end.",
    "",
]


def make_pdf(path: Path, pages: list[str]) -> Path:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), text, fontsize=11)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return Settings(
        _env_file=None,
        llm_provider="mock",
        embeddings_provider="fake",
        data_dir=tmp_path / "data",
    )


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        provider = app.state.services.provider
        if hasattr(provider, "delay_s"):
            provider.delay_s = 0
        yield test_client


@pytest.fixture
def services(client, app):
    return app.state.services


@pytest.fixture(scope="session")
def sample_pdf() -> Path:
    return SAMPLE_PDFS / "rfc2324-htcpcp.pdf"


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    return make_pdf(tmp_path / "tiny.pdf", TINY_PAGES)


def upload(client: TestClient, path: Path, name: str | None = None) -> dict[str, Any]:
    with path.open("rb") as fh:
        response = client.post(
            "/documents", files=[("files", (name or path.name, fh, "application/pdf"))]
        )
    assert response.status_code == 201, response.text
    return wait_done(client, response.json()[0]["id"])


def wait_done(client: TestClient, document_id: str, timeout_s: float = 60) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        doc = next(d for d in client.get("/documents").json() if d["id"] == document_id)
        if doc["status"] in ("ready", "failed"):
            return doc
        time.sleep(0.05)
    raise AssertionError("ingestion did not finish in time")


def read_sse(text: str) -> list[tuple[str, Any]]:
    """Parse an SSE body into ``(event, data)`` pairs (data JSON-decoded)."""
    events: list[tuple[str, Any]] = []
    event, data_lines = "message", []
    for line in text.splitlines() + [""]:
        if line == "":
            if data_lines:
                events.append((event, json.loads("\n".join(data_lines))))
            event, data_lines = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    return events
