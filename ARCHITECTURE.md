# Architecture

local-bigquery emulates the BigQuery REST (and later Storage gRPC) APIs on top of
DuckDB. The goals, in order: correct, fast, small, easy to change.

## Principles

1. **DuckDB does the work.** Storage, time travel, sessions, BigQuery functions
   (as SQL macros), row encoding, loads and exports all run inside DuckDB.
   Python orchestrates.
2. **One place per concern.** A type mapping, a translation rule, a BigQuery
   function, an error reason or a piece of job state lives in exactly one spot.
   Adding a feature should mean touching one file plus one test case.
3. **Typed state.** Metadata, jobs and sessions are typed tables with primary
   keys, not JSON blobs.
4. **Tests are the spec.** `tests/` drives the emulator through the real
   `google-cloud-bigquery` client. Expected values match real BigQuery; known
   gaps are strict xfails, so every fix shows up and nothing silently regresses.

## Layout

```
src/local_bigquery/
  cli.py            serve | repl | reset (goccy-compatible flags)
  settings.py       environment configuration
  app.py            FastAPI app, error handling, discovery routes, auto-501 stubs
  errors.py         BigQueryError(reason); reason → HTTP status; exception → reason
  resource.py       lenient pydantic base for generated models
  models.py         generated from discovery.json by scripts/generate_models.py
  api/              thin HTTP handlers, one module per resource
  engine/           the DuckDB instance, cursors, sessions, BigQuery ↔ DuckDB types
  catalog/          datasets, tables and routines metadata
  sql/              translation rules, functions.sql macros, scripting, JS UDFs
  jobs/             runner, query/load/copy/extract handlers, result paging
  grpc/             Storage Read/Write APIs
  repl.py           interactive shell, a client of the HTTP API
```

## Storage

- Each project is a DuckLake catalog with a DuckDB-file metadata store under the
  data directory. DuckLake gives time travel, snapshots, clones and table stats.
- `emulator.duckdb` holds typed tables for BigQuery-only metadata (labels, options,
  etags), jobs, sessions, and `_results` tables for query results.
- An in-memory `bq` catalog holds the macro library loaded from `functions.sql`,
  on every cursor's `search_path`.
- One server process owns the data directory; the REPL talks to it over HTTP.

## Query lifecycle

```
jobs.insert / jobs.query
  → jobs.runner: Job(PENDING) on a worker pool; jobs.query waits up to timeoutMs
  → worker: session cursor or a fresh cursor
      → sql.script for multi-statement / procedural SQL (child jobs)
      → sql.translate: parse → ordered rules → DuckDB SQL
      → SELECT: CREATE TABLE _results.<job> AS …; DML/DDL: statistics
  → Job(DONE) with statistics, statementType or errorResult
getQueryResults / tabledata.list
  → LIMIT/OFFSET page, rows encoded to REST JSON inside DuckDB
```

- Every failure is a `BigQueryError` with a BigQuery reason. Job failures are
  `DONE` jobs with `errorResult`, never HTTP errors from `jobs.insert`.
- `engine/types.py` is the only BigQuery ↔ DuckDB type table. Results are cast
  to BigQuery types once (TIMESTAMP ↔ TIMESTAMPTZ, DATETIME ↔ TIMESTAMP,
  NUMERIC ↔ DECIMAL(38,9), HUGEINT → INT64), so rules never special-case types.
- Pydantic models validate requests and metadata; row payloads bypass them.
- Cancellation and timeouts use `cursor.interrupt()`.

## Beyond the REST API

- `EXTERNAL_QUERY` rewrites to `postgres_query()` over lazily attached, isolated
  Postgres connections, one per connection id.
- Loads, extracts and `EXPORT DATA` use DuckDB readers and `COPY TO`, against
  local paths, upload endpoints or `gs://` through httpfs.
- Storage Read/Write reuse the `google-cloud-bigquery-storage` message types and
  stream DuckDB Arrow batches.

## Contributing a feature

1. Add or un-xfail a case in `tests/` that shows the BigQuery behaviour.
2. Implement it in the one place it belongs: a macro in `functions.sql`, a rule
   in `sql/rules/`, a type in `engine/types.py`, or a handler in `api/`/`jobs/`.
3. `uv run pytest` — fixed xfails fail loudly until their marker is removed.

Regenerate API models after a discovery revision with
`uv run python scripts/generate_models.py`.
