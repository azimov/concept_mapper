"""Cohort-free, person-level impact of each source code on a concept set.

The concept set is resolved to standard concept ids with ohdsi-circepy's query
builder, then qualifying records are counted per person with no index dates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from circe.vocabulary.concept import ConceptSetExpression
from circe.vocabulary.concept_set_expression_query_builder import (
    ConceptSetExpressionQueryBuilder,
)

from concept_mapper.frequency import DOMAIN_TABLES
from concept_mapper.models import MappingResult
from concept_mapper.repository.base import VocabularyRepository, in_ints, quote

UNLISTED_PREFIX = "unlisted: "
OTHER_LABEL = "(no source concept)"


@dataclass
class SourceImpact:
    total_persons: int = 0
    total_records: int = 0
    # label -> (persons, records, persons only captured by this code)
    by_code: dict[str, dict[str, int]] = field(default_factory=dict)
    by_standard: list[dict] = field(default_factory=list)
    overlap: list[dict] = field(default_factory=list)
    standard_ids: list[int] = field(default_factory=list)


def resolve_concept_set_ids(
    repo: VocabularyRepository, expression: dict, vocabulary_schema_prefix: str | None = None
) -> list[int]:
    """Resolve a Circe concept set expression to concept ids using circepy SQL."""
    parsed = ConceptSetExpression.model_validate(expression)
    sql = ConceptSetExpressionQueryBuilder().build_expression_query(parsed)
    prefix = vocabulary_schema_prefix
    if prefix is None:
        prefix = repo._table("x")[: -len("x")]
    sql = sql.replace("@vocabulary_database_schema.", prefix)
    return sorted({int(r["concept_id"]) for r in repo._fetch(sql)})


def _label_values(result: MappingResult) -> tuple[str, list[str]]:
    rows: dict[int, str] = {}
    labels: list[str] = []
    for match in result.source_matches:
        ids = match.source_concept_ids or (
            [match.source_concept.concept_id] if match.source_concept else []
        )
        if not ids:
            continue
        labels.append(match.input_code)
        for cid in ids:
            rows.setdefault(int(cid), match.input_code)
    if not rows:
        return "SELECT CAST(NULL AS BIGINT) AS src_id, CAST(NULL AS VARCHAR) AS label WHERE 1=0", labels
    values = ", ".join(f"({cid}, {quote(label)})" for cid, label in rows.items())
    return f"SELECT * FROM (VALUES {values}) AS v(src_id, label)", labels


def compute_source_impact(
    repo: VocabularyRepository,
    standard_ids: list[int],
    result: MappingResult,
    domain: str = "Condition",
    catalog: str | None = None,
    schema: str | None = None,
) -> SourceImpact:
    table, std_col, src_col = DOMAIN_TABLES[domain]
    impact = SourceImpact(standard_ids=list(standard_ids))
    if not standard_ids:
        return impact
    labels_sql, _ = _label_values(result)
    tbl = repo._table(table, catalog, schema)
    base = (
        f"WITH labels AS ({labels_sql}), "
        f"base AS (SELECT t.person_id AS person_id, t.{std_col} AS std_id, "
        f"COALESCE(l.label, '{UNLISTED_PREFIX}' || c.concept_code, {quote(OTHER_LABEL)}) AS label "
        f"FROM {tbl} t LEFT JOIN labels l ON t.{src_col} = l.src_id "
        f"LEFT JOIN {repo._table('concept')} c ON c.concept_id = t.{src_col} "
        f"WHERE t.{std_col} IN {in_ints(standard_ids)}), "
        f"pl AS (SELECT DISTINCT person_id, label FROM base)"
    )

    totals = repo._fetch(
        base + " SELECT COUNT(DISTINCT person_id) AS persons, COUNT(*) AS records FROM base"
    )[0]
    impact.total_persons = int(totals["persons"] or 0)
    impact.total_records = int(totals["records"] or 0)

    per_code = repo._fetch(
        base + " SELECT label, COUNT(DISTINCT person_id) AS persons, COUNT(*) AS records "
        "FROM base GROUP BY label"
    )
    unique = repo._fetch(
        base + ", n AS (SELECT person_id, COUNT(*) AS n FROM pl GROUP BY person_id) "
        "SELECT pl.label AS label, COUNT(*) AS persons FROM pl "
        "JOIN n ON pl.person_id = n.person_id WHERE n.n = 1 GROUP BY pl.label"
    )
    unique_by = {r["label"]: int(r["persons"]) for r in unique}
    for r in per_code:
        impact.by_code[r["label"]] = {
            "persons": int(r["persons"]),
            "records": int(r["records"]),
            "unique_persons": unique_by.get(r["label"], 0),
        }

    impact.by_standard = [
        {
            "standard_concept_id": int(r["std_id"]),
            "label": r["label"],
            "persons": int(r["persons"]),
            "records": int(r["records"]),
        }
        for r in repo._fetch(
            base + " SELECT std_id, label, COUNT(DISTINCT person_id) AS persons, "
            "COUNT(*) AS records FROM base GROUP BY std_id, label ORDER BY std_id, label"
        )
    ]
    impact.overlap = [
        {"code_a": r["code_a"], "code_b": r["code_b"], "persons": int(r["persons"])}
        for r in repo._fetch(
            base + " SELECT a.label AS code_a, b.label AS code_b, "
            "COUNT(*) AS persons FROM pl a JOIN pl b "
            "ON a.person_id = b.person_id AND a.label < b.label "
            "GROUP BY a.label, b.label ORDER BY persons DESC"
        )
    ]
    return impact
