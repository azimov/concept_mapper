"""CDM frequency counting for standard and source concepts."""

from __future__ import annotations

from collections import defaultdict

from concept_mapper.models import MappingResult
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
            source_by_domain[match.source_concept.domain_id].add(
                match.source_concept.concept_id
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
            match.source_record_count = source_counts.get(match.source_concept.concept_id, 0)
