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
        self.location = location

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
        "Function not found: {name}",
    ),
    (
        re.compile(r'Referenced column "(?P<name>[^"]+)" not found'),
        "invalidQuery",
        "Unrecognized name: {name}",
    ),
    (
        re.compile(r"syntax error at or near (?P<name>.+)"),
        "invalidQuery",
        "Syntax error: Unexpected {name} at [{line}:{column}]",
    ),
]
DUCKDB_PREFIX = re.compile(r"^[A-Za-z ]+ Error: ")


def _position(message: str) -> tuple[int, int]:
    match = re.search(r"\nLINE (\d+): (.*)\n( *)\^", message)
    if not match:
        return 1, 1
    return int(match[1]), len(match[3]) - len(f"LINE {match[1]}: ") + 1


def from_duckdb(error: Exception, context=None) -> BigQueryError:
    message = str(error)
    first = message.split("\n")[0]
    line, column = _position(message)
    for pattern, reason, template in DUCKDB_ERRORS:
        if match := pattern.search(first):
            name = match["name"].strip("!\"'")
            table = name
            if context is not None and "." not in name:
                table = f"{context.project_id}:{context.dataset_id}.{name}"
            return BigQueryError(
                reason,
                template.format(name=name, table=table, line=line, column=column),
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
