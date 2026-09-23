import pytest
import requests

from tests.cases import unique


@pytest.fixture(scope="module")
def api(endpoint, project):
    if endpoint == "google":
        pytest.skip("raw REST tests need an unauthenticated endpoint")
    base = f"{endpoint}/bigquery/v2/projects/{project}"

    def call(method, path, **kwargs):
        return requests.request(method, base + path, timeout=5, **kwargs)

    return call


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


@pytest.mark.xfail(reason="responses contain null keys")
def test_no_null_keys(api):
    result = jobs_query(api, "SELECT STRUCT(1 AS a) AS r, NULL AS n")
    assert null_paths(result) == []


def test_null_cell(api):
    assert jobs_query(api, "SELECT NULL AS n")["rows"] == [{"f": [{"v": None}]}]


@pytest.mark.xfail(reason="NULL arrays encoded as null")
def test_null_and_empty_arrays(api):
    result = jobs_query(
        api, "SELECT CAST(NULL AS ARRAY<INT64>) AS n, ARRAY<INT64>[] AS e"
    )
    assert result["rows"] == [{"f": [{"v": []}, {"v": []}]}]


@pytest.mark.xfail(reason="TIMESTAMP encoded as int micros")
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


@pytest.mark.xfail(reason="DATETIME and NUMERIC encoded wrongly")
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


@pytest.mark.xfail(reason="error envelope lacks status")
def test_error_envelope_status(api):
    response = api("GET", f"/datasets/{unique('missing')}")
    assert response.json()["error"]["status"] == "NOT_FOUND"


@pytest.mark.xfail(reason="deletes return a null JSON body")
def test_delete_returns_empty_body(api):
    dataset_id = unique("wire")
    body = {"datasetReference": {"datasetId": dataset_id}}
    assert api("POST", "/datasets", json=body).status_code == 200
    response = api("DELETE", f"/datasets/{dataset_id}")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.xfail(reason="job id lacks project:location prefix")
def test_job_id_format(api, project):
    job = insert_job(api, "SELECT 1")
    reference = job["jobReference"]
    assert reference["location"] == "US"
    assert job["id"] == f"{project}:US.{reference['jobId']}"


@pytest.mark.xfail(reason="timestamps are seconds, not milliseconds")
def test_statistics_times_are_milliseconds(api):
    statistics = insert_job(api, "SELECT 1")["statistics"]
    assert len(statistics["creationTime"]) == 13
    assert int(statistics["startTime"]) <= int(statistics["endTime"])


@pytest.mark.xfail(reason="bad SQL rejected at jobs.insert")
def test_insert_bad_sql_returns_failed_job(api):
    job = insert_job(api, "SELEC 1")
    assert job["status"]["state"] == "DONE"
    assert job["status"]["errorResult"]["reason"] == "invalidQuery"


@pytest.mark.xfail(reason="maxResults ignored by getQueryResults")
def test_get_query_results_max_results_zero(api):
    job_id = insert_job(api, "SELECT 1")["jobReference"]["jobId"]
    result = api("GET", f"/queries/{job_id}", params={"maxResults": 0}).json()
    assert result["jobComplete"] is True
    assert result["totalRows"] == "1"
    assert "rows" not in result
    assert "schema" in result


@pytest.mark.xfail(reason="pageToken paging not supported")
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


@pytest.mark.xfail(reason="kind omitted from responses")
def test_query_response_kind(api):
    assert jobs_query(api, "SELECT 1")["kind"] == "bigquery#queryResponse"
