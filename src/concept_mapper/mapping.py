"""Mapping engine: resolve source codes and chase to standard concepts."""

from __future__ import annotations

from collections import defaultdict

from concept_mapper.codes import (
    candidate_compact_codes,
    compact_code,
    is_pattern,
    normalize_code,
    pattern_to_regex,
    validate_code,
    validate_vocabulary,
)
from concept_mapper.models import (
    ConceptRow,
    MappingResult,
    SourceMatch,
    StandardConcept,
)
from concept_mapper.repository.base import VocabularyRepository

MAPS_TO_RELATIONSHIPS = ["Maps to", "Maps to value"]


def _match_type(code: str, row: ConceptRow) -> str:
    if normalize_code(row.concept_code) == code:
        return "exact"
    if compact_code(row.concept_code) == compact_code(code):
        return "normalized"
    return "rolled_up"


def _chase_standard(
    repo: VocabularyRepository, source_ids: list[int]
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    standard_map: dict[int, set[int]] = {sid: set() for sid in source_ids}
    value_map: dict[int, set[int]] = {sid: set() for sid in source_ids}
    origins: dict[int, set[int]] = {sid: {sid} for sid in source_ids}
    frontier = set(source_ids)
    visited = set(source_ids)

    while frontier:
        rels = repo.get_relationships(sorted(frontier), MAPS_TO_RELATIONSHIPS)
        children: dict[int, list] = defaultdict(list)
        new_ids: set[int] = set()
        for r in rels:
            children[r.concept_id_1].append(r)
            new_ids.add(r.concept_id_2)

        concepts = repo.get_concepts(sorted(new_ids))
        nxt: set[int] = set()

        for parent, rlist in children.items():
            parent_origins = origins.get(parent, set())
            for r in rlist:
                target = concepts.get(r.concept_id_2)
                if target is None:
                    continue
                is_standard = target.standard_concept == "S"
                if r.relationship_id == "Maps to value":
                    if is_standard:
                        for origin in parent_origins:
                            value_map[origin].add(target.concept_id)
                    elif target.concept_id not in visited:
                        origins.setdefault(target.concept_id, set()).update(parent_origins)
                        nxt.add(target.concept_id)
                else:
                    if is_standard:
                        for origin in parent_origins:
                            standard_map[origin].add(target.concept_id)
                    elif target.concept_id not in visited:
                        origins.setdefault(target.concept_id, set()).update(parent_origins)
                        nxt.add(target.concept_id)

        visited |= nxt
        frontier = nxt

    return standard_map, value_map


def _expand_patterns(
    repo: VocabularyRepository, codes: list[str], vocabularies: list[str]
) -> tuple[list[str], dict[str, list[str]], list[str]]:
    """Replace wildcard/regex entries with the concrete vocabulary codes they match."""
    literals: list[str] = []
    expanded_from: dict[str, list[str]] = defaultdict(list)
    unmatched: list[str] = []
    for code in codes:
        if not is_pattern(code):
            literals.append(code)
            continue
        pattern = code.strip()
        rows = repo.find_concepts_by_regex(pattern_to_regex(pattern), vocabularies)
        found: set[str] = set()
        for row in rows:
            try:
                found.add(validate_code(row.concept_code))
            except ValueError:
                continue  # codes with characters outside the safe set (e.g. ICDO3 '/')
        if not found:
            unmatched.append(pattern)
        for concept_code in sorted(found):
            literals.append(concept_code)
            expanded_from[concept_code].append(pattern)
    return literals, expanded_from, unmatched


def map_codes(
    repo: VocabularyRepository,
    codes: list[str],
    source_vocabularies: list[str],
    target_vocabulary: str | None = "SNOMED",
    target_domains: list[str] | None = None,
) -> MappingResult:
    domains = {d.strip().lower() for d in target_domains or [] if d.strip()}
    vocabularies = [validate_vocabulary(v) for v in source_vocabularies]
    expanded_from: dict[str, list[str]] = {}
    unmatched_patterns: list[str] = []
    if vocabularies:
        codes, expanded_from, unmatched_patterns = _expand_patterns(repo, codes, vocabularies)
    unmatched_matches = [
        SourceMatch(input_code=p, notes=["pattern matched no codes"]) for p in unmatched_patterns
    ]
    input_codes: list[str] = []
    seen: set[str] = set()
    for code in codes:
        norm = validate_code(code)
        if norm not in seen:
            seen.add(norm)
            input_codes.append(norm)

    if not input_codes or not vocabularies:
        return MappingResult(source_matches=unmatched_matches, standard_concepts={})

    candidates_by_code = {code: candidate_compact_codes(code) for code in input_codes}
    all_compacts = sorted({cc for cands in candidates_by_code.values() for cc in cands})
    concept_rows = repo.find_concepts(all_compacts, vocabularies)

    compact_index: dict[str, list[ConceptRow]] = defaultdict(list)
    for row in concept_rows:
        compact_index[compact_code(row.concept_code)].append(row)

    source_concepts_by_code: dict[str, list[ConceptRow]] = {}
    matches: list[SourceMatch] = []
    for code in input_codes:
        rows: list[ConceptRow] | None = None
        for cand in candidates_by_code[code]:
            found = compact_index.get(cand)
            if found:
                rows = found
                break
        if rows is None:
            matches.append(SourceMatch(input_code=code))
            continue
        source_concepts_by_code[code] = rows
        types = {_match_type(code, r) for r in rows}
        if "exact" in types:
            match_type = "exact"
        elif "normalized" in types:
            match_type = "normalized"
        else:
            match_type = "rolled_up"
        notes: list[str] = []
        if code in expanded_from:
            notes.append(f"from pattern: {', '.join(expanded_from[code])}")
        vocab_ids = sorted({r.vocabulary_id for r in rows})
        if len(vocab_ids) > 1:
            notes.append(f"matched in multiple vocabularies: {', '.join(vocab_ids)}")
        matches.append(
            SourceMatch(
                input_code=code,
                matched_code=rows[0].concept_code,
                match_type=match_type,
                source_concept=rows[0],
                notes=notes,
            )
        )

    all_source_ids = sorted(
        {r.concept_id for rows in source_concepts_by_code.values() for r in rows}
    )
    standard_map, value_map = _chase_standard(repo, all_source_ids)

    all_standard_ids = sorted({sid for ids in standard_map.values() for sid in ids})
    all_value_ids = sorted({vid for ids in value_map.values() for vid in ids})
    concepts = repo.get_concepts(all_standard_ids + all_value_ids)

    standard_concepts: dict[int, StandardConcept] = {}
    value_concepts: dict[int, ConceptRow] = {}
    for sid in all_standard_ids:
        row = concepts.get(sid)
        if row is None:
            continue
        if target_vocabulary and row.vocabulary_id != target_vocabulary:
            continue
        if domains and row.domain_id.lower() not in domains:
            continue
        standard_concepts[sid] = StandardConcept(concept=row)
    for vid in all_value_ids:
        row = concepts.get(vid)
        if row is not None:
            value_concepts[vid] = row

    match_by_code = {m.input_code: m for m in matches}
    for code, rows in source_concepts_by_code.items():
        match = match_by_code[code]
        standard_ids: set[int] = set()
        value_ids: set[int] = set()
        dropped_vocabs: set[str] = set()
        dropped_domains: set[str] = set()
        for row in rows:
            for sid in standard_map.get(row.concept_id, ()):
                concept = concepts.get(sid)
                if concept is None:
                    continue
                if target_vocabulary and concept.vocabulary_id != target_vocabulary:
                    dropped_vocabs.add(concept.vocabulary_id)
                elif domains and concept.domain_id.lower() not in domains:
                    dropped_domains.add(concept.domain_id)
                else:
                    standard_ids.add(sid)
            for vid in value_map.get(row.concept_id, ()):
                value_ids.add(vid)
        match.standard_concept_ids = sorted(standard_ids)
        match.value_concept_ids = sorted(value_ids)
        if not standard_ids and dropped_vocabs:
            match.notes.append(
                f"mapped to non-target vocabulary: {', '.join(sorted(dropped_vocabs))}"
            )
        if not standard_ids and dropped_domains:
            match.notes.append(
                f"mapped to non-target domain: {', '.join(sorted(dropped_domains))}"
            )
        for sid in standard_ids:
            standard_concepts[sid].source_codes.append(code)
        for vid in value_ids:
            match.notes.append(f"Maps to value: {value_concepts[vid].concept_name} ({vid})")

    return MappingResult(
        source_matches=matches + unmatched_matches,
        standard_concepts=standard_concepts,
        maps_to_value_concepts=value_concepts,
    )
