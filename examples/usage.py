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
