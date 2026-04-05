from src.ingestion.cloner import clone_repo
from src.ingestion.document_loader import load_codebase

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Error: Please provide a valid GitHub URL")
        sys.exit(1)

    url = sys.argv[1]
    clone_path, files = clone_repo(url)

    print(f"\nCloned to : {clone_path}")
    print(f"Code files: {len(files)}\n")

    for f in files[:20]:  # Print first 20 so it doesn't flood terminal
        print(f" → {f}")

    if len(files) > 20:
        print(f" ... and {len(files) - 20} more")

    documents = load_codebase([file for file in files])

    for doc in documents:
        print(doc.metadata)

    print(f"DOCUMENTS:\n{documents}")
