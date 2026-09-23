import pathlib
import re

from sqlglot import exp
from sqlglot.tokens import TokenType
from sqlglot.dialects.bigquery import BigQuery as BaseBigQuery
from sqlglot.dialects.duckdb import DuckDB as BaseDuckDB

FUNCTIONS = sorted((pathlib.Path(__file__).parent / "functions").glob("*.sql"))
MACRO = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?MACRO\s+(\w+)", re.IGNORECASE)
MACROS = sorted(
    {name for path in FUNCTIONS for name in MACRO.findall(path.read_text())}
)


def macro(name: str, *args: exp.Expression) -> exp.Anonymous:
    return exp.Anonymous(this=f"bq.main.{name}", expressions=list(args))


def _parser(name: str):
    return lambda args: macro(name, *args)


def _table_function(name: str):
    def parse(self) -> exp.Anonymous:
        self._match(TokenType.TABLE)
        arguments = [self._parse_table()]
        while self._match(TokenType.COMMA):
            arguments.append(self._parse_lambda())
        return exp.Anonymous(this=name, expressions=arguments)

    return parse


class TableMacro(exp.Expression):
    arg_types = {"this": True}


def table_body(tree: exp.Expression) -> exp.Query | None:
    body = tree.expression
    if tree.meta.get("table_function") and isinstance(body, exp.Subquery):
        return body.this
    if isinstance(body, exp.Query) and not isinstance(body, exp.Subquery):
        return body
    return None


class BigQueryDialect(BaseBigQuery):
    INVERSE_TIME_MAPPING = BaseBigQuery.INVERSE_TIME_MAPPING

    class Parser(BaseBigQuery.Parser):
        FUNCTION_PARSERS = {
            **BaseBigQuery.Parser.FUNCTION_PARSERS,
            "RANGE_SESSIONIZE": _table_function("RANGE_SESSIONIZE"),
        }
        FUNCTIONS = {
            **BaseBigQuery.Parser.FUNCTIONS,
            **{
                name.upper(): _parser(name)
                for name in MACROS
                if not name.startswith("_")
            },
        }


class DuckDBDialect(BaseDuckDB):
    INVERSE_TIME_MAPPING = BaseDuckDB.INVERSE_TIME_MAPPING

    class Generator(BaseDuckDB.Generator):
        TRANSFORMS = {
            **BaseDuckDB.Generator.TRANSFORMS,
            TableMacro: lambda self, e: f"TABLE {self.sql(e, 'this')}",
        }
        TYPE_MAPPING = {
            **BaseDuckDB.Generator.TYPE_MAPPING,
            exp.DataType.Type.GEOGRAPHY: "GEOMETRY",
        }
