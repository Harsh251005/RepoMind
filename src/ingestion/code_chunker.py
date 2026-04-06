import re
import ast
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_CHUNK_SIZE = 1500       # characters — raised to fit real-world functions
CHUNK_OVERLAP  = 200        # characters
MIN_CHUNK_SIZE = 30         # characters — anything below this is noise


# ─── Data Model ───────────────────────────────────────────────────────────────

@dataclass
class CodeChunk:
    content:     str
    file_path:   str          = ""
    language:    str          = "text"
    start_line:  int          = 0
    end_line:    int          = 0
    chunk_index: int          = 0
    metadata:    dict         = field(default_factory=dict)

    def is_valid(self) -> bool:
        return bool(self.content.strip()) and len(self.content.strip()) >= MIN_CHUNK_SIZE


# ─── Public Entry Point ───────────────────────────────────────────────────────

def chunk_code(content: str, ext: str, file_path: str = "") -> List[CodeChunk]:
    """
    Main entry point for code chunking.

    Pipeline:
    1. AST-based splitting  (Python only, most accurate)
    2. Tree-sitter splitting (multi-language, accurate)
    3. Structure-based splitting (heuristic fallback)
    4. Enforce size constraints on all chunks
    5. Filter noise chunks

    Args:
        content   : Full file content as string
        ext       : File extension e.g. ".py", ".js"
        file_path : Source file path — stored in chunk metadata

    Returns:
        List[CodeChunk]
    """

    if not content or not content.strip():
        return []

    language = _map_extension_to_language(ext)
    chunks: List[CodeChunk] = []

    # Step 1 — Python AST (most reliable for .py files)
    if language == "python":
        chunks = _chunk_python_ast(content, file_path)
        if chunks:
            logger.debug(f"AST chunking produced {len(chunks)} chunks for {file_path}")

    # Step 2 — Tree-sitter (for all other supported languages)
    if not chunks and language != "text":
        chunks = _chunk_tree_sitter(content, language, file_path)
        if chunks:
            logger.debug(f"Tree-sitter chunking produced {len(chunks)} chunks for {file_path}")

    # Step 3 — Structural heuristic fallback
    if not chunks:
        logger.warning(f"Falling back to structural chunking for {file_path} (lang={language})")
        chunks = _chunk_by_structure(content, language, file_path)

    # Step 4 — Enforce size limits
    chunks = _enforce_chunk_size(chunks)

    # Step 5 — Filter noise
    chunks = [c for c in chunks if c.is_valid()]

    # Re-index after filtering
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i

    return chunks


# ─── Strategy 1: Python AST ───────────────────────────────────────────────────

def _chunk_python_ast(content: str, file_path: str) -> List[CodeChunk]:
    """
    Uses Python's built-in AST to extract top-level and nested definitions.

    Captures:
    - Module-level functions (including decorators)
    - Classes (as a single chunk with all their methods)
    - Falls back the remaining module-level code as one chunk
    """

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.warning(f"AST parse failed for {file_path}: {e}")
        return []

    lines = content.splitlines(keepends=True)
    chunks: List[CodeChunk] = []
    covered_lines = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        # Only top-level nodes (parent is Module)
        # We check this by confirming no parent function/class wraps it
        # ast.walk doesn't give parents, so we limit to top-level by line depth
        if not _is_top_level(node, tree):
            continue

        # Include decorator lines — this is the key fix for orphaned decorators
        start = _get_decorator_start(node) - 1   # 0-indexed
        end   = node.end_lineno                   # 1-indexed inclusive

        chunk_lines = lines[start:end]
        chunk_content = "".join(chunk_lines).strip()

        if not chunk_content:
            continue

        chunks.append(CodeChunk(
            content    = chunk_content,
            file_path  = file_path,
            language   = "python",
            start_line = start + 1,
            end_line   = end,
        ))

        covered_lines.update(range(start, end))

    # Collect module-level code not part of any top-level definition
    remaining_lines = [
        line for i, line in enumerate(lines)
        if i not in covered_lines
    ]
    remaining = "".join(remaining_lines).strip()

    if remaining and len(remaining) >= MIN_CHUNK_SIZE:
        chunks.append(CodeChunk(
            content    = remaining,
            file_path  = file_path,
            language   = "python",
            start_line = 1,
            end_line   = len(lines),
            metadata   = {"type": "module_level"},
        ))

    return chunks


