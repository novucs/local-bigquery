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
services:
  bigquery:
    image: ghcr.io/novucs/local-bigquery:latest
    ports:
      - "8000:8000"
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
    client_options={"api_endpoint": "http://localhost:8000"},
)

client.query("""
CREATE TABLE my_dataset.my_table (
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
