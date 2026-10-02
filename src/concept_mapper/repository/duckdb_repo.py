"""DuckDB-backed vocabulary repository (local ATHENA CSV files)."""

from __future__ import annotations

from pathlib import Path

import duckdb

from concept_mapper.repository.base import VocabularyRepository


class DuckDBRepository(VocabularyRepository):
    def __init__(self, csv_dir: str | None = None, db_path: str | None = None):
        self._conn = duckdb.connect(db_path or ":memory:")
        self._owns_connection = True
        self.supports_ancestors = False
        if csv_dir:
            self._load_csvs(Path(csv_dir))

    def _load_csvs(self, csv_dir: Path) -> None:
        concept = csv_dir / "CONCEPT.csv"
        relationship = csv_dir / "CONCEPT_RELATIONSHIP.csv"
        ancestor = csv_dir / "CONCEPT_ANCESTOR.csv"
        if not concept.exists():
            raise FileNotFoundError(f"Missing CONCEPT.csv in {csv_dir}")
        if not relationship.exists():
            raise FileNotFoundError(f"Missing CONCEPT_RELATIONSHIP.csv in {csv_dir}")
        self._conn.execute(
            "CREATE TABLE concept AS SELECT * FROM read_csv_auto(?, header=true)",
            [str(concept)],
        )
        self._conn.execute(
            "CREATE TABLE concept_relationship AS "
            "SELECT * FROM read_csv_auto(?, header=true)",
            [str(relationship)],
        )
        if ancestor.exists():
            self._conn.execute(
                "CREATE TABLE concept_ancestor AS "
                "SELECT * FROM read_csv_auto(?, header=true)",
                [str(ancestor)],
            )
            self.supports_ancestors = True

    def _table(self, name: str, catalog: str | None = None, schema: str | None = None) -> str:
        return name

    def load_table(self, name: str, csv_path: str) -> None:
        self._conn.execute(
            "CREATE TABLE " + name + " AS SELECT * FROM read_csv_auto(?, header=true)",
            [csv_path],
        )

    def _fetch(self, sql: str) -> list[dict]:
        result = self._conn.execute(sql)
        columns = [d[0] for d in result.description]
        return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
