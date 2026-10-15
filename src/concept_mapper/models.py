"""Domain models for the concept mapper."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConceptRow:
    concept_id: int
    concept_name: str
    concept_code: str
    vocabulary_id: str
    domain_id: str
    concept_class_id: str
    standard_concept: str | None = None
    invalid_reason: str | None = None

    @classmethod
    def from_row(cls, row: tuple | dict) -> ConceptRow:
        if isinstance(row, dict):
            get = row.get
        else:
            keys = (
                "concept_id",
                "concept_name",
                "concept_code",
                "vocabulary_id",
                "domain_id",
                "concept_class_id",
                "standard_concept",
                "invalid_reason",
            )
            get = dict(zip(keys, row, strict=False)).get
        return cls(
            concept_id=int(get("concept_id")),
            concept_name=str(get("concept_name") or ""),
            concept_code=str(get("concept_code") or ""),
            vocabulary_id=str(get("vocabulary_id") or ""),
            domain_id=str(get("domain_id") or ""),
            concept_class_id=str(get("concept_class_id") or ""),
            standard_concept=get("standard_concept") or None,
            invalid_reason=get("invalid_reason") or None,
        )


@dataclass
class RelationshipRow:
    concept_id_1: int
    concept_id_2: int
    relationship_id: str


@dataclass
class ReverseMapRow:
    standard_concept_id: int
    source_concept_id: int
    source_concept_code: str
    source_concept_name: str
    source_vocabulary_id: str


@dataclass
class SourceMatch:
    input_code: str
    matched_code: str | None = None
    match_type: str = "not_found"
    source_concept: ConceptRow | None = None
    source_concept_ids: list[int] = field(default_factory=list)
    standard_concept_ids: list[int] = field(default_factory=list)
    value_concept_ids: list[int] = field(default_factory=list)
    source_record_count: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.match_type == "not_found":
            return "not_found"
        if not self.standard_concept_ids:
            return "unmapped"
        return "mapped"


@dataclass
class SourceConceptCount:
    concept_id: int
    concept_code: str
    concept_name: str
    vocabulary_id: str
    record_count: int | None = None
    in_input: bool = False


@dataclass
class StandardConcept:
    concept: ConceptRow
    source_codes: list[str] = field(default_factory=list)
    extra_source_codes: list[str] = field(default_factory=list)
    record_count: int | None = None
    source_counts: list[SourceConceptCount] = field(default_factory=list)

    @property
    def is_overbroad(self) -> bool:
        return bool(self.extra_source_codes)


@dataclass
class OverbroadSource:
    """A source concept not in the input that is pulled into the set via a standard concept."""

    source_concept_id: int
    source_concept_code: str
    source_concept_name: str
    source_vocabulary_id: str
    standard_concept_id: int
    introducing_input_codes: list[str] = field(default_factory=list)
    # Per introducing input code, its other standard concept ids (empty => sole dependency).
    alternative_standards: dict[str, list[int]] = field(default_factory=dict)
    # Other in-set standard concepts this source concept also maps to.
    other_in_set_standard_ids: list[int] = field(default_factory=list)

    @property
    def input_one_to_many(self) -> bool:
        return bool(self.alternative_standards) and all(self.alternative_standards.values())

    @property
    def source_one_to_many(self) -> bool:
        return bool(self.other_in_set_standard_ids)

    @property
    def removal_impact(self) -> str:
        if self.source_one_to_many:
            return "not removable alone"
        if self.input_one_to_many:
            return "trivial"
        return "needs review"


@dataclass
class MappingResult:
    source_matches: list[SourceMatch]
    standard_concepts: dict[int, StandardConcept]
    maps_to_value_concepts: dict[int, ConceptRow] = field(default_factory=dict)

    @property
    def standard_ids(self) -> list[int]:
        return sorted(self.standard_concepts)

    @property
    def missed(self) -> list[SourceMatch]:
        return [m for m in self.source_matches if m.status != "mapped"]

    @property
    def overbroad(self) -> list[StandardConcept]:
        return [c for c in self.standard_concepts.values() if c.is_overbroad]


@dataclass
class ValidationReport:
    result: MappingResult
    missed: list[SourceMatch] = field(default_factory=list)
    added: list[StandardConcept] = field(default_factory=list)
    exclusions: list[StandardConcept] = field(default_factory=list)
    needs_review: list[StandardConcept] = field(default_factory=list)
    descendant_suggestions: dict[int, list[ConceptRow]] = field(default_factory=dict)
    overbroad_sources: list[OverbroadSource] = field(default_factory=list)

    def surviving_extra_codes(self, standard_concept_id: int) -> dict[str, list[int]]:
        """Extra codes of a standard that would still be captured via other in-set standards."""
        return {
            o.source_concept_code: o.other_in_set_standard_ids
            for o in self.overbroad_sources
            if o.standard_concept_id == standard_concept_id and o.source_one_to_many
        }
