import datetime
import itertools
import re

import duckdb
from sqlglot import exp
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify

from local_bigquery.catalog import tables
from local_bigquery.engine.types import bigquery_type
from local_bigquery.errors import BigQueryError

Type = exp.DataType.Type
DECIMALS = {Type.DECIMAL: "DECIMAL(38, 9)", Type.BIGDECIMAL: "DECIMAL(38, 18)"}
FLOATS = {Type.DOUBLE, Type.FLOAT}
BYTES = {Type.BINARY, Type.VARBINARY}
BITWISE = (exp.BitwiseAnd, exp.BitwiseOr, exp.BitwiseXor)
TO_JSON = {"bq.main.to_json_string", "bq.main.to_json"}
COMPARISONS = {
    exp.EQ: "=",
    exp.NEQ: "!=",
    exp.LT: "<",
    exp.LTE: "<=",
    exp.GT: ">",
    exp.GTE: ">=",
}
FAMILIES = [
    exp.DataType.TEXT_TYPES,
    exp.DataType.REAL_TYPES | exp.DataType.INTEGER_TYPES,
    {Type.BOOLEAN},
    BYTES,
]


def _schema(tree: exp.Expression) -> dict:
    schema = {}
    for table in tree.find_all(exp.Table):
        if not (table.catalog and table.db and isinstance(table.this, exp.Identifier)):
            continue
        try:
            fields = tables.columns(table.catalog, table.db, table.name)
        except (BigQueryError, duckdb.Error):
            continue
        columns = {field.name: bigquery_type(field) for field in fields}
        schema.setdefault(table.catalog, {}).setdefault(table.db, {})[table.name] = (
            columns
        )
    return schema


def _is(datatype: exp.DataType | None, kinds: set) -> bool:
    return datatype is not None and datatype.this in kinds


def _transfer(original: exp.Expression, copy: exp.Expression):
    if isinstance(copy, exp.Alias) and not isinstance(original, exp.Alias):
        copy = copy.this
    if type(original) is not type(copy):
        return
    if copy.type is not None:
        original.type = copy.type
    if isinstance(copy, exp.Bracket):
        path = [copy.this, *copy.this.find_all(exp.Column)]
        original.meta["json"] = any(_is(node.type, {Type.JSON}) for node in path)
    for key, value in original.args.items():
        other = copy.args.get(key)
        if isinstance(value, exp.Expression) and isinstance(other, exp.Expression):
            _transfer(value, other)
        elif isinstance(value, list) and isinstance(other, list):
            for item, match in zip(value, other):
                if isinstance(item, exp.Expression) and isinstance(
                    match, exp.Expression
                ):
                    _transfer(item, match)


def _typed(tree: exp.Expression, schema: dict, positional: bool) -> exp.Expression:
    copy = tree.copy()
    if not positional:
        for node in list(copy.find_all(exp.Group, exp.Order)):
            for item in node.expressions:
                target = item.this if isinstance(item, exp.Ordered) else item
                if isinstance(target, exp.Literal) and target.is_int:
                    target.replace(exp.null())
    qualify(
        copy,
        dialect="bigquery",
        schema=schema,
        expand_stars=False,
        validate_qualify_columns=False,
        quote_identifiers=False,
        identify=False,
    )
    return annotate_types(copy, schema=schema, dialect="bigquery")


def annotate(tree: exp.Expression, context) -> exp.Expression:
    schema = _schema(tree)
    for positional in (True, False):
        try:
            _transfer(tree, _typed(tree, schema, positional))
            return tree
        except Exception:
            continue
    try:
        return annotate_types(tree, dialect="bigquery")
    except Exception:
        return tree


def _decimal(node: exp.Expression) -> exp.DataType | None:
    target = DECIMALS.get(node.type.this) if node.type else None
    return exp.DataType.build(target, dialect="duckdb") if target else None


def _float_literal(node: exp.Expression) -> bool:
    if isinstance(node, exp.Cast) and node.to.this in FLOATS:
        node = node.this
    return (
        isinstance(node, exp.Literal)
        and node.is_number
        and any(c in node.this for c in ".eE")
    )


def literal_coercion(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, (exp.Add, exp.Sub, exp.Mul, exp.Div)):
        return node
    left, right = node.this, node.expression
    for decimal, literal, key in ((left, right, "expression"), (right, left, "this")):
        if _decimal(decimal) is not None and _float_literal(literal):
            value = literal.this if isinstance(literal, exp.Cast) else literal
            node.set(key, exp.cast(value, _decimal(decimal)))
            node.type = decimal.type
    return node


def _family(datatype: exp.DataType | None) -> int | None:
    kind = datatype.this if datatype else None
    return next((i for i, family in enumerate(FAMILIES) if kind in family), None)


def comparable(node: exp.Expression, context) -> exp.Expression:
    operator = COMPARISONS.get(type(node))
    if operator is None:
        return node
    assignment = isinstance(node.parent, exp.Update)
    if not assignment and exp.Null in (type(node.this), type(node.expression)):
        raise BigQueryError(
            "invalidQuery", f"Operands of {operator} cannot be literal NULL"
        )
    left, right = node.this.type, node.expression.type
    families = {_family(left), _family(right)}
    if None in families or len(families) == 1:
        return node
    arguments = ", ".join(t.sql(dialect="bigquery") for t in (left, right))
    raise BigQueryError(
        "invalidQuery",
        f"No matching signature for operator {operator} for argument types: "
        f"{arguments}",
    )


