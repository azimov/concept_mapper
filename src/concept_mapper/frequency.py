"""CDM frequency counting for standard and source concepts."""

from __future__ import annotations

from collections import defaultdict

from concept_mapper.models import MappingResult, SourceConceptCount
from concept_mapper.repository.base import VocabularyRepository

DOMAIN_TABLES: dict[str, tuple[str, str, str]] = {
    "Condition": ("condition_occurrence", "condition_concept_id", "condition_source_concept_id"),
    "Drug": ("drug_exposure", "drug_concept_id", "drug_source_concept_id"),
    "Procedure": ("procedure_occurrence", "procedure_concept_id", "procedure_source_concept_id"),
    "Measurement": ("measurement", "measurement_concept_id", "measurement_source_concept_id"),
    "Observation": ("observation", "observation_concept_id", "observation_source_concept_id"),
    "Device": ("device_exposure", "device_concept_id", "device_source_concept_id"),
    "Visit": ("visit_occurrence", "visit_concept_id", "visit_source_concept_id"),
    "Specimen": ("specimen", "specimen_concept_id", "specimen_source_concept_id"),
}


def count_frequencies(
    repo: VocabularyRepository,
    result: MappingResult,
    catalog: str | None = None,
    schema: str | None = None,
    source_vocabularies: list[str] | None = None,
) -> None:
    standard_by_domain: dict[str, list[int]] = defaultdict(list)
    for standard in result.standard_concepts.values():
        standard_by_domain[standard.concept.domain_id].append(standard.concept.concept_id)

    for domain, concept_ids in standard_by_domain.items():
        mapping = DOMAIN_TABLES.get(domain)
        if mapping is None:
            continue
        table, concept_column, _ = mapping
        counts = repo.count_in_table(table, concept_column, concept_ids, catalog, schema)
        for concept_id in concept_ids:
            result.standard_concepts[concept_id].record_count = counts.get(concept_id, 0)

    source_by_domain: dict[str, set[int]] = defaultdict(set)
    for match in result.source_matches:
        if match.source_concept is not None:
            source_by_domain[match.source_concept.domain_id].update(
                match.source_concept_ids or [match.source_concept.concept_id]
            )

    source_counts: dict[int, int] = {}
    for domain, concept_ids in source_by_domain.items():
        mapping = DOMAIN_TABLES.get(domain)
        if mapping is None:
            continue
        table, _, source_column = mapping
        source_counts.update(
            repo.count_in_table(table, source_column, concept_ids, catalog, schema)
        )

    for match in result.source_matches:
        if match.source_concept is not None:
            ids = match.source_concept_ids or [match.source_concept.concept_id]
            match.source_record_count = sum(source_counts.get(cid, 0) for cid in ids)

    if source_vocabularies:
        _count_all_sources(repo, result, source_vocabularies, catalog, schema)


def _count_all_sources(
    repo: VocabularyRepository,
    result: MappingResult,
    source_vocabularies: list[str],
    catalog: str | None,
    schema: str | None,
) -> None:
    """Attach a count for every source concept that maps to each standard concept."""
    reverse_rows = repo.reverse_maps_to(result.standard_ids, source_vocabularies)
    input_source_ids = {cid for m in result.source_matches for cid in m.source_concept_ids}

    # A source concept is counted in the table of the standard concept's domain.
    ids_by_domain: dict[str, set[int]] = defaultdict(set)
    for row in reverse_rows:
        standard = result.standard_concepts.get(row.standard_concept_id)
        if standard is not None:
            ids_by_domain[standard.concept.domain_id].add(row.source_concept_id)

    counts_by_domain: dict[str, dict[int, int]] = {}
    for domain, ids in ids_by_domain.items():
        mapping = DOMAIN_TABLES.get(domain)
        if mapping is None:
            continue
        table, _, source_column = mapping
        counts_by_domain[domain] = repo.count_in_table(
            table, source_column, sorted(ids), catalog, schema
        )

    for row in reverse_rows:
        standard = result.standard_concepts.get(row.standard_concept_id)
        if standard is None:
            continue
        domain_counts = counts_by_domain.get(standard.concept.domain_id)
        standard.source_counts.append(
            SourceConceptCount(
                concept_id=row.source_concept_id,
                concept_code=row.source_concept_code,
                concept_name=row.source_concept_name,
                vocabulary_id=row.source_vocabulary_id,
                record_count=None
                if domain_counts is None
                else domain_counts.get(row.source_concept_id, 0),
                in_input=row.source_concept_id in input_source_ids,
            )
        )
    for standard in result.standard_concepts.values():
        standard.source_counts.sort(key=lambda s: (-(s.record_count or 0), s.concept_code))
