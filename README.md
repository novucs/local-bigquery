# Local BigQuery

A local BigQuery implementation written in Python.

Uses [SQLGlot](https://github.com/tobymao/sqlglot) for translation, and [DuckDB](https://github.com/duckdb/duckdb) for execution.

## What's supported

- **REST API v2**: datasets, tables, tabledata, routines, projects and jobs (query, load,
  copy, extract; paging, dry runs, cancellation, sessions, script child jobs), plus
  multipart and resumable uploads. Every other discovery method answers `501`.
- **GoogleSQL** translated to DuckDB: standard functions, DML and DDL including `MERGE`,
  scripting and procedures, SQL/JavaScript UDFs and table functions,
  `INFORMATION_SCHEMA`, wildcard tables, time travel, snapshots and clones,
  `GEOGRAPHY`, `RANGE`, `EXPORT DATA` and `EXTERNAL_QUERY` against Postgres.
- **Row access policies** filter rows for the caller named by the `X-Local-BigQuery-Caller` and
  `X-Local-BigQuery-Groups` headers (default `CALLER=user:local-bigquery@localhost`).
- **Known gaps** are the strict `xfail` cases in [`tests/`](tests), each with its reason.

## Usage

Grab the container, run it, and hit it with a BigQuery client.

### Docker
Start the container
```bash
docker run --init -d --rm -p 9050:9050 -v /tmp/local-bigquery/:/data --name bigquery ghcr.io/novucs/local-bigquery:0.2.5
```

Enter the REPL
```bash
docker exec -it bigquery local-bigquery repl
```

Delete all projects, datasets, and tables
```bash
docker exec -it bigquery local-bigquery reset
```

Stop the container
```bash
docker stop bigquery
```

### Docker Compose
```yaml
volumes:
  bigquery_data: {}
services:
  bigquery:
    image: ghcr.io/novucs/local-bigquery:0.2.5
    ports:
      - "9050:9050"
    environment:
      # Optional configuration, defaults are shown
      BIGQUERY_PORT: 9050
      BIGQUERY_HOST: 0.0.0.0
      DATA_DIR: /data
      DEFAULT_PROJECT_ID: local
      DEFAULT_DATASET_ID: local
      # Support for external connections to Postgres, requires an available Postgres instance.
      # SELECT * FROM EXTERNAL_QUERY('us.default', 'SELECT 1');
      POSTGRES_CONNECTION_ID: us.default
      POSTGRES_URI: postgresql://postgres:example@db:5432/postgres
      # gs://<bucket>/<path> in loads, extracts and EXPORT DATA is served from GCS_LOCAL_ROOT,
      # else a storage emulator such as fake-gcs-server, else $DATA_DIR/gcs.
      # GCS_LOCAL_ROOT: /data/gcs
      # STORAGE_EMULATOR_HOST: http://gcs:4443
    volumes:
      - bigquery_data:/data
```

### Without Docker
```bash
uv run local-bigquery --port 9050 --grpc-port 9060 --project local --dataset local --data-dir /tmp/local-bigquery
```

The BigQuery Storage Read/Write APIs are served over insecure gRPC on `--grpc-port`:
```python
import grpc
from google.cloud import bigquery_storage_v1
from google.cloud.bigquery_storage_v1.services.big_query_read.transports import BigQueryReadGrpcTransport

channel = grpc.insecure_channel("localhost:9060")
bqstorage = bigquery_storage_v1.BigQueryReadClient(transport=BigQueryReadGrpcTransport(channel=channel))
frame = client.list_rows("dataset.table").to_dataframe(bqstorage_client=bqstorage)
```

### BQ CLI
```bash
bq --api http://localhost:9050 query "SELECT 1"
```

### Python
```bash
pip install google-cloud-bigquery
```

```python
from google.cloud import bigquery
client = bigquery.Client(client_options={"api_endpoint": "http://localhost:9050"})
# ... your code here ...
```

### SQLAlchemy
```bash
pip install sqlalchemy-bigquery
```

```python
from google.cloud import bigquery
from sqlalchemy import create_engine
client = bigquery.Client(client_options={"api_endpoint": "http://localhost:9050"})
engine = create_engine("bigquery://project/dataset", connect_args={"client": client})
# ... your code here ...
```

### Testcontainers
```python
from google.cloud import bigquery
from testcontainers.core.container import DockerContainer

bigquery_image = "ghcr.io/novucs/local-bigquery:0.2.5"
with DockerContainer(bigquery_image).with_exposed_ports(9050) as container:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(9050)
    client = bigquery.Client(client_options={"api_endpoint": f"http://{host}:{port}"})
```

### Go
```bash
go get github.com/googleapis/google-cloud-go/bigquery
```

```go
package main

import (
    "context"

    "cloud.google.com/go/bigquery"
    "google.golang.org/api/option"
)

func main() {
    ctx := context.Background()
    client, err := bigquery.NewClient(ctx, "project", option.WithEndpoint("http://localhost:9050/bigquery/v2/"))
    // ... your code here ...
}
```

## Development

Run the test suite with `uv run pytest`, or against real
BigQuery with `uv run pytest --endpoint google --project <your-project>`.
