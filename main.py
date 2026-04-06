import sys
from src.ingestion.ingestion_pipeline import ingestion_pipeline
from src.ingestion.retriever import retrieve


def main():
    if len(sys.argv) < 2:
        print("[Error] Enter a valid github url")
        print("Usage: python main.py <github_repo_url>")
        sys.exit(1)

    url = sys.argv[1]

    result = ingestion_pipeline(url)

    if result is None:
        sys.exit(1)


    query = "What dependencies are listed in requirements.txt?"

    results = retrieve(query, collection_name="blog_generation_app_6da2b180")

    for r in results:
        print("\n---")
        print("Score:", r.score)
        print(r.payload["content"][:300])


if __name__ == "__main__":
    main()