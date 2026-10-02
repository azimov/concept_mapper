"""Excel workbook output with highlight of missed and added concepts."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from concept_mapper.models import ValidationReport

_RED = PatternFill(start_color="FFFFC7CE", end_color="FFFFC7CE", fill_type="solid")
_RED_FONT = Font(color="FF9C0006")
_YELLOW = PatternFill(start_color="FFFFEB9C", end_color="FFFFEB9C", fill_type="solid")
_YELLOW_FONT = Font(color="FF9C6500")
_HEADER_FILL = PatternFill(start_color="FFDDEBF7", end_color="FFDDEBF7", fill_type="solid")
_HEADER_FONT = Font(bold=True)


def _autosize(ws, widths: list[int]) -> None:
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width


def _write_header(ws, columns: list[str], widths: list[int]) -> None:
    ws.append(columns)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    _autosize(ws, widths)


def _std_refs(ids: list[int], report: ValidationReport) -> tuple[str, str, str]:
    names: list[str] = []
    codes: list[str] = []
    for cid in ids:
        standard = report.result.standard_concepts.get(cid)
        if standard is not None:
            names.append(standard.concept.concept_name)
            codes.append(standard.concept.concept_code)
    return (
        "; ".join(str(i) for i in ids),
        "; ".join(codes),
        "; ".join(names),
    )


def write_workbook(path: str | Path, report: ValidationReport) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    # ── Source Codes sheet ────────────────────────────────────────────
    ws = wb.active
    ws.title = "Source Codes"
    _write_header(
        ws,
        [
            "input_code",
            "matched_code",
            "match_type",
            "source_concept_id",
            "source_concept_name",
            "source_vocabulary_id",
            "source_domain_id",
            "standard_concept_ids",
            "standard_concept_codes",
            "standard_concept_names",
            "value_concept_ids",
            "source_record_count",
            "status",
            "notes",
        ],
        [14, 14, 12, 18, 42, 20, 16, 18, 24, 48, 18, 18, 12, 50],
    )
    for match in report.result.source_matches:
        src = match.source_concept
        std_ids, std_codes, std_names = _std_refs(match.standard_concept_ids, report)
        row = [
            match.input_code,
            match.matched_code or "",
            match.match_type,
            src.concept_id if src else "",
            src.concept_name if src else "",
            src.vocabulary_id if src else "",
            src.domain_id if src else "",
            std_ids,
            std_codes,
            std_names,
            "; ".join(str(v) for v in match.value_concept_ids),
            match.source_record_count if match.source_record_count is not None else "",
            match.status,
            "; ".join(match.notes),
        ]
        ws.append(row)
        if match.status != "mapped":
            for cell in ws[ws.max_row]:
                cell.fill = _RED
                cell.font = _RED_FONT

    # ── Standard Concepts sheet ───────────────────────────────────────
    ws2 = wb.create_sheet("Standard Concepts")
    _write_header(
        ws2,
        [
            "concept_id",
            "concept_code",
            "concept_name",
            "vocabulary_id",
            "domain_id",
            "concept_class_id",
            "source_codes",
            "extra_source_codes",
            "record_count",
            "is_overbroad",
            "recommendation",
        ],
        [18, 14, 48, 14, 14, 18, 40, 40, 14, 14, 24],
    )
    recommendation_by_id: dict[int, str] = {}
    for standard in report.exclusions:
        recommendation_by_id[standard.concept.concept_id] = "exclude"
    for standard in report.needs_review:
        recommendation_by_id[standard.concept.concept_id] = "needs review"

    for cid in report.result.standard_ids:
        standard = report.result.standard_concepts[cid]
        c = standard.concept
        ws2.append(
            [
                c.concept_id,
                c.concept_code,
                c.concept_name,
                c.vocabulary_id,
                c.domain_id,
                c.concept_class_id,
                "; ".join(standard.source_codes),
                "; ".join(standard.extra_source_codes),
                standard.record_count if standard.record_count is not None else "",
                "yes" if standard.is_overbroad else "no",
                recommendation_by_id.get(cid, ""),
            ]
        )
        if standard.is_overbroad:
            for cell in ws2[ws2.max_row]:
                cell.fill = _YELLOW
                cell.font = _YELLOW_FONT

    # ── Summary sheet ─────────────────────────────────────────────────
    ws3 = wb.create_sheet("Summary")
    _write_header(ws3, ["section", "detail"], [24, 100])
    total = len(report.result.source_matches)
    mapped = total - len(report.missed)
    ws3.append(["total input codes", str(total)])
    ws3.append(["mapped", str(mapped)])
    ws3.append(["missed", str(len(report.missed))])
    ws3.append(["standard concepts in set", str(len(report.result.standard_ids))])
    ws3.append(["added / overbroad", str(len(report.added))])
    ws3.append(["suggested exclusions", str(len(report.exclusions))])
    ws3.append(["needs review", str(len(report.needs_review))])
    ws3.append([])
    ws3.append(["Missed source codes", ""])
    for m in report.missed:
        reason = "not found" if m.match_type == "not_found" else "no standard mapping"
        ws3.append([m.input_code, reason])
    ws3.append([])
    ws3.append(["Added / overbroad standard concepts", ""])
    for standard in report.added:
        c = standard.concept
        ws3.append(
            [f"{c.concept_id} ({c.concept_code})",
             f"{c.concept_name} -> extra codes: {', '.join(standard.extra_source_codes)}"]
        )
    ws3.append([])
    ws3.append(["Suggested exclusions", ""])
    for standard in report.exclusions:
        c = standard.concept
        ws3.append([f"{c.concept_id} ({c.concept_code})", c.concept_name])
    ws3.append([])
    ws3.append(["Needs review (overbroad but required)", ""])
    for standard in report.needs_review:
        c = standard.concept
        suggestions = report.descendant_suggestions.get(c.concept_id, [])
        desc = "; ".join(f"{d.concept_id} {d.concept_name}" for d in suggestions)
        ws3.append([f"{c.concept_id} ({c.concept_code})", f"{c.concept_name}; consider: {desc}"])

    wb.save(path)
    return path
