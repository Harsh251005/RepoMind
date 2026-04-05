import re
from typing import List


def chunk_code(content: str, ext: str) -> List[str]:
    """
    Main entry point for code chunking.

    Steps:
    1. Try language-aware chunking
    2. Fallback to structure-based splitting
    3. Enforce chunk size constraints

    Args:
        content (str): Full file content
        ext (str): File extension (e.g., ".py", ".js")

    Returns:
        List[str]: List of code chunks
    """

    if not content or not content.strip():
        return []

    # Step 1: Try language-aware splitting
    try:
        chunks = _chunk_by_language(content, ext)
    except Exception:
        chunks = []

    # Step 2: Fallback if language-based failed or returned nothing
    if not chunks:
        chunks = _split_by_structure(content)

    # Step 3: Enforce size constraints
    chunks = _enforce_chunk_size(chunks)

    return chunks


from typing import List


def _chunk_by_language(content: str, ext: str) -> List[str]:
    """
    Attempts language-aware code chunking using a code-aware splitter.

    Falls back silently if:
    - language is unsupported
    - splitter fails
    """

    language = _map_extension_to_language(ext)

    # If unknown language → skip
    if language == "text":
        return []

    try:
        from code_splitter import CodeSplitter

        splitter = CodeSplitter(language=language)

        chunks = splitter.split_text(content)

        # Basic validation
        if not chunks or not isinstance(chunks, list):
            return []

        return [chunk.strip() for chunk in chunks if chunk.strip()]

    except Exception:
        # Fail silently → fallback will handle
        return []




def _split_by_structure(content: str) -> List[str]:
    """
    Fallback code chunking using simple structural heuristics.

    Splits code based on:
    - function definitions
    - class definitions
    - common keywords across languages

    This is language-agnostic and ensures reasonable chunks
    even when language-aware splitting fails.
    """

    if not content or not content.strip():
        return []

    # Heuristic pattern for common code boundaries
    pattern = r"\n(?=def |class |function |export |public |private |protected )"

    parts = re.split(pattern, content)

    chunks = []

    for part in parts:
        part = part.strip()

        if not part:
            continue

        chunks.append(part)

    return chunks


from typing import List


MAX_CHUNK_SIZE = 1000   # characters
CHUNK_OVERLAP = 150     # characters


def _enforce_chunk_size(chunks: List[str]) -> List[str]:
    """
    Ensures all chunks are within size limits.

    - Keeps small chunks as-is
    - Splits large chunks using sliding window
    """

    final_chunks = []

    for chunk in chunks:
        chunk = chunk.strip()

        if not chunk:
            continue

        # If chunk is within limit → keep as is
        if len(chunk) <= MAX_CHUNK_SIZE:
            final_chunks.append(chunk)
        else:
            # Too large → split further
            split_chunks = _sliding_window(chunk)
            final_chunks.extend(split_chunks)

    return final_chunks


def _sliding_window(text: str) -> List[str]:
    """
    Splits text into overlapping chunks.

    Uses:
    - MAX_CHUNK_SIZE for chunk length
    - CHUNK_OVERLAP to preserve context between chunks
    """

    chunks = []

    text_length = len(text)
    start = 0

    while start < text_length:
        end = start + MAX_CHUNK_SIZE

        chunk = text[start:end]
        chunks.append(chunk)

        # Move forward with overlap
        start += MAX_CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def _map_extension_to_language(ext: str) -> str:
    """
    Maps file extensions to language names understood by the code splitter.

    Returns:
        str: language name (e.g., "python", "javascript")
             or "text" if unsupported
    """

    ext = ext.lower()

    mapping = {
        # Python
        ".py": "python",

        # JavaScript / TypeScript
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",

        # JVM languages
        ".java": "java",
        ".kt": "kotlin",

        # Systems languages
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".h": "cpp",
        ".hpp": "cpp",

        # Others
        ".go": "go",
        ".rs": "rust",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
    }

    return mapping.get(ext, "text")