from pathlib import Path

from concept_mapper.frequency import DOMAIN_TABLES, count_frequencies
from concept_mapper.mapping import map_codes
from concept_mapper.repository import DuckDBRepository

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE_VOCABULARIES = ["ICD10CM"]


def _repo():
    repo = DuckDBRepository(csv_dir=str(FIXTURES))
    repo.load_table(
        "condition_occurrence", str(FIXTURES / "CONDITION_OCCURRENCE.csv")
    )
    return repo


def test_domain_table_mapping():
    assert DOMAIN_TABLES["Condition"] == (
        "condition_occurrence",
        "condition_concept_id",
        "condition_source_concept_id",
    )


def test_count_in_table():
    repo = _repo()
    try:
        counts = repo.count_in_table(
            "condition_occurrence", "condition_concept_id", [2001, 2002]
        )
        assert counts == {2001: 3, 2002: 1}
    finally:
        repo.close()


def test_count_frequencies():
    repo = _repo()
    try:
        result = map_codes(repo, ["E11.9", "C01.9", "I21.0"], SOURCE_VOCABULARIES, "SNOMED")
        count_frequencies(repo, result)

        standards = result.standard_concepts
        assert standards[2001].record_count == 3
        assert standards[2002].record_count == 1
        assert standards[2003].record_count == 1
        assert standards[2004].record_count == 0

        by_code = {m.input_code: m for m in result.source_matches}
        assert by_code["E11.9"].source_record_count == 2
        assert by_code["C01.9"].source_record_count == 1
        assert by_code["I21.0"].source_record_count == 1
    finally:
        repo.close()
