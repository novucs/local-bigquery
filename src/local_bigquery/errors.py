import re

import duckdb
import sqlglot

MISSING = re.compile(r"(Table|Schema|View|Catalog) .*(does not exist|not found)")
STATUSES = {
    "invalid": (400, "INVALID_ARGUMENT"),
    "invalidQuery": (400, "INVALID_ARGUMENT"),
    "resourceInUse": (400, "FAILED_PRECONDITION"),
    "accessDenied": (403, "PERMISSION_DENIED"),
    "notFound": (404, "NOT_FOUND"),
    "duplicate": (409, "ALREADY_EXISTS"),
    "conditionNotMet": (412, "FAILED_PRECONDITION"),
    "stopped": (400, "CANCELLED"),
    "notImplemented": (501, "UNIMPLEMENTED"),
    "dontRetry": (500, "INTERNAL"),
}


class BigQueryError(Exception):
    def __init__(self, reason: str, message: str, location: str | None = None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.location = location or ("query" if reason == "invalidQuery" else None)

    @property
    def code(self) -> int:
        return STATUSES[self.reason][0]

    def proto(self) -> dict:
        proto = {"reason": self.reason, "message": self.message}
        return proto | ({"location": self.location} if self.location else {})

    def response(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "errors": [self.proto() | {"domain": "global"}],
                "status": STATUSES[self.reason][1],
            }
        }


def not_found(kind: str, name: str) -> BigQueryError:
    return BigQueryError("notFound", f"Not found: {kind} {name}")


def already_exists(kind: str, name: str) -> BigQueryError:
    return BigQueryError("duplicate", f"Already Exists: {kind} {name}")


def not_implemented(feature: str) -> BigQueryError:
    return BigQueryError(
        "notImplemented",
        f"{feature} is not implemented yet. "
        "See https://github.com/novucs/local-bigquery/issues",
    )


DUCKDB_ERRORS = [
    (
        re.compile(r"Overflow in (?P<name>\w+) of"),
        "invalidQuery",
        "Integer Overflow",
    ),
    (
        re.compile(r'invalid date field format: "(?P<name>[^"]*)"'),
        "invalidQuery",
        "Invalid date: '{name}'",
    ),
    (
        re.compile(r"Unknown TimeZone '(?P<name>[^']*)'"),
        "invalidQuery",
        "Invalid time zone: {name}",
    ),
    (
        re.compile(r"More than one row returned by a (?P<name>subquery)"),
        "invalidQuery",
        "Scalar subquery produced more than one element",
    ),
    (
        re.compile(r'Table with name "?(?P<name>[^"\s]+)"? already exists'),
        "duplicate",
        "Already Exists: Table {table}",
    ),
    (
        re.compile(r"Table with name (?P<name>\S+) does not exist"),
        "notFound",
        "Not found: Table {table} was not found in location US",
    ),
    (
        re.compile(
            r"(?:Scalar|Aggregate|Table) Function with name (?P<name>\S+) does not exist"
        ),
        "invalidQuery",
        "Function not found: {function_name} at [{function_position}]",
    ),
    (
        re.compile(
            r"Python exception occurred while executing the UDF: \w+: (?P<name>.*)"
        ),
        "invalidQuery",
        "{name}",
    ),
    (
        re.compile(r'Referenced column "(?P<name>[^"]+)" (?:was )?not found'),
        "invalidQuery",
        "Unrecognized name: {name}",
    ),
    (
        re.compile(r"syntax error at or near (?P<name>.+)"),
        "invalidQuery",
        "Syntax error: Unexpected {name} at [{line}:{column}]",
    ),
    (
        re.compile(
            r"No function matches the given name and argument types "
            r"'(?P<name>[^(]+)\((?P<arguments>.*)\)'"
        ),
        "invalidQuery",
        "No matching signature for {kind} {function} for argument types: {arguments}",
    ),
]
ARGUMENT_TYPES = {
    "VARCHAR": "STRING",
    "STRING_LITERAL": "STRING",
    "INTEGER_LITERAL": "INT64",
    "TINYINT": "INT64",
    "SMALLINT": "INT64",
    "INTEGER": "INT64",
    "BIGINT": "INT64",
    "HUGEINT": "INT64",
    "FLOAT": "FLOAT64",
    "DOUBLE": "FLOAT64",
    "DECIMAL": "NUMERIC",
    "BOOLEAN": "BOOL",
    "BLOB": "BYTES",
    "TIMESTAMP": "DATETIME",
    "TIMESTAMP WITH TIME ZONE": "TIMESTAMP",
}
DUCKDB_PREFIX = re.compile(r"^[A-Za-z ]+ Error: ")


def _position(message: str) -> tuple[int, int]:
    match = re.search(r"\nLINE (\d+): (.*)\n( *)\^", message)
    if not match:
        return 1, 1
    return int(match[1]), len(match[3]) - len(f"LINE {match[1]}: ") + 1


