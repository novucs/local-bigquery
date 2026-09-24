import atexit
import hashlib
import inspect
import json
import re
import threading

import duckdb
import pyarrow
import sqlglot
from duckdb.sqltypes import DuckDBPyType
from py_mini_racer import JSEvalException, MiniRacer
from sqlglot import exp

from local_bigquery.catalog import names
from local_bigquery.engine import database
from local_bigquery.sql.dialect import BigQueryDialect, DuckDBDialect

INTEGERS = {"tinyint", "smallint", "integer", "bigint", "hugeint"}
THROWN = re.compile(r"^<anonymous>:(\d+): (.*)$")
_contexts: dict[str, tuple[MiniRacer, threading.Lock]] = {}
_registered: set[tuple[int, str]] = set()
_lock = threading.Lock()


@atexit.register
def _close():
    while _contexts:
        context, _ = _contexts.popitem()[1]
        context.close()


def is_udf(tree: exp.Expression) -> bool:
    language = tree.find(exp.LanguageProperty)
    return language is not None and language.name.lower() == "js"


def _type(node: exp.Expression | None) -> DuckDBPyType:
    return DuckDBPyType(node.sql(dialect=DuckDBDialect) if node else "JSON")


def _convert(value, t: DuckDBPyType):
    if value is None:
        return None
    if t.id in INTEGERS:
        return int(value)
    if t.id in ("double", "float"):
        return float(value)
    return value


def _error(error: JSEvalException, signature: str) -> ValueError:
    location, line, caret = str(error).split("\n")[:3]
    number, message = THROWN.match(location).groups()
    column = len(caret) - len(caret.lstrip()) + 1
    return ValueError(
        f"{message} at {signature} line {int(number) - 1}, column {column}"
    )


def _function(
    names: list[str], kinds: list[DuckDBPyType], body: str, returns, signature: str
):
    source = f"(function({', '.join(names)}) {{\n{body}\n}})"
    strings = [kind.id in INTEGERS for kind in kinds]

    def evaluate(rows: list) -> list:
        with _lock:
            if source not in _contexts:
                context = MiniRacer()
                context.eval(f"var f = {source};")
                context.eval("var batch = rows => rows.map(row => f.apply(null, row));")
                _contexts[source] = context, threading.Lock()
        context, lock = _contexts[source]
        try:
            with lock:
                values = context.call("batch", rows)
        except JSEvalException as error:
            raise _error(error, signature) from None
        return [_convert(value, returns) for value in values]

    if not names:
        return lambda: evaluate([[]])[0]

    def call(*arrays):
        columns = [
            [None if v is None else str(v) for v in a.to_pylist()]
            if string
            else a.to_pylist()
            for a, string in zip(arrays, strings)
        ]
        rows = json.loads(json.dumps(list(zip(*columns)), default=str))
        return pyarrow.array(evaluate(rows))

    call.__signature__ = inspect.Signature(
        [inspect.Parameter(n, inspect.Parameter.POSITIONAL_OR_KEYWORD) for n in names]
    )
    return call


def _params(tree: exp.Expression) -> list[exp.ColumnDef]:
    return [p for p in tree.this.expressions if isinstance(p, exp.ColumnDef)]


def register(tree: exp.Expression) -> str:
    params, returns = _params(tree), tree.find(exp.ReturnsProperty)
    body = tree.expression.name
    types = ", ".join(p.kind.sql(dialect=BigQueryDialect) for p in params)
    signature = f"{tree.this.this.name}({types})"
    key = [signature, returns.sql() if returns else "", body]
    name = "js_" + hashlib.sha1("\n".join(key).encode()).hexdigest()[:16]
    connection = database.connection()
    with _lock:
        if (id(connection), name) not in _registered:
            return_type = _type(returns.this if returns else None)
            kinds = [_type(p.kind) for p in params]
            connection.create_function(
                name,
                _function(
                    [p.name for p in params], kinds, body, return_type, signature
                ),
                kinds,
                return_type,
                type="arrow" if params else "native",
                null_handling="special",
            )
            _registered.add((id(connection), name))
    return name


def restore():
    connection = database.connection()
    if (id(connection), "") in _registered:
        return
    for (definition,) in database.fetch("SELECT definition FROM emulator.js_functions"):
        register(sqlglot.parse_one(definition, dialect=BigQueryDialect))
    _registered.add((id(connection), ""))


def bind(cur: duckdb.DuckDBPyConnection, tree: exp.Expression, context):
    name = register(tree)
    target = tree.this.this
    if tree.find(exp.TemporaryProperty):
        context.functions[target.name.casefold()] = (
            name,
            [p.kind for p in _params(tree)],
        )
        return
    qualified = ".".join(
        exp.to_identifier(part).sql(dialect=DuckDBDialect)
        for part in names.reference(target, context.project_id, context.dataset_id)
    )
    params = ", ".join(p.name for p in _params(tree))
    create = "CREATE OR REPLACE MACRO" if tree.args.get("replace") else "CREATE MACRO"
    exists = " IF NOT EXISTS" if tree.args.get("exists") else ""
    cur.execute(f"{create}{exists} {qualified}({params}) AS {name}({params})")
    database.execute(
        "INSERT OR REPLACE INTO emulator.js_functions VALUES (?, ?)",
        [name, tree.sql(dialect=BigQueryDialect)],
    )
