import inspect

import duckdb
from duckdb.sqltypes import DuckDBPyType
from py_mini_racer import MiniRacer
from sqlglot import exp


def is_udf(tree: exp.Expression) -> bool:
    language = tree.find(exp.LanguageProperty)
    return language is not None and language.name.lower() == "js"


def _type(node: exp.Expression) -> DuckDBPyType:
    try:
        return DuckDBPyType(node.sql("duckdb"))
    except duckdb.Error:
        return DuckDBPyType("VARCHAR")


def bind(cur: duckdb.DuckDBPyConnection, tree: exp.Expression):
    name = tree.find(exp.Table).name
    params = [n for n in tree.find_all(exp.ColumnDef) if n.this]
    names = ", ".join(p.name for p in params)
    body = tree.expression.this

    def fn(*args):
        ctx = MiniRacer()
        ctx.eval(f"var f = function({names}) {{ {body} }}")
        return ctx.call("f", *args)

    fn.__name__ = name
    fn.__signature__ = inspect.Signature(
        [
            inspect.Parameter(p.name, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            for p in params
        ]
    )
    returns = tree.find(exp.ReturnsProperty)
    cur.create_function(
        name,
        fn,
        [_type(p.kind) for p in params],
        _type(returns.this) if returns and returns.this else None,
    )
