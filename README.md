# Local BigQuery

Run BigQuery on your machine for development and tests. Point any BigQuery client at it,
and it answers the REST API and the Storage Read/Write APIs, running GoogleSQL on
[DuckDB](https://github.com/duckdb/duckdb) via [SQLGlot](https://github.com/tobymao/sqlglot).

## Quick start

```bash
docker run --rm -p 9050:9050 -p 9060:9060 -v local-bigquery:/data ghcr.io/novucs/local-bigquery:latest
```

```python
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

client = bigquery.Client(
    project="local",
    credentials=AnonymousCredentials(),
    client_options={"api_endpoint": "http://localhost:9050"},
)
client.create_dataset("shop", exists_ok=True)
client.query_and_wait("CREATE TABLE shop.orders AS SELECT 1 AS id, 'Alice' AS name")
print(list(client.query_and_wait("SELECT * FROM shop.orders")))
```

Any project ID works, and state persists in `/data` across restarts. More in
[`examples/`](examples).

## Clients

**Python with pandas**: pass a Storage Read client for fast `to_dataframe()`
(port `9060`, plain gRPC).

```python
import grpc
from google.cloud import bigquery_storage_v1
from google.cloud.bigquery_storage_v1.services.big_query_read.transports import (
    BigQueryReadGrpcTransport,
)

channel = grpc.insecure_channel("localhost:9060")
bqstorage = bigquery_storage_v1.BigQueryReadClient(
    transport=BigQueryReadGrpcTransport(channel=channel)
)
frame = client.query_and_wait("SELECT * FROM shop.orders").to_dataframe(
    bqstorage_client=bqstorage
)
```

**SQLAlchemy**: `create_engine("bigquery://local/shop", connect_args={"client": client})`.

**Go**:

```go
client, err := bigquery.NewClient(ctx, "local",
    option.WithEndpoint("http://localhost:9050/bigquery/v2/"),
    option.WithoutAuthentication())
```

**Testcontainers**: see [`examples/testcontainers_example.py`](examples/testcontainers_example.py).

## Features

- **GoogleSQL**: standard functions, DML including `MERGE`, DDL, scripting and
  procedures, SQL/JavaScript UDFs and table functions, `INFORMATION_SCHEMA`, wildcard
  tables, time travel, snapshots and clones, materialized views, `GEOGRAPHY` and `RANGE`.
- **Jobs**: query, load, copy and extract, with dry runs, cancellation, sessions and
  script child jobs.
- **Streaming**: `insert_rows_json` (`tabledata.insertAll`) and the Storage Write API.
- **Resources**: datasets, tables, routines, models, row access policies and IAM
  policies, with PATCH/PUT and etags.

Unsupported API methods return `501`. Known gaps are the strict `xfail` tests in
[`tests/`](tests).

### Files and `gs://`

Loads, extracts and `EXPORT DATA` read and write `gs://bucket/path` as
`$DATA_DIR/gcs/bucket/path`. Set `GCS_LOCAL_ROOT` to use another directory, or
`STORAGE_EMULATOR_HOST` to use a GCS emulator such as fake-gcs-server. Local files load
with `client.load_table_from_file(...)`.

### Row access policies

Row access policies filter by the calling principal, taken from the service account
that signed the request. Any key works, because signatures aren't checked:

```python
from google.oauth2 import service_account

alice = service_account.Credentials.from_service_account_file(
    "alice.json", always_use_jwt_access=True
)
client = bigquery.Client(
    project="local",
    credentials=alice,
    client_options={"api_endpoint": "http://localhost:9050"},
)
```

A key whose `client_email` ends in `.gserviceaccount.com` is `serviceAccount:<email>`,
and any other email is `user:<email>`. Unsigned requests run as `CALLER`.

### Postgres

`EXTERNAL_QUERY('us.default', 'SELECT ...')` runs against `POSTGRES_URI`.

### REPL

```bash
docker exec -it <container> local-bigquery repl    # interactive SQL
docker exec -it <container> local-bigquery reset   # delete all data
```

## Configuration

Set these as environment variables, or pass the matching flag to `local-bigquery`.

| Variable | Flag | Default | Purpose |
|---|---|---|---|
| `BIGQUERY_PORT` | `--port` | `9050` | REST API |
| `GRPC_PORT` | `--grpc-port` | `9060` | Storage Read/Write APIs |
| `DATA_DIR` | `--data-dir` | `/data` | Persistent state |
| `DEFAULT_PROJECT_ID` | `--project` | `local` | Project created at startup |
| `DEFAULT_DATASET_ID` | `--dataset` | `local` | Dataset created at startup |
| `CALLER` | | `user:local-bigquery@localhost` | Principal for unsigned requests |
| `GROUPS` | | `{}` | Group membership, e.g. `{"user:alice@example.com": ["group:team@example.com"]}` |
| `GCS_LOCAL_ROOT` | | `$DATA_DIR/gcs` | Directory backing `gs://` |
| `STORAGE_EMULATOR_HOST` | | | GCS emulator backing `gs://` |
| `POSTGRES_CONNECTION_ID` | | `us.default` | Connection ID for `EXTERNAL_QUERY` |
| `POSTGRES_URI` | | `postgresql://postgres:example@db:5432/postgres` | Postgres for `EXTERNAL_QUERY` |

See [`examples/docker-compose.yml`](examples/docker-compose.yml) for a Compose setup.

## Development

```bash
uv run local-bigquery --data-dir /tmp/local-bigquery   # serve from source
uv run pytest                                           # run the tests
uv run pytest --endpoint google --project <project>     # run them against BigQuery
```
