from typing import List, Union
from src.ingestion.code_chunker import chunk_code, CodeChunk
from src.ingestion.text_chunker import chunk_text, TextChunk
from src.ingestion.document_loader import Document


def chunk_documents(documents: List[Document]) -> List[Document]:
    """
    Routes documents to appropriate chunkers and returns chunked Documents.

    - Code files  → chunk_code()  → CodeChunk (carries start_line, end_line, language)
    - Text files  → chunk_text()  → TextChunk (carries file_type, json_key etc.)

    All chunk metadata is merged into the Document metadata so nothing is lost.
    """

    chunked_docs = []

    for doc in documents:
        doc_type = doc.metadata.get("type")
        ext      = doc.metadata.get("extension", "")
        path     = doc.metadata.get("path", "")

        if not doc.content or not doc.content.strip():
            continue

        if doc_type == "code":
            chunks: List[Union[CodeChunk, TextChunk]] = chunk_code(
                doc.content, ext, file_path=path
            )
        else:
            chunks = chunk_text(
                doc.content, ext, file_path=path
            )

        if not chunks:
            continue

        for chunk in chunks:
            # Pull all fields off the chunk dataclass into metadata
            chunk_metadata = _extract_chunk_metadata(chunk)

            chunked_docs.append(Document(
                content  = chunk.content,
                metadata = {
                    **doc.metadata,       # original doc metadata (filename, path, type…)
                    **chunk_metadata,     # chunk-specific metadata (lines, language…)
                },
            ))

    return chunked_docs


def _extract_chunk_metadata(chunk: Union[CodeChunk, TextChunk]) -> dict:
    """
    Extracts serialisable metadata from a CodeChunk or TextChunk.
    Keeps only fields that are useful downstream in the vector store.
    """

    base = {
        "chunk_index": chunk.chunk_index,
        "chunk_type":  type(chunk).__name__,   # "CodeChunk" or "TextChunk"
    }

    if isinstance(chunk, CodeChunk):
        base.update({
            "language":   chunk.language,
            "start_line": chunk.start_line,
            "end_line":   chunk.end_line,
        })

    if isinstance(chunk, TextChunk):
        base.update({
            "file_type": chunk.file_type,   # "markdown" | "structured" | "text"
        })

    # Merge any extra metadata the chunk carries (e.g. json_key, sub_chunk_index)
    if chunk.metadata:
        base.update(chunk.metadata)

    return base