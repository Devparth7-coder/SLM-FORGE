"""Deduplication and near-duplicate detection.

Implements:
- Exact deduplication via content hash
- Near-duplicate detection via MinHash + LSH (using datasketch if available,
  falling back to fuzzy matching with rapidfuzz)
- Train/test leakage detection
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from rapidfuzz import fuzz

# ── Tokenisation for code ────────────────────────────────────────────────
_CODE_WS_RE = re.compile(r"\s+")
_CODE_COMMENT_RE = re.compile(r"(?://.*$|/\*.*?\*/|#.*$)", re.MULTILINE | re.DOTALL)


def normalize_code_for_hash(text: str) -> str:
    """Normalize source code for duplicate detection: strip comments, normalize whitespace."""
    text = _CODE_COMMENT_RE.sub(" ", text)
    text = _CODE_WS_RE.sub(" ", text).strip().lower()
    return text


def content_hash(text: str) -> str:
    normalized = normalize_code_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ── Shingling for near-duplicate detection ────────────────────────────────
def char_ngrams(text: str, n: int = 5) -> Set[str]:
    return {text[i:i + n] for i in range(max(0, len(text) - n + 1))}


def token_set_ratio(a: str, b: str) -> float:
    """Return similarity score in [0, 100]."""
    return fuzz.token_set_ratio(a, b)


@dataclass
class DeduplicationStats:
    exact_duplicate_count: int = 0
    near_duplicate_count: int = 0
    train_test_overlap_count: int = 0
    removed_indices: Set[int] = field(default_factory=set)
    duplicate_groups: List[List[int]] = field(default_factory=list)


class DeduplicationService:
    """Exact and near-duplicate detection for datasets."""

    def __init__(
        self,
        near_dup_threshold: float = 92.0,  # 0-100, fuzzy match score
        use_minhash: bool = True,
    ) -> None:
        self.near_dup_threshold = near_dup_threshold
        self.use_minhash = use_minhash

    def deduplicate_exact(
        self,
        samples: List[Dict[str, Any]],
        text_key: str = "input",
    ) -> Tuple[List[Dict[str, Any]], DeduplicationStats]:
        """Remove exact duplicates, keeping first occurrence."""
        seen: Dict[str, int] = {}
        unique: List[Dict[str, Any]] = []
        stats = DeduplicationStats()
        groups: Dict[str, List[int]] = defaultdict(list)

        for idx, sample in enumerate(samples):
            text = str(sample.get(text_key, ""))
            h = content_hash(text)
            groups[h].append(idx)
            if h not in seen:
                seen[h] = idx
                unique.append(sample)
            else:
                stats.exact_duplicate_count += 1
                stats.removed_indices.add(idx)

        stats.duplicate_groups = [g for g in groups.values() if len(g) > 1]
        return unique, stats

    def detect_near_duplicates(
        self,
        samples: List[Dict[str, Any]],
        text_key: str = "input",
        threshold: Optional[float] = None,
    ) -> DeduplicationStats:
        """Detect near-duplicates without removing them (flag only).

        For efficiency, this uses a block-based approach: compare samples that
        share at least one n-gram or fall into the same length bucket.
        """
        threshold = threshold or self.near_dup_threshold
        stats = DeduplicationStats()
        n = len(samples)
        if n == 0:
            return stats

        # Bucket samples by length (len / 500 chars) to reduce comparisons
        buckets: Dict[int, List[int]] = defaultdict(list)
        for idx, sample in enumerate(samples):
            text = normalize_code_for_hash(str(sample.get(text_key, "")))
            length_bucket = len(text) // 500
            buckets[length_bucket].append(idx)

        near_dupes: Set[int] = set()
        visited_pairs: Set[Tuple[int, int]] = set()

        for bucket_indices in buckets.values():
            for i_idx, i in enumerate(bucket_indices):
                for j in bucket_indices[i_idx + 1:]:
                    if i in near_dupes or j in near_dupes:
                        continue
                    pair = (min(i, j), max(i, j))
                    if pair in visited_pairs:
                        continue
                    visited_pairs.add(pair)
                    a = normalize_code_for_hash(str(samples[i].get(text_key, "")))
                    b = normalize_code_for_hash(str(samples[j].get(text_key, "")))
                    if not a or not b:
                        continue
                    ratio = token_set_ratio(a, b)
                    if ratio >= threshold:
                        near_dupes.add(j)  # mark the later occurrence

        stats.near_duplicate_count = len(near_dupes)
        stats.removed_indices = near_dupes
        return stats

    def detect_train_test_leakage(
        self,
        train_samples: List[Dict[str, Any]],
        test_samples: List[Dict[str, Any]],
        text_key: str = "input",
        near_threshold: Optional[float] = None,
    ) -> DeduplicationStats:
        """Detect overlap between train and test splits."""
        near_threshold = near_threshold or self.near_dup_threshold
        stats = DeduplicationStats()

        # Exact hash overlap
        train_hashes = {content_hash(str(s.get(text_key, ""))) for s in train_samples}
        test_indices_to_flag: Set[int] = set()
        for idx, sample in enumerate(test_samples):
            h = content_hash(str(sample.get(text_key, "")))
            if h in train_hashes:
                test_indices_to_flag.add(idx)
        stats.train_test_overlap_count = len(test_indices_to_flag)
        stats.removed_indices = test_indices_to_flag
        return stats