def _function(tree, name: str, context=None) -> tuple[str, str]:
    for node in tree.find_all(sqlglot.exp.Anonymous) if tree is not None else []:
        if node.name.casefold() != name.casefold() or "line" not in node.meta:
            continue
        column = node.meta["col"] - len(node.name) + 1
        if isinstance(node.parent, sqlglot.exp.Dot):
            path = node.parent.this
            meta = next(iter(path.find_all(sqlglot.exp.Identifier))).meta
            column = meta.get("col", 0) - (meta.get("end", 0) - meta.get("start", 0))
            parts = [
                part
                for identifier in path.find_all(sqlglot.exp.Identifier)
                for part in identifier.name.split(".")
            ]
            if len(parts) == 1 and context is not None:
                parts.insert(0, context.project_id)
            return f"`{'.'.join(parts)}`.{node.name}", f"{meta['line']}:{column}"
        return node.name, f"{node.meta['line']}:{column}"
    return name, "1:1"


def _text_position(sql: str, offset: int) -> str:
    line = sql.count("\n", 0, offset) + 1
    return f"{line}:{offset - (sql.rfind(chr(10), 0, offset) + 1) + 1}"


def syntax_error(error: Exception, sql: str) -> BigQueryError:
    if isinstance(error, sqlglot.errors.TokenError):
        quotes = [i for i, c in enumerate(sql) if c in "'\""]
        offset = quotes[-1] if quotes else 0
        return BigQueryError(
            "invalidQuery",
            f"Syntax error: Unclosed string literal at [{_text_position(sql, offset)}]",
        )
    if not isinstance(error, sqlglot.errors.ParseError) or not error.errors:
        return BigQueryError("invalidQuery", f"Syntax error: {error}")
    detail = error.errors[0]
    first = sql.lstrip().split(None, 1)[0] if sql.strip() else ""
    tokens = sqlglot.tokens.Tokenizer().tokenize(sql)
    if tokens and tokens[0].token_type == sqlglot.tokens.TokenType.VAR:
        offset = len(sql) - len(sql.lstrip())
        return BigQueryError(
            "invalidQuery",
            f'Syntax error: Unexpected identifier "{first}" at '
            f"[{_text_position(sql, offset)}]",
        )
    context = detail.get("start_context") or ""
    previous = context.rstrip().rsplit(None, 1)[-1] if context.strip() else ""
    column = detail["col"] - len(context) + len(context.rstrip()) - len(previous)
    column -= len(detail.get("highlight") or "") - 1
    if detail["description"] == "Expecting )" and previous.isalpha():
        return BigQueryError(
            "invalidQuery",
            f'Syntax error: Expected "," but got keyword {previous.upper()} '
            f"at [{detail['line']}:{column}]",
        )
    return BigQueryError(
        "invalidQuery",
        f"Syntax error: {detail['description']} at [{detail['line']}:{detail['col']}]",
    )


def from_duckdb(error: Exception, context=None, tree=None) -> BigQueryError:
    message = str(error)
    first = message.split("\n")[0]
    line, column = _position(message)
    for pattern, reason, template in DUCKDB_ERRORS:
        if match := pattern.search(first):
            name = match["name"].strip("!\"'")
            table = name
            if context is not None and "." not in name:
                table = f"{context.project_id}:{context.dataset_id}.{name}"
            function_name, function_position = _function(tree, name, context)
            arguments = ", ".join(
                ARGUMENT_TYPES.get(argument.split("(")[0], argument.split("(")[0])
                for argument in (match.groupdict().get("arguments") or "").split(", ")
            )
            return BigQueryError(
                reason,
                template.format(
                    name=name,
                    table=table,
                    line=line,
                    column=column,
                    kind="function" if name[:1].isalpha() else "operator",
                    function=name.upper(),
                    arguments=arguments,
                    function_name=function_name,
                    function_position=function_position,
                ),
            )
    if "already exists" in first:
        reason = "duplicate"
    elif MISSING.search(first):
        reason = "notFound"
    else:
        reason = "invalidQuery"
    return BigQueryError(reason, DUCKDB_PREFIX.sub("", first))


def from_exception(error: Exception) -> BigQueryError:
    message = str(error).split("\n\nLINE ")[0]
    match error:
        case BigQueryError():
            return error
        case NotImplementedError():
            return not_implemented(message)
        case duckdb.Error():
            return from_duckdb(error)
        case sqlglot.errors.ParseError() if error.errors:
            detail = error.errors[0]
            return BigQueryError(
                "invalidQuery",
                f"Syntax error: {detail['description']} "
                f"at [{detail['line']}:{detail['col']}]",
            )
        case sqlglot.errors.SqlglotError():
            return BigQueryError("invalidQuery", f"Syntax error: {message}")
    return BigQueryError("dontRetry", f"Internal error: {error!r}")
