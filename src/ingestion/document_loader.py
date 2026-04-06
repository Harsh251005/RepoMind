from dataclasses import dataclass
from typing import List
from pathlib import Path
from src.ingestion.cloner import CODE_EXTENSIONS


@dataclass
class Document:
    content: str
    metadata: dict


def load_codebase(file_paths: List[str]) -> List[Document]:
    """
    Loads code files into structured Document objects.

    Each document contains:
    - content: file content
    - metadata: file path, extension, filename, type
    """

    documents = []

    for path in file_paths:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            documents.append(
                Document(
                    content=content,
                    metadata={
                        "path": path,
                        "filename": Path(path).name,
                        "extension": Path(path).suffix,
                        "type": "code" if Path(path).suffix in CODE_EXTENSIONS else "text"
                    }
                )
            )

        except Exception as e:
            # Skip problematic files but don't crash pipeline
            print(f"[Loader] Skipped {path}: {e}")

    return documents