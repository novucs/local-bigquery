import dataclasses
import datetime
import json
from collections.abc import Callable

from sqlglot import exp

from local_bigquery.resource import Resource

Evaluate = Callable[[exp.Expression], object]


DAY_MS = 86_400_000


def _labels(node: exp.Expression, evaluate) -> dict:
    return {k.name: v.name for k, v in (pair.expressions for pair in node.expressions)}


def _render_labels(labels: dict) -> str:
    pairs = ", ".join(
        f"STRUCT({json.dumps(k)}, {json.dumps(v)})" for k, v in labels.items()
    )
    return f"[{pairs}]"


def _milliseconds(node: exp.Expression, evaluate) -> str:
    moment = datetime.datetime.fromisoformat(evaluate(node))
    return str(int(moment.timestamp() * 1000))


def _render_timestamp(value: str) -> str:
    moment = datetime.datetime.fromtimestamp(int(value) / 1000, datetime.UTC)
    return f'TIMESTAMP "{moment.isoformat()}"'


@dataclasses.dataclass(frozen=True)
class Option:
    key: str
    kind: str = "STRING"
    parse: Callable = lambda node, evaluate: evaluate(node)
    render: Callable = json.dumps


OPTIONS = {
    "description": Option("description"),
    "friendly_name": Option("friendlyName"),
    "labels": Option(
        "labels", "ARRAY<STRUCT<STRING, STRING>>", _labels, _render_labels
    ),
    "expiration_timestamp": Option(
        "expirationTime", "TIMESTAMP", _milliseconds, _render_timestamp
    ),
    "require_partition_filter": Option(
        "requirePartitionFilter", "BOOL", render=lambda value: str(value).lower()
    ),
    "default_table_expiration_days": Option(
        "defaultTableExpirationMs",
        "FLOAT64",
        lambda node, evaluate: str(int(float(evaluate(node)) * DAY_MS)),
        lambda value: str(int(value) / DAY_MS),
    ),
    "location": Option("location", render=lambda value: json.dumps(value.lower())),
}
COLUMN_OPTIONS = {"description": OPTIONS["description"]}
TABLE_OPTIONS = {
    name: OPTIONS[name]
    for name in (
        "description",
        "friendly_name",
        "labels",
        "expiration_timestamp",
        "require_partition_filter",
    )
}
DATASET_OPTIONS = {
    name: OPTIONS[name]
    for name in (
        "description",
        "friendly_name",
        "labels",
        "location",
        "default_table_expiration_days",
    )
}


def options(node: exp.Expression | None, mapping: dict, evaluate: Evaluate) -> dict:
    return {
        option.key: option.parse(prop.args["value"], evaluate)
        for prop in (node.find_all(exp.Property) if node else [])
        if (option := mapping.get(prop.name.lower())) is not None
    }


def rendered(resource: Resource, mapping: dict) -> list[tuple[str, str, str]]:
    values = resource.dump()
    return [
        (name, option.kind, option.render(values[option.key]))
        for name, option in mapping.items()
        if values.get(option.key) not in (None, {}, False)
    ]
