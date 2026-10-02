# concept-mapper

A small CLI that builds standard OHDSI/OMOP concept sets from ICD 9/10/O-3
(and other source) code strings.

Given a list of source codes such as `C01.9` or `E11.9`, it:

1. Resolves each code to a source concept (with dot-normalisation and
   hierarchy roll-up, e.g. `C01.9` -> `C01` when the sub-code is absent).
2. Follows `Maps to` relationships to the standard target vocabulary
   (SNOMED by default), chasing multi-hop mappings until standard concepts
   are reached.
3. Emits an OHDSI Circe `ConceptSetExpression` JSON for the standard concepts.
4. Validates the set against the input list and writes an Excel workbook that
   highlights:
   - **missed** source codes (not found / no standard mapping), and
   - **added** standard concepts that map back to source codes *not* in the
     original input (overbroad), with suggested exclusions.

The vocabulary is read from a **Databricks SQL** database (primary) or from
local ATHENA CSV files via **DuckDB** (used for tests / local runs).

## Install

```bash
uv sync
```

## Usage

Databricks (primary):

```bash
export DATABRICKS_SERVER_HOSTNAME=...
export DATABRICKS_HTTP_PATH=...
export DATABRICKS_TOKEN=...
export DATABRICKS_CATALOG=...
export DATABRICKS_SCHEMA=...

uv run concept-mapper map \
  --codes C01.9,E11.9,I21.0 \
  --source-vocabularies ICD10CM ICD9CM \
  --target-vocabulary SNOMED \
  --name "Example conditions" \
  --output-dir ./out
```

Local DuckDB (CSV files from an ATHENA download):

```bash
uv run concept-mapper map \
  --codes-file codes.txt \
  --source-vocabularies ICD10CM \
  --backend duckdb \
  --csv-dir ./vocabulary_download \
  --output-dir ./out
```

`--codes-file` accepts one code per line, or a CSV with a `code` column
(optionally a `vocabulary_id` column to force a specific source vocabulary).

## Options

| Option | Description |
|---|---|
| `--codes` | Comma-separated list of source codes. |
| `--codes-file` | File of codes (one per line, or CSV with `code` column). |
| `--source-vocabularies` | Source vocabularies to search (default `ICD10CM ICD9CM ICDO3 ICD10PCS ICD9Proc`). |
| `--target-vocabulary` | Target standard vocabulary (default `SNOMED`). |
| `--backend` | `databricks` (default) or `duckdb`. |
| `--catalog` / `--schema` | Databricks catalog/schema (fall back to env vars). |
| `--csv-dir` | Directory of ATHENA CSVs for the DuckDB backend. |
| `--output-dir` | Where to write `concept_set.json` and `concept_set.xlsx`. |
| `--name` | Concept set name. |

## Outputs

- `concept_set.json` — OHDSI Circe `ConceptSetExpression` (`{"items": [...]}`),
  importable into ATLAS.
- `concept_set.xlsx` — workbook with `Source Codes`, `Standard Concepts`, and
  `Summary` sheets. Missed source codes are highlighted red; added/overbroad
  standard concepts are highlighted yellow.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

## License

Apache-2.0. See [LICENSE](LICENSE).
