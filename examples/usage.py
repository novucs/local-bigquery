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
