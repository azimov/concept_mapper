import pytest

from concept_mapper.connections import (
    load_connection,
    pick_cdm,
    vocabulary_schema_parts,
)

YAML = """\
databricks:
  driver: databricks
  connection:
    server_hostname: adb-123.azuredatabricks.net
    http_path: /sql/1.0/warehouse/abc123
    personal_access_token: dapi-secret
cdms:
  primary:
    cdm_schema: main.cdm
    vocabulary_schema: main.vocab
    results_schema: main.results
  secondary:
    cdm_schema: other.cdm
"""


@pytest.fixture
def conn_dir(tmp_path):
    (tmp_path / "test_connection.yml").write_text(YAML)
    return tmp_path


def test_load_connection(conn_dir):
    config = load_connection("test", str(conn_dir))
    assert config.driver == "databricks"
    assert config.databricks.server_hostname == "adb-123.azuredatabricks.net"
    assert config.databricks.token == "dapi-secret"
    assert set(config.cdms) == {"primary", "secondary"}


def test_vocabulary_schema_parts_explicit(conn_dir):
    config = load_connection("test", str(conn_dir))
    assert vocabulary_schema_parts(config, "primary") == ("main", "vocab")


def test_vocabulary_schema_defaults_to_cdm(conn_dir):
    config = load_connection("test", str(conn_dir))
    assert vocabulary_schema_parts(config, "secondary") == ("other", "cdm")


def test_pick_cdm_requires_name_when_multiple(conn_dir):
    config = load_connection("test", str(conn_dir))
    with pytest.raises(ValueError):
        pick_cdm(config)


def test_missing_connection_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_connection("nope", str(tmp_path))
