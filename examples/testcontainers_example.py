from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

with DockerContainer("ghcr.io/novucs/local-bigquery:latest").with_exposed_ports(
    9050
) as container:
    wait_for_logs(container, "Uvicorn running")
    host, port = container.get_container_host_ip(), container.get_exposed_port(9050)
    client = bigquery.Client(
        project="local",
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": f"http://{host}:{port}"},
    )
    print(list(client.query_and_wait("SELECT CURRENT_DATE()")))
