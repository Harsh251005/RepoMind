import os
import re
import hashlib
import shutil
from pathlib import Path
from typing import List, Tuple
import git
from git import GitCommandError

BASE_CLONE_DIR = os.path.join(os.getcwd(), "repo_cache")  # persistent folder

# All extensions we consider "code files"
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",  # Python, JavaScript, TypeScript
    ".java", ".kt",  # JVM
    ".go",  # Go
    ".rs",  # Rust
    ".cpp", ".cc", ".c", ".h", ".hpp",  # C/C++
    ".cs",  # C#
    ".rb",  # Ruby
    ".php",  # PHP
    ".swift",  # Swift
}

TEXT_EXTENSIONS = {
    ".md", ".txt", ".rst",
    ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg"
}

ALL_EXTENSIONS = CODE_EXTENSIONS | TEXT_EXTENSIONS

# Folders that are never worth indexing
EXCLUDED_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", "dist", "build", ".next", ".nuxt", "coverage",
    ".pytest_cache", ".mypy_cache", "migrations",
}


def clone_repo(github_url: str, force_refresh: bool = False) -> Tuple[str, str, List[str]]:
    """
    Clone repo with caching.

    - Same repo → same path
    - Avoids re-cloning unless forced
    """

    os.makedirs(BASE_CLONE_DIR, exist_ok=True)

    collection_name = generate_collection_name(github_url)

    repo_name = github_url.rstrip("/").split("/")[-1].replace(".git", "")
    clone_path = os.path.join(BASE_CLONE_DIR, repo_name)

    # If already cloned
    if os.path.exists(clone_path):
        if force_refresh:
            shutil.rmtree(clone_path)
        else:
            print(f"[Cache] Using existing repo at {clone_path}")
            return collection_name, clone_path, _get_code_files(clone_path)

    print(f"[Cloner] Cloning {github_url} into {clone_path}")

    try:
        git.Repo.clone_from(github_url, clone_path, depth=1)
    except GitCommandError as e:
        raise RuntimeError(f"Clone failed: {e}")

    return collection_name, clone_path, _get_code_files(clone_path)


def _get_code_files(root_dir: str) -> list[str]:
    """
    Recursively walks the cloned repo and returns paths
    of all files whose extension is in CODE_EXTENSIONS,
    skipping any EXCLUDED_DIRS along the way.
    """
    files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):

        # Prune excluded directories in-place so os.walk skips them
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            ext = Path(filename).suffix.lower()
            if ext in ALL_EXTENSIONS:
                full_path = os.path.join(dirpath, filename)
                files.append(full_path)

    return sorted(files)  # sorted for deterministic ordering




def generate_collection_name(repo_url: str, max_length: int = 50) -> str:
    """
    Generate a safe, unique Qdrant collection name from repo URL.

    Format:
        <normalized_repo_name>_<short_hash>

    Example:
        blog_generation_app_a1b2c3d4
    """

    # Step 1: Extract repo name
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")

    # Step 2: Normalize
    repo_name = repo_name.lower()

    # Replace non-alphanumeric characters with underscore
    repo_name = re.sub(r"[^a-z0-9]+", "_", repo_name)

    # Remove leading/trailing underscores
    repo_name = repo_name.strip("_")

    # Step 3: Generate short hash from full URL
    repo_hash = hashlib.md5(repo_url.encode()).hexdigest()[:8]

    # Step 4: Combine
    collection_name = f"{repo_name}_{repo_hash}"

    # Step 5: Enforce max length (important for safety)
    if len(collection_name) > max_length:
        # Trim repo name but keep hash
        trim_length = max_length - len(repo_hash) - 1
        repo_name = repo_name[:trim_length]
        collection_name = f"{repo_name}_{repo_hash}"

    return collection_name