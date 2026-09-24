# Local BigQuery

A BigQuery emulator for local development and tests. Point the official BigQuery
clients at it and run GoogleSQL offline, with no Google Cloud project, credentials or cost.

- **Works with the client you already use**: it serves BigQuery's REST API and
  Storage Read/Write gRPC APIs, so Python, Go, pandas and SQLAlchemy code runs
  unchanged apart from the endpoint.
- **Broad GoogleSQL**: scripting, procedures, UDFs, `MERGE`, `INFORMATION_SCHEMA`,
  time travel, `GEOGRAPHY` and more, translated to [DuckDB](https://duckdb.org).
- **BigQuery's behaviour, not just its syntax**: errors, job lifecycles, type rules and
  row access policies match BigQuery, checked by a test suite that also runs
  against real BigQuery.

## Quick start

```bash
docker run --name bigquery -p 9050:9050 -p 9060:9060 -v bigquery:/data ghcr.io/novucs/local-bigquery:latest
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

Any project ID works. Data persists in the `/data` volume.

## Testing with pytest

Start one emulator per test run with [Testcontainers](https://testcontainers.com), and
give each test its own dataset:

```python
# conftest.py
import uuid

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs


@pytest.fixture(scope="session")
def bq():
    image = "ghcr.io/novucs/local-bigquery:latest"
    with DockerContainer(image).with_exposed_ports(9050) as container:
        wait_for_logs(container, "Uvicorn running")
        host, port = container.get_container_host_ip(), container.get_exposed_port(9050)
        yield bigquery.Client(
            project="local",
            credentials=AnonymousCredentials(),
            client_options={"api_endpoint": f"http://{host}:{port}"},
        )


@pytest.fixture
def dataset(bq):
    dataset = bq.create_dataset(f"test_{uuid.uuid4().hex}")
    yield dataset.dataset_id
    bq.delete_dataset(dataset, delete_contents=True)
```

```python
def test_totals(bq, dataset):
    bq.query_and_wait(f"CREATE TABLE {dataset}.orders (customer STRING, amount INT64)")
    bq.insert_rows_json(f"{dataset}.orders", [{"customer": "a", "amount": 2}] * 3)
    rows = bq.query_and_wait(f"SELECT SUM(amount) AS total FROM {dataset}.orders")
    assert [row.total for row in rows] == [6]
```

## Other clients

**pandas**: use the Storage Read API on port `9060` (plain gRPC) for fast downloads.

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

**SQLAlchemy**: `create_engine("bigquery://local/shop", connect_args={"client": client})`

**Go**:

```go
client, err := bigquery.NewClient(ctx, "local",
    option.WithEndpoint("http://localhost:9050/bigquery/v2/"),
    option.WithoutAuthentication())
```

## Features

| Area | Supported |
|---|---|
| SQL | GoogleSQL functions, DML including `MERGE`, DDL, scripting, procedures, SQL/JavaScript UDFs, table functions, wildcard tables, `INFORMATION_SCHEMA` |
| Tables | Partitioning, clustering, constraints, views, materialized views, snapshots, clones, time travel, search and vector indexes |
| Jobs | Query, load, copy and extract jobs, with dry runs, cancellation, sessions and script child jobs |
| Data in and out | CSV, JSON, Parquet, Avro and ORC loads, CSV, JSON, Parquet and Avro exports, `insert_rows_json`, Storage Read and Write APIs |
| Resources | Datasets, tables, routines, models, row access policies and IAM policies, with PATCH/PUT and etags |

**Files and `gs://`**: loads, extracts and `EXPORT DATA` map `gs://bucket/path` to
`$DATA_DIR/gcs/bucket/path`, or to a GCS emulator such as fake-gcs-server via
`STORAGE_EMULATOR_HOST`.

**Row access policies**: the caller is the service account that signed the request, as
in BigQuery. Any key works, because signatures aren't checked:

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

An email ending in `.gserviceaccount.com` becomes `serviceAccount:<email>`, and any other
email becomes `user:<email>`. Unsigned requests run as `CALLER`, and group membership
comes from `GROUPS`.

**Postgres**: `EXTERNAL_QUERY('us.default', 'SELECT ...')` runs against `POSTGRES_URI`.

**REPL**: `docker exec -it bigquery local-bigquery repl` for interactive SQL, and
`local-bigquery reset` to delete all data.

## Limitations

- **Not for production or large data**: it runs on one machine with DuckDB, and is
  built for correctness on test-sized data.
- **No security**: requests aren't authenticated, and IAM policies are stored but
  not enforced.
- **Legacy SQL** and **BigQuery ML** functions such as `ML.PREDICT` aren't supported.
  `CREATE MODEL` records the model without training it.
- **Transactions**: a failed statement aborts the whole transaction, as DuckDB has no
  savepoints.
- **Parameterized types**: `STRING(n)` and `BYTES(n)` lengths aren't enforced on write.
- **Other API methods**: anything not listed above returns `501 Not Implemented`.

Found a difference from BigQuery? Please [open an issue](https://github.com/novucs/local-bigquery/issues).

## Configuration

Set environment variables, or pass the matching flag to `local-bigquery`.

| Variable | Flag | Default | Purpose |
|---|---|---|---|
| `BIGQUERY_PORT` | `--port` | `9050` | REST API port |
| `GRPC_PORT` | `--grpc-port` | `9060` | Storage Read/Write API port |
| `DATA_DIR` | `--data-dir` | `/data` | Where data is stored |
| `DEFAULT_PROJECT_ID` | `--project` | `local` | Project created at startup |
| `DEFAULT_DATASET_ID` | `--dataset` | `local` | Dataset created at startup |
| `CALLER` | | `user:local-bigquery@localhost` | Principal for unsigned requests |
| `GROUPS` | | `{}` | Group membership, e.g. `{"user:alice@example.com": ["group:team@example.com"]}` |
| `GCS_LOCAL_ROOT` | | `$DATA_DIR/gcs` | Directory backing `gs://` |
| `STORAGE_EMULATOR_HOST` | | | GCS emulator backing `gs://` |
| `POSTGRES_CONNECTION_ID` | | `us.default` | Connection ID for `EXTERNAL_QUERY` |
| `POSTGRES_URI` | | `postgresql://postgres:example@db:5432/postgres` | Postgres for `EXTERNAL_QUERY` |

With Docker Compose:

```yaml
services:
  bigquery:
    image: ghcr.io/novucs/local-bigquery:latest
    ports: ["9050:9050", "9060:9060"]
    volumes: ["bigquery:/data"]
volumes:
  bigquery: {}
```

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv run local-bigquery --data-dir /tmp/local-bigquery   # run from source
uv run pytest                                           # run the tests
uv run pytest --endpoint google --project <project>     # run the tests against real BigQuery
```

Contributions are welcome. New behaviour should come with a test that passes against
real BigQuery.

## License

[MIT](LICENSE)
