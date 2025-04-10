from google.cloud import bigquery
from testcontainers.core.container import DockerContainer

bigquery_image = "ghcr.io/novucs/local-bigquery:latest"
with DockerContainer(bigquery_image).with_exposed_ports(9050) as container:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(9050)
    client = bigquery.Client(client_options={"api_endpoint": f"http://{host}:{port}"})
    print(next(client.query_and_wait("SELECT current_date()"))[0])
