from pathlib import Path

from sqlalchemy import delete

from app.db.models import Chunk
from app.retrieval.hybrid import retrieve
from tests.conftest import make_pdf, upload


def test_retrieve_respects_scope_and_limits(client, services, tmp_path: Path) -> None:
    tea = make_pdf(
        tmp_path / "tea.pdf",
        [
            "Any attempt to brew coffee with a teapot should result in the error code 418 I'm a teapot."
        ],
    )
    rockets = make_pdf(
        tmp_path / "rockets.pdf",
        ["The crawler transporter carries the mobile launcher and the rocket to the launch pad."],
    )
    tea_doc = upload(client, tea)
    rockets_doc = upload(client, rockets)
    assert tea_doc["status"] == "ready" and rockets_doc["status"] == "ready"

    hits = retrieve(
        services, "which error does a teapot return", [tea_doc["id"], rockets_doc["id"]]
    )
    assert hits and hits[0].chunk.document_id == tea_doc["id"]
    assert hits[0].chunk.document.filename == "tea.pdf"
    assert hits[0].vector_rank == 1 and hits[0].bm25_rank == 1
    assert len(hits) <= services.settings.top_k_final

    only_rockets = retrieve(services, "teapot error", [rockets_doc["id"]])
    assert {h.chunk.document_id for h in only_rockets} == {rockets_doc["id"]}
    assert retrieve(services, "teapot", []) == []
    assert retrieve(services, "   ", [tea_doc["id"]]) == []
    assert len(retrieve(services, "teapot", [tea_doc["id"], rockets_doc["id"]], top_k_final=1)) == 1

    with services.session_factory() as session:
        session.execute(delete(Chunk).where(Chunk.document_id == tea_doc["id"]))
        session.commit()
    stale = retrieve(services, "teapot error 418", [tea_doc["id"], rockets_doc["id"]])
    assert {h.chunk.document_id for h in stale} == {rockets_doc["id"]}
