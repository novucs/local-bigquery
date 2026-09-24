from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

client = bigquery.Client(
    project="local",
    credentials=AnonymousCredentials(),
    client_options={"api_endpoint": "http://localhost:9050"},
)

client.create_dataset("shop", exists_ok=True)
client.query_and_wait(
    "CREATE OR REPLACE TABLE shop.orders (id INT64, customer STRING, amount NUMERIC)"
)
client.insert_rows_json(
    "local.shop.orders",
    [
        {"id": 1, "customer": "Alice", "amount": "9.99"},
        {"id": 2, "customer": "Bob", "amount": "20.00"},
    ],
)

rows = client.query_and_wait(
    "SELECT customer, SUM(amount) AS total FROM shop.orders "
    "WHERE amount > @minimum GROUP BY customer ORDER BY customer",
    job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("minimum", "NUMERIC", "5")]
    ),
)
for row in rows:
    print(row.customer, row.total)
