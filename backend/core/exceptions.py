"""Domain exceptions with HTTP status codes and machine-readable error codes.

Each class maps 1:1 to an error code from PRD Section 13.2.
FastAPI exception handlers in main.py catch these and return the standard
error envelope: {error, error_code, details}.
"""

from typing import Any


class AppError(Exception):
    """Base class for all application errors.

    Args:
        message: Human-readable error message.
        error_code: Machine-readable code (PRD Section 13.2).
        http_status: HTTP status code to return.
        details: Optional additional context.
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        http_status: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        self.details = details or {}


class InvalidDomainError(AppError):
    def __init__(self, domain: str) -> None:
        super().__init__(
            message=f"Domain '{domain}' is not valid. Must be 'finance' or 'law'.",
            error_code="INVALID_DOMAIN",
            http_status=400,
            details={"received": domain},
        )


class InvalidFileTypeError(AppError):
    def __init__(self, domain: str, filename: str) -> None:
        super().__init__(
            message=f"File type not permitted for domain '{domain}'.",
            error_code="INVALID_FILE_TYPE",
            http_status=400,
            details={"domain": domain, "filename": filename},
        )


class MissingRequiredColumnsError(AppError):
    def __init__(self, missing: list[str], found_columns: list[str] | None = None) -> None:
        details = {"missing_columns": missing}
        if found_columns is not None:
            details["found_columns"] = found_columns
            
        super().__init__(
            message=f"CSV missing required columns: {', '.join(missing)}.",
            error_code="MISSING_REQUIRED_COLUMNS",
            http_status=400,
            details=details,
        )


class EmptyFileError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="Uploaded file has 0 bytes or 0 parseable rows.",
            error_code="EMPTY_FILE",
            http_status=400,
        )


class ParseError(AppError):
    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(
            message=f"Failed to parse file '{filename}': {reason}.",
            error_code="PARSE_ERROR",
            http_status=400,
            details={"filename": filename, "reason": reason},
        )


class SessionNotFoundError(AppError):
    def __init__(self, session_id: str) -> None:
        super().__init__(
            message=f"Session '{session_id}' not found.",
            error_code="SESSION_NOT_FOUND",
            http_status=404,
            details={"session_id": session_id},
        )


class FileNotFoundError(AppError):
    def __init__(self, file_id: str) -> None:
        super().__init__(
            message=f"File '{file_id}' not found.",
            error_code="FILE_NOT_FOUND",
            http_status=404,
            details={"file_id": file_id},
        )


class FileSessionMismatchError(AppError):
    def __init__(self, file_id: str, session_id: str) -> None:
        super().__init__(
            message="File does not belong to the provided session.",
            error_code="FILE_SESSION_MISMATCH",
            http_status=403,
            details={"file_id": file_id, "session_id": session_id},
        )


class FolderNotFoundError(AppError):
    def __init__(self, folder_id: str) -> None:
        super().__init__(
            message=f"Folder '{folder_id}' not found.",
            error_code="FOLDER_NOT_FOUND",
            http_status=404,
            details={"folder_id": folder_id},
        )


class FolderPermissionError(AppError):
    def __init__(self, action: str) -> None:
        super().__init__(
            message=f"Not permitted to {action} this folder.",
            error_code="FOLDER_PERMISSION_DENIED",
            http_status=403,
            details={"action": action},
        )


class FolderCycleError(AppError):
    def __init__(self, folder_id: str, parent_id: str) -> None:
        super().__init__(
            message="Cannot move a folder into one of its descendants.",
            error_code="FOLDER_MOVE_CYCLE",
            http_status=400,
            details={"folder_id": folder_id, "parent_id": parent_id},
        )


class FileTooLargeError(AppError):
    def __init__(self, size_bytes: int, limit_mb: int) -> None:
        super().__init__(
            message=f"File exceeds the {limit_mb} MB size limit.",
            error_code="FILE_TOO_LARGE",
            http_status=413,
            details={"size_bytes": size_bytes, "limit_mb": limit_mb},
        )


class IngestionFailedError(AppError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Ingestion failed: {reason}.",
            error_code="INGESTION_FAILED",
            http_status=500,
            details={"reason": reason},
        )


class StorageWriteFailedError(AppError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Supabase Storage upload failed: {reason}.",
            error_code="STORAGE_WRITE_FAILED",
            http_status=500,
            details={"reason": reason},
        )


class DatabaseError(AppError):
    def __init__(self, operation: str, reason: str) -> None:
        super().__init__(
            message=f"Database error during '{operation}': {reason}.",
            error_code="DATABASE_ERROR",
            http_status=500,
            details={"operation": operation, "reason": reason},
        )


class LLMUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            message="All LLM providers unavailable. Please try again shortly.",
            error_code="LLM_UNAVAILABLE",
            http_status=503,
            details={"retry_after_seconds": 30},
        )


class EmbeddingServiceUnavailableError(AppError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Embedding service unreachable: {reason}.",
            error_code="EMBEDDING_SERVICE_UNAVAILABLE",
            http_status=503,
            details={"reason": reason},
        )
