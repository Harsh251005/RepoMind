# text_enricher.py

from typing import List
from src.ingestion.document_loader import Document


def documents_to_texts(documents: List[Document]) -> List[str]:
    """
    Converts Document objects to enriched strings for embedding.

    Enrichment strategy differs by chunk type:
    - CodeChunk  : includes language + line range so the LLM has full context
    - TextChunk  : includes file type + optional json_key for structured files
    - Fallback   : just filename + path

    Richer text at embedding time = better semantic retrieval.
    """

    texts = []

    for doc in documents:
        if not doc.content or not doc.content.strip():
            continue

        meta         = doc.metadata
        chunk_type   = meta.get("chunk_type", "")
        enriched     = _build_enriched_text(doc.content, meta, chunk_type)

        texts.append(enriched)

    return texts


def _build_enriched_text(content: str, meta: dict, chunk_type: str) -> str:

    filename = meta.get("filename", "unknown")
    path     = meta.get("path", "")
    idx      = meta.get("chunk_index", 0)

    if chunk_type == "CodeChunk":
        language   = meta.get("language", "unknown")
        start_line = meta.get("start_line", "?")
        end_line   = meta.get("end_line", "?")

        header = (
            f"File: {filename}\n"
            f"Path: {path}\n"
            f"Language: {language}\n"
            f"Lines: {start_line}–{end_line}\n"
            f"Chunk: {idx}"
        )

    elif chunk_type == "TextChunk":
        file_type = meta.get("file_type", "text")
        json_key  = meta.get("json_key")

        header = (
            f"File: {filename}\n"
            f"Path: {path}\n"
            f"Type: {file_type}\n"
        )
        if json_key:
            header += f"Section: {json_key}\n"
        header += f"Chunk: {idx}"

    else:
        header = (
            f"File: {filename}\n"
            f"Path: {path}\n"
            f"Chunk: {idx}"
        )

    return f"{header}\n\nContent:\n{content}"