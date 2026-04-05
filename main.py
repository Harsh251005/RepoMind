import sys
from src.ingestion.ingestion_pipeline import ingestion_pipeline


def main():
    if len(sys.argv) < 2:
        print("[Error] Enter a valid github url")
        print("Usage: python main.py <github_repo_url>")
        sys.exit(1)

    url = sys.argv[1]

    result = ingestion_pipeline(url)

    if result is None:
        sys.exit(1)


if __name__ == "__main__":
    main()