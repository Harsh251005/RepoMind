from typing import List
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

from src.ingestion.document_loader import Document
from src.ingestion.chunks_embedder import embed_texts


def create_qdrant_collection(client: QdrantClient, collection_name: str, vector_size: int):
    """
    Creates collection if not exists
    """
    collections = client.get_collections().collections
    existing = [c.name for c in collections]

    if collection_name in existing:
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )


def store_in_qdrant(
    documents: List[Document],
    collection_name: str,
):
    """
    Converts documents → embeddings → stores in Qdrant
    """

    qdrant = QdrantClient(host="localhost", port=6333)

    texts = prepare_text_for_embedding(documents)

    # Generate embeddings
    embeddings = embed_texts(texts)

    vector_size = len(embeddings[0])

    # Create collection if needed
    create_qdrant_collection(qdrant, collection_name, vector_size)

    points = []

    for doc, vector in zip(documents, embeddings):
        payload = {
            "content": doc.content,
            "path": doc.metadata.get("path"),
            "filename": doc.metadata.get("filename"),
            "extension": doc.metadata.get("extension"),
            "type": doc.metadata.get("type"),
            "chunk_id": doc.metadata.get("chunk_id"),
        }

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload,
            )
        )

    qdrant.upsert(
        collection_name=collection_name,
        points=points,
    )


def prepare_text_for_embedding(documents):
    texts = []

    for doc in documents:
        content = doc.content
        metadata = doc.metadata

        if not content or not content.strip():
            continue

        filename = metadata.get("filename")
        ext = metadata.get("extension")

        description = get_file_description(ext, filename)

        enriched_text = f"""
        File: {filename}\n
        Type: {ext}\n
        Description: {description}\n
        Content:\n{content}
"""

        texts.append(enriched_text.strip())

    return texts


def get_file_description(ext: str, filename: str) -> str:
    ext = ext.lower()

    if ext in {".py", ".js", ".ts", ".java", ".cpp", ".go", ".rs"}:
        return "Source code file containing application logic and functions."

    elif ext in {".md", ".rst"}:
        return "Documentation file describing the project, usage, or setup."

    elif ext in {".txt"}:
        if "requirements" in filename.lower():
            return "List of project dependencies and libraries."
        return "Text file containing project-related information."

    elif ext in {".json", ".yaml", ".yml", ".toml"}:
        return "Configuration file defining project settings or dependencies."

    else:
        return "Project file."