import duckdb
import sqlglot
from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import BigQueryDialect
from local_bigquery.sql.translate import Context, translate

SOURCE, PAIRS, INSERTS, ORPHANS = (
    "__merge_source",
    "__merge_pairs",
    "__merge_inserts",
    "__merge_orphans",
)


def _sql(node: exp.Expression | None) -> str:
    return node.sql(dialect=BigQueryDialect) if node is not None else "TRUE"


def _unaliased(node: exp.Expression) -> str:
    node = node.copy()
    node.set("alias", None)
    return _sql(node)


def _clause(whens: list[exp.When]) -> str:
    if not whens:
        return "NULL"
    cases = " ".join(
        f"WHEN {_sql(when.args.get('condition'))} THEN {index}"
        for index, when in enumerate(whens)
    )
    return f"CASE {cases} END"


def run(cur: duckdb.DuckDBPyConnection, tree: exp.Merge, context: Context) -> dict:
    def execute(sql: str) -> int:
        translated, bound = translate(
            sqlglot.parse_one(sql, dialect=BigQueryDialect), context
        )
        result = cur.execute(translated, bound).fetchone()
        return result[0] if result else 0

    target, source = tree.this, tree.args["using"]
    table, alias = _unaliased(target), target.alias_or_name
    source_alias = source.alias_or_name
    whens = tree.args["whens"].expressions
    matched = [w for w in whens if w.args.get("matched")]
    by_target = [
        w for w in whens if not w.args.get("matched") and not w.args.get("source")
    ]
    by_source = [w for w in whens if not w.args.get("matched") and w.args.get("source")]
    counts = {"insertedRowCount": 0, "updatedRowCount": 0, "deletedRowCount": 0}
    try:
        cur.execute("BEGIN")
        owned = True
    except duckdb.TransactionException:
        owned = False
    try:
        execute(
            f"CREATE OR REPLACE TEMP TABLE {SOURCE} AS SELECT ROW_NUMBER() OVER () AS __sid, "
            f"{source_alias}.* FROM {_unaliased(source)} AS {source_alias}"
        )
        execute(
            f"CREATE OR REPLACE TEMP TABLE {PAIRS} AS SELECT {alias}.rowid AS __tid, "
            f"{source_alias}.__sid AS __sid, {_clause(matched)} AS __clause "
            f"FROM {table} AS {alias} JOIN {SOURCE} AS {source_alias} ON {_sql(tree.args['on'])}"
        )
        if (
            matched
            and cur.execute(
                f"SELECT 1 FROM {PAIRS} GROUP BY __tid HAVING count(*) > 1 LIMIT 1"
            ).fetchone()
        ):
            raise BigQueryError(
                "invalidQuery",
                "UPDATE/MERGE must match at most one source row for each target row",
            )
        execute(
            f"CREATE OR REPLACE TEMP TABLE {INSERTS} AS SELECT __sid, {_clause(by_target)} AS __clause "
            f"FROM {SOURCE} AS {source_alias} WHERE __sid NOT IN (SELECT __sid FROM {PAIRS})"
        )
        execute(
            f"CREATE OR REPLACE TEMP TABLE {ORPHANS} AS SELECT {alias}.rowid AS __tid, "
            f"{_clause(by_source)} AS __clause FROM {table} AS {alias} "
            f"WHERE {alias}.rowid NOT IN (SELECT __tid FROM {PAIRS})"
        )
        for decisions, clauses in ((PAIRS, matched), (ORPHANS, by_source)):
            for index, when in enumerate(clauses):
                rows = f"{alias}.rowid IN (SELECT __tid FROM {decisions} WHERE __clause = {index})"
                action = when.args["then"]
                if isinstance(action, exp.Update):
                    assignments = ", ".join(_sql(e) for e in action.expressions)
                    joined = decisions == PAIRS
                    counts["updatedRowCount"] += execute(
                        f"UPDATE {table} AS {alias} SET {assignments} "
                        + (
                            f"FROM {SOURCE} AS {source_alias}, {PAIRS} AS __p "
                            f"WHERE __p.__clause = {index} AND {alias}.rowid = __p.__tid "
                            f"AND {source_alias}.__sid = __p.__sid"
                            if joined
                            else f"WHERE {rows}"
                        )
                    )
                else:
                    counts["deletedRowCount"] += execute(
                        f"DELETE FROM {table} AS {alias} WHERE {rows}"
                    )
        for index, when in enumerate(by_target):
            action = when.args["then"]
            chosen = f"__sid IN (SELECT __sid FROM {INSERTS} WHERE __clause = {index})"
            if isinstance(action.this, exp.Var):
                select = f"SELECT * EXCEPT (__sid) FROM {SOURCE} AS {source_alias} WHERE {chosen}"
                columns = ""
            else:
                values = ", ".join(_sql(v) for v in action.expression.expressions)
                select = (
                    f"SELECT {values} FROM {SOURCE} AS {source_alias} WHERE {chosen}"
                )
                columns = _sql(action.this) if action.this else ""
            counts["insertedRowCount"] += execute(
                f"INSERT INTO {table} {columns} {select}"
            )
        for name in (SOURCE, PAIRS, INSERTS, ORPHANS):
            cur.execute(f"DROP TABLE IF EXISTS temp.{name}")
        if owned:
            cur.execute("COMMIT")
    except Exception:
        if owned:
            cur.execute("ROLLBACK")
        raise
    return {
        "numDmlAffectedRows": str(sum(counts.values())),
        "dmlStats": {key: str(value) for key, value in counts.items()},
    }
