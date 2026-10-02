"""Build an OHDSI Circe ConceptSetExpression JSON from a mapping result."""

from __future__ import annotations

import json
from pathlib import Path

from concept_mapper.models import ConceptRow, MappingResult, StandardConcept

_STANDARD_CAPTION = {"S": "Standard", "C": "Classification"}
_INVALID_CAPTION = {"D": "Deprecated", "U": "Updated"}


def concept_to_dict(concept: ConceptRow) -> dict:
    return {
        "CONCEPT_ID": concept.concept_id,
        "CONCEPT_NAME": concept.concept_name or "",
        "STANDARD_CONCEPT": concept.standard_concept or "",
        "STANDARD_CONCEPT_CAPTION": _STANDARD_CAPTION.get(
            concept.standard_concept or "", ""
        ),
        "INVALID_REASON": concept.invalid_reason or "",
        "INVALID_REASON_CAPTION": _INVALID_CAPTION.get(concept.invalid_reason or "", ""),
        "CONCEPT_CODE": concept.concept_code or "",
        "DOMAIN_ID": concept.domain_id or "",
        "VOCABULARY_ID": concept.vocabulary_id or "",
        "CONCEPT_CLASS_ID": concept.concept_class_id or "",
    }


def _item(concept: ConceptRow, *, excluded: bool = False) -> dict:
    return {
        "concept": concept_to_dict(concept),
        "isExcluded": excluded,
        "includeDescendants": False,
        "includeMapped": False,
    }


def build_concept_set(
    result: MappingResult,
    exclusions: list[StandardConcept],
) -> dict:
    items: list[dict] = []
    for concept_id in result.standard_ids:
        items.append(_item(result.standard_concepts[concept_id].concept))
    for standard in exclusions:
        items.append(_item(standard.concept, excluded=True))
    return {"items": items}


def write_concept_set(
    path: str | Path,
    result: MappingResult,
    exclusions: list[StandardConcept],
    name: str | None = None,
) -> Path:
    path = Path(path)
    data = build_concept_set(result, exclusions)
    if name:
        data["name"] = name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path
