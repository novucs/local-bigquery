from local_bigquery.sql.rules import (
    arrays,
    columns,
    external,
    literals,
    parameters,
    query,
    safe,
    tables,
)

MODULES = [columns, query, arrays, tables, external, parameters, literals, safe]
STATEMENT_RULES = [
    rule for module in MODULES for rule in getattr(module, "STATEMENT_RULES", [])
]
NODE_RULES = [rule for module in MODULES for rule in getattr(module, "NODE_RULES", [])]
