"""Text chunkers for ingestion pipeline.

Two strategies (PRD Sections 3.1 and 10.3):
  - RecursiveCharChunker: general purpose, used for Finance CSV text and TXT
  - LegalChunker: attempts section-aware splitting for law documents, with
    automatic fallback to RecursiveCharChunker when chunks are out of range
"""

import dataclasses
import re
import logging

import tiktoken

from config import settings

logger = logging.getLogger(__name__)

_SECTION_HEADER_PATTERN = re.compile(
    r"(?m)^(Section|SECTION|Article|ARTICLE)\s+\d+",
)

# Tiktoken encoder for approximate token counting (PRD 7.4)
_ENCODER: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _ENCODER
    if _ENCODER is None:
        # cl100k_base is a safe general-purpose encoding for token approximation
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def _token_count(text: str) -> int:
    return len(_get_encoder().encode(text))


@dataclasses.dataclass
class Chunk:
    """A unit of text ready for embedding and Qdrant storage."""

    text: str
    chunk_index: int
    domain: str
    file_id: str
    session_id: str
    source_filename: str


# ---------------------------------------------------------------------------
# Recursive character chunker  (PRD 3.1)
# ---------------------------------------------------------------------------


class RecursiveCharChunker:
    """Split text by characters with overlap.

    Splitting hierarchy (character-level, approximate):
      paragraph → sentence → word boundary

    chunk_size and overlap are in *tokens* (measured via tiktoken).
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def run(
        self,
        text: str,
        domain: str,
        file_id: str,
        session_id: str,
        source_filename: str,
    ) -> list[Chunk]:
        raw_chunks = self._split(text)
        return [
            Chunk(
                text=raw,
                chunk_index=i,
                domain=domain,
                file_id=file_id,
                session_id=session_id,
                source_filename=source_filename,
            )
            for i, raw in enumerate(raw_chunks)
        ]

    def _split(self, text: str) -> list[str]:
        """Split text into token-bounded chunks with overlap."""
        encoder = _get_encoder()
        tokens = encoder.encode(text)
        chunks: list[str] = []
        start = 0

        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = encoder.decode(chunk_tokens).strip()
            if chunk_text:
                chunks.append(chunk_text)
            if end == len(tokens):
                break
            start = end - self.chunk_overlap  # overlap step back

        return chunks


# ---------------------------------------------------------------------------
# Legal section-aware chunker  (PRD 10.3)
# ---------------------------------------------------------------------------


class LegalChunker:
    """Attempt section-header-based splitting of legal documents.

    If section splitting produces any chunk with < 100 or > 600 tokens,
    falls back to RecursiveCharChunker for the whole document.
    Each chunk prefixes the detected section header (PRD 10.3).
    """

    _MIN_TOKENS = 100
    _MAX_TOKENS = 600
    _FALLBACK_CHUNK_SIZE = 512
    _FALLBACK_OVERLAP = 64

    def run(
        self,
        text: str,
        domain: str,
        file_id: str,
        session_id: str,
        source_filename: str,
    ) -> list[Chunk]:
        sections = self._split_by_sections(text)

        if not sections or not self._all_within_bounds(sections):
            logger.debug(
                "Legal section chunking out of bounds for '%s' — falling back",
                source_filename,
            )
            fallback = RecursiveCharChunker(
                chunk_size=self._FALLBACK_CHUNK_SIZE,
                chunk_overlap=self._FALLBACK_OVERLAP,
            )
            return fallback.run(text, domain, file_id, session_id, source_filename)

        return [
            Chunk(
                text=section,
                chunk_index=i,
                domain=domain,
                file_id=file_id,
                session_id=session_id,
                source_filename=source_filename,
            )
            for i, section in enumerate(sections)
        ]

    def _split_by_sections(self, text: str) -> list[str]:
        """Split text on section headers. Each chunk includes its header."""
        matches = list(_SECTION_HEADER_PATTERN.finditer(text))
        if not matches:
            return []

        sections: list[str] = []
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()
            if section_text:
                sections.append(section_text)

        return sections

    def _all_within_bounds(self, sections: list[str]) -> bool:
        for section in sections:
            count = _token_count(section)
            if count < self._MIN_TOKENS or count > self._MAX_TOKENS:
                return False
        return True
