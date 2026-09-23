import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

import duckdb
import sqlglot
from sqlglot import exp
from sqlglot.tokens import TokenType

from local_bigquery.catalog import routines
from local_bigquery.errors import BigQueryError, from_exception
from local_bigquery.sql.dialect import BigQueryDialect
from local_bigquery.sql.rules.parameters import VALUE, read
from local_bigquery.sql.translate import Context, parse, translate

OPEN = {TokenType.L_PAREN, TokenType.L_BRACKET, TokenType.L_BRACE}
CLOSE = {TokenType.R_PAREN, TokenType.R_BRACKET, TokenType.R_BRACE}
QUOTED = {TokenType.STRING, TokenType.IDENTIFIER}
RAISE_MESSAGE = re.compile(r"(?is)^USING\s+MESSAGE\s*=\s*(.*)$")
ALIASES = {"LEAVE": "BREAK", "ITERATE": "CONTINUE"}


class Tokenizer(BigQueryDialect.tokenizer_class):
    COMMANDS = set()


@dataclass
class Statement:
    kind: str
    text: str = ""
    body: list["Statement"] = field(default_factory=list)
    branches: list[tuple[str, list["Statement"]]] = field(default_factory=list)
    otherwise: list["Statement"] | None = None
    names: list[str] = field(default_factory=list)
    items: list[tuple[str, str | None]] = field(default_factory=list)


