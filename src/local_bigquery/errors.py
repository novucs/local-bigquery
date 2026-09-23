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


def from_exception(error: Exception) -> BigQueryError:
    message = str(error).split("\n\nLINE ")[0]
    match error:
        case BigQueryError():
            return error
        case NotImplementedError():
            return not_implemented(message)
        case duckdb.CatalogException() if "already exists" in message:
            return BigQueryError("duplicate", message)
        case duckdb.CatalogException() | duckdb.BinderException() if MISSING.search(
            message
        ):
            return BigQueryError("notFound", message)
        case duckdb.Error() | sqlglot.errors.SqlglotError():
            return BigQueryError("invalidQuery", message)
    return BigQueryError("dontRetry", f"Internal error: {error!r}")
