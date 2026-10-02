from concept_mapper.mapping import map_codes
from concept_mapper.validation import validate_result

SOURCE_VOCABULARIES = ["ICD10CM"]


def _run(repo, codes):
    result = map_codes(repo, codes, SOURCE_VOCABULARIES, "SNOMED")
    return validate_result(repo, result, SOURCE_VOCABULARIES, "SNOMED")


def test_overbreadth_detection(repo):
    report = _run(repo, ["E11.9", "C01.9", "I21.0", "Z01.0"])
    by_id = {c.concept.concept_id: c for c in report.result.standard_concepts.values()}

    assert by_id[2001].extra_source_codes == ["E11"]
    assert by_id[2004].extra_source_codes == ["I21"]
    assert by_id[2002].extra_source_codes == []
    assert by_id[2003].extra_source_codes == []
    assert by_id[2005].extra_source_codes == []


def test_exclusions_vs_needs_review(repo):
    report = _run(repo, ["E11.9", "C01.9", "I21.0", "Z01.0"])
    exclusion_ids = {c.concept.concept_id for c in report.exclusions}
    review_ids = {c.concept.concept_id for c in report.needs_review}
    added_ids = {c.concept.concept_id for c in report.added}

    assert exclusion_ids == {2004}
    assert review_ids == {2001}
    assert added_ids == {2001, 2004}


def test_missed_report(repo):
    report = _run(repo, ["X99.9", "A00"])
    missed = {m.input_code: m.status for m in report.missed}
    assert missed == {"X99.9": "not_found", "A00": "unmapped"}
