from concept_mapper.mapping import map_codes

SOURCE_VOCABULARIES = ["ICD10CM"]


def test_one_to_one_mapping(repo):
    result = map_codes(repo, ["E11.9"], SOURCE_VOCABULARIES, "SNOMED")
    match = result.source_matches[0]
    assert match.status == "mapped"
    assert match.match_type == "exact"
    assert match.standard_concept_ids == [2001]


def test_rollup_when_subcode_absent(repo):
    result = map_codes(repo, ["C01.9"], SOURCE_VOCABULARIES, "SNOMED")
    match = result.source_matches[0]
    assert match.match_type == "rolled_up"
    assert match.matched_code == "C01"
    assert match.standard_concept_ids == [2002]


def test_multi_target_mapping(repo):
    result = map_codes(repo, ["I21.0"], SOURCE_VOCABULARIES, "SNOMED")
    match = result.source_matches[0]
    assert set(match.standard_concept_ids) == {2003, 2004}


def test_multi_hop_mapping(repo):
    result = map_codes(repo, ["Z01.0"], SOURCE_VOCABULARIES, "SNOMED")
    match = result.source_matches[0]
    assert match.standard_concept_ids == [2005]


def test_not_found(repo):
    result = map_codes(repo, ["X99.9"], SOURCE_VOCABULARIES, "SNOMED")
    match = result.source_matches[0]
    assert match.status == "not_found"
    assert match.match_type == "not_found"


def test_unmapped_source(repo):
    result = map_codes(repo, ["A00"], SOURCE_VOCABULARIES, "SNOMED")
    match = result.source_matches[0]
    assert match.status == "unmapped"
    assert match.match_type == "exact"


def test_deduplicates_input_codes(repo):
    result = map_codes(repo, ["E11.9", "E11.9"], SOURCE_VOCABULARIES, "SNOMED")
    assert len(result.source_matches) == 1
