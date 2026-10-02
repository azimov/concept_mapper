import pytest

from concept_mapper.codes import (
    candidate_compact_codes,
    compact_code,
    normalize_code,
    validate_code,
    validate_vocabulary,
)


def test_normalize_code():
    assert normalize_code("  c01.9 ") == "C01.9"


def test_compact_code_strips_dots_and_dashes():
    assert compact_code("C01.9") == "C019"
    assert compact_code("M-8000/3") == "M8000/3"


def test_validate_code_rejects_unsafe():
    with pytest.raises(ValueError):
        validate_code("E11'; DROP TABLE x")


def test_validate_vocabulary():
    assert validate_vocabulary(" ICD10CM ") == "ICD10CM"
    with pytest.raises(ValueError):
        validate_vocabulary("bad;vocab")


def test_candidate_compact_codes_order():
    candidates = candidate_compact_codes("C01.9")
    assert candidates[0] == "C019"
    assert "C01" in candidates
    assert "C0" not in candidates
    assert "C" not in candidates
