"""Ingest router — POST /api/v1/ingest

PRD Section 5.2
"""

import logging

from fastapi import APIRouter, Form, UploadFile

from core.schemas import IngestResponse
from pipelines.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["ingest"])

_pipeline = IngestionPipeline()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile,
    domain: str = Form(...),
    session_id: str = Form(...),
    folder_id: str | None = Form(None),
    column_mapping: str | None = Form(None),
):
    """Upload and index a file for the given domain and session (PRD 5.2).

    Request: multipart/form-data with fields: file, domain, session_id.
    File is processed in memory — never written to local disk (PRD 14.1).

    Responses:
      200: {"file_id", "filename", "domain", "chunk_count", "status": "indexed"}
      400: INVALID_FILE_TYPE, MISSING_REQUIRED_COLUMNS, EMPTY_FILE
      413: FILE_TOO_LARGE
      422: missing required form fields (FastAPI native)
      500: INGESTION_FAILED, STORAGE_WRITE_FAILED
    """
    from core.exceptions import InvalidDomainError
    from core.schemas import VALID_DOMAINS

    if domain not in VALID_DOMAINS:
        raise InvalidDomainError(domain)

    # Verify session exists before doing expensive work
    from core import database
    await database.get_session(session_id)

    file_bytes = await file.read()
    content_type = file.content_type or ""
    filename = file.filename or "upload"
    
    mapping_dict = None
    if column_mapping:
        import json
        try:
            mapping_dict = json.loads(column_mapping)
        except json.JSONDecodeError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid JSON for column_mapping")

    result = await _pipeline.run(
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
        domain=domain,
        session_id=session_id,
        folder_id=folder_id,
        column_mapping=mapping_dict,
    )

    return IngestResponse(**result)


@router.get("/files/{file_id}/chart")
async def get_file_chart(file_id: str, query: str = ""):
    """Retrieve the computed chart analytics data for an indexed file.
    
    Accepts an optional `query` param to apply the same top-N filtering
    that is applied during live query submissions.
    """
    from core import database
    from fastapi import HTTPException
    from routers.query import _filter_chart_data
    
    chart_data = await database.get_file_chart_data(file_id)
    if not chart_data:
        raise HTTPException(status_code=404, detail="Chart data not found or file not fully processed yet")
    
    if query:
        chart_data = _filter_chart_data(chart_data, query)
    
    return chart_data


@router.delete("/files/{file_id}")
async def delete_ingested_file(file_id: str):
    """Delete an uploaded file from Supabase DB, Storage, and Qdrant."""
    from core import database, qdrant as qdrant_client
    from fastapi import HTTPException
    
    # 1. Look up the file to get its domain
    file_record = await database.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
        
    domain = file_record.get("domain")
    
    # 2. Delete vectors from Qdrant
    if domain:
        try:
            collection = qdrant_client.collection_for_domain(domain)
            await qdrant_client.delete_points_by_file(collection, file_id)
        except Exception as e:
            logger.error("Failed to delete Qdrant points for file %s: %s", file_id, e)
            
    # 3. Delete from Supabase DB and Storage
    await database.delete_file(file_id)
    
    return {"status": "deleted", "file_id": file_id}
