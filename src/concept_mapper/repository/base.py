"""Repository interface and shared SQL for vocabulary access."""

from __future__ import annotations

from abc import ABC, abstractmethod

from concept_mapper.models import (
    ConceptRow,
    RelationshipRow,
    ReverseMapRow,
)

_CONCEPT_COLUMNS = (
    "concept_id",
    "concept_name",
    "concept_code",
    "vocabulary_id",
    "domain_id",
    "concept_class_id",
    "standard_concept",
    "invalid_reason",
)


def quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def in_literals(values: list[str]) -> str:
    return "(" + ", ".join(quote(v) for v in values) + ")"


def in_ints(values: list[int]) -> str:
    return "(" + ", ".join(str(int(v)) for v in values) + ")"


class VocabularyRepository(ABC):
    supports_ancestors: bool = False

    @abstractmethod
    def _table(self, name: str, catalog: str | None = None, schema: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def _fetch(self, sql: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    def find_concepts(
        self, compact_codes: list[str], vocabularies: list[str]
    ) -> list[ConceptRow]:
        if not compact_codes or not vocabularies:
            return []
        sql = (
            f"SELECT {', '.join(_CONCEPT_COLUMNS)} FROM {self._table('concept')} "
            f"WHERE vocabulary_id IN {in_literals(vocabularies)} "
            f"AND replace(replace(concept_code, '.', ''), '-', '') IN "
            f"{in_literals(compact_codes)}"
        )
        return [ConceptRow.from_row(row) for row in self._fetch(sql)]

    def _regex_predicate(self, column: str, pattern: str) -> str:
        return f"regexp_matches({column}, {quote('(?i)' + pattern)})"

    def find_concepts_by_regex(
        self, pattern: str, vocabularies: list[str]
    ) -> list[ConceptRow]:
        if not pattern or not vocabularies:
            return []
        sql = (
            f"SELECT {', '.join(_CONCEPT_COLUMNS)} FROM {self._table('concept')} "
            f"WHERE vocabulary_id IN {in_literals(vocabularies)} "
            f"AND {self._regex_predicate('concept_code', pattern)}"
        )
        return [ConceptRow.from_row(row) for row in self._fetch(sql)]

    def get_concepts(self, concept_ids: list[int]) -> dict[int, ConceptRow]:
        if not concept_ids:
            return {}
        ids = sorted({int(i) for i in concept_ids})
        sql = (
            f"SELECT {', '.join(_CONCEPT_COLUMNS)} FROM {self._table('concept')} "
            f"WHERE concept_id IN {in_ints(ids)}"
        )
        return {row.concept_id: row for row in (ConceptRow.from_row(r) for r in self._fetch(sql))}

    def get_relationships(
        self, concept_ids: list[int], relationship_ids: list[str]
    ) -> list[RelationshipRow]:
        if not concept_ids or not relationship_ids:
            return []
        ids = sorted({int(i) for i in concept_ids})
        sql = (
            f"SELECT concept_id_1, concept_id_2, relationship_id "
            f"FROM {self._table('concept_relationship')} "
            f"WHERE concept_id_1 IN {in_ints(ids)} "
            f"AND relationship_id IN {in_literals(relationship_ids)} "
            f"AND (invalid_reason IS NULL OR invalid_reason = '')"
        )
        return [
            RelationshipRow(
                concept_id_1=int(r["concept_id_1"]),
                concept_id_2=int(r["concept_id_2"]),
                relationship_id=str(r["relationship_id"]),
            )
            for r in self._fetch(sql)
        ]

    def reverse_maps_to(
        self, standard_ids: list[int], vocabularies: list[str]
    ) -> list[ReverseMapRow]:
        if not standard_ids or not vocabularies:
            return []
        ids = sorted({int(i) for i in standard_ids})
        sql = (
            f"SELECT cr.concept_id_2 AS standard_concept_id, "
            f"c.concept_id AS source_concept_id, c.concept_code AS source_concept_code, "
            f"c.concept_name AS source_concept_name, c.vocabulary_id AS source_vocabulary_id "
            f"FROM {self._table('concept_relationship')} cr "
            f"JOIN {self._table('concept')} c ON c.concept_id = cr.concept_id_1 "
            f"WHERE cr.concept_id_2 IN {in_ints(ids)} "
            f"AND cr.relationship_id = 'Maps to' "
            f"AND (cr.invalid_reason IS NULL OR cr.invalid_reason = '') "
            f"AND c.vocabulary_id IN {in_literals(vocabularies)}"
        )
        return [
            ReverseMapRow(
                standard_concept_id=int(r["standard_concept_id"]),
                source_concept_id=int(r["source_concept_id"]),
                source_concept_code=str(r["source_concept_code"]),
                source_concept_name=str(r["source_concept_name"]),
                source_vocabulary_id=str(r["source_vocabulary_id"]),
            )
            for r in self._fetch(sql)
        ]

    def get_descendants(self, concept_ids: list[int]) -> dict[int, list[int]]:
        if not self.supports_ancestors or not concept_ids:
            return {}
        ids = sorted({int(i) for i in concept_ids})
        sql = (
            f"SELECT ancestor_concept_id, descendant_concept_id "
            f"FROM {self._table('concept_ancestor')} "
            f"WHERE ancestor_concept_id IN {in_ints(ids)} "
            f"AND descendant_concept_id != ancestor_concept_id"
        )
        result: dict[int, list[int]] = {}
        for r in self._fetch(sql):
            ancestor = int(r["ancestor_concept_id"])
            result.setdefault(ancestor, []).append(int(r["descendant_concept_id"]))
        return result

    def count_in_table(
        self,
        table: str,
        concept_column: str,
        concept_ids: list[int],
        catalog: str | None = None,
        schema: str | None = None,
    ) -> dict[int, int]:
        if not concept_ids:
            return {}
        ids = sorted({int(i) for i in concept_ids})
        sql = (
            f"SELECT {concept_column} AS concept_id, COUNT(*) AS record_count "
            f"FROM {self._table(table, catalog, schema)} "
            f"WHERE {concept_column} IN {in_ints(ids)} "
            f"GROUP BY {concept_column}"
        )
        return {int(r["concept_id"]): int(r["record_count"]) for r in self._fetch(sql)}
