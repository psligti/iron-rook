"""
N² complexity fixture - evaluates performance reviewer's ability to detect
O(n²) or worse algorithms that could be optimized.
"""

from typing import List, Dict, Any


def find_duplicates(items: List[int]) -> List[int]:
    """
    Find duplicate items in a list.
    COMPLEXITY: O(n²) - nested loop
    """
    duplicates = []
    for i, item in enumerate(items):
        for j in range(i + 1, len(items)):
            if items[j] == item and item not in duplicates:
                duplicates.append(item)
                break
    return duplicates


# BETTER: O(n) using set
def find_duplicates_fast(items: List[int]) -> List[int]:
    """Optimized version - O(n)."""
    seen = set()
    duplicates = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return list(duplicates)


def count_word_pairs(texts: List[str]) -> Dict[str, int]:
    """
    Count all word pairs across texts.
    COMPLEXITY: O(n² × m) where n = number of texts, m = words per text
    """
    pairs = {}
    for i, text1 in enumerate(texts):
        words1 = text1.split()
        for j, text2 in enumerate(texts):
            if i >= j:
                continue
            words2 = text2.split()
            for w1 in words1:
                for w2 in words2:
                    pair = f"{w1},{w2}"
                    pairs[pair] = pairs.get(pair, 0) + 1
    return pairs


def matrix_multiply(a: List[List[int]], b: List[List[int]]) -> List[List[int]]:
    """
    Standard matrix multiplication.
    COMPLEXITY: O(n³) for n×n matrices
    """
    n = len(a)
    result = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                result[i][j] += a[i][k] * b[k][j]
    return result


def find_anagrams(words: List[str]) -> Dict[str, List[str]]:
    """
    Group words by anagrams.
    COMPLEXITY: O(n² × m log m) - comparing every pair
    """
    groups = {}
    for word in words:
        sorted_word = "".join(sorted(word))
        found_group = None
        for key in groups:
            if "".join(sorted(key)) == sorted_word:
                found_group = key
                break
        if found_group:
            groups[found_group].append(word)
        else:
            groups[word] = [word]
    return groups


# BETTER: O(n × m log m) using sorted as key
def find_anagrams_fast(words: List[str]) -> Dict[str, List[str]]:
    """Optimized version."""
    groups = {}
    for word in words:
        key = "".join(sorted(word))
        if key not in groups:
            groups[key] = []
        groups[key].append(word)
    return groups


def shortest_path_bfs_slow(graph: Dict[str, List[str]], start: str, end: str) -> List[str]:
    """
    Find shortest path - inefficient implementation.
    COMPLEXITY: Could explore all paths repeatedly
    """
    if start == end:
        return [start]

    def get_all_paths(current: str, visited: set) -> List[List[str]]:
        if current == end:
            return [[current]]

        paths = []
        for neighbor in graph.get(current, []):
            if neighbor not in visited:
                for path in get_all_paths(neighbor, visited | {current}):
                    paths.append([current] + path)
        return paths

    all_paths = get_all_paths(start, set())
    if not all_paths:
        return []
    return min(all_paths, key=len)


def contains_substring_slow(texts: List[str], pattern: str) -> List[str]:
    """
    Find texts containing pattern.
    COMPLEXITY: O(n × m × k) - naive substring search
    """
    matches = []
    for text in texts:
        for i in range(len(text) - len(pattern) + 1):
            match = True
            for j, char in enumerate(pattern):
                if text[i + j] != char:
                    match = False
                    break
            if match:
                matches.append(text)
                break
    return matches


# BETTER: Use built-in `in` which uses optimized algorithms
def contains_substring_fast(texts: List[str], pattern: str) -> List[str]:
    """Optimized version."""
    return [text for text in texts if pattern in text]


def cartesian_product_all(lists: List[List[Any]]) -> List[List[Any]]:
    """
    Generate all combinations.
    COMPLEXITY: O(n^m) where n = avg list size, m = number of lists
    """
    if not lists:
        return [[]]

    result = [[]]
    for lst in lists:
        new_result = []
        for prefix in result:
            for item in lst:
                new_result.append(prefix + [item])
        result = new_result
    return result


# Expected review findings:
# 1. find_duplicates - O(n²) nested loop, should use hash set
# 2. count_word_pairs - O(n² × m²), highly inefficient
# 3. matrix_multiply - O(n³) is standard but could note for large matrices
# 4. find_anagrams - O(n² × m log m), should use sorted string as dict key
# 5. shortest_path_bfs_slow - explores all paths, should use proper BFS
# 6. contains_substring_slow - naive O(n × m × k), use KMP or built-in
# 7. cartesian_product_all - exponential, should warn about memory
# 8. Suggest algorithms: hash tables, sorting, proper BFS/DFS
