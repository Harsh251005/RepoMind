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

    texts = [doc.content for doc in documents]

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
