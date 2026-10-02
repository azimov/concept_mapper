from openpyxl import load_workbook

from concept_mapper.mapping import map_codes
from concept_mapper.output.concept_set import build_concept_set, write_concept_set
from concept_mapper.output.excel import write_workbook
from concept_mapper.validation import validate_result

SOURCE_VOCABULARIES = ["ICD10CM"]


def _report(repo):
    result = map_codes(repo, ["E11.9", "C01.9", "I21.0", "Z01.0"], SOURCE_VOCABULARIES, "SNOMED")
    return validate_result(repo, result, SOURCE_VOCABULARIES, "SNOMED")


def test_concept_set_json_includes_exclusions(repo):
    report = _report(repo)
    data = build_concept_set(report.result, report.exclusions)
    assert len(data["items"]) == len(report.result.standard_ids) + len(report.exclusions)
    concepts = {i["concept"]["CONCEPT_ID"]: i for i in data["items"]}
    assert concepts[2004]["isExcluded"] is True
    assert concepts[2001]["isExcluded"] is False
    assert concepts[2001]["concept"]["CONCEPT_CODE"] == "44054006"


def test_write_concept_set(repo, tmp_path):
    report = _report(repo)
    path = write_concept_set(
        tmp_path / "concept_set.json", report.result, report.exclusions, name="x"
    )
    assert path.exists()
    assert '"items"' in path.read_text()


def test_write_workbook(repo, tmp_path):
    report = _report(repo)
    path = write_workbook(tmp_path / "concept_set.xlsx", report)
    assert path.exists()
    wb = load_workbook(path)
    assert wb.sheetnames == ["Source Codes", "Standard Concepts", "Summary"]
