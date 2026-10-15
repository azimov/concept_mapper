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


def test_overbroad_sources_input_one_to_many(repo):
    report = _run(repo, ["E11.9", "C01.9", "I21.0", "Z01.0"])
    by_key = {(o.source_concept_code, o.standard_concept_id): o for o in report.overbroad_sources}
    assert set(by_key) == {("E11", 2001), ("I21", 2004)}

    i21 = by_key[("I21", 2004)]
    assert i21.introducing_input_codes == ["I21.0"]
    assert i21.alternative_standards == {"I21.0": [2003]}
    assert i21.input_one_to_many is True
    assert i21.removal_impact == "trivial"

    e11 = by_key[("E11", 2001)]
    assert e11.alternative_standards == {"E11.9": []}
    assert e11.removal_impact == "needs review"


def test_overbroad_sources_source_one_to_many(repo):
    report = _run(repo, ["K50.0", "K50.1"])
    by_key = {(o.source_concept_code, o.standard_concept_id): o for o in report.overbroad_sources}
    assert set(by_key) == {("K50", 2006), ("K50", 2007)}
    assert by_key[("K50", 2006)].other_in_set_standard_ids == [2007]
    assert by_key[("K50", 2007)].other_in_set_standard_ids == [2006]
    assert all(o.removal_impact == "not removable alone" for o in by_key.values())
    assert {c.concept.concept_id for c in report.needs_review} == {2006, 2007}


def test_surviving_extra_codes(repo):
    report = _run(repo, ["K50.0", "K50.1", "I21.0"])
    assert report.surviving_extra_codes(2006) == {"K50": [2007]}
    assert report.surviving_extra_codes(2004) == {}
