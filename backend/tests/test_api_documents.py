from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import make_pdf, upload, wait_done


def test_upload_sample_pdf_becomes_ready(client: TestClient, sample_pdf: Path) -> None:
    doc = upload(client, sample_pdf)
    assert doc["status"] == "ready" and doc["error"] is None
    assert doc["page_count"] == 10 and doc["chunk_count"] > 0
    assert doc["filename"] == "rfc2324-htcpcp.pdf"
    assert doc["size_bytes"] == sample_pdf.stat().st_size
    listed = client.get("/documents").json()
    assert [d["id"] for d in listed] == [doc["id"]]
    assert client.get("/health").json()["documents"] == 1


def test_rejects_non_pdf_uploads(client: TestClient, tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text("hello")
    with txt.open("rb") as fh:
        assert (
            client.post(
                "/documents", files=[("files", ("notes.txt", fh, "text/plain"))]
            ).status_code
            == 415
        )
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"this is not a pdf at all")
    with fake.open("rb") as fh:
        response = client.post("/documents", files=[("files", ("fake.pdf", fh, "application/pdf"))])
    assert response.status_code == 415 and "PDF" in response.json()["detail"]
    assert client.get("/documents").json() == []


def test_rejects_too_many_files(client: TestClient, tiny_pdf: Path) -> None:
    data = tiny_pdf.read_bytes()
    files = [("files", (f"f{i}.pdf", data, "application/pdf")) for i in range(6)]
    assert client.post("/documents", files=files).status_code == 422


def test_rejects_oversized_file(tmp_path: Path, sample_pdf: Path) -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="mock",
        embeddings_provider="fake",
        data_dir=tmp_path / "data",
        max_upload_mb=0.01,
    )
    with TestClient(create_app(settings)) as client, sample_pdf.open("rb") as fh:
        response = client.post("/documents", files=[("files", ("big.pdf", fh, "application/pdf"))])
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]


def test_file_endpoint_supports_range_and_head(client: TestClient, sample_pdf: Path) -> None:
    doc = upload(client, sample_pdf)
    full = client.get(f"/documents/{doc['id']}/file")
    assert full.status_code == 200
    assert full.headers["content-type"] == "application/pdf"
    assert full.headers["accept-ranges"] == "bytes"
    assert "inline" in full.headers["content-disposition"]
    partial = client.get(f"/documents/{doc['id']}/file", headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 0-99/{sample_pdf.stat().st_size}"
    assert len(partial.content) == 100
    assert client.head(f"/documents/{doc['id']}/file").status_code == 200
    assert client.get("/documents/nope/file").status_code == 404


def test_delete_removes_everything(client: TestClient, services, sample_pdf: Path) -> None:
    doc = upload(client, sample_pdf)
    stored = services.settings.uploads_dir / f"{doc['id']}.pdf"
    assert stored.is_file()
    assert services.vector_store.count() == doc["chunk_count"]
    assert services.bm25.search([doc["id"]], "teapot", 5)
    assert client.delete(f"/documents/{doc['id']}").status_code == 204
    assert client.delete(f"/documents/{doc['id']}").status_code == 404
    assert client.get(f"/documents/{doc['id']}/file").status_code == 404
    assert services.vector_store.count() == 0
    assert services.bm25.search([doc["id"]], "teapot", 5) == []
    assert not stored.exists()
    assert client.get("/documents").json() == []


def test_corrupt_and_text_free_pdfs_fail(client: TestClient, tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7\n" + b"\x00" * 200)
    with corrupt.open("rb") as fh:
        response = client.post(
            "/documents", files=[("files", ("corrupt.pdf", fh, "application/pdf"))]
        )
    assert response.status_code == 201
    failed = wait_done(client, response.json()[0]["id"])
    assert failed["status"] == "failed" and failed["error"]
    blank = make_pdf(tmp_path / "blank.pdf", ["", ""])
    doc = upload(client, blank)
    assert doc["status"] == "failed"
    assert "No extractable text" in doc["error"]
    assert doc["page_count"] is None
