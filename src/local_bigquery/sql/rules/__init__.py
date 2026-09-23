from local_bigquery.sql.rules import (
    columns,
    external,
    literals,
    parameters,
    safe,
    tables,
    udfs,
)

MODULES = [columns, tables, udfs, external, parameters, literals, safe]
STATEMENT_RULES = [
    rule for module in MODULES for rule in getattr(module, "STATEMENT_RULES", [])
]
NODE_RULES = [rule for module in MODULES for rule in getattr(module, "NODE_RULES", [])]
