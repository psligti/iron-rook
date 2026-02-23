"""
I/O amplification fixture - evaluates performance reviewer's ability to detect
excessive I/O operations that could be batched or reduced.
"""

import os
import json
from typing import List, Dict, Any


def get_file_sizes(directory: str) -> Dict[str, int]:
    """
    Get sizes of all files in directory.
    PROBLEM: Multiple os.stat calls per file.
    """
    sizes = {}
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            # I/O: os.path.isfile + os.path.getsize = 2 syscalls per file
            sizes[filename] = os.path.getsize(filepath)
    return sizes


def read_all_config_files(config_dir: str) -> Dict[str, Any]:
    """
    Read all JSON config files.
    PROBLEM: Opens each file separately.
    """
    configs = {}
    for filename in os.listdir(config_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(config_dir, filename)
            with open(filepath) as f:
                configs[filename] = json.load(f)
    return configs


def check_files_exist(filepaths: List[str]) -> Dict[str, bool]:
    """
    Check if each file exists.
    PROBLEM: N separate filesystem calls.
    """
    results = {}
    for filepath in filepaths:
        results[filepath] = os.path.exists(filepath)
    return results


def append_logs(log_entries: List[str], log_file: str) -> None:
    """
    Append multiple log entries to file.
    PROBLEM: Opens/closes file N times.
    """
    for entry in log_entries:
        with open(log_file, "a") as f:
            f.write(entry + "\n")


def fetch_user_data(user_ids: List[int], api_client) -> Dict[int, Any]:
    """
    Fetch data for multiple users.
    PROBLEM: N separate API calls instead of batch.
    """
    results = {}
    for user_id in user_ids:
        # I/O: HTTP request per user
        results[user_id] = api_client.get(f"/users/{user_id}")
    return results


def read_lines_and_process(filename: str) -> List[Any]:
    """
    Read file lines and process each.
    PROBLEM: readlines() loads entire file into memory, then we iterate.
    """
    with open(filename) as f:
        lines = f.readlines()  # Loads entire file

    results = []
    for line in lines:
        # Process each line
        results.append(line.strip().upper())
    return results


# BETTER: Stream processing
def read_lines_and_process_better(filename: str) -> List[Any]:
    """Stream processing - one line at a time."""
    results = []
    with open(filename) as f:
        for line in f:  # Iterator, doesn't load all
            results.append(line.strip().upper())
    return results


def copy_file_byte_by_byte(src: str, dst: str) -> None:
    """
    Copy file one byte at a time.
    PROBLEM: Severe I/O amplification - 1 syscall per byte!
    """
    with open(src, "rb") as f_src:
        with open(dst, "wb") as f_dst:
            while True:
                byte = f_src.read(1)  # I/O per byte
                if not byte:
                    break
                f_dst.write(byte)  # I/O per byte


# BETTER: Chunked copy
def copy_file_chunked(src: str, dst: str, chunk_size: int = 8192) -> None:
    """Copy in chunks - much fewer I/O calls."""
    with open(src, "rb") as f_src:
        with open(dst, "wb") as f_dst:
            while chunk := f_src.read(chunk_size):
                f_dst.write(chunk)


def process_directory_tree(root: str) -> Dict[str, Any]:
    """
    Process entire directory tree.
    PROBLEM: os.walk is fine, but we stat every file.
    """
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            # Multiple I/O calls per file
            stat = os.stat(filepath)
            result[filepath] = {
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_executable": os.access(filepath, os.X_OK),
            }
    return result


def save_items_separately(items: List[Dict], directory: str) -> None:
    """
    Save each item to separate file.
    PROBLEM: N file opens/writes for N items.
    """
    os.makedirs(directory, exist_ok=True)
    for i, item in enumerate(items):
        filepath = os.path.join(directory, f"item_{i}.json")
        with open(filepath, "w") as f:
            json.dump(item, f)


# BETTER: Single file with all items
def save_items_together(items: List[Dict], filepath: str) -> None:
    """Save all items to single file."""
    with open(filepath, "w") as f:
        json.dump(items, f)


def query_database_row_by_row(db, query: str, ids: List[int]) -> List[Dict]:
    """
    Query database for each ID separately.
    PROBLEM: N separate queries instead of single IN clause.
    """
    results = []
    for id_ in ids:
        cursor = db.execute(f"SELECT * FROM items WHERE id = {id_}")
        results.append(cursor.fetchone())
    return results


# BETTER: Batch query
def query_database_batch(db, ids: List[int]) -> List[Dict]:
    """Single query with IN clause."""
    placeholders = ",".join("?" * len(ids))
    cursor = db.execute(f"SELECT * FROM items WHERE id IN ({placeholders})", ids)
    return cursor.fetchall()


# Expected review findings:
# 1. get_file_sizes - 2 syscalls per file, could use scandir
# 2. read_all_config_files - N file opens, consider batching
# 3. check_files_exist - N separate filesystem calls
# 4. append_logs - N file opens, should batch writes
# 5. fetch_user_data - N API calls, should use batch endpoint
# 6. read_lines_and_process - loads entire file, should stream
# 7. copy_file_byte_by_byte - catastrophic I/O amplification
# 8. process_directory_tree - multiple stats per file
# 9. save_items_separately - N file writes vs 1
# 10. query_database_row_by_row - N queries vs single IN clause
