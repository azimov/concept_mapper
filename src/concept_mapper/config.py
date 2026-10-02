"""Configuration and repository factory."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from concept_mapper.repository import DatabricksRepository, DuckDBRepository, VocabularyRepository

DEFAULT_SOURCE_VOCABULARIES = ["ICD10CM", "ICD9CM", "ICDO3", "ICD10PCS", "ICD9Proc"]


@dataclass
class Settings:
    backend: str = "databricks"
    source_vocabularies: list[str] = field(
        default_factory=lambda: list(DEFAULT_SOURCE_VOCABULARIES)
    )
    target_vocabulary: str = "SNOMED"
    output_dir: str = "out"
    name: str = "Concept set"
    server_hostname: str | None = None
    http_path: str | None = None
    token: str | None = None
    catalog: str | None = None
    schema: str | None = None
    cdm_catalog: str | None = None
    cdm_schema: str | None = None
    csv_dir: str | None = None
    db_path: str | None = None


def settings_from_env(settings: Settings) -> Settings:
    settings.server_hostname = settings.server_hostname or os.environ.get(
        "DATABRICKS_SERVER_HOSTNAME"
    )
    settings.http_path = settings.http_path or os.environ.get("DATABRICKS_HTTP_PATH")
    settings.token = settings.token or os.environ.get("DATABRICKS_TOKEN")
    settings.catalog = settings.catalog or os.environ.get("DATABRICKS_CATALOG")
    settings.schema = settings.schema or os.environ.get("DATABRICKS_SCHEMA")
    settings.csv_dir = settings.csv_dir or os.environ.get("CONCEPT_MAPPER_CSV_DIR")
    return settings


def build_repository(settings: Settings) -> VocabularyRepository:
    if settings.backend == "duckdb":
        return DuckDBRepository(csv_dir=settings.csv_dir, db_path=settings.db_path)
    if settings.backend == "databricks":
        return DatabricksRepository(
            server_hostname=settings.server_hostname or "",
            http_path=settings.http_path or "",
            token=settings.token or "",
            catalog=settings.catalog or "",
            schema=settings.schema or "",
        )
    raise ValueError(f"Unknown backend: {settings.backend!r} (choose 'databricks' or 'duckdb')")
