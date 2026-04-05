from typing import List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings using OpenAI
    """


    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )

    return [item.embedding for item in response.data]