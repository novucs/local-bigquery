import gzip
import json
import time

import pytest

from tests.cases import unique


@pytest.fixture(scope="module")
def api(rest, project):
    return lambda method, path, **kwargs: rest(
        method, f"/bigquery/v2/projects/{project}{path}", **kwargs
    )


def jobs_query(api, sql, **body):
    response = api(
        "POST", "/queries", json={"query": sql, "useLegacySql": False, **body}
    )
    assert response.status_code == 200, response.text
    return response.json()


def insert_job(api, sql):
    body = {"configuration": {"query": {"query": sql, "useLegacySql": False}}}
    response = api("POST", "/jobs", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def null_paths(value, path=""):
    if value is None:
        return [path]
    if isinstance(value, dict):
        return [
            p
            for k, v in value.items()
            if k != "v"
            for p in null_paths(v, f"{path}.{k}")
        ]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in null_paths(v, f"{path}[{i}]")]
    return []


def test_legacy_type_names(api):
    result = jobs_query(
        api,
        "SELECT 1 AS i, 1.5 AS f, TRUE AS b, 'x' AS s, STRUCT(1 AS a) AS r, [1] AS a",
    )
    assert [(f["name"], f["type"], f["mode"]) for f in result["schema"]["fields"]] == [
        ("i", "INTEGER", "NULLABLE"),
        ("f", "FLOAT", "NULLABLE"),
        ("b", "BOOLEAN", "NULLABLE"),
        ("s", "STRING", "NULLABLE"),
        ("r", "RECORD", "NULLABLE"),
        ("a", "INTEGER", "REPEATED"),
    ]


def test_cells_are_strings(api):
    result = jobs_query(
        api, "SELECT 1 AS i, 1.5 AS f, TRUE AS b, STRUCT(1 AS a) AS r, [1, 2] AS a"
    )
    assert result["rows"] == [
        {
            "f": [
                {"v": "1"},
                {"v": "1.5"},
                {"v": "true"},
                {"v": {"f": [{"v": "1"}]}},
                {"v": [{"v": "1"}, {"v": "2"}]},
            ]
        }
    ]
    assert result["totalRows"] == "1"


def test_no_null_keys(api):
    result = jobs_query(api, "SELECT STRUCT(1 AS a) AS r, NULL AS n")
    assert null_paths(result) == []


def test_null_cell(api):
    assert jobs_query(api, "SELECT NULL AS n")["rows"] == [{"f": [{"v": None}]}]


def test_null_and_empty_arrays(api):
    result = jobs_query(
        api, "SELECT CAST(NULL AS ARRAY<INT64>) AS n, ARRAY<INT64>[] AS e"
    )
    assert result["rows"] == [{"f": [{"v": []}, {"v": []}]}]


def test_timestamp_default_encoding(api):
    result = jobs_query(api, "SELECT TIMESTAMP '2020-01-01 00:00:00.5+00' AS t")
    assert float(result["rows"][0]["f"][0]["v"]) == 1577836800.5


def test_timestamp_int64_encoding(api):
    result = jobs_query(
        api,
        "SELECT TIMESTAMP '2020-01-01 00:00:00.5+00' AS t",
        formatOptions={"useInt64Timestamp": True},
    )
    assert result["rows"][0]["f"][0]["v"] == "1577836800500000"


def test_scalar_encodings(api):
    result = jobs_query(
        api,
        "SELECT DATE '2020-01-02' AS d, DATETIME '2020-01-02 03:04:05' AS dt, "
        "TIME '03:04:05' AS t, b'abc' AS by, NUMERIC '1.10' AS n, JSON '{\"a\":1}' AS j",
    )
    assert [c["v"] for c in result["rows"][0]["f"]] == [
        "2020-01-02",
        "2020-01-02T03:04:05",
        "03:04:05",
        "YWJj",
        "1.1",
        '{"a":1}',
    ]


