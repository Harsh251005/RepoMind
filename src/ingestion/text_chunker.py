from langchain_text_splitters import RecursiveCharacterTextSplitter


CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def chunk_text_rcts(content: str):
    """
    Chunk text using RecursiveCharacterTextSplitter.

    Designed for:
    - README
    - docs
    - config files
    """

    if not content or not content.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    chunks = splitter.split_text(content)

    # Clean chunks
    return [chunk.strip() for chunk in chunks if chunk.strip()]