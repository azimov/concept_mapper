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
uv run concept-mapper map \
  --codes C01.9,E11.9,I21.0 \
  --connection mydb --cdm mycdm \
  --source-vocabularies ICD10CM \
  --name "Example conditions" \
  --output-dir ./out
```

Alternatively, provide Databricks credentials directly via env vars
(`DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`,
`DATABRICKS_CATALOG`, `DATABRICKS_SCHEMA`) or `--catalog`/`--schema` flags.

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

## Wildcard and regex codes

Any entry in `--codes`, `--codes-file`, `--exclude-codes` or
`--exclude-codes-file` can be a pattern. It is expanded to the concrete codes
that exist in the selected source vocabularies, and each expanded code is then
mapped like a normal input code (the workbook notes `from pattern: ...`).

| Entry | Matches |
|---|---|
| `C01.*` | `C01.0`, `C01.2`, ... (codes starting with `C01.`) |
| `C0*` | every code starting with `C0` (including `C01`) |
| `E1*.9` | `*` matches any run of characters, anywhere in the code |
| `re:^C0[1-2]\.\d$` | a regular expression, matched anywhere in the code (anchor with `^`/`$`) |

Matching is case-insensitive and runs against the vocabulary's dotted
`concept_code`. A pattern that matches nothing is reported as `not_found`. Use
`--codes-file` for regexes containing commas (e.g. `{1,2}`), since `--codes`
splits on commas. Single quotes are not allowed in patterns. Regex syntax is
evaluated by the database (RE2 for DuckDB, Java for Databricks), so stick to
common constructs.

## Connection configuration

Named connections are read from `.config/ohdsi/<name>_connection.yml` (under
your home directory, or a directory given via `--config-dir`). Example:

```yaml
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
```

Use `--connection mydb --cdm mycdm` to select a connection and CDM. The
`vocabulary_schema` (falling back to `cdm_schema`) determines where the
`CONCEPT` / `CONCEPT_RELATIONSHIP` tables live. If multiple `cdms` are defined,
`--cdm` is required.

## Options

| Option | Description |
|---|---|
| `--codes` | Comma-separated list of source codes. |
| `--codes-file` | File of codes (one per line, or CSV with `code` column). |
| `--exclude-codes` | Comma-separated source codes to exclude (written with `isExcluded: true`). |
| `--exclude-codes-file` | File of codes to exclude (same format as `--codes-file`). |
| `--source-vocabularies` | Source vocabularies to search (default `ICD10CM ICD9CM ICDO3 ICD10PCS ICD9Proc`). |
| `--target-vocabulary` | Target standard vocabulary (default `SNOMED`). |
| `--domain` | Comma-separated target domains to keep, e.g. `Condition` (default: all). Case-insensitive; applies to included and excluded codes. |
| `--backend` | `databricks` (default) or `duckdb`. |
| `--connection` | Named connection from `.config/ohdsi/<name>_connection.yml`. |
| `--cdm` | CDM to use from the connection config. |
| `--config-dir` | Directory holding `<name>_connection.yml` files. |
| `--catalog` / `--schema` | Databricks catalog/schema (fall back to env vars). |
| `--csv-dir` | Directory of ATHENA CSVs for the DuckDB backend. |
| `--output-dir` | Where to write `concept_set.json` and `concept_set.xlsx`. |
| `--name` | Concept set name. |
| `--count` | Count record frequency of standard/source concepts in the CDM (requires `--connection` with a `cdm` block). |

## Exclusion code lists

Codes given via `--exclude-codes` / `--exclude-codes-file` are mapped to standard
concepts with the same source vocabularies and target vocabulary as the main
list. They are written to the concept set with `"isExcluded": true`; if a
concept is in both lists, the exclusion wins and the include item is dropped.

```bash
uv run concept-mapper map \
  --codes-file stroke.txt --exclude-codes G45.4 \
  --connection mydb --cdm mycdm --output-dir ./out
```

The workbook gains two sheets when exclusions are given:

- `Excluded Source Codes` — each excluded input code, its match type and the
  standard concepts it mapped to (unmapped codes highlighted red).
- `Excluded Concepts` — the resulting standard concepts and the excluded codes
  that led to them; concepts also in the included set are highlighted yellow.

Excluded concepts only remove concepts from the set. Cohort-level rules (for
example a time window around a pregnancy record) cannot be expressed here and
should be built as a separate concept set. All codes are searched in every
source vocabulary, so codes that mean different things in ICD-9-CM and ICD-10-CM
(e.g. `V27`) can match the wrong one; check the `Excluded Source Codes` sheet.

## Frequency counting (`--count`)

With `--count`, each standard concept's `domain_id` is used to select the CDM
domain table (e.g. `Condition` -> `condition_occurrence`), and the record count
per standard concept is computed from that table. Source-concept frequencies are
computed from the matching `*_source_concept_id` column. Counts are added to the
Excel workbook (`record_count` / `source_record_count` columns).

Supported domains: Condition, Drug, Procedure, Measurement, Observation, Device,
Visit, Specimen.

## Outputs

- `concept_set.json` — OHDSI Circe `ConceptSetExpression` (`{"items": [...]}`),
  importable into ATLAS. Excluded concepts have `isExcluded: true`.
- `concept_set.xlsx` — workbook with `Source Codes`, `Standard Concepts`, and
  `Summary` sheets. Missed source codes are highlighted red; added/overbroad
  standard concepts are highlighted yellow.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

## License

Apache-2.0. See [LICENSE](LICENSE).