def test_error_envelope(api):
    response = api("GET", f"/datasets/{unique('missing')}")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == 404
    assert error["message"]
    assert error["errors"][0]["reason"] == "notFound"
    assert error["errors"][0]["domain"] == "global"


def test_error_envelope_status(api):
    response = api("GET", f"/datasets/{unique('missing')}")
    assert response.json()["error"]["status"] == "NOT_FOUND"


def test_delete_returns_empty_body(api):
    dataset_id = unique("wire")
    body = {"datasetReference": {"datasetId": dataset_id}}
    assert api("POST", "/datasets", json=body).status_code == 200
    response = api("DELETE", f"/datasets/{dataset_id}")
    assert response.status_code == 204
    assert response.content == b""


def test_job_id_format(api, project):
    job = insert_job(api, "SELECT 1")
    reference = job["jobReference"]
    assert reference["location"] == "US"
    assert job["id"] == f"{project}:US.{reference['jobId']}"


def done(api, job: dict) -> dict:
    while job["status"]["state"] != "DONE":
        time.sleep(0.05)
        job = api("GET", f"/jobs/{job['jobReference']['jobId']}").json()
    return job


def test_insert_does_not_wait_for_slow_jobs(api):
    sql = (
        "CREATE TEMP FUNCTION slow() RETURNS INT64 LANGUAGE js AS "
        "'const start = Date.now(); while (Date.now() - start < 1500) {} return 1;'; "
        "SELECT slow()"
    )
    started = time.monotonic()
    job = insert_job(api, sql)
    assert time.monotonic() - started < 3
    assert job["status"]["state"] == "RUNNING"
    assert done(api, job)["status"]["state"] == "DONE"


def test_statistics_times_are_milliseconds(api):
    statistics = done(api, insert_job(api, "SELECT 1"))["statistics"]
    assert len(statistics["creationTime"]) == 13
    assert int(statistics["startTime"]) <= int(statistics["endTime"])


def test_insert_bad_sql_returns_failed_job(api):
    job = insert_job(api, "SELEC 1")
    assert job["status"]["state"] == "DONE"
    assert job["status"]["errorResult"]["reason"] == "invalidQuery"


def test_get_query_results_max_results_zero(api):
    job_id = insert_job(api, "SELECT 1")["jobReference"]["jobId"]
    result = api("GET", f"/queries/{job_id}", params={"maxResults": 0}).json()
    assert result["jobComplete"] is True
    assert result["totalRows"] == "1"
    assert "rows" not in result
    assert "schema" in result


def test_get_query_results_page_tokens(api):
    sql = "SELECT x FROM UNNEST(GENERATE_ARRAY(1, 5)) AS x ORDER BY x"
    job_id = insert_job(api, sql)["jobReference"]["jobId"]
    pages, token = [], None
    for _ in range(5):
        params = {"maxResults": 2, **({"pageToken": token} if token else {})}
        result = api("GET", f"/queries/{job_id}", params=params).json()
        pages.append([row["f"][0]["v"] for row in result["rows"]])
        token = result.get("pageToken")
        if not token:
            break
    assert pages == [["1", "2"], ["3", "4"], ["5"]]


def test_query_response_kind(api):
    assert jobs_query(api, "SELECT 1")["kind"] == "bigquery#queryResponse"


def test_job_delete_returns_empty_object(api):
    job_id = insert_job(api, "SELECT 1")["jobReference"]["jobId"]
    response = api("DELETE", f"/jobs/{job_id}/delete")
    assert (response.status_code, response.json()) == (200, {})


def test_dataset_defaults(api, dataset):
    body = api("GET", f"/datasets/{dataset.dataset_id}").json()
    assert body["maxTimeTravelHours"] == "168"
    assert {entry["role"] for entry in body["access"]} == {"OWNER", "WRITER", "READER"}


