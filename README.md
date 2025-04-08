# Local BigQuery

A local BigQuery implementation written in Python.

Uses [SQLGlot](https://github.com/tobymao/sqlglot) for translation, and [DuckDB](https://github.com/duckdb/duckdb) for execution.

## Usage

Grab the container, run it, and hit it with a BigQuery client.

```bash
docker pull ghcr.io/novucs/local-bigquery:latest
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
      BIGQUERY_PORT: 9050
      BIGQUERY_HOST: 0.0.0.0
      DATABASE_PATH: /data/bigquery.db
    volumes:
      - bigquery_data:/data
```

### BigQuery Client
```bash
pip install google-cloud-bigquery
```

```python
from google.cloud import bigquery

client = bigquery.Client(
    project="my-project",
    location="us-central1",
    client_options={"api_endpoint": "http://localhost:9050"},
)

client.create_dataset("my_dataset", exists_ok=True)

client.query("""
CREATE TABLE IF NOT EXISTS my_dataset.my_table (
    id INT64,
    name STRING
)
""")

client.query("""
INSERT INTO my_dataset.my_table (id, name)
VALUES (1, 'Alice'), (2, 'Bob')
""")

results = client.query("""
SELECT * FROM my_dataset.my_table
""").result()

for row in results:
    print(f"id: {row.id}, name: {row.name}")
```
