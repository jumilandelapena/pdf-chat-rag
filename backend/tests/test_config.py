import sys
import types
from pathlib import Path

import pytest

from app.config import MIB, Settings


def test_blank_api_key_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    assert Settings(_env_file=None).anthropic_api_key is None


def test_anthropic_provider_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None, llm_provider="anthropic")


def test_limits_and_paths(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    assert settings.max_upload_bytes == 50 * MIB
    assert settings.body_limit_bytes == 5 * (50 * MIB + MIB)
    assert settings.uploads_dir == tmp_path / "uploads"
    assert settings.sqlite_url.startswith("sqlite:///")
    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_embedding_model_path_skips_hub_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeSentenceTransformer:
        def __init__(self, source: str, device: str = "cpu", **kwargs) -> None:
            calls.append((source, kwargs))

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    from app.ingest.embeddings import LocalEmbedder

    LocalEmbedder(Settings(_env_file=None, embedding_model_path=tmp_path))
    LocalEmbedder(Settings(_env_file=None, embedding_model_path=tmp_path / "missing"))
    assert calls[0] == (str(tmp_path), {})
    assert calls[1] == (
        "BAAI/bge-small-en-v1.5",
        {"revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"},
    )
