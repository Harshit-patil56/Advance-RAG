"""Ingestion pipeline orchestrator.

Implements the complete ingest flow from PRD Section 3.1:
  1. Upload raw file to Supabase Storage
  2. Insert uploaded_files row (status=pending)
  3. Parse file (domain-specific)
  4. Compute Finance chart data if applicable (PRD 9.1)
  5. Chunk text
  6. Embed chunks (batched, with cache)
  7. Upsert Qdrant points
  8. On any failure in steps 4-7 → rollback (delete Qdrant points, set status=failed)
  9. Update uploaded_files row (status=indexed)

No file bytes are written to local disk (PRD 14.1).
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from config import settings
from core import database, qdrant as qdrant_client
from core.exceptions import (
    FileTooLargeError,
    IngestionFailedError,
    InvalidFileTypeError,
    StorageWriteFailedError,
)
from pipelines.finance.aggregator import CsvAggregator
from pipelines.finance.validator import dataframe_to_text
from pipelines.ingestion.chunker import LegalChunker, RecursiveCharChunker
from pipelines.ingestion.embedder import HFEmbedder
from pipelines.ingestion.file_parser import CsvParser, PdfParser, TxtParser

logger = logging.getLogger(__name__)

_SAFE_FILENAME_PATTERN = re.compile(r"[^\w\-.]")


def _sanitise_filename(filename: str) -> str:
    """Strip path traversal characters and special chars (PRD 14.5)."""
    name = filename.replace("/", "_").replace("\\", "_")
    name = _SAFE_FILENAME_PATTERN.sub("_", name)
    return name[:200]  # cap length


def _validate_file_type(domain: str, filename: str, content_type: str) -> None:
    """Enforce domain-specific file type rules (PRD 4.3)."""
    lower_name = filename.lower()
    if domain == "finance":
        if content_type not in ("text/csv",) and not lower_name.endswith(".csv"):
            raise InvalidFileTypeError(domain, filename)
    elif domain == "law":
        allowed_types = {"application/pdf", "text/plain"}
        allowed_exts = (".pdf", ".txt")
        if content_type not in allowed_types and not lower_name.endswith(allowed_exts):
            raise InvalidFileTypeError(domain, filename)
    elif domain == "global":
        allowed_types = {"text/csv", "application/pdf", "text/plain"}
        allowed_exts = (".csv", ".pdf", ".txt")
        if content_type not in allowed_types and not lower_name.endswith(allowed_exts):
            raise InvalidFileTypeError(domain, filename)
    # Domain validation is done at the API layer before this is called.


class IngestionPipeline:
    """Orchestrate the full file ingestion flow."""

    def __init__(self) -> None:
        self._csv_parser = CsvParser()
        self._pdf_parser = PdfParser()
        self._txt_parser = TxtParser()
        self._recursive_chunker = RecursiveCharChunker()
        self._legal_chunker = LegalChunker()
        self._aggregator = CsvAggregator()
        self._embedder = HFEmbedder()

    async def run(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        domain: str,
        session_id: str,
        folder_id: str | None = None,
        column_mapping: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute the full ingest pipeline and return the response dict.

        Raises AppError subclasses on validation or processing failure.
        """
        # --- Size validation (PRD 5.2)
        limit_bytes = settings.max_file_size_mb * 1024 * 1024
        if len(file_bytes) > limit_bytes:
            raise FileTooLargeError(len(file_bytes), settings.max_file_size_mb)

        # --- File type validation (PRD 4.3)
        _validate_file_type(domain, filename, content_type)

        safe_name = _sanitise_filename(filename)
        storage_path = f"{domain}/{session_id}/{safe_name}"

        # --- Step 1: Upload to Supabase Storage (PRD 3.1)
        await self._upload_to_storage(file_bytes, storage_path, content_type)

        # --- Step 2: Insert pending row in uploaded_files
        file_row = await database.insert_uploaded_file(
            session_id=session_id,
            domain=domain,
            filename=safe_name,
            storage_path=storage_path,
            file_size_bytes=len(file_bytes),
            folder_id=folder_id,
        )
        file_id: str = str(file_row["file_id"])

        # --- Steps 3–7: Processing with rollback on failure
        try:
            chart_data, text = self._parse(file_bytes, filename, domain, column_mapping=column_mapping)
            chunks = self._chunk(text, domain, file_id, session_id, safe_name)
            chunk_texts = [c.text for c in chunks]
            vectors = await self._embedder.embed_texts(chunk_texts)
            points = self._build_qdrant_points(chunks, vectors, session_id)
            collection = qdrant_client.collection_for_domain(domain)
            await qdrant_client.upsert_points(collection, points)
        except Exception as exc:
            logger.error("Ingestion failed for file '%s': %s", file_id, exc)
            # --- Rollback: delete any Qdrant points written, update status
            try:
                await qdrant_client.delete_points_by_file(
                    qdrant_client.collection_for_domain(domain), file_id
                )
            except Exception as rollback_exc:
                logger.error("Rollback failed: %s", rollback_exc)

            await database.update_file_status(
                file_id=file_id,
                status="failed",
                error_message=str(exc),
            )

            # Re-raise as IngestionFailedError if not already an AppError
            from core.exceptions import AppError
            if isinstance(exc, AppError):
                raise
            raise IngestionFailedError(str(exc)) from exc

        # --- Step 9: Update status to indexed
        await database.update_file_status(
            file_id=file_id,
            status="indexed",
            chunk_count=len(chunks),
            chart_data=chart_data,
            full_markdown=text,
        )

        return {
            "file_id": file_id,
            "filename": safe_name,
            "domain": domain,
            "chunk_count": len(chunks),
            "status": "indexed",
            "folder_id": folder_id,
        }

    async def _upload_to_storage(self, file_bytes: bytes, storage_path: str, content_type: str = "") -> None:
        """Upload raw bytes to Supabase Storage (PRD 3.1).

        Uses the actual MIME content type so files are stored correctly
        and can be previewed/downloaded with the right type from the dashboard.
        """
        from core.database import get_client

        client = get_client()
        # Use real content type; fall back to octet-stream if unknown
        upload_content_type = content_type if content_type else "application/octet-stream"
        try:
            # upsert=True allows replacing an existing file instead of crashing with a 500 duplicate error
            client.storage.from_(settings.storage_bucket).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": upload_content_type, "upsert": "true"},
            )
        except Exception as exc:
            raise StorageWriteFailedError(str(exc)) from exc

    def _parse(
        self, file_bytes: bytes, filename: str, domain: str, column_mapping: dict[str, str] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        """Parse the file based on domain. Returns (chart_data | None, text)."""
        lower = filename.lower()
        if domain == "finance":
            df = self._csv_parser.run(file_bytes, filename, column_mapping=column_mapping)
            chart_data = self._aggregator.compute(df)
            text = dataframe_to_text(df)
            return chart_data, text

        if domain == "global" and lower.endswith(".csv"):
            import io
            df = pd.read_csv(io.BytesIO(file_bytes))

            for col in df.select_dtypes(include="object").columns:
                df[col] = df[col].astype(str).str.strip()

            if df.empty:
                from core.exceptions import EmptyFileError
                raise EmptyFileError()

            text = df.to_markdown(index=False)
            return None, text

        elif lower.endswith(".pdf"):
            text = self._pdf_parser.run(file_bytes, filename)
            return None, text

        else:  # .txt
            text = self._txt_parser.run(file_bytes, filename)
            return None, text

    def _chunk(
        self,
        text: str,
        domain: str,
        file_id: str,
        session_id: str,
        source_filename: str,
    ):
        """Select chunker strategy based on domain (PRD 3.1, 10.3)."""
        if domain == "law":
            return self._legal_chunker.run(
                text, domain, file_id, session_id, source_filename
            )
        return self._recursive_chunker.run(
            text, domain, file_id, session_id, source_filename
        )

    def _build_qdrant_points(
        self,
        chunks,
        vectors: list[list[float]],
        session_id: str,
    ) -> list[dict[str, Any]]:
        """Build the list of dicts expected by qdrant_client.upsert_points."""
        now = datetime.now(timezone.utc).isoformat()
        points = []
        for chunk, vector in zip(chunks, vectors):
            points.append(
                {
                    "vector": vector,
                    "payload": {
                        "chunk_text": chunk.text,
                        "file_id": chunk.file_id,
                        "session_id": session_id,
                        "chunk_index": chunk.chunk_index,
                        "source_filename": chunk.source_filename,
                        "domain": chunk.domain,
                        "created_at": now,
                    },
                }
            )
        return points
