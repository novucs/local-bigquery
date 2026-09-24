import dataclasses

import sqlglot
from sqlglot import exp

from local_bigquery.catalog import metadata, names, row_access
from local_bigquery.models import Table
from local_bigquery.sql.dialect import BigQueryDialect
from local_bigquery.sql.rules.tables import resolve


def _filtered(
    table: exp.Table, reference: tuple[str, str, str]
) -> exp.Expression | None:
    condition = row_access.predicate(*reference)
    if condition is None:
        return None
    source = table.copy()
    source.set("alias", None)
    source.meta["secured"] = True
    predicate = sqlglot.parse_one(condition, dialect=BigQueryDialect)
    return exp.select("*").from_(source).where(predicate)


def _view(
    reference: tuple[str, str, str], context, depth: int
) -> exp.Expression | None:
    if depth > 16 or not any(key[0] == reference[0] for key in row_access.secured()):
        return None
    stored = metadata.load(Table, *reference)
    query = stored and stored.view and stored.view.query
    if not query:
        return None
    scope = dataclasses.replace(
        context, project_id=reference[0], dataset_id=reference[1], temporary=set()
    )
    return _secure(sqlglot.parse_one(query, dialect=BigQueryDialect), scope, depth + 1)


def _secure(tree: exp.Expression, context, depth: int = 0) -> exp.Expression:
    if isinstance(tree, exp.Drop | exp.Alter | exp.Command) or (
        isinstance(tree, exp.Create) and tree.args.get("kind") not in ("TABLE", None)
    ):
        return tree
    ctes = {cte.alias_or_name.casefold() for cte in tree.find_all(exp.CTE)}
    target = names.target(tree)
    for table in list(tree.find_all(exp.Table)):
        if table is target or table.meta.get("secured"):
            continue
        if (reference := resolve(table, context, ctes)) is None:
            continue
        replacement = _view(reference, context, depth) or _filtered(table, reference)
        if replacement is not None:
            alias = exp.TableAlias(this=exp.to_identifier(table.alias_or_name))
            table.replace(exp.Subquery(this=replacement, alias=alias))
    return tree


def row_access_policies(tree: exp.Expression, context) -> exp.Expression:
    return _secure(tree, context) if row_access.secured() else tree


def session_user(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.SessionUser | exp.CurrentUser):
        return node
    principal = row_access.members()[0]
    return exp.Literal.string(principal.split(":", 1)[-1])


STATEMENT_RULES = [row_access_policies]
NODE_RULES = [session_user]
