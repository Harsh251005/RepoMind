from typing import List
from qdrant_client import QdrantClient
from openai import OpenAI


client = OpenAI()


def embed_query(query: str) -> List[float]:
    """
    Convert query into embedding
    """
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )

    return response.data[0].embedding


def retrieve(
    query: str,
    collection_name: str,
    top_k: int = 5,
):
    """
    Retrieve top-k relevant chunks from Qdrant
    """

    qdrant = QdrantClient(host="localhost", port=6333)

    query_vector = embed_query(query)

    response = qdrant.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
    )

    results = response.points

    return results