def test_table_byte_counters(api, dataset):
    jobs_query(api, f"CREATE TABLE {dataset.dataset_id}.counters (a INT64)")
    body = api("GET", f"/datasets/{dataset.dataset_id}/tables/counters").json()
    for key in (
        "numLongTermBytes",
        "numTotalLogicalBytes",
        "numActiveLogicalBytes",
        "numLongTermLogicalBytes",
    ):
        assert body[key] == "0"


def test_get_table_selected_fields(api, dataset):
    table = f"/datasets/{dataset.dataset_id}/tables/selected"
    jobs_query(
        api,
        f"CREATE TABLE {dataset.dataset_id}.selected "
        "(a INT64, b STRING, r STRUCT<x INT64, y INT64>)",
    )
    body = api("GET", table, params={"selectedFields": "b,R.y"}).json()
    assert body["schema"]["fields"] == [
        {"name": "b", "type": "STRING", "mode": "NULLABLE"},
        {
            "name": "r",
            "type": "RECORD",
            "mode": "NULLABLE",
            "fields": [{"name": "y", "type": "INTEGER", "mode": "NULLABLE"}],
        },
    ]


def test_get_table_basic_view(api, dataset):
    table = f"/datasets/{dataset.dataset_id}/tables/basic"
    jobs_query(api, f"CREATE TABLE {dataset.dataset_id}.basic (a INT64)")
    body = api("GET", table, params={"view": "BASIC"}).json()
    assert "schema" in body and "numRows" not in body and "numBytes" not in body
    assert "numRows" in api("GET", table, params={"view": "FULL"}).json()


@pytest.mark.xfail(
    reason="datasets.undelete needs dropped schemas restored from DuckLake history"
)
def test_undelete_dataset(api):
    dataset_id = unique("undelete")
    api("POST", "/datasets", json={"datasetReference": {"datasetId": dataset_id}})
    assert api("DELETE", f"/datasets/{dataset_id}").status_code == 204
    response = api("POST", f"/datasets/{dataset_id}:undelete", json={})
    assert response.status_code == 200, response.text
    assert api("GET", f"/datasets/{dataset_id}").status_code == 200


def test_insert_all_conversion_error(api, dataset):
    jobs_query(api, f"CREATE TABLE {dataset.dataset_id}.numbers (n INT64)")
    rows = [{"json": {"n": 1}}, {"json": {"n": "not-a-number"}}]
    body = api(
        "POST",
        f"/datasets/{dataset.dataset_id}/tables/numbers/insertAll",
        json={"skipInvalidRows": True, "rows": rows},
    ).json()
    assert body["insertErrors"] == [
        {
            "index": 1,
            "errors": [
                {
                    "reason": "invalid",
                    "location": "n",
                    "debugInfo": "",
                    "message": "Cannot convert value to integer (bad value): not-a-number",
                }
            ],
        }
    ]


@pytest.fixture(scope="module")
def upload(rest, project):
    return lambda method, params, **kwargs: rest(
        method, f"/upload/bigquery/v2/projects/{project}/jobs", params=params, **kwargs
    )


def load_config(dataset, **load) -> dict:
    table = {
        "projectId": dataset.project,
        "datasetId": dataset.dataset_id,
        "tableId": unique("uploaded"),
    }
    return {"configuration": {"load": {"destinationTable": table} | load}}


