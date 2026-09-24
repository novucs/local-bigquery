import contextlib
import signal
import socket
import subprocess
import time

import grpc
import pytest
import requests

INSERTED = 50_000_000


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def local(request):
    if request.config.getoption("--endpoint"):
        pytest.skip("starts the emulator's own entry point")


@contextlib.contextmanager
def serve(data_dir):
    rest, rpc = free_port(), free_port()
    command = ["local-bigquery", "--host", "127.0.0.1", "--port", str(rest)]
    command += ["--grpc-port", str(rpc), "--data-dir", str(data_dir)]
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
        yield process, f"http://127.0.0.1:{rest}/bigquery/v2/projects/local", rpc
    finally:
        process.kill()
        process.wait(timeout=10)


def query(base: str, sql: str, timeout_ms: int = 20_000) -> dict:
    body = {"query": sql, "useLegacySql": False, "timeoutMs": timeout_ms}
    response = requests.post(f"{base}/queries", json=body, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()


def count(base: str) -> int:
    return int(query(base, "SELECT COUNT(*) FROM d.t")["rows"][0]["f"][0]["v"])


def test_serve_starts_rest_and_grpc(local, tmp_path):
    with serve(tmp_path) as (_, base, rpc):
        projects = requests.get(base.rsplit("/", 1)[0]).json()
        assert [p["id"] for p in projects["projects"]] == ["local"]
        time.sleep(3)
        grpc.channel_ready_future(grpc.insecure_channel(f"127.0.0.1:{rpc}")).result(
            timeout=5
        )


def test_state_survives_a_kill_mid_write(local, tmp_path):
    with serve(tmp_path) as (process, base, _):
        requests.post(f"{base}/datasets", json={"datasetReference": {"datasetId": "d"}})
        query(base, "CREATE TABLE d.t AS SELECT x FROM UNNEST([1, 2, 3]) AS x")
        query(
            base,
            "CREATE FUNCTION d.twice(x INT64) RETURNS INT64 LANGUAGE js AS 'return x * 2;'",
        )
        sql = f"INSERT d.t SELECT x FROM UNNEST(GENERATE_ARRAY(1, {INSERTED})) AS x"
        job_id = query(base, sql, timeout_ms=100)["jobReference"]["jobId"]
        time.sleep(0.2)
        job = requests.get(f"{base}/jobs/{job_id}", timeout=5).json()
        assert job["status"]["state"] == "RUNNING"
        process.send_signal(signal.SIGKILL)
    with serve(tmp_path) as (_, base, _):
        assert count(base) == 3
        query(base, "INSERT d.t (x) VALUES (4)")
        assert count(base) == 4
        assert query(base, "SELECT d.twice(21)")["rows"] == [{"f": [{"v": "42"}]}]
