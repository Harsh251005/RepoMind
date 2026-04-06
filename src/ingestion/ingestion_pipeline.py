import time
from src.ingestion.cloner import clone_repo
from src.ingestion.document_loader import load_codebase
from src.ingestion.chunker_pipeline import chunk_documents
from src.ingestion.chunks_embedder import embed_texts
from src.ingestion.text_enricher import documents_to_texts
from src.ingestion.vector_store import store_in_qdrant


def ingestion_pipeline(repo_url: str):
    """
    End-to-end ingestion pipeline:
    clone → load → chunk → embed → vector_store
    """

    try:
        start_time = time.time()

        print(f"\n[Step 1] Cloning {repo_url}")
        collection_name, clone_path, files = clone_repo(repo_url)
        print(f"[✓] Cloned to: {clone_path}")
        print(f"[✓] Files found: {len(files)}\n")

        print("[Step 2] Loading documents...")
        documents = load_codebase(files)
        print(f"[✓] Documents created: {len(documents)}\n")

        print("[Step 3] Chunking documents...")
        chunks = chunk_documents(documents)
        print(f"[✓] Chunks created: {len(chunks)}\n")

        print("[Step 4] Converting documents into list of strings for embeddings...")
        text_documents = documents_to_texts(chunks)
        print(f"[✓] Documents successfully converted into text...\n")

        print("[Step 5] Embedding text documents...")
        embeddings = embed_texts(text_documents)
        print(f"[✓] Embeddings created...\n")

        print("[Step 6] Storing embeddings into vector store...")
        vector_store = store_in_qdrant(documents=chunks, collection_name=collection_name)
        print(f"[✓] Stored data in Qdrant...")

        total_time = time.time() - start_time
        print(f"[Done] Total time: {total_time:.2f}s\n")

        return {
            "repo_path": clone_path,
            "documents": documents,
            "chunks": chunks,
        }

    except Exception as e:
        print(f"[Error] Ingestion failed: {e}")
        return None