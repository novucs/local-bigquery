import socket
import subprocess
import time

import grpc
import pytest
import requests


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def served(request, tmp_path):
    if request.config.getoption("--endpoint"):
        pytest.skip("starts the emulator's own entry point")
    rest, rpc = free_port(), free_port()
    command = ["local-bigquery", "--host", "127.0.0.1", "--port", str(rest)]
    command += ["--grpc-port", str(rpc), "--data-dir", str(tmp_path)]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                requests.get(f"http://127.0.0.1:{rest}/bigquery/v2/projects", timeout=1)
                break
            except requests.ConnectionError:
                time.sleep(0.05)
        yield rest, rpc
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_serve_starts_rest_and_grpc(served):
    rest, rpc = served
    projects = requests.get(f"http://127.0.0.1:{rest}/bigquery/v2/projects").json()
    assert [p["id"] for p in projects["projects"]] == ["local"]
    time.sleep(3)
    grpc.channel_ready_future(grpc.insecure_channel(f"127.0.0.1:{rpc}")).result(
        timeout=5
    )
