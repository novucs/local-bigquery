import contextlib
import math
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery

STANDARD_TYPES = {
    "INTEGER": "INT64",
    "FLOAT": "FLOAT64",
    "BOOLEAN": "BOOL",
    "RECORD": "STRUCT",
}
FAST_RETRY = bigquery.DEFAULT_RETRY.with_timeout(5)
_UNSET = object()


@dataclass(frozen=True)
class Query:
    sql: str
    rows: list[tuple] | None = None
    types: tuple[str, ...] | None = None
    error: str | None = None
    params: list = field(default_factory=list)

    def check(self, bq: bigquery.Client, dataset: bigquery.Dataset):
        config = bigquery.QueryJobConfig(
            default_dataset=dataset.reference, query_parameters=self.params
        )
        if self.error:
            with pytest.raises(GoogleAPICallError) as info:
                run(bq, self.sql, config)
            message = reason_and_message(info.value)
            assert self.sql not in message, "error message echoes the query"
            assert re.search(self.error, message), message
            return
        result = run(bq, self.sql, config)
        rows = [tuple(row.values()) for row in result]
        if self.types is not None:
            types = tuple(type_name(f) for f in result.schema)
            assert types == self.types, f"{types} != {self.types}"
        if self.rows is not None:
            assert same(rows, self.rows), f"{rows} != {self.rows}"


def run(bq: bigquery.Client, sql: str, config=None):
    return bq.query_and_wait(sql, job_config=config, retry=FAST_RETRY, job_retry=None)


def rows(bq: bigquery.Client, sql: str) -> list[tuple]:
    return [tuple(row.values()) for row in run(bq, sql)]


def scalar(bq: bigquery.Client, sql: str) -> Any:
    return rows(bq, sql)[0][0]


def run_job(bq: bigquery.Client, sql: str, **config) -> bigquery.QueryJob:
    job = bq.query(
        sql,
        job_config=bigquery.QueryJobConfig(**config),
        retry=FAST_RETRY,
        job_retry=None,
    )
    job.result(retry=FAST_RETRY)
    return job


def q(
    sql: str,
    value: Any = _UNSET,
    *,
    rows: list[tuple] | None = None,
    types: str | tuple[str, ...] | None = None,
    error: str | None = None,
    params: list | None = None,
    xfail: str | None = None,
    crash: str | None = None,
):
    if value is not _UNSET:
        rows = [(value,)]
    if isinstance(types, str):
        types = (types,)
    case = Query(sql, rows, types, error, params or [])
    marks = [pytest.mark.xfail(reason=xfail or crash, run=not crash)]
    if not (xfail or crash):
        marks = []
    return pytest.param(case, marks=marks, id=" ".join(sql.split())[:80])


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def type_name(field: bigquery.SchemaField) -> str:
    name = STANDARD_TYPES.get(field.field_type, field.field_type)
    if name == "STRUCT":
        name = f"STRUCT<{', '.join(f'{f.name} {type_name(f)}' for f in field.fields)}>"
    return f"ARRAY<{name}>" if field.mode == "REPEATED" else name


@contextlib.contextmanager
def fails(exception: type[GoogleAPICallError], reason: str):
    with pytest.raises(exception) as info:
        yield info
    assert reason in [e.get("reason") for e in info.value.errors], info.value


def reason_and_message(error: GoogleAPICallError) -> str:
    reasons = [e.get("reason", "") for e in error.errors or []]
    return f"{' '.join(reasons)}: {error.message}"


def same(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float) and isinstance(actual, float):
        return math.isclose(actual, expected, rel_tol=1e-9) or (
            math.isnan(actual) and math.isnan(expected)
        )
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        return len(actual) == len(expected) and all(map(same, actual, expected))
    if isinstance(expected, dict) and isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(
            same(actual[k], expected[k]) for k in expected
        )
    return type(actual) is type(expected) and actual == expected