def _date_literal(node: exp.Literal) -> exp.Expression:
    match = re.fullmatch(r"\s*(\d{1,4})-(\d{1,2})-(\d{1,2})\s*", node.this)
    try:
        valid = match and datetime.date(*map(int, match.groups()))
    except ValueError:
        valid = None
    if not valid:
        meta = node.meta
        column = meta.get("col", 0) - (meta.get("end", 0) - meta.get("start", 0))
        raise BigQueryError(
            "invalidQuery",
            f'Could not cast literal "{node.this}" to type DATE '
            f"at [{meta.get('line', 1)}:{column}]",
        )
    return exp.cast(node, Type.DATE)


def _string_parameter(node: exp.Expression) -> bool:
    return (
        isinstance(node, exp.Cast)
        and node.to.this in exp.DataType.TEXT_TYPES
        and node.find(exp.Parameter, exp.Placeholder) is not None
    )


def date_arithmetic(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, (exp.Add, exp.Sub)):
        return node
    sides = [("this", "expression"), ("expression", "this")]
    for date_key, days_key in sides if isinstance(node, exp.Add) else sides[:1]:
        date, days = node.args[date_key], node.args[days_key]
        if not _is(days.type, exp.DataType.INTEGER_TYPES):
            continue
        if isinstance(date, exp.Literal) and date.is_string:
            date = _date_literal(date)
        elif _string_parameter(date):
            date = exp.cast(date, Type.DATE)
        elif not _is(date.type, {Type.DATE}):
            continue
        node.set(date_key, date)
        node.set(days_key, exp.cast(days, Type.INT))
        node.type = exp.DataType.build("DATE")
        return node
    return node


def average(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Avg) and not isinstance(node.parent, exp.Window):
        target = _decimal(node)
    elif isinstance(node, exp.Window) and isinstance(node.this, exp.Avg):
        target = _decimal(node.this)
    else:
        return node
    return exp.cast(node, target) if target else node


def nan_first(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.Order) or isinstance(node.parent, exp.Window):
        return node
    expressions = []
    for ordered in node.expressions:
        value = ordered.this
        if _is(value.type, FLOATS):
            rank = exp.Case(
                ifs=[
                    exp.If(
                        this=exp.Is(this=value.copy(), expression=exp.null()),
                        true=exp.Literal.number(0),
                    ),
                    exp.If(
                        this=exp.func("isnan", value.copy()), true=exp.Literal.number(1)
                    ),
                ],
                default=exp.Literal.number(2),
            )
            expressions.append(exp.Ordered(this=rank, desc=ordered.args.get("desc")))
        expressions.append(ordered)
    node.set("expressions", expressions)
    return node


def json_subscript(node: exp.Expression, context) -> exp.Expression:
    if not (isinstance(node, exp.Bracket) and node.meta.get("json")):
        return node
    (index,) = node.expressions
    if isinstance(index, exp.Literal) and index.is_string:
        return node
    return exp.JSONExtract(this=node.this, expression=index)


def _base64(value: exp.Expression, datatype: exp.DataType, names) -> exp.Expression:
    if datatype.this in BYTES:
        return exp.func("base64", value)
    if datatype.this == Type.STRUCT:
        fields = [
            exp.PropertyEQ(
                this=exp.to_identifier(field.name),
                expression=_base64(
                    exp.func(
                        "struct_extract", value.copy(), exp.Literal.string(field.name)
                    ),
                    field.args["kind"],
                    names,
                ),
            )
            for field in datatype.expressions
        ]
        return exp.Struct(expressions=fields)
    if datatype.this == Type.ARRAY and datatype.expressions:
        name = exp.to_identifier(f"b{next(names)}")
        element = _base64(exp.column(name), datatype.expressions[0], names)
        return exp.func(
            "list_transform", value, exp.Lambda(this=element, expressions=[name])
        )
    return value


def json_bytes(node: exp.Expression, context) -> exp.Expression:
    if not (
        isinstance(node, exp.Anonymous)
        and node.name.lower() in TO_JSON
        and node.expressions
        and node.expressions[0].type
    ):
        return node
    argument = node.expressions[0]
    if any(_is(datatype, BYTES) for datatype in argument.type.find_all(exp.DataType)):
        converted = _base64(argument.copy(), argument.type, itertools.count())
        node.set("expressions", [converted, *node.expressions[1:]])
    return node


def bitwise_bytes(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, BITWISE) and _is(node.type, BYTES):
        bits = type(node)(
            this=exp.cast(node.this, "BIT"), expression=exp.cast(node.expression, "BIT")
        )
        return exp.cast(bits, "BLOB")
    if isinstance(node, exp.BitwiseNot) and _is(node.type, BYTES):
        return exp.cast(exp.BitwiseNot(this=exp.cast(node.this, "BIT")), "BLOB")
    return node


STATEMENT_RULES = [annotate]
NODE_RULES = [
    comparable,
    date_arithmetic,
    literal_coercion,
    average,
    nan_first,
    json_subscript,
    json_bytes,
    bitwise_bytes,
]