def _is_top_level(node: ast.AST, tree: ast.Module) -> bool:
    """Returns True if node is a direct child of the module."""
    return node in ast.walk(tree) and node in tree.body


def _get_decorator_start(node) -> int:
    """Returns the line number of the first decorator, or the node itself."""
    if node.decorator_list:
        return node.decorator_list[0].lineno
    return node.lineno


# ─── Strategy 2: Tree-sitter ──────────────────────────────────────────────────

def _chunk_tree_sitter(content: str, language: str, file_path: str) -> List[CodeChunk]:
    """
    Uses tree-sitter to parse and extract function/class/method nodes.

    Requires: pip install tree-sitter tree-sitter-languages

    Node types targeted per language:
    - function_definition, class_definition (Python-like)
    - function_declaration, method_definition (JS/TS)
    - method_declaration (Java, C#)
    """

    try:
        from tree_sitter_languages import get_language, get_parser

        ts_language = get_language(language)
        parser      = get_parser(language)

    except ImportError:
        logger.warning("tree-sitter-languages not installed. Skipping tree-sitter chunking.")
        return []
    except Exception as e:
        logger.warning(f"Tree-sitter setup failed for language '{language}': {e}")
        return []

    try:
        tree  = parser.parse(bytes(content, "utf-8"))
        lines = content.splitlines(keepends=True)

        target_node_types = {
            "function_definition", "async_function_definition",
            "function_declaration", "async_function_declaration",
            "class_definition", "class_declaration",
            "method_definition", "method_declaration",
            "arrow_function",
        }

        chunks: List[CodeChunk] = []
        seen_ranges: List[tuple] = []

        def traverse(node):
            if node.type in target_node_types:
                start_line = node.start_point[0]     # 0-indexed
                end_line   = node.end_point[0] + 1   # 0-indexed end, make exclusive

                # Skip if already covered by a parent node
                if any(s <= start_line and end_line <= e for s, e in seen_ranges):
                    return

                chunk_content = "".join(lines[start_line:end_line]).strip()

                if chunk_content and len(chunk_content) >= MIN_CHUNK_SIZE:
                    chunks.append(CodeChunk(
                        content    = chunk_content,
                        file_path  = file_path,
                        language   = language,
                        start_line = start_line + 1,
                        end_line   = end_line,
                    ))
                    seen_ranges.append((start_line, end_line))

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return chunks

    except Exception as e:
        logger.warning(f"Tree-sitter parsing failed for {file_path}: {e}")
        return []


# ─── Strategy 3: Structural Heuristic Fallback ───────────────────────────────

def _chunk_by_structure(content: str, language: str, file_path: str) -> List[CodeChunk]:
    """
    Language-agnostic fallback using blank lines + indentation heuristics.

    Logic:
    - Splits on double newlines (paragraph-style natural boundaries)
    - Further splits on common definition keywords only at line-start
      (not mid-code occurrences like 'public' as a field modifier)

    Overlap is applied here too for consistency with the sliding window.
    """

    if not content or not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    chunks: List[CodeChunk] = []
    current_block: List[str] = []
    current_start = 1

    # Keywords that signal a new top-level block — only when at column 0
    top_level_keywords = re.compile(
        r"^(def |async def |class |function |export (default |async )?function |"
        r"public (static |final |abstract )?(class |void |int |String )|"
        r"private |protected |func |fn |impl |struct |enum )"
    )

    def flush_block(end_line: int):
        nonlocal current_start
        block = "".join(current_block).strip()
        if block and len(block) >= MIN_CHUNK_SIZE:
            chunks.append(CodeChunk(
                content    = block,
                file_path  = file_path,
                language   = language,
                start_line = current_start,
                end_line   = end_line,
            ))
        current_block.clear()
        current_start = end_line + 1

    for i, line in enumerate(lines, start=1):
        is_new_block = (
            top_level_keywords.match(line)
            and current_block                # don't split on very first block
            and "".join(current_block).strip()
        )

        if is_new_block:
            flush_block(i - 1)

        current_block.append(line)

    # Flush remaining
    if current_block:
        flush_block(len(lines))

    return chunks


