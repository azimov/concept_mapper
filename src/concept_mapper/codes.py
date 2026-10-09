"""Code normalisation and ICD hierarchy roll-up helpers."""

from __future__ import annotations

import re

_CODE_RE = re.compile(r"^[A-Za-z0-9.\-]+$")
_VOCAB_RE = re.compile(r"^[A-Za-z0-9_ .\-]+$")

MIN_ROLLUP_LENGTH = 3

REGEX_PREFIX = "re:"
_WILDCARD_RE = re.compile(r"^[A-Za-z0-9.\-*]+$")
_MAX_PATTERN_LENGTH = 200


def is_pattern(code: str) -> bool:
    """True for a wildcard (``C01.*``) or regex (``re:^C0[12]``) entry."""
    stripped = code.strip()
    return stripped.lower().startswith(REGEX_PREFIX) or "*" in stripped


def pattern_to_regex(code: str) -> str:
    """Translate a wildcard or ``re:`` entry to a regex; raise ValueError if invalid."""
    stripped = code.strip()
    if len(stripped) > _MAX_PATTERN_LENGTH:
        raise ValueError(f"Pattern too long: {stripped[:30]!r}...")
    if stripped.lower().startswith(REGEX_PREFIX):
        pattern = stripped[len(REGEX_PREFIX):]
        if not pattern:
            raise ValueError("Empty regex pattern.")
        if "'" in pattern:
            raise ValueError("Single quotes are not allowed in regex patterns.")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex {pattern!r}: {exc}") from exc
        return pattern
    if not _WILDCARD_RE.match(stripped):
        raise ValueError(f"Unsafe wildcard pattern: {code!r}")
    return "^" + ".*".join(re.escape(part) for part in stripped.split("*")) + "$"


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
