import json
import logging
from dataclasses import dataclass, field
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

PROSE_CHUNK_SIZE    = 1200
PROSE_CHUNK_OVERLAP = 200
MIN_CHUNK_SIZE      = 40    # anything below is noise

STRUCTURED_CHUNK_SIZE    = 800
STRUCTURED_CHUNK_OVERLAP = 100


# ─── Data Model ───────────────────────────────────────────────────────────────

@dataclass
class TextChunk:
    content:     str
    file_path:   str  = ""
    file_type:   str  = "text"    # "prose" | "structured" | "markdown"
    chunk_index: int  = 0
    metadata:    dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        return bool(self.content.strip()) and len(self.content.strip()) >= MIN_CHUNK_SIZE


# ─── Public Entry Point ───────────────────────────────────────────────────────

def chunk_text(content: str, ext: str, file_path: str = "") -> List[TextChunk]:
    """
    Chunks non-code text files with a strategy appropriate to file type.

    Routes:
    - .md / .rst / .txt / .mdx  → markdown-aware prose chunking
    - .json                      → JSON-aware structural chunking
    - .yaml / .toml / .env / .ini → block-based structural chunking
    - everything else            → generic prose chunking
    """

    if not content or not content.strip():
        return []

    ext = ext.lower()

    if ext in {".md", ".mdx", ".rst", ".txt", ".markdown"}:
        chunks = _chunk_prose(content, file_path, file_type="markdown")

    elif ext == ".json":
        chunks = _chunk_json(content, file_path)

    elif ext in {".yaml", ".yml", ".toml", ".env", ".ini", ".cfg"}:
        chunks = _chunk_config_blocks(content, file_path)

    else:
        chunks = _chunk_prose(content, file_path, file_type="text")

    # Filter noise
    chunks = [c for c in chunks if c.is_valid()]

    # Re-index
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i

    return chunks


# ─── Strategy 1: Prose / Markdown ─────────────────────────────────────────────

def _chunk_prose(content: str, file_path: str, file_type: str) -> List[TextChunk]:
    """
    Prose chunking using paragraph → sentence → word hierarchy.

    Separator order matters:
    - Double newline  : paragraph boundary (strongest semantic unit)
    - Single newline  : line break within a paragraph
    - Space           : word boundary (last resort)

    Period intentionally excluded — sentences are weak boundaries for docs.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size    = PROSE_CHUNK_SIZE,
        chunk_overlap = PROSE_CHUNK_OVERLAP,
        separators    = ["\n\n", "\n", " ", ""],
    )

    raw_chunks = splitter.split_text(content)

    return [
        TextChunk(
            content   = chunk.strip(),
            file_path = file_path,
            file_type = file_type,
        )
        for chunk in raw_chunks
        if chunk.strip()
    ]


# ─── Strategy 2: JSON ─────────────────────────────────────────────────────────

def _chunk_json(content: str, file_path: str) -> List[TextChunk]:
    """
    Chunks JSON files by top-level keys.

    Each top-level key becomes its own chunk — preserves logical grouping.
    Falls back to prose chunking if JSON is invalid or flat (non-dict).
    """

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON at {file_path}: {e}. Falling back to prose.")
        return _chunk_prose(content, file_path, file_type="structured")

    if not isinstance(parsed, dict):
        # JSON array or scalar — treat as prose
        return _chunk_prose(content, file_path, file_type="structured")

    chunks = []
    for key, value in parsed.items():
        chunk_content = json.dumps({key: value}, indent=2)
        chunks.append(TextChunk(
            content   = chunk_content,
            file_path = file_path,
            file_type = "structured",
            metadata  = {"json_key": key},
        ))

        # If a single key's value is itself too large, further split it
        if len(chunk_content) > STRUCTURED_CHUNK_SIZE:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size    = STRUCTURED_CHUNK_SIZE,
                chunk_overlap = STRUCTURED_CHUNK_OVERLAP,
                separators    = ["\n", ", ", " ", ""],
            )
            sub_chunks = splitter.split_text(chunk_content)
            chunks.pop()   # remove the oversized one
            chunks.extend([
                TextChunk(
                    content   = sc.strip(),
                    file_path = file_path,
                    file_type = "structured",
                    metadata  = {"json_key": key, "split": True},
                )
                for sc in sub_chunks if sc.strip()
            ])

    return chunks


# ─── Strategy 3: Config Block Splitting ───────────────────────────────────────

def _chunk_config_blocks(content: str, file_path: str) -> List[TextChunk]:
    """
    Chunks YAML/TOML/INI/ENV files by top-level blocks.

    A "block" is a group of lines that belongs to one top-level key.
    Detected by: non-indented, non-comment, non-empty lines that start a new section.

    Example — this YAML gets 2 chunks, not split mid-block:
        database:
          host: localhost
          port: 5432

        server:
          port: 8080
    """

    lines  = content.splitlines(keepends=True)
    chunks: List[TextChunk] = []
    current_block: List[str] = []

    def flush():
        block = "".join(current_block).strip()
        if block:
            chunks.append(TextChunk(
                content   = block,
                file_path = file_path,
                file_type = "structured",
            ))
        current_block.clear()

    for line in lines:
        stripped = line.strip()

        is_top_level_key = (
            stripped
            and not stripped.startswith("#")          # not a comment
            and not line[0].isspace()                 # not indented
            and not stripped.startswith("-")          # not a list item
            and (":" in stripped or "=" in stripped)  # looks like a key
        )

        if is_top_level_key and current_block:
            flush()

        current_block.append(line)

    flush()

    # If any config block is still too large, prose-split it further
    final: List[TextChunk] = []
    for chunk in chunks:
        if len(chunk.content) <= STRUCTURED_CHUNK_SIZE:
            final.append(chunk)
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size    = STRUCTURED_CHUNK_SIZE,
                chunk_overlap = STRUCTURED_CHUNK_OVERLAP,
                separators    = ["\n\n", "\n", " ", ""],
            )
            for sc in splitter.split_text(chunk.content):
                if sc.strip():
                    final.append(TextChunk(
                        content   = sc.strip(),
                        file_path = file_path,
                        file_type = "structured",
                        metadata  = {"split": True},
                    ))

    return final