# Local BigQuery

A local BigQuery implementation written in Python.

Uses [SQLGlot](https://github.com/tobymao/sqlglot) for translation, and [DuckDB](https://github.com/duckdb/duckdb) for execution.

## Usage

Grab the container, run it, and hit it with a BigQuery client.

### Docker
Start the container
```bash
docker run --init -d --rm -p 9050:9050 -v /tmp/local-bigquery/:/data --name bigquery ghcr.io/novucs/local-bigquery:latest
```

Enter the REPL
```bash
docker exec -it bigquery repl
```

Delete all projects, datasets, and tables
```bash
docker exec -it bigquery reset
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
    image: ghcr.io/novucs/local-bigquery:latest
    ports:
      - "9050:9050"
    environment:
      # Optional configuration, defaults are shown
      BIGQUERY_PORT: 9050
      BIGQUERY_HOST: 0.0.0.0
      DATA_DIR: /data
      DEFAULT_PROJECT_ID: local
      DEFAULT_DATASET_ID: local
      INTERNAL_PROJECT_ID: internal
      INTERNAL_DATASET_ID: internal
    volumes:
      - bigquery_data:/data
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

bigquery_image = "ghcr.io/novucs/local-bigquery:latest"
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
