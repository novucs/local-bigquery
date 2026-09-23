import pathlib
import re

from sqlglot import exp
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


class TableMacro(exp.Expression):
    arg_types = {"this": True}


class BigQueryDialect(BaseBigQuery):
    INVERSE_TIME_MAPPING = BaseBigQuery.INVERSE_TIME_MAPPING

    class Parser(BaseBigQuery.Parser):
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
