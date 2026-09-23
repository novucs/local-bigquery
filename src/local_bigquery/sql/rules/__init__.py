from local_bigquery.sql.rules import (
    columns,
    ddl,
    dml,
    external,
    information_schema,
    literals,
    parameters,
    safe,
    tables,
)

MODULES = [
    columns,
    information_schema,
    dml,
    tables,
    ddl,
    external,
    parameters,
    literals,
    safe,
]
STATEMENT_RULES = [
    rule for module in MODULES for rule in getattr(module, "STATEMENT_RULES", [])
]
NODE_RULES = [rule for module in MODULES for rule in getattr(module, "NODE_RULES", [])]
