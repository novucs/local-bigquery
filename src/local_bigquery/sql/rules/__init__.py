from local_bigquery.sql.rules import (
    arrays,
    columns,
    datetime,
    ddl,
    dml,
    external,
    information_schema,
    json,
    literals,
    math,
    parameters,
    query,
    safe,
    strings,
    tables,
    udfs,
)

MODULES = [
    columns,
    query,
    arrays,
    information_schema,
    dml,
    tables,
    udfs,
    ddl,
    datetime,
    external,
    math,
    parameters,
    literals,
    safe,
    strings,
    json,
]
STATEMENT_RULES = [
    rule for module in MODULES for rule in getattr(module, "STATEMENT_RULES", [])
]
NODE_RULES = [rule for module in MODULES for rule in getattr(module, "NODE_RULES", [])]
