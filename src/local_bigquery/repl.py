import sys

import duckdb
import prompt_toolkit
import sqlglot
from prompt_toolkit import PromptSession
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.sql import GoogleSqlLexer

from local_bigquery import db
from local_bigquery.db import cursor, bigquery_to_duckdb_sqlglot, is_js_udf, bind_js_udf
from local_bigquery.settings import settings
from prompt_toolkit.completion import Completer, Completion

display = prompt_toolkit.print_formatted_text

BIGQUERY_WORDS = """
ABS ALL ALTER AND ARRAY AS AS ASSERT AVG BEGIN BETWEEN BIGDECIMAL BIGNUMERIC
BOOL BOOLEAN BY BYTES CALL CASE CAST CEIL CEILING CLUSTER COALESCE COMMIT CONCAT
CORR COUNT COUNTIF CREATE CROSS CURRENT_DATE CURRENT_TIMESTAMP DATE DATETIME
DATE_ADD DATE_DIFF DATE_SUB DATE_TRUNC DECIMAL DECLARE DELETE DISTINCT DROP ELSE
END EXCEPT EXECUTE EXP EXTRACT FALSE FLOAT FLOAT64 FLOOR FOR FORMAT FROM FULL
FUNCTION GENERATE_ARRAY GENERATE_DATE_ARRAY GEOGRAPHY GROUP HAVING IF IFNULL
IMMEDIATE IN INNER INSERT INT64 INTEGER INTERSECT INTERVAL INTO IS ITERATE JOIN
JSON_EXTRACT JSON_EXTRACT_SCALAR LAG LEAD LEAVE LEFT LENGTH LIKE LIMIT LN LOG
LOG10 LOOP LOWER MATERIALIZED MAX MIN MOD NOT NTILE NULL NUMERIC OF OFFSET ON
OPTIONS OR ORDER OUTER PARTITION POWER PROCEDURE RAND RANK RECURSIVE
REGEXP_CONTAINS REGEXP_EXTRACT REGEXP_REPLACE RENAME REPLACE RETURN RIGHT
ROLLBACK ROUND ROW_NUMBER SAFE_CAST SCHEMA SELECT SET SET SPLIT SQRT STARTS_WITH
STDDEV_POP STDDEV_SAMP STRING STRING_AGG STRUCT SUBSTR SUBSTRING SUM SYSTEM_TIME
TABLE THEN TIME TIMESTAMP TIMESTAMP_ADD TIMESTAMP_DIFF TIMESTAMP_MICROS
TIMESTAMP_MILLIS TIMESTAMP_SECONDS TIMESTAMP_TRUNC TO TRANSACTION TRIM TRUE
TRUNC UNION UNNEST UPDATE UPPER USING VALUES VAR_POP VAR_SAMP VIEW WHEN WHERE
WHILE WINDOW WITH
""".split()


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
    found_projects = {project.stem for project in settings.data_dir.glob("*.ducklake")}
    for project in found_projects:
        db.attach_project(cur, project)
    # `SHOW ALL TABLES` currently unsupported by DuckLake.
    result = cur.sql(
        """
        SELECT
            c.database_name AS project,
            c.schema_name AS dataset,
            c.table_name AS table,
            ARRAY_AGG(c.column_name) AS columns
        FROM
            duckdb_databases() d
            JOIN duckdb_schemas() s
                ON d.database_name = s.database_name
            JOIN duckdb_tables() t
                 ON s.database_name = t.database_name
                     AND s.schema_name = t.schema_name
            JOIN duckdb_columns() c
                 ON t.database_name = c.database_name
                     AND t.schema_name = c.schema_name
                     AND t.table_name = c.table_name
        WHERE
            d.type='ducklake'
        GROUP BY
            c.database_name,
            c.schema_name,
            c.table_name
        """
    )
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
    db.reset()
    display("All projects, datasets, and tables have been deleted.")
    display("A REPL restart is required to see the changes.")
    display("Exiting the REPL...")
    exit_()


def exit_():
    display("Goodbye!")
    sys.exit(0)


def get_current_scope(cur):
    results = cur.sql(
        "SELECT current_catalog() AS project_id, current_schema() AS dataset_id"
    ).fetchone()
    return results


def execute_sql(cur, sql):
    try:
        project_id, dataset_id = get_current_scope(cur)
        transform = bigquery_to_duckdb_sqlglot(project_id, dataset_id)
        trees = sqlglot.parse(sql, "bigquery")
    except sqlglot.ParseError as e:
        display(e)
        return
    try:
        for tree in trees:
            if not tree:
                continue
            if is_js_udf(tree):
                bind_js_udf(cur, tree)
                continue
            sql = tree.transform(transform).sql("duckdb")
            result = cur.sql(sql)
            if result:
                display(result)
    except (duckdb.Error, sqlglot.ParseError) as e:
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