class Parser:
    def __init__(self, sql: str):
        self.sql = sql
        self.tokens = Tokenizer().tokenize(sql)
        self.i = 0

    def word(self, offset: int = 0) -> str | None:
        if self.i + offset >= len(self.tokens):
            return None
        token = self.tokens[self.i + offset]
        return "" if token.token_type in QUOTED else token.text.upper()

    def take(self, word: str):
        if self.word() != word:
            found = self.word() or "end of script"
            raise BigQueryError(
                "invalidQuery", f"Syntax error: Expected {word} but got {found}"
            )
        self.i += 1

    def text(self, start: int, end: int) -> str:
        if start >= end:
            return ""
        return self.sql[self.tokens[start].start : self.tokens[end - 1].end + 1]

    def scan(self, stops: set[str] = frozenset()) -> list[str]:
        depth, start, items = 0, self.i, []
        while self.i < len(self.tokens):
            kind, word = self.tokens[self.i].token_type, self.word()
            if depth == 0 and (word in stops or word == ";" or kind in CLOSE):
                break
            if kind in OPEN or word == "CASE":
                depth += 1
            elif kind in CLOSE or (word == "END" and depth):
                depth -= 1
            elif depth == 0 and kind == TokenType.COMMA:
                items.append(self.text(start, self.i))
                start = self.i + 1
            self.i += 1
        return [item for item in [*items, self.text(start, self.i)] if item.strip()]

    def until(self, stops: set[str] = frozenset()) -> str:
        start = self.i
        self.scan(stops)
        return self.text(start, self.i)

    def block(self, stops: set[str]) -> list[Statement]:
        statements = []
        while (word := self.word()) is not None and word not in stops:
            if word == ";":
                self.i += 1
            else:
                statements.append(self.statement())
        return statements

    def statement(self) -> Statement:
        word, following = self.word(), self.word(1)
        if word == "BEGIN" and following not in ("TRANSACTION", ";", None):
            return self.begin()
        if word == "EXECUTE" and following == "IMMEDIATE":
            return self.execute()
        if word == "CREATE" and "PROCEDURE" in (self.word(n) for n in range(1, 5)):
            return self.procedure()
        if word == "DROP" and following == "PROCEDURE":
            return Statement("DROP_PROCEDURE", self.until())
        if word in ("BREAK", "LEAVE", "CONTINUE", "ITERATE", "RETURN"):
            self.i += 1
            return Statement(ALIASES.get(word, word))
        if parse := PARSERS.get(word):
            return parse(self)
        return Statement(word if word in ("DECLARE", "SET") else "SQL", self.until())

    def begin(self) -> Statement:
        self.take("BEGIN")
        body = self.block({"EXCEPTION", "END"})
        handler = None
        if self.word() == "EXCEPTION":
            for word in ("EXCEPTION", "WHEN", "ERROR", "THEN"):
                self.take(word)
            handler = self.block({"END"})
        self.take("END")
        return Statement("BLOCK", body=body, otherwise=handler)

    def branches(self, separator: str, subject: str = "") -> Statement:
        statement = Statement("IF")
        while self.word() in ("IF", separator):
            self.i += 1
            condition = self.until({"THEN"})
            self.take("THEN")
            if subject:
                condition = f"({subject}) = ({condition})"
            body = self.block({separator, "ELSE", "END"})
            statement.branches.append((condition, body))
        if self.word() == "ELSE":
            self.take("ELSE")
            statement.otherwise = self.block({"END"})
        self.take("END")
        return statement

    def if_(self) -> Statement:
        statement = self.branches("ELSEIF")
        self.take("IF")
        return statement

    def case(self) -> Statement:
        self.take("CASE")
        statement = self.branches("WHEN", self.until({"WHEN"}))
        self.take("CASE")
        return statement

    def loop_body(self, closing: str) -> list[Statement]:
        body = self.block({"END"})
        self.take("END")
        self.take(closing)
        return body

    def while_(self) -> Statement:
        self.take("WHILE")
        condition = self.until({"DO"})
        self.take("DO")
        return Statement("WHILE", condition, self.loop_body("WHILE"))

    def loop(self) -> Statement:
        self.take("LOOP")
        return Statement("WHILE", "TRUE", self.loop_body("LOOP"))

    def repeat(self) -> Statement:
        self.take("REPEAT")
        body = self.block({"UNTIL"})
        self.take("UNTIL")
        condition = self.until({"END"})
        self.take("END")
        self.take("REPEAT")
        return Statement("REPEAT", condition, body)

    def for_(self) -> Statement:
        self.take("FOR")
        name = self.tokens[self.i].text
        self.i += 1
        self.take("IN")
        query = self.until({"DO"})
        self.take("DO")
        return Statement("FOR", query, self.loop_body("FOR"), names=[name])

    def raise_(self) -> Statement:
        self.take("RAISE")
        match = RAISE_MESSAGE.match(self.until())
        return Statement("RAISE", match[1] if match else "")

    def assert_(self) -> Statement:
        self.take("ASSERT")
        condition = self.until({"AS"})
        description = ""
        if self.word() == "AS":
            self.take("AS")
            description = self.until()
        return Statement("ASSERT", condition, names=[description])

    def execute(self) -> Statement:
        self.take("EXECUTE")
        self.take("IMMEDIATE")
        statement = Statement("EXECUTE", self.until({"INTO", "USING"}))
        if self.word() == "INTO":
            self.take("INTO")
            statement.names = [name.strip() for name in self.scan({"USING"})]
        if self.word() == "USING":
            self.take("USING")
            for item in self.scan():
                expression, separator, alias = item.rpartition(" AS ")
                statement.items.append(
                    (expression, alias.strip()) if separator else (item, None)
                )
        return statement

    def arguments(self) -> list[tuple[str, None]]:
        self.i += 1
        arguments = [(argument, None) for argument in self.scan()]
        self.i += 1
        return arguments

    def call(self) -> Statement:
        self.take("CALL")
        name = self.until({"("})
        return Statement("CALL", name.strip(), items=self.arguments())

    def procedure(self) -> Statement:
        start = self.i
        while self.tokens[self.i].token_type != TokenType.L_PAREN:
            self.i += 1
        header = self.text(start, self.i)
        arguments = self.arguments()
        while self.word() != "BEGIN":
            self.i += 1
        body_start = self.i + 1
        self.begin()
        return Statement(
            "PROCEDURE",
            self.text(body_start, self.i - 1),
            names=header.split(),
            items=arguments,
        )


