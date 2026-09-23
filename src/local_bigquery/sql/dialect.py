import pathlib
import re

from sqlglot import exp
from sqlglot.tokens import TokenType
from sqlglot.dialects.bigquery import BigQuery as BaseBigQuery
from sqlglot.dialects.duckdb import DuckDB as BaseDuckDB

from local_bigquery.errors import BigQueryError

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


class AlterColumnOptions(exp.Expression):
    arg_types = {"this": True, "expressions": True}


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

        def reset(self):
            super().reset()
            self._calls = []

        def _parse_function_call(self, *args, **kwargs):
            self._calls.append(self._curr)
            try:
                return super()._parse_function_call(*args, **kwargs)
            except (IndexError, ValueError) as error:
                raise self._signature([None]) from error
            finally:
                self._calls.pop()

        def validate_expression(self, expression, args=None):
            if args is not None and (
                expression is None or list(expression.error_messages(args))
            ):
                raise self._signature(args)
            return super().validate_expression(expression, args)

        def _parse_schema(self, this=None):
            schema = super()._parse_schema(this)
            if isinstance(schema, exp.Table) and (version := self._parse_version()):
                schema.set("version", version)
            return schema

        def _parse_alter_table_alter(self) -> exp.Expression | None:
            index = self._index
            self._match(TokenType.COLUMN)
            self._parse_exists()
            column = self._parse_field(any_token=True)
            if self._match_text_seq("SET", "OPTIONS"):
                return AlterColumnOptions(
                    this=column, expressions=self._parse_with_property()
                )
            self._retreat(index)
            return super()._parse_alter_table_alter()

        def _signature(self, args: list) -> BigQueryError:
            token = self._calls[-1]
            name = token.text.upper()
            suffix = "" if args else " with no arguments"
            column = token.col - len(token.text) + 1
            return BigQueryError(
                "invalidQuery",
                f"No matching signature for function {name}{suffix} "
                f"at [{token.line}:{column}]",
            )


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