def multipart(metadata: str, data: bytes) -> tuple[dict, bytes]:
    boundary = "wire-boundary"
    body = (
        (
            f"--{boundary}\r\nContent-Type: application/json\r\n\r\n{metadata}\r\n"
            f"--{boundary}\r\nContent-Type: text/csv\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return {"Content-Type": f'multipart/related; boundary="{boundary}"'}, body


def test_resumable_upload_id_and_status_probe(upload, dataset):
    started = upload("POST", {"uploadType": "resumable"}, json=load_config(dataset))
    upload_id = started.headers["X-GUploader-UploadID"]
    headers = {"Content-Range": "bytes 0-9/100", "Content-Type": "text/csv"}
    upload("PUT", {"upload_id": upload_id}, headers=headers, data=b"x\n1\n2\n3\n4\n")
    probe = upload(
        "PUT", {"upload_id": upload_id}, headers={"Content-Range": "bytes */100"}
    )
    assert (probe.status_code, probe.headers["Range"]) == (308, "bytes=0-9")


def test_resumable_upload_of_unknown_size(bq, upload, dataset):
    config = load_config(
        dataset,
        sourceFormat="CSV",
        skipLeadingRows=1,
        schema={"fields": [{"name": "x", "type": "INTEGER"}]},
    )
    started = upload("POST", {"uploadType": "resumable"}, json=config)
    params = {"upload_id": started.headers["X-GUploader-UploadID"]}
    chunk = upload(
        "PUT", params, headers={"Content-Range": "bytes 0-3/*"}, data=b"x\n1\n"
    )
    assert (chunk.status_code, chunk.headers["Range"]) == (308, "bytes=0-3")
    status = upload("PUT", params, headers={"Content-Range": "bytes */*"})
    assert (status.status_code, status.headers["Range"]) == (308, "bytes=0-3")
    last = upload("PUT", params, headers={"Content-Range": "bytes 4-5/6"}, data=b"2\n")
    job = bq.get_job(last.json()["jobReference"]["jobId"])
    assert job.result().state == "DONE"
    table = config["configuration"]["load"]["destinationTable"]
    sql = f"SELECT x FROM {table['datasetId']}.{table['tableId']} ORDER BY x"
    assert [tuple(row.values()) for row in bq.query_and_wait(sql)] == [(1,), (2,)]


def test_multipart_invalid_metadata(upload):
    headers, body = multipart("{not json", b"x\n1\n")
    response = upload("POST", {"uploadType": "multipart"}, headers=headers, data=body)
    assert response.status_code == 400
    assert response.json()["error"]["status"] == "INVALID_ARGUMENT"


def test_multipart_unknown_source_format(upload, dataset):
    metadata = json.dumps(load_config(dataset, sourceFormat="BOGUS"))
    headers, body = multipart(metadata, b"x\n1\n")
    response = upload("POST", {"uploadType": "multipart"}, headers=headers, data=body)
    assert response.status_code == 400
    assert response.json()["error"]["status"] == "INVALID_ARGUMENT"


def test_gzip_request_body(api):
    dataset_id = unique("gz")
    body = json.dumps({"datasetReference": {"datasetId": dataset_id}}).encode()
    headers = {"Content-Encoding": "gzip", "Content-Type": "application/json"}
    response = api("POST", "/datasets", data=gzip.compress(body), headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["datasetReference"]["datasetId"] == dataset_id


def test_put_dataset_replaces_its_fields(api):
    dataset_id = unique("put")
    body = {"datasetReference": {"datasetId": dataset_id}, "description": "d"}
    api("POST", "/datasets", json=body | {"labels": {"k": "v"}})
    replaced = api(
        "PUT",
        f"/datasets/{dataset_id}",
        json={"datasetReference": body["datasetReference"], "friendlyName": "f"},
    ).json()
    assert (
        replaced.get("description"),
        replaced.get("labels"),
        replaced["friendlyName"],
    ) == (
        None,
        None,
        "f",
    )
    assert replaced["datasetReference"]["datasetId"] == dataset_id


def test_put_table_replaces_its_fields(api, dataset):
    table_id = unique("put")
    reference = {"datasetId": dataset.dataset_id, "tableId": table_id}
    schema = {"fields": [{"name": "x", "type": "INTEGER"}]}
    path = f"/datasets/{dataset.dataset_id}/tables"
    api(
        "POST",
        path,
        json={"tableReference": reference, "schema": schema, "description": "d"},
    )
    replaced = api(
        "PUT",
        f"{path}/{table_id}",
        json={"tableReference": reference, "schema": schema, "friendlyName": "f"},
    ).json()
    assert (replaced.get("description"), replaced["friendlyName"]) == (None, "f")
    assert [f["name"] for f in replaced["schema"]["fields"]] == ["x"]
