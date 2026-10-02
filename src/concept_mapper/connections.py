"""Load OHDSI connection configuration from YAML files.

Expected layout (``.config/ohdsi/<name>_connection.yml``)::

    databricks:
      driver: databricks
      connection:
        server_hostname: <host>.url
        http_path: /sql/1.0/warehouse/<id>
        personal_access_token: <token>
    cdms:
      mycdm:
        cdm_schema: catalog.schema
        vocabulary_schema: catalog.schema_vocab   # optional, defaults to cdm_schema
        results_schema: catalog.schema_results
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "ohdsi"


@dataclass
class DatabricksConnection:
    server_hostname: str = ""
    http_path: str = ""
    token: str = ""
    catalog: str | None = None
    schema: str | None = None


@dataclass
class Cdm:
    name: str
    cdm_schema: str = ""
    vocabulary_schema: str | None = None
    results_schema: str | None = None


@dataclass
class ConnectionConfig:
    name: str
    driver: str = "databricks"
    databricks: DatabricksConnection = field(default_factory=DatabricksConnection)
    cdms: dict[str, Cdm] = field(default_factory=dict)


def resolve_config_dir(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser()
    env = os.environ.get("CONCEPT_MAPPER_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    return DEFAULT_CONFIG_DIR


def load_connection(
    name: str, config_dir: str | None = None
) -> ConnectionConfig:
    path = resolve_config_dir(config_dir) / f"{name}_connection.yml"
    if not path.exists():
        raise FileNotFoundError(
            f"Connection config not found: {path} "
            f"(looked for .config/ohdsi/{name}_connection.yml)"
        )
    data = yaml.safe_load(path.read_text()) or {}

    databricks = data.get("databricks") or {}
    connection = databricks.get("connection") or {}
    databricks_conn = DatabricksConnection(
        server_hostname=str(connection.get("server_hostname") or ""),
        http_path=str(connection.get("http_path") or ""),
        token=str(
            connection.get("personal_access_token")
            or connection.get("token")
            or ""
        ),
        catalog=connection.get("catalog"),
        schema=connection.get("schema"),
    )

    cdms: dict[str, Cdm] = {}
    for cdm_name, raw in (data.get("cdms") or {}).items():
        cdms[cdm_name] = Cdm(
            name=cdm_name,
            cdm_schema=str(raw.get("cdm_schema") or ""),
            vocabulary_schema=raw.get("vocabulary_schema"),
            results_schema=raw.get("results_schema"),
        )

    return ConnectionConfig(
        name=name,
        driver=str(databricks.get("driver") or "databricks"),
        databricks=databricks_conn,
        cdms=cdms,
    )


def pick_cdm(config: ConnectionConfig, cdm_name: str | None = None) -> Cdm:
    if not config.cdms:
        raise ValueError(f"Connection '{config.name}' defines no cdms.")
    if cdm_name:
        if cdm_name not in config.cdms:
            raise ValueError(
                f"Unknown cdm '{cdm_name}'. Available: {', '.join(sorted(config.cdms))}"
            )
        return config.cdms[cdm_name]
    if len(config.cdms) == 1:
        return next(iter(config.cdms.values()))
    raise ValueError(
        f"Connection '{config.name}' has multiple cdms "
        f"({', '.join(sorted(config.cdms))}); select one with --cdm."
    )


def split_schema(schema: str | None) -> tuple[str | None, str | None]:
    if not schema:
        return None, None
    if "." in schema:
        catalog, _, rest = schema.partition(".")
        return catalog, rest
    return None, schema


def vocabulary_schema_parts(
    config: ConnectionConfig, cdm_name: str | None = None
) -> tuple[str | None, str | None]:
    """Resolve (catalog, schema) for the vocabulary from the selected cdm."""
    cdm = pick_cdm(config, cdm_name)
    vocab = cdm.vocabulary_schema or cdm.cdm_schema
    catalog, schema = split_schema(vocab)
    if catalog is None:
        catalog = config.databricks.catalog
    if schema is None:
        schema = config.databricks.schema
    return catalog, schema


def cdm_schema_parts(
    config: ConnectionConfig, cdm_name: str | None = None
) -> tuple[str | None, str | None]:
    """Resolve (catalog, schema) for the CDM data tables from the selected cdm."""
    cdm = pick_cdm(config, cdm_name)
    catalog, schema = split_schema(cdm.cdm_schema)
    if catalog is None:
        catalog = config.databricks.catalog
    return catalog, schema
