from local_bigquery.sql.rules import (
    columns,
    external,
    json,
    literals,
    parameters,
    safe,
    strings,
    tables,
)

MODULES = [columns, tables, external, parameters, literals, safe, strings, json]
STATEMENT_RULES = [
    rule for module in MODULES for rule in getattr(module, "STATEMENT_RULES", [])
]
NODE_RULES = [rule for module in MODULES for rule in getattr(module, "NODE_RULES", [])]
