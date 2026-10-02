"""Code normalisation and ICD hierarchy roll-up helpers."""

from __future__ import annotations

import re

_CODE_RE = re.compile(r"^[A-Za-z0-9.\-]+$")
_VOCAB_RE = re.compile(r"^[A-Za-z0-9_ .\-]+$")

MIN_ROLLUP_LENGTH = 3


def normalize_code(code: str) -> str:
    """Strip whitespace and upper-case a source code."""
    return code.strip().upper()


def compact_code(code: str) -> str:
    """Remove dots and upper-case, giving a canonical matchable form."""
    return normalize_code(code).replace(".", "").replace("-", "")


def validate_code(code: str) -> str:
    """Validate a source code token; raise ValueError if unsafe."""
    norm = normalize_code(code)
    if not norm:
        raise ValueError("Source code must not be empty.")
    if not _CODE_RE.match(norm):
        raise ValueError(f"Unsafe source code token: {code!r}")
    return norm


def validate_vocabulary(vocab: str) -> str:
    """Validate a vocabulary_id token; raise ValueError if unsafe."""
    v = vocab.strip()
    if not v:
        raise ValueError("Vocabulary id must not be empty.")
    if not _VOCAB_RE.match(v):
        raise ValueError(f"Unsafe vocabulary id: {vocab!r}")
    return v


def candidate_compact_codes(code: str) -> list[str]:
    """Return candidate compact forms for a code, most-specific first.

    Order: full compact code, then progressively shorter prefixes (roll-up)
    down to ``MIN_ROLLUP_LENGTH`` characters. This lets a sub-code such as
    ``C01.9`` resolve to its parent category ``C01`` when the exact sub-code is
    absent from the vocabulary.
    """
    compact = compact_code(code)
    candidates: list[str] = []
    for length in range(len(compact), MIN_ROLLUP_LENGTH - 1, -1):
        prefix = compact[:length]
        if prefix not in candidates:
            candidates.append(prefix)
    return candidates
