from pathlib import Path

from typer.testing import CliRunner

from concept_mapper.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
runner = CliRunner()


def test_cli_end_to_end(tmp_path):
    result = runner.invoke(
        app,
        [
            "map",
            "--codes",
            "E11.9,C01.9",
            "--source-vocabularies",
            "ICD10CM",
            "--backend",
            "duckdb",
            "--csv-dir",
            str(FIXTURES),
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "concept_set.json").exists()
    assert (tmp_path / "concept_set.xlsx").exists()


def test_cli_requires_codes():
    result = runner.invoke(app, ["map"])
    assert result.exit_code != 0
