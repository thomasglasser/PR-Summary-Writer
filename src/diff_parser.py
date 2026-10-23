import os
import re
from typing import List, Dict, Tuple

IGNORED_SUFFIXES = (
    # Binaries and media
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".ogg", ".mp3", ".wav",
    ".jar", ".zip", ".tar", ".gz", ".7z",
    ".class", ".pyc", ".exe", ".dll", ".so", ".dylib",
    # 3D models and raw assets
    ".geo.json", ".obj", ".blend", ".fbx",
    # Lockfiles
    ".lock",
)

IGNORED_PATH_PATTERNS = [
    r"gradle\.lockfile$",
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"pnpm-lock\.yaml$",
    r"(?:^|/)\.gradle/",
    r"(?:^|/)assets/",
    r"(?:^|/)build/",
    r"(?:^|/)dist/",
    r"(?:^|/)out/",
    r"(?:^|/)bin/",
    r"(?:^|/)\.idea/",
    r"(?:^|/)\.vscode/",
    r"(?:^|/)src/generated/",
]


MAX_SUMMARY_DIFF_CHARS = 120_000


def is_summarizable_file(file_path: str) -> bool:
    """
    Returns True if the file should be included in the PR diff analysis.
    Filters out binaries, lockfiles, heavy assets, and generated build folders.
    """
    clean_path = file_path.replace("\\", "/").strip().lower()
    if clean_path.endswith(IGNORED_SUFFIXES):
        return False
    for pat in IGNORED_PATH_PATTERNS:
        if re.search(pat, clean_path, re.IGNORECASE):
            return False
    return True


def filter_diff_for_summary(raw_diff: str) -> Tuple[str, List[str], List[str]]:
    """
    Parses a unified diff, keeping only summarizable files.
    Returns:
      (filtered_diff_text, list_of_included_files, list_of_ignored_files)
    """
    if not raw_diff:
        return "", [], []

    # Split unified diff into per-file chunks
    file_chunks = re.split(r"(?=^diff --git )", raw_diff, flags=re.MULTILINE)
    included_chunks: List[str] = []
    included_files: List[str] = []
    ignored_files: List[str] = []

    for chunk in file_chunks:
        if not chunk.strip():
            continue

        match = re.search(r"^diff --git a/(.*?) b/(.*?)$", chunk, re.MULTILINE)
        if not match:
            # If header missing, include chunk defensively
            included_chunks.append(chunk)
            continue

        file_path = match.group(2)
        if is_summarizable_file(file_path):
            included_files.append(file_path)
            included_chunks.append(chunk)
        else:
            ignored_files.append(file_path)

    combined_diff = "".join(included_chunks)

    # If the combined diff exceeds MAX_SUMMARY_DIFF_CHARS, intelligently truncate large hunks
    if len(combined_diff) > MAX_SUMMARY_DIFF_CHARS:
        combined_diff = combined_diff[:MAX_SUMMARY_DIFF_CHARS] + "\n\n... [Diff truncated for context length] ...\n"

    return combined_diff, included_files, ignored_files
