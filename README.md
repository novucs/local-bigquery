# Local BigQuery

A local BigQuery implementation written in Python.

Uses [SQLGlot](https://github.com/tobymao/sqlglot) for translation, and [DuckDB](https://github.com/duckdb/duckdb) for execution.

## Usage

Grab the container, run it, and hit it with a BigQuery client.

### Docker
Run the container
```bash
docker run --rm -p 9050:9050 -v /tmp/local-bigquery/:/data --name local-bigquery ghcr.io/novucs/local-bigquery:latest
```

Clear data
```bash
rm -rf /tmp/local-bigquery
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
      DATABASE_PATH: /data
      DEFAULT_PROJECT_ID: main
      DEFAULT_DATASET_ID: main
      INTERNAL_PROJECT_ID: internal
      INTERNAL_DATASET_ID: internal
    volumes:
      - bigquery_data:/data
```

### Python BigQuery Client
```bash
pip install google-cloud-bigquery
```

<pre lang="python">
from google.cloud import bigquery
client = bigquery.Client(<b>client_options={"api_endpoint": "http://localhost:9050"}</b>)
# ... your code here ...
</pre>

### Python SQLAlchemy
```bash
pip install sqlalchemy-bigquery
```

<pre lang="python">
from google.cloud import bigquery
from sqlalchemy import create_engine
client = bigquery.Client(<b>client_options={"api_endpoint": "http://localhost:9050"}</b>)
engine = create_engine("bigquery://project/dataset", <b>connect_args={"client": bq}</b>)
# ... your code here ...
</pre>

### Go
```bash
go get github.com/googleapis/google-cloud-go/bigquery
```

<pre lang="go">
package main
import (
    "context"

    "cloud.google.com/go/bigquery"
    "google.golang.org/api/option"
)

func main() {
    ctx := context.Background()
    client, err := bigquery.NewClient(ctx, "project", <b>option.WithEndpoint("http://localhost:9050/bigquery/v2/")</b>)
    // ... your code here ...
}
</pre>
