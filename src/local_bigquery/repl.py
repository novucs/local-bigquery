import sys

import duckdb
import prompt_toolkit
import sqlglot
from prompt_toolkit import PromptSession
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.sql import GoogleSqlLexer

from local_bigquery.db import cursor
from local_bigquery.settings import settings
from prompt_toolkit.completion import Completer, Completion

display = prompt_toolkit.print_formatted_text

BIGQUERY_WORDS = [
    # Keywords
    "SELECT",
    "FROM",
    "WHERE",
    "INSERT",
    "INTO",
    "VALUES",
    "UPDATE",
    "SET",
    "DELETE",
    "CREATE",
    "TABLE",
    "SCHEMA",
    "VIEW",
    "MATERIALIZED",
    "FUNCTION",
    "PROCEDURE",
    "ALTER",
    "DROP",
    "RENAME",
    "TO",
    "JOIN",
    "INNER",
    "LEFT",
    "RIGHT",
    "FULL",
    "OUTER",
    "CROSS",
    "ON",
    "USING",
    "AS",
    "DISTINCT",
    "GROUP",
    "BY",
    "ORDER",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "UNION",
    "ALL",
    "INTERSECT",
    "EXCEPT",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "AND",
    "OR",
    "NOT",
    "IN",
    "LIKE",
    "BETWEEN",
    "IS",
    "NULL",
    "TRUE",
    "FALSE",
    "WITH",
    "RECURSIVE",
    "PARTITION",
    "CLUSTER",
    "OPTIONS",
    "UNNEST",
    "ARRAY",
    "STRUCT",
    "FOR",
    "SYSTEM_TIME",
    "AS",
    "OF",
    "ASSERT",
    "BEGIN",
    "TRANSACTION",
    "COMMIT",
    "ROLLBACK",
    "DECLARE",
    "SET",
    "EXECUTE",
    "IMMEDIATE",
    "CALL",
    "LOOP",
    "WHILE",
    "IF",
    "LEAVE",
    "ITERATE",
    "RETURN",
    # Data Types
    "STRING",
    "BYTES",
    "INTEGER",
    "INT64",
    "FLOAT",
    "FLOAT64",
    "NUMERIC",
    "DECIMAL",
    "BIGNUMERIC",
    "BIGDECIMAL",
    "BOOLEAN",
    "BOOL",
    "TIMESTAMP",
    "DATE",
    "TIME",
    "DATETIME",
    "GEOGRAPHY",
    "INTERVAL",
    # Common Functions (Examples - add more as needed)
    "ABS",
    "AVG",
    "CAST",
    "CEIL",
    "CEILING",
    "COALESCE",
    "CONCAT",
    "CORR",
    "COUNT",
    "COUNTIF",
    "CURRENT_DATE",
    "CURRENT_TIMESTAMP",
    "DATE_ADD",
    "DATE_DIFF",
    "DATE_SUB",
    "DATE_TRUNC",
    "EXP",
    "EXTRACT",
    "FLOOR",
    "FORMAT",
    "GENERATE_ARRAY",
    "GENERATE_DATE_ARRAY",
    "IFNULL",
    "JSON_EXTRACT",
    "JSON_EXTRACT_SCALAR",
    "LAG",
    "LEAD",
    "LENGTH",
    "LN",
    "LOG",
    "LOG10",
    "LOWER",
    "MAX",
    "MIN",
    "MOD",
    "NTILE",
    "POWER",
    "RAND",
    "RANK",
    "REGEXP_CONTAINS",
    "REGEXP_EXTRACT",
    "REGEXP_REPLACE",
    "REPLACE",
    "ROUND",
    "ROW_NUMBER",
    "SAFE_CAST",
    "SPLIT",
    "SQRT",
    "STARTS_WITH",
    "STDDEV_POP",
    "STDDEV_SAMP",
    "STRING_AGG",
    "SUBSTR",
    "SUBSTRING",
    "SUM",
    "TIMESTAMP_ADD",
    "TIMESTAMP_DIFF",
    "TIMESTAMP_MICROS",
    "TIMESTAMP_MILLIS",
    "TIMESTAMP_SECONDS",
    "TIMESTAMP_TRUNC",
    "TRIM",
    "TRUNC",
    "UPPER",
    "VAR_POP",
    "VAR_SAMP",
    "WINDOW",
]