PARSERS = {
    "IF": Parser.if_,
    "CASE": Parser.case,
    "WHILE": Parser.while_,
    "LOOP": Parser.loop,
    "REPEAT": Parser.repeat,
    "FOR": Parser.for_,
    "RAISE": Parser.raise_,
    "ASSERT": Parser.assert_,
    "CALL": Parser.call,
}


def parse_script(sql: str) -> list[Statement]:
    return Parser(sql).block(set())


def is_script(statements: list[Statement]) -> bool:
    return len(statements) > 1 or any(s.kind != "SQL" for s in statements)


class Control(Exception):
    pass


class Break(Control):
    pass


class Continue(Control):
    pass


class Return(Control):
    pass


def _select(value: exp.Expression) -> exp.Select:
    return exp.Select(
        expressions=[exp.Alias(this=value, alias=exp.to_identifier(VALUE))]
    )


def _temporary_table(prefix: str) -> str:
    return f'temp.main."__{prefix}_{uuid.uuid4().hex[:12]}"'


class Interpreter:
    def __init__(
        self,
        cursor: duckdb.DuckDBPyConnection,
        context: Context,
        run_sql: Callable[[exp.Expression], dict | None],
    ):
        self.cursor = cursor
        self.context = context
        self.run_sql = run_sql
        self.handlers = {
            "SQL": self.sql,
            "DECLARE": self.declare,
            "SET": self.set,
            "IF": self.branch,
            "WHILE": self.repeat_while,
            "REPEAT": self.repeat_until,
            "FOR": self.for_each,
            "BLOCK": self.block,
            "BREAK": self.control(Break),
            "CONTINUE": self.control(Continue),
            "RETURN": self.control(Return),
            "RAISE": self.raise_error,
            "ASSERT": self.check,
            "EXECUTE": self.execute,
            "CALL": self.call,
            "PROCEDURE": self.procedure,
            "DROP_PROCEDURE": self.drop_procedure,
        }

    def run(self, statements: list[Statement]):
        try:
            self.statements(statements)
        except Return:
            pass

    def statements(self, statements: list[Statement]):
        kinds = [statement.kind for statement in statements]
        first = next((i for i, k in enumerate(kinds) if k != "DECLARE"), len(kinds))
        if "DECLARE" in kinds[first:]:
            raise BigQueryError(
                "invalidQuery",
                "Variable declarations are allowed only at the start of a block "
                "or script",
            )
        for statement in statements:
            self.context.system["statement_text"] = statement.text
            self.handlers[statement.kind](statement)

    def scope(self, statements: list[Statement], variables: dict | None = None):
        saved = self.context.variables
        self.context.variables = saved | (variables or {})
        try:
            self.statements(statements)
        finally:
            self.context.variables = saved

    def expression(self, sql: str) -> exp.Expression:
        return sqlglot.parse_one(f"SELECT {sql}", dialect=BigQueryDialect).expressions[
            0
        ]

    def evaluate(self, sql: str):
        select = _select(self.expression(sql))
        query, bound = translate(select, self.context)
        return self.cursor.sql(query, params=bound).fetchone()[0]

    def test(self, condition: str) -> bool:
        return bool(self.evaluate(f"CAST(({condition}) AS BOOL)"))

    def store(self, value: exp.Expression) -> str:
        table = _temporary_table("variable")
        query, bound = translate(_select(value), self.context)
        self.cursor.execute(f"CREATE TEMP TABLE {table} AS {query}", bound)
        return table

    def assign(self, table: str, value: exp.Expression):
        query, bound = translate(_select(value), self.context)
        self.cursor.execute(
            f"UPDATE {table} SET {VALUE} = (SELECT {VALUE} FROM ({query}))", bound
        )

    def variable(self, name: str) -> str:
        if (table := self.context.variables.get(name.lower())) is None:
            raise BigQueryError("invalidQuery", f"Undeclared variable: {name}")
        return table

    def sql(self, statement: Statement):
        for tree in parse(statement.text):
            statistics = self.run_sql(tree) or {}
            if "numDmlAffectedRows" in statistics:
                self.context.system["row_count"] = int(statistics["numDmlAffectedRows"])

    def declare(self, statement: Statement):
        tree = sqlglot.parse_one(statement.text, dialect=BigQueryDialect)
        for item in tree.expressions:
            value = item.args.get("default") or exp.null()
            if kind := item.args.get("kind"):
                value = exp.cast(value, kind)
            for name in item.this:
                self.context.variables[name.name.lower()] = self.store(value.copy())

    def set(self, statement: Statement):
        tree = sqlglot.parse_one(statement.text, dialect=BigQueryDialect)
        for item in tree.expressions:
            target, value = item.this.this, item.this.expression
            if isinstance(target, exp.Parameter):
                self.set_system(target.this.name.lower(), value)
                continue
            targets = target.expressions if isinstance(target, exp.Tuple) else [target]
            values = value.expressions if isinstance(value, exp.Tuple) else [value]
            tables = [self.variable(target.name) for target in targets]
            for table, part in zip(tables, values):
                self.assign(table, part)

    def set_system(self, name: str, value: exp.Expression):
        result = self.evaluate(value.sql(dialect=BigQueryDialect))
        if name in ("project_id", "dataset_id"):
            setattr(self.context, name, result)
        else:
            self.context.system[name] = result

    def branch(self, statement: Statement):
        for condition, body in statement.branches:
            if self.test(condition):
                return self.scope(body)
        if statement.otherwise is not None:
            self.scope(statement.otherwise)

    def iterate(self, body: list[Statement], variables: dict | None = None) -> bool:
        try:
            self.scope(body, variables)
        except Break:
            return False
        except Continue:
            pass
        return True

    def repeat_while(self, statement: Statement):
        while self.test(statement.text) and self.iterate(statement.body):
            pass

    def repeat_until(self, statement: Statement):
        while self.iterate(statement.body) and not self.test(statement.text):
            pass

    def for_each(self, statement: Statement):
        rows = _temporary_table("rows")
        select = sqlglot.parse_one(
            f"SELECT * FROM {statement.text}", dialect=BigQueryDialect
        )
        query, bound = translate(select, self.context)
        self.cursor.execute(
            f"CREATE TEMP TABLE {rows} AS "
            f"SELECT row_number() OVER () AS __n, q AS {VALUE} FROM ({query}) AS q",
            bound,
        )
        (count,) = self.cursor.sql(f"SELECT count(*) FROM {rows}").fetchone()
        name = statement.names[0].lower()
        for index in range(1, count + 1):
            table = _temporary_table("variable")
            self.cursor.execute(
                f"CREATE TEMP TABLE {table} AS SELECT {VALUE} FROM {rows} WHERE __n = {index}"
            )
            if not self.iterate(statement.body, {name: table}):
                break

    def block(self, statement: Statement):
        if statement.otherwise is None:
            return self.scope(statement.body)
        try:
            self.scope(statement.body)
        except Control:
            raise
        except Exception as exception:
            error = from_exception(exception)
            self.context.system |= {
                "error.message": error.message,
                "error.statement_text": self.context.system.get("statement_text"),
                "error.formatted_stack_trace": "",
            }
            self.scope(statement.otherwise)

    def control(self, signal: type[Control]) -> Callable[[Statement], None]:
        def handler(statement: Statement):
            raise signal()

        return handler

    def raise_error(self, statement: Statement):
        if statement.text:
            message = self.evaluate(statement.text)
        else:
            message = self.context.system.get("error.message")
        raise BigQueryError("invalidQuery", str(message))

    def check(self, statement: Statement):
        if not self.test(statement.text):
            description = statement.names[0]
            message = self.evaluate(description) if description else None
            raise BigQueryError(
                "invalidQuery", message or f"Assertion failed: {statement.text}"
            )

    def execute(self, statement: Statement):
        sql = self.evaluate(statement.text)
        saved = self.context.parameters
        parameters = {}
        for index, (expression, alias) in enumerate(statement.items):
            table = self.store(self.expression(expression))
            parameters[alias or f"p{index}"] = read(table)
        self.context.parameters = saved | parameters
        try:
            trees = parse(sql)
            for tree in trees:
                self.context.position = 0
                if statement.names and tree is trees[-1]:
                    self.into(tree, statement.names)
                else:
                    self.sql(Statement("SQL", tree.sql(dialect=BigQueryDialect)))
        finally:
            self.context.parameters = saved

    def into(self, tree: exp.Expression, names: list[str]):
        rows = _temporary_table("rows")
        query, bound = translate(tree, self.context)
        self.cursor.execute(f"CREATE TEMP TABLE {rows} AS {query}", bound)
        columns = self.cursor.sql(f"SELECT * FROM {rows}").columns
        for name, column in zip(names, columns):
            self.cursor.execute(
                f"UPDATE {self.variable(name)} "
                f'SET {VALUE} = (SELECT "{column}" FROM {rows} LIMIT 1)'
            )

    def reference(self, name: str) -> tuple[str, str, str]:
        table = exp.to_table(name, dialect=BigQueryDialect)
        return (
            table.catalog or self.context.project_id,
            table.db or self.context.dataset_id,
            table.name,
        )

    def call(self, statement: Statement):
        if statement.text.upper() == "BQ.REFRESH_MATERIALIZED_VIEW":
            return
        project_id, dataset_id, routine_id = self.reference(statement.text)
        routine = routines.load(project_id, dataset_id, routine_id)
        if routine is None or routine.get("routineType") != "PROCEDURE":
            raise BigQueryError(
                "invalidQuery",
                f"Procedure not found: {project_id}.{dataset_id}.{routine_id}",
            )
        variables, outputs = {}, []
        for argument, (expression, _) in zip(routine["arguments"], statement.items):
            kind = exp.DataType.build(
                argument["dataType"]["typeKind"], dialect=BigQueryDialect
            )
            name = argument["name"].lower()
            variables[name] = self.store(exp.cast(self.expression(expression), kind))
            if argument.get("mode") in ("OUT", "INOUT"):
                outputs.append((self.variable(expression.strip()), variables[name]))
        saved = self.context.variables
        self.context.variables = variables
        try:
            self.statements(parse_script(routine["definitionBody"]))
        except Return:
            pass
        finally:
            self.context.variables = saved
        for target, source in outputs:
            self.cursor.execute(f"UPDATE {target} SET {VALUE} = {read(source)}")

    def procedure(self, statement: Statement):
        words = [word.upper() for word in statement.names]
        project_id, dataset_id, routine_id = self.reference(statement.names[-1])
        if routines.load(project_id, dataset_id, routine_id) is not None:
            if "EXISTS" in words:
                return
            if "REPLACE" not in words:
                raise BigQueryError(
                    "duplicate",
                    f"Already Exists: Routine {project_id}:{dataset_id}.{routine_id}",
                )
        arguments = []
        for text, _ in statement.items:
            parts = text.split()
            mode = "IN"
            if parts[0].upper() in ("IN", "OUT", "INOUT"):
                mode = parts.pop(0).upper()
            kind = " ".join(parts[1:]).upper()
            arguments.append(
                {"name": parts[0], "mode": mode, "dataType": {"typeKind": kind}}
            )
        routines.save(
            project_id,
            dataset_id,
            routine_id,
            {
                "routineType": "PROCEDURE",
                "language": "SQL",
                "arguments": arguments,
                "definitionBody": statement.text,
            },
        )

    def drop_procedure(self, statement: Statement):
        words = statement.text.split()
        project_id, dataset_id, routine_id = self.reference(words[-1])
        if routines.load(project_id, dataset_id, routine_id) is None:
            if "EXISTS" in (word.upper() for word in words):
                return
            raise BigQueryError(
                "notFound", f"Not found: Routine {project_id}:{dataset_id}.{routine_id}"
            )
        routines.delete(project_id, dataset_id, routine_id)
