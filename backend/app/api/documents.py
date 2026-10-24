"""Document upload, listing, deletion and file serving."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from app.api.schemas import DocumentOut
from app.config import MIB
from app.db import repo
from app.db.models import Document
from app.ingest.pipeline import delete_document_everywhere, ingest_document
from app.services import AppServices, get_services

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}
COPY_CHUNK = MIB


def document_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,  # type: ignore[arg-type]
        error=doc.error,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        scanned_pages=doc.scanned_pages or 0,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
    )


def _display_name(upload: UploadFile) -> str:
    raw = upload.filename or "upload.pdf"
    return (re.split(r"[\/]", raw)[-1] or "upload.pdf")[:200]


async def _validate(upload: UploadFile, max_bytes: int, max_mb: float) -> None:
    name = _display_name(upload)
    if not name.lower().endswith(".pdf"):
        raise HTTPException(415, f"{name} is not a .pdf file")
    if upload.content_type and upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"{name} has unsupported content type {upload.content_type}")
    if upload.size is not None and upload.size > max_bytes:
        raise HTTPException(413, f"{name} exceeds {max_mb:g} MiB")
    head = await upload.read(1024)
    await upload.seek(0)
    if b"%PDF-" not in head:
        raise HTTPException(415, f"{name} is not a PDF file (missing %PDF header)")


async def _save(upload: UploadFile, dest: Path, max_bytes: int, max_mb: float) -> int:
    part = dest.with_suffix(".part")
    size = 0
    try:
        with part.open("wb") as fh:
            while chunk := await upload.read(COPY_CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"{_display_name(upload)} exceeds {max_mb:g} MiB")
                fh.write(chunk)
        os.replace(part, dest)
    finally:
        part.unlink(missing_ok=True)
    return size


@router.post("", status_code=201, response_model=list[DocumentOut])
async def upload_documents(
    background: BackgroundTasks,
    files: Annotated[list[UploadFile], File(description="One or more PDF files")],
    services: Annotated[AppServices, Depends(get_services)],
) -> list[DocumentOut]:
    settings = services.settings
    if len(files) > settings.max_upload_files:
        raise HTTPException(422, f"Upload at most {settings.max_upload_files} files per request")
    for upload in files:
        await _validate(upload, settings.max_upload_bytes, settings.max_upload_mb)
    created: list[DocumentOut] = []
    for upload in files:
        document_id = uuid.uuid4().hex
        dest = settings.uploads_dir / f"{document_id}.pdf"
        try:
            size = await _save(upload, dest, settings.max_upload_bytes, settings.max_upload_mb)
        finally:
            await upload.close()
        with services.session_factory() as session:
            doc = repo.create_document(
                session,
                document_id=document_id,
                filename=_display_name(upload),
                stored_path=str(dest),
                size_bytes=size,
            )
            created.append(document_out(doc))
        background.add_task(ingest_document, document_id, services)
    return created


@router.get("", response_model=list[DocumentOut])
def list_documents(services: Annotated[AppServices, Depends(get_services)]) -> list[DocumentOut]:
    with services.session_factory() as session:
        return [document_out(d) for d in repo.list_documents(session)]


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, services: Annotated[AppServices, Depends(get_services)]
) -> Response:
    if not delete_document_everywhere(document_id, services):
        raise HTTPException(404, "Document not found")
    return Response(status_code=204)


@router.api_route("/{document_id}/file", methods=["GET", "HEAD"])
def get_document_file(
    document_id: str, services: Annotated[AppServices, Depends(get_services)]
) -> FileResponse:
    with services.session_factory() as session:
        doc = repo.get_document(session, document_id)
    if doc is None or not Path(doc.stored_path).is_file():
        raise HTTPException(404, "Document not found")
    return FileResponse(
        doc.stored_path,
        media_type="application/pdf",
        filename=doc.filename,
        content_disposition_type="inline",
    )