class BigQueryCompleter(Completer):
    def __init__(self):
        super().__init__()
        self.projects = {}

    def add_project(self, project):
        self.projects.add(project)

    def add_dataset(self, project, dataset):
        self.projects[project] = dataset

    def get_completions(self, document, complete_event):
        if document.text_after_cursor.strip():
            return

        text_before_cursor = document.text_before_cursor
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        word_before_cursor_lower = word_before_cursor.lower()

        if word_before_cursor_lower.endswith("."):
            parts = text_before_cursor.split(" ")[-1].split(".")
            parts = [part.strip("`") for part in parts if part]
            start_pos = 0
            completions = set()

            if len(parts) == 0:
                start_pos = -1
                completions.update(self.projects.keys())
                completions.update(self.projects.get(settings.default_project_id, {}))
            elif len(parts) == 1:
                a = parts[0]
                completions.update(self.projects.get(a, {}))
                completions.update(
                    self.projects.get(settings.default_project_id, {}).get(a, {})
                )
            elif len(parts) == 2:
                a, b = parts
                completions.update(self.projects.get(a, {}).get(b, {}))
                completions.update(
                    self.projects.get(settings.default_project_id, {})
                    .get(a, {})
                    .get(b, {})
                )
            elif len(parts) == 3:
                a, b, c = parts
                completions.update(self.projects.get(a, {}).get(b, {}).get(c, {}))

            for item in sorted(list(completions)):
                if "-" in item:
                    item = f"`{item}`"
                yield Completion(item, start_position=start_pos)
        else:
            for item in sorted(list(BIGQUERY_WORDS)):
                if item.lower().startswith(word_before_cursor_lower):
                    yield Completion(item, start_position=-len(word_before_cursor))


def refresh(cur, completer):
    for db in settings.data_dir.glob("*.db"):
        cur.execute(f"ATTACH IF NOT EXISTS '{db}' AS \"{db.stem}\"")
    result = cur.sql("SHOW ALL TABLES")
    for row in result.fetchall():
        project, dataset, table, columns, *_ = row
        for column in columns:
            completer.projects.setdefault(project, {}).setdefault(
                dataset, {}
            ).setdefault(table, set()).add(column)


def help_():
    display("Available commands:")
    display("  help   - Show this message")
    display("  exit   - Exit the REPL")
    display("  reset  - Delete all projects, datasets, and tables")
    display("  clear  - Clear the screen")
    display()
    display("Shortcuts:")
    display("  CTRL+C - Cancel a query")
    display("  CTRL+D - Exit the REPL")


def clear():
    prompt_toolkit.shortcuts.clear()


def reset():
    for db in settings.data_dir.glob("*.db"):
        db.unlink()
    display("All projects, datasets, and tables have been deleted.")
    display("A REPL restart is required to see the changes.")
    display("Exiting the REPL...")
    exit_()


def exit_():
    display("Goodbye!")
    sys.exit(0)


def execute_sql(cur, sql):
    try:
        duckdb_sqls = sqlglot.transpile(sql, "bigquery", write="duckdb")
    except sqlglot.ParseError as e:
        display(e)
        return
    try:
        for sql in duckdb_sqls:
            result = cur.sql(sql)
            if result:
                display(result)
    except duckdb.Error as e:
        display(e)
        return
    except RuntimeError as e:
        if str(e) == "Query interrupted":
            display("\nQuery cancelled")
            return
        raise


def main():
    history = FileHistory(settings.data_dir / "repl-history.txt")
    completer = BigQueryCompleter()
    session = PromptSession(
        history=history,
        prompt_continuation="... ",
        lexer=PygmentsLexer(GoogleSqlLexer),
        completer=completer,
        complete_while_typing=True,
    )

    def continue_input():
        buffer = session.default_buffer.text.strip()
        if buffer.endswith(";"):
            return False
        if buffer.lower() in {"exit", "quit", "help", "clear", "reset"}:
            return False
        return True

    session.multiline = Condition(continue_input)

    display("Welcome to the Local BigQuery REPL!")
    display("Type 'help' for a list of commands.")
    try:
        with cursor(settings.default_project_id, settings.default_dataset_id) as cur:
            while True:
                refresh(cur, completer)
                try:
                    text = session.prompt("--> ").strip()
                except KeyboardInterrupt:
                    continue
                refresh(cur, completer)
                commands = {
                    "exit": exit_,
                    "quit": exit_,
                    "help": help_,
                    "clear": clear,
                    "reset": reset,
                }
                if command := commands.get(text.rstrip(";")):
                    command()
                else:
                    execute_sql(cur, text)
    except EOFError:
        pass
    exit_()


if __name__ == "__main__":
    main()
