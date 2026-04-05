from typing import List
from src.ingestion.code_chunker import chunk_code
from src.ingestion.text_chunker import chunk_text_rcts
from src.ingestion.document_loader import Document


def chunk_documents(documents: List[Document]) -> List[Document]:
    """
    Routes documents to appropriate chunkers (code/text)
    and returns chunked Document objects.
    """

    chunked_docs = []

    for doc in documents:
        doc_type = doc.metadata.get("type")
        ext = doc.metadata.get("extension")

        if not doc.content:
            continue

        # Route based on type
        if doc_type == "code":
            doc_chunks = chunk_code(doc.content, ext)
        else:
            doc_chunks = chunk_text_rcts(doc.content)

        if not doc_chunks:
            continue

        for i, chunk in enumerate(doc_chunks):
            chunked_docs.append(
                Document(
                    content=chunk,
                    metadata={
                        **doc.metadata,
                        "chunk_id": i,
                    }
                )
            )

    return chunked_docs


from typing import List
from src.ingestion.document_loader import Document


def documents_to_texts(documents: List[Document]) -> List[str]:
    """
    Convert Document objects into enriched text for better embeddings.
    """

    texts = []

    for doc in documents:
        if not doc.content or not doc.content.strip():
            continue

        metadata = doc.metadata

        enriched_text = f"""
        File: {metadata.get("filename")}
        Path: {metadata.get("path")}
        Type: {metadata.get("type")}
        
        Content:
        {doc.content}
"""

        texts.append(enriched_text.strip())

    return texts