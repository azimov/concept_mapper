"""Command-line interface for concept-mapper."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from concept_mapper import __version__
from concept_mapper.config import (
    DEFAULT_SOURCE_VOCABULARIES,
    Settings,
    build_repository,
    settings_from_env,
)
from concept_mapper.connections import (
    cdm_schema_parts,
    load_connection,
    vocabulary_schema_parts,
)
from concept_mapper.frequency import count_frequencies
from concept_mapper.mapping import map_codes
from concept_mapper.output.concept_set import write_concept_set
from concept_mapper.output.excel import write_source_impact, write_workbook
from concept_mapper.source_impact import compute_source_impact, resolve_concept_set_ids
from concept_mapper.validation import validate_result

app = typer.Typer(help="Build OHDSI Standard concept sets from lists of source codes.")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"concept-mapper {__version__}")
        raise typer.Exit()


def read_codes_file(path: Path) -> list[str]:
    with path.open(newline="") as fh:
        sample = fh.read(4096)
    lines = sample.splitlines()
    if lines and "," in lines[0]:
        with path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames and "code" not in reader.fieldnames:
                raise typer.BadParameter(f"CSV {path} must contain a 'code' column.")
            return [row["code"].strip() for row in reader if row.get("code", "").strip()]
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True)
    ] = False,
) -> None:
    pass


@app.command()
def map(
    codes: Annotated[
        str, typer.Option("--codes", "-c", help="Comma-separated source codes.")
    ] = None,
    codes_file: Annotated[
        Path,
        typer.Option("--codes-file", "-f", help="File of codes (one per line or CSV with 'code')."),
    ] = None,
    source_vocabularies: Annotated[
        str,
        typer.Option("--source-vocabularies", "-s", help="Comma-separated source vocabularies."),
    ] = None,
    target_vocabulary: Annotated[
        str, typer.Option("--target-vocabulary", "-t", help="Target standard vocabulary.")
    ] = "SNOMED",
    domain: Annotated[
        str,
        typer.Option(
            "--domain", "-d", help="Comma-separated target domains to keep (e.g. Condition)."
        ),
    ] = None,
    backend: Annotated[
        str, typer.Option("--backend", "-b", help="Backend: databricks or duckdb.")
    ] = "databricks",
    catalog: Annotated[str, typer.Option("--catalog", help="Databricks catalog.")] = None,
    schema: Annotated[str, typer.Option("--schema", help="Databricks schema.")] = None,
    connection: Annotated[
        str,
        typer.Option(
            "--connection", help="Named connection from .config/ohdsi/<name>_connection.yml."
        ),
    ] = None,
    cdm: Annotated[
        str, typer.Option("--cdm", help="CDM to use from the connection config.")
    ] = None,
    config_dir: Annotated[
        Path, typer.Option("--config-dir", help="Directory holding <name>_connection.yml files.")
    ] = None,
    csv_dir: Annotated[
        Path, typer.Option("--csv-dir", help="Directory of ATHENA CSVs (DuckDB backend).")
    ] = None,
    exclude_codes: Annotated[
        str,
        typer.Option("--exclude-codes", help="Comma-separated source codes to exclude."),
    ] = None,
    exclude_codes_file: Annotated[
        Path,
        typer.Option("--exclude-codes-file", help="File of codes to exclude (isExcluded: true)."),
    ] = None,
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Output directory.")
    ] = Path("out"),
    name: Annotated[
        str, typer.Option("--name", "-n", help="Concept set name.")
    ] = "Concept set",
    count: Annotated[
        bool,
        typer.Option(
            "--count", help="Count standard/source concept record frequency in the CDM."
        ),
    ] = False,
) -> None:
    all_codes = _split_csv(codes)
    if codes_file:
        all_codes.extend(read_codes_file(codes_file))
    if not all_codes:
        raise typer.BadParameter("No codes provided (use --codes or --codes-file).")

    all_exclude_codes = _split_csv(exclude_codes)
    if exclude_codes_file:
        all_exclude_codes.extend(read_codes_file(exclude_codes_file))

    src_vocabularies = _split_csv(source_vocabularies) or list(DEFAULT_SOURCE_VOCABULARIES)
    target_domains = _split_csv(domain)
    settings = Settings(
        backend=backend,
        target_vocabulary=target_vocabulary,
        output_dir=str(output_dir),
        name=name,
        catalog=catalog,
        schema=schema,
        csv_dir=str(csv_dir) if csv_dir else None,
    )
    if connection:
        config = load_connection(connection, str(config_dir) if config_dir else None)
        resolved_catalog, resolved_schema = vocabulary_schema_parts(config, cdm)
        settings.backend = config.driver
        settings.server_hostname = config.databricks.server_hostname
        settings.http_path = config.databricks.http_path
        settings.token = config.databricks.token
        settings.catalog = resolved_catalog or catalog
        settings.schema = resolved_schema or schema
        cdm_catalog, cdm_schema = cdm_schema_parts(config, cdm)
        settings.cdm_catalog = cdm_catalog or resolved_catalog
        settings.cdm_schema = cdm_schema
    settings = settings_from_env(settings)

    if count and not settings.cdm_schema:
        raise typer.BadParameter(
            "--count requires a CDM (provide --connection with a cdm block)."
        )

    repo = build_repository(settings)
    try:
        result = map_codes(
            repo, all_codes, src_vocabularies, settings.target_vocabulary, target_domains
        )
        report = validate_result(repo, result, src_vocabularies, settings.target_vocabulary)
        excluded_result = (
            map_codes(
                repo,
                all_exclude_codes,
                src_vocabularies,
                settings.target_vocabulary,
                target_domains,
            )
            if all_exclude_codes
            else None
        )
        if count:
            count_frequencies(
                repo,
                result,
                settings.cdm_catalog,
                settings.cdm_schema,
                src_vocabularies,
            )
    finally:
        repo.close()

    out_dir = Path(settings.output_dir)
    json_path = write_concept_set(
        out_dir / "concept_set.json",
        result,
        report.exclusions,
        name=settings.name,
        excluded_result=excluded_result,
    )
    xlsx_path = write_workbook(out_dir / "concept_set.xlsx", report, excluded_result)

    console.print(f"Input codes:       {len(result.source_matches)}")
    console.print(f"Mapped:            {len(result.source_matches) - len(report.missed)}")
    console.print(f"Missed:            {len(report.missed)}")
    console.print(f"Standard concepts: {len(result.standard_ids)}")
    console.print(f"Added/overbroad:   {len(report.added)}")
    console.print(f"Suggested exclusions: {len(report.exclusions)}")
    console.print(f"Needs review:      {len(report.needs_review)}")
    console.print(f"Wrote: {json_path}")
    console.print(f"Wrote: {xlsx_path}")


@app.command("source-impact")
def source_impact(
    concept_set: Annotated[
        Path, typer.Option("--concept-set", help="Circe concept set JSON (from `map`).")
    ],
    codes: Annotated[str, typer.Option("--codes", "-c", help="Comma-separated source codes.")] = None,
    codes_file: Annotated[Path, typer.Option("--codes-file", "-f")] = None,
    source_vocabularies: Annotated[str, typer.Option("--source-vocabularies", "-s")] = None,
    target_vocabulary: Annotated[str, typer.Option("--target-vocabulary", "-t")] = "SNOMED",
    domain: Annotated[str, typer.Option("--domain", "-d", help="CDM domain table.")] = "Condition",
    backend: Annotated[str, typer.Option("--backend", "-b")] = "databricks",
    catalog: Annotated[str, typer.Option("--catalog")] = None,
    schema: Annotated[str, typer.Option("--schema")] = None,
    connection: Annotated[str, typer.Option("--connection")] = None,
    cdm: Annotated[str, typer.Option("--cdm")] = None,
    config_dir: Annotated[Path, typer.Option("--config-dir")] = None,
    csv_dir: Annotated[Path, typer.Option("--csv-dir")] = None,
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("out"),
) -> None:
    """Person-level (cohort-free) impact of each source code on a concept set."""
    all_codes = _split_csv(codes)
    if codes_file:
        all_codes.extend(read_codes_file(codes_file))
    if not all_codes:
        raise typer.BadParameter("No codes provided (use --codes or --codes-file).")
    src_vocabularies = _split_csv(source_vocabularies) or list(DEFAULT_SOURCE_VOCABULARIES)
    settings = Settings(
        backend=backend,
        target_vocabulary=target_vocabulary,
        catalog=catalog,
        schema=schema,
        csv_dir=str(csv_dir) if csv_dir else None,
    )
    if connection:
        config = load_connection(connection, str(config_dir) if config_dir else None)
        resolved_catalog, resolved_schema = vocabulary_schema_parts(config, cdm)
        settings.backend = config.driver
        settings.server_hostname = config.databricks.server_hostname
        settings.http_path = config.databricks.http_path
        settings.token = config.databricks.token
        settings.catalog = resolved_catalog or catalog
        settings.schema = resolved_schema or schema
        cdm_catalog, cdm_schema = cdm_schema_parts(config, cdm)
        settings.cdm_catalog = cdm_catalog or resolved_catalog
        settings.cdm_schema = cdm_schema
    settings = settings_from_env(settings)

    expression = json.loads(concept_set.read_text())
    repo = build_repository(settings)
    try:
        standard_ids = resolve_concept_set_ids(repo, expression)
        result = map_codes(repo, all_codes, src_vocabularies, settings.target_vocabulary, [])
        impact = compute_source_impact(
            repo, standard_ids, result, domain, settings.cdm_catalog, settings.cdm_schema
        )
    finally:
        repo.close()

    xlsx_path = write_source_impact(Path(output_dir) / "source_impact.xlsx", impact)
    console.print(f"Concept set standard concepts: {len(standard_ids)}")
    console.print(f"Persons in set:    {impact.total_persons}")
    for label, m in sorted(impact.by_code.items(), key=lambda kv: -kv[1]["unique_persons"]):
        console.print(f"  {label}: persons={m['persons']} lost_if_removed={m['unique_persons']}")
    console.print(f"Wrote: {xlsx_path}")


if __name__ == "__main__":
    app()
