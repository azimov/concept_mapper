"""Validation: coverage and overbreadth analysis of a mapped concept set."""

from __future__ import annotations

from collections import defaultdict

from concept_mapper.codes import compact_code, validate_vocabulary
from concept_mapper.models import (
    ConceptRow,
    MappingResult,
    OverbroadSource,
    ReverseMapRow,
    StandardConcept,
    ValidationReport,
)
from concept_mapper.repository.base import VocabularyRepository


def validate_result(
    repo: VocabularyRepository,
    result: MappingResult,
    source_vocabularies: list[str],
    target_vocabulary: str | None = "SNOMED",
) -> ValidationReport:
    vocabularies = [validate_vocabulary(v) for v in source_vocabularies]

    missed = result.missed
    added: list[StandardConcept] = []
    exclusions: list[StandardConcept] = []
    needs_review: list[StandardConcept] = []
    descendant_suggestions: dict[int, list[ConceptRow]] = {}
    overbroad_sources: list[OverbroadSource] = []

    if result.standard_ids and vocabularies:
        matched_compacts = {
            compact_code(m.matched_code) for m in result.source_matches if m.matched_code
        }
        reverse_rows = repo.reverse_maps_to(result.standard_ids, vocabularies)

        by_standard: dict[int, set[str]] = defaultdict(set)
        for row in reverse_rows:
            by_standard[row.standard_concept_id].add(row.source_concept_code)

        for sid, standard in result.standard_concepts.items():
            extras: set[str] = set()
            for source_code in by_standard.get(sid, ()):
                if compact_code(source_code) not in matched_compacts:
                    extras.add(source_code)
            standard.extra_source_codes = sorted(extras)

        code_standard_ids: dict[str, set[int]] = defaultdict(set)
        for match in result.source_matches:
            code_standard_ids[match.input_code].update(match.standard_concept_ids)

        for standard in result.overbroad:
            added.append(standard)
            sole_dependents = [
                c for c in standard.source_codes if len(code_standard_ids[c]) <= 1
            ]
            if sole_dependents:
                needs_review.append(standard)
            else:
                exclusions.append(standard)

        overbroad_sources = _build_overbroad_sources(
            result, reverse_rows, matched_compacts, code_standard_ids
        )

        needs_review_ids = [sc.concept.concept_id for sc in needs_review]
        if needs_review_ids and repo.supports_ancestors:
            desc_map = repo.get_descendants(needs_review_ids)
            all_desc = sorted({d for ds in desc_map.values() for d in ds})
            desc_concepts = repo.get_concepts(all_desc)
            for standard in needs_review:
                descendants = [
                    desc_concepts[d]
                    for d in desc_map.get(standard.concept.concept_id, [])
                    if d in desc_concepts
                    and desc_concepts[d].standard_concept == "S"
                    and (
                        not target_vocabulary
                        or desc_concepts[d].vocabulary_id == target_vocabulary
                    )
                ]
                descendant_suggestions[standard.concept.concept_id] = descendants

    return ValidationReport(
        result=result,
        missed=missed,
        added=added,
        exclusions=exclusions,
        needs_review=needs_review,
        descendant_suggestions=descendant_suggestions,
        overbroad_sources=overbroad_sources,
    )


def _build_overbroad_sources(
    result: MappingResult,
    reverse_rows: list[ReverseMapRow],
    matched_compacts: set[str],
    code_standard_ids: dict[str, set[int]],
) -> list[OverbroadSource]:
    """One row per (overbroad source concept, in-set standard concept that pulls it in)."""
    in_set_by_source: dict[int, set[int]] = defaultdict(set)
    for row in reverse_rows:
        if row.standard_concept_id in result.standard_concepts:
            in_set_by_source[row.source_concept_id].add(row.standard_concept_id)

    rows: list[OverbroadSource] = []
    seen: set[tuple[int, int]] = set()
    for row in reverse_rows:
        sid = row.standard_concept_id
        standard = result.standard_concepts.get(sid)
        if standard is None or compact_code(row.source_concept_code) in matched_compacts:
            continue
        key = (row.source_concept_id, sid)
        if key in seen:
            continue
        seen.add(key)
        input_codes = list(dict.fromkeys(standard.source_codes))
        rows.append(
            OverbroadSource(
                source_concept_id=row.source_concept_id,
                source_concept_code=row.source_concept_code,
                source_concept_name=row.source_concept_name,
                source_vocabulary_id=row.source_vocabulary_id,
                standard_concept_id=sid,
                introducing_input_codes=input_codes,
                alternative_standards={
                    code: sorted(code_standard_ids[code] - {sid}) for code in input_codes
                },
                other_in_set_standard_ids=sorted(in_set_by_source[row.source_concept_id] - {sid}),
            )
        )
    rows.sort(key=lambda o: (o.source_concept_code, o.standard_concept_id))
    return rows
