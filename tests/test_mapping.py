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


def test_wildcard_expands_to_vocabulary_codes(repo):
    result = map_codes(repo, ["E11.*", "I2*"], SOURCE_VOCABULARIES, "SNOMED")
    codes = {m.input_code for m in result.source_matches}
    assert {"E11.9", "I21.0"} <= codes
    assert all(m.status == "mapped" for m in result.source_matches)
    e11 = next(m for m in result.source_matches if m.input_code == "E11.9")
    assert "from pattern: E11.*" in e11.notes


def test_regex_expands_to_vocabulary_codes(repo):
    result = map_codes(repo, [r"re:^[EI]\d\d\.\d$"], SOURCE_VOCABULARIES, "SNOMED")
    assert {m.input_code for m in result.source_matches} == {"E11.9", "I21.0"}


def test_pattern_with_no_match_is_reported(repo):
    result = map_codes(repo, ["X99*"], SOURCE_VOCABULARIES, "SNOMED")
    match = result.source_matches[0]
    assert match.input_code == "X99*"
    assert match.status == "not_found"
