"""Databricks SQL-backed vocabulary repository."""

from __future__ import annotations

from concept_mapper.repository.base import VocabularyRepository, quote


class DatabricksRepository(VocabularyRepository):
    def __init__(
        self,
        server_hostname: str,
        http_path: str,
        token: str,
        catalog: str,
        schema: str,
    ):
        from databricks import sql

        if not all([server_hostname, http_path, token]):
            raise ValueError(
                "Databricks requires server_hostname, http_path and token "
                "(set via args or DATABRICKS_* env vars)."
            )
        self._catalog = catalog
        self._schema = schema
        self.supports_ancestors = True
        self._conn = sql.connect(
            server_hostname=server_hostname,
            http_path=http_path,
            access_token=token,
            catalog=catalog or None,
            schema=schema or None,
        )
        self._cursor = self._conn.cursor()

    def _table(self, name: str, catalog: str | None = None, schema: str | None = None) -> str:
        c = catalog or self._catalog
        s = schema or self._schema
        if c and s:
            return f"{c}.{s}.{name}"
        if s:
            return f"{s}.{name}"
        return name

    def _regex_predicate(self, column: str, pattern: str) -> str:
        # Spark SQL string literals treat backslash as an escape character.
        return f"{column} RLIKE {quote('(?i)' + pattern.replace(chr(92), chr(92) * 2))}"

    def _fetch(self, sql: str) -> list[dict]:
        self._cursor.execute(sql)
        columns = [d[0] for d in self._cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in self._cursor.fetchall()]

    def close(self) -> None:
        if self._cursor is not None:
            try:
                self._cursor.close()
            except Exception:
                pass
            self._cursor = None
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