# ─── Size Enforcement ─────────────────────────────────────────────────────────

def _enforce_chunk_size(chunks: List[CodeChunk]) -> List[CodeChunk]:
    """
    Splits chunks that exceed MAX_CHUNK_SIZE using a line-aware sliding window.

    Line-awareness ensures we never cut mid-line — unlike the old char-slicing.
    """

    final_chunks: List[CodeChunk] = []

    for chunk in chunks:
        if len(chunk.content) <= MAX_CHUNK_SIZE:
            final_chunks.append(chunk)
        else:
            sub_chunks = _line_aware_sliding_window(chunk)
            final_chunks.extend(sub_chunks)

    return final_chunks


def _line_aware_sliding_window(chunk: CodeChunk) -> List[CodeChunk]:
    """
    Splits a large chunk into overlapping sub-chunks on line boundaries.

    Unlike raw character slicing, this always breaks at newlines so
    no line of code is ever cut in the middle.
    """

    lines       = chunk.content.splitlines(keepends=True)
    sub_chunks: List[CodeChunk] = []
    start_idx   = 0
    sub_index   = 0

    while start_idx < len(lines):
        accumulated = []
        char_count  = 0
        end_idx     = start_idx

        # Consume lines until we hit the size limit
        while end_idx < len(lines):
            line = lines[end_idx]
            if char_count + len(line) > MAX_CHUNK_SIZE and accumulated:
                break
            accumulated.append(line)
            char_count += len(line)
            end_idx    += 1

        content = "".join(accumulated).strip()

        if content and len(content) >= MIN_CHUNK_SIZE:
            sub_chunks.append(CodeChunk(
                content    = content,
                file_path  = chunk.file_path,
                language   = chunk.language,
                start_line = chunk.start_line + start_idx,
                end_line   = chunk.start_line + end_idx - 1,
                metadata   = {**chunk.metadata, "sub_chunk_index": sub_index},
            ))
            sub_index += 1

        # Move forward, backing up CHUNK_OVERLAP worth of characters for overlap
        overlap_chars = 0
        overlap_lines = 0
        for line in reversed(accumulated):
            if overlap_chars >= CHUNK_OVERLAP:
                break
            overlap_chars += len(line)
            overlap_lines += 1

        next_start = end_idx - overlap_lines
        if next_start <= start_idx:
            next_start = start_idx + 1   # safety: always advance

        start_idx = next_start

    return sub_chunks


# ─── Language Mapping ─────────────────────────────────────────────────────────

def _map_extension_to_language(ext: str) -> str:
    """
    Maps file extensions to language identifiers.
    Both AST and tree-sitter strategies use these names.
    """

    mapping = {
        ".py":   "python",
        ".js":   "javascript",
        ".jsx":  "javascript",
        ".ts":   "typescript",
        ".tsx":  "typescript",
        ".java": "java",
        ".kt":   "kotlin",
        ".c":    "c",
        ".cpp":  "cpp",
        ".cc":   "cpp",
        ".h":    "cpp",
        ".hpp":  "cpp",
        ".go":   "go",
        ".rs":   "rust",
        ".cs":   "c_sharp",
        ".rb":   "ruby",
        ".php":  "php",
        ".swift":"swift",
    }

    return mapping.get(ext.lower(), "text")