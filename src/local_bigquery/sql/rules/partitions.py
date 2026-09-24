from sqlglot import exp

from local_bigquery.catalog import tables
from local_bigquery.engine import database
from local_bigquery.errors import BigQueryError

PSEUDO_COLUMNS = {"_PARTITIONTIME", "_PARTITIONDATE"}
INGESTION_TIME = exp.ColumnDef(
    this=exp.to_identifier(tables.INGESTION_TIME, quoted=True),
    kind=exp.DataType.build("TIMESTAMPTZ", dialect="duckdb"),
    constraints=[
        exp.ColumnConstraint(
            kind=exp.DefaultColumnConstraint(
                this=exp.cast(
                    exp.func(
                        "date_trunc", exp.Literal.string("day"), exp.CurrentTimestamp()
                    ),
                    "TIMESTAMPTZ",
                )
            )
        )
    ],
)


def _ingestion_partitioned(tree: exp.Create) -> bool:
    partitioning = tree.find(exp.PartitionedByProperty)
    return partitioning is not None and any(
        column.name.upper() in PSEUDO_COLUMNS
        for column in partitioning.find_all(exp.Column, exp.Identifier)
    )


def _hidden(table: exp.Table) -> bool:
    if not (table.catalog and table.db) or not isinstance(table.this, exp.Identifier):
        return False
    return bool(
        database.fetch(
            "SELECT 1 FROM duckdb_columns() WHERE database_name = ? AND schema_name = ? "
            "AND table_name = ? AND column_name = ?",
            [table.catalog, table.db, table.name, tables.INGESTION_TIME],
        )
    )


def _hide_from_stars(select: exp.Select):
    for star in select.expressions:
        if isinstance(star, exp.Star):
            hidden = exp.column(tables.INGESTION_TIME, quoted=True)
            star.set("except_", [*(star.args.get("except_") or []), hidden])


def ingestion_time(tree: exp.Expression, context) -> exp.Expression:
    if isinstance(tree, exp.Create) and _ingestion_partitioned(tree):
        if isinstance(tree.this, exp.Schema):
            tree.this.append("expressions", INGESTION_TIME.copy())
        return tree
    for table in list(tree.find_all(exp.Table)):
        if not _hidden(table):
            continue
        if isinstance(tree, exp.Insert) and tree.this is table:
            raise BigQueryError(
                "invalidQuery",
                "Omitting INSERT target column list is unsupported for "
                f"ingestion-time partitioned table {table.db}.{table.name}",
            )
        if isinstance(select := table.find_ancestor(exp.Select), exp.Select):
            _hide_from_stars(select)
    return tree


def partition_date(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Column) and node.name.upper() == "_PARTITIONDATE":
        time = exp.column(tables.INGESTION_TIME, table=node.table or None, quoted=True)
        date = exp.cast(time, "DATE")
        return (
            exp.alias_(date, node.name) if isinstance(node.parent, exp.Select) else date
        )
    return node


STATEMENT_RULES = [ingestion_time]
NODE_RULES = [partition_date]
