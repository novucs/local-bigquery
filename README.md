# Local BigQuery

A BigQuery emulator for development and tests. It serves the BigQuery REST and Storage
APIs and runs GoogleSQL on DuckDB, so the official clients work with no project or
credentials.

## Quick start

```bash
docker run -p 9050:9050 -p 9060:9060 -v bigquery:/data ghcr.io/novucs/local-bigquery:latest
```

Then point a client at `http://localhost:9050`, without credentials. Any project ID
works, and data persists in `/data`.

## Connecting

### Python

```python
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

client = bigquery.Client(
    project="local",
    credentials=AnonymousCredentials(),
    client_options={"api_endpoint": "http://localhost:9050"},
)
rows = client.query_and_wait("SELECT 1 AS x")
```

For faster `to_dataframe()`, add the Storage Read API, served as plain gRPC on port `9060`:

```python
import grpc
from google.cloud import bigquery_storage_v1
from google.cloud.bigquery_storage_v1.services.big_query_read.transports import (
    BigQueryReadGrpcTransport,
)

transport = BigQueryReadGrpcTransport(channel=grpc.insecure_channel("localhost:9060"))
bqstorage = bigquery_storage_v1.BigQueryReadClient(transport=transport)
frame = client.query_and_wait("SELECT 1 AS x").to_dataframe(bqstorage_client=bqstorage)
```

For SQLAlchemy, pass the client in:
`create_engine("bigquery://local", connect_args={"client": client})`.

### Go

```go
client, err := bigquery.NewClient(ctx, "local",
    option.WithEndpoint("http://localhost:9050/bigquery/v2/"),
    option.WithoutAuthentication(),
)
```

### Node.js

```js
import { BigQuery } from "@google-cloud/bigquery";

const bigquery = new BigQuery({ projectId: "local", apiEndpoint: "http://localhost:9050" });
const [rows] = await bigquery.query("SELECT 1 AS x");
```

## Testing with pytest

One emulator per test run, one dataset per test:

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

## Features

- **SQL**: GoogleSQL functions, DML including `MERGE`, DDL, scripting, procedures,
  SQL/JavaScript UDFs, table functions, wildcard tables, `INFORMATION_SCHEMA`.
- **Tables**: partitioning, clustering, constraints, views, materialized views,
  snapshots, clones, time travel, search and vector indexes.
- **Jobs**: query, load, copy and extract, with dry runs, cancellation and sessions.
- **Data**: CSV, JSON, Parquet, Avro and ORC loads, and CSV, JSON, Parquet and Avro exports.
  Also `insert_rows_json` and the Storage Read and Write APIs.
- **`gs://`**: maps to `$DATA_DIR/gcs`, or to a GCS emulator set by `STORAGE_EMULATOR_HOST`.
- **Row access policies**: the caller is the service account that signed the request.
  Signatures aren't checked, so any key works:
  `service_account.Credentials.from_service_account_file("key.json", always_use_jwt_access=True)`.
  Unsigned requests run as `CALLER`.
- **`EXTERNAL_QUERY`** against Postgres at `POSTGRES_URI`.
- **REPL**: `local-bigquery repl`. Delete all data with `local-bigquery reset`.

## Limitations

- For test-sized data on one machine. There's no authentication, and IAM policies
  aren't enforced.
- Legacy SQL and BigQuery ML functions (`ML.PREDICT` and so on) aren't supported.
- A failed statement aborts the whole transaction.
- `STRING(n)` and `BYTES(n)` lengths aren't enforced.
- Other API methods return `501`.

Found a difference from BigQuery? [Open an issue](https://github.com/novucs/local-bigquery/issues).

## Configuration

Set these as environment variables, or pass the matching flag to `local-bigquery`.

| Variable | Flag | Default |
|---|---|---|
| `BIGQUERY_PORT` | `--port` | `9050` |
| `GRPC_PORT` | `--grpc-port` | `9060` |
| `DATA_DIR` | `--data-dir` | `/data` |
| `DEFAULT_PROJECT_ID` | `--project` | `local` |
| `DEFAULT_DATASET_ID` | `--dataset` | `local` |
| `CALLER` | | `user:local-bigquery@localhost` |
| `GROUPS` | | `{}`, e.g. `{"user:alice@example.com": ["group:team@example.com"]}` |
| `GCS_LOCAL_ROOT` | | `$DATA_DIR/gcs` |
| `STORAGE_EMULATOR_HOST` | | |
| `POSTGRES_CONNECTION_ID` | | `us.default` |
| `POSTGRES_URI` | | `postgresql://postgres:example@db:5432/postgres` |

## Development

```bash
uv run local-bigquery --data-dir /tmp/local-bigquery   # run from source
uv run pytest                                           # run the tests
uv run pytest --endpoint google --project <project>     # run them against real BigQuery
```

## License

[MIT](LICENSE)
