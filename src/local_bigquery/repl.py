import json
import urllib.error
import urllib.request

import prompt_toolkit
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.sql import GoogleSqlLexer

from local_bigquery.settings import settings

display = prompt_toolkit.print_formatted_text
COMMANDS = {"exit", "quit", "help", "clear"}
KEYWORDS = """
ABS ALL ALTER AND ARRAY AS ASSERT AVG BEGIN BETWEEN BIGNUMERIC BOOL BY BYTES CALL
CASE CAST CLUSTER COALESCE COMMIT CONCAT COUNT COUNTIF CREATE CROSS CURRENT_DATE
CURRENT_TIMESTAMP DATE DATETIME DATE_ADD DATE_DIFF DATE_SUB DATE_TRUNC DECLARE
DELETE DISTINCT DROP ELSE END EXCEPT EXECUTE EXISTS EXTRACT FALSE FLOAT64 FOR
FORMAT FROM FULL FUNCTION GENERATE_ARRAY GEOGRAPHY GROUP HAVING IF IFNULL
IMMEDIATE IN INNER INSERT INT64 INTERSECT INTERVAL INTO IS JOIN JSON JSON_VALUE
LEFT LIKE LIMIT LOOP MERGE NOT NULL NUMERIC OFFSET ON OPTIONS OR ORDER OVER
PARTITION QUALIFY REPLACE RIGHT ROLLBACK SAFE_CAST SCHEMA SELECT SET STRING
STRUCT SUM TABLE THEN TIME TIMESTAMP TRUE UNION UNNEST UPDATE USING VALUES VIEW
WHEN WHERE WHILE WINDOW WITH
""".split()


def request(method: str, path: str, body: dict | None = None) -> dict:
    url = (
        f"http://localhost:{settings.bigquery_port}/bigquery/v2/projects/"
        f"{settings.default_project_id}{path}"
    )
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data, {"Content-Type": "application/json"}, method=method
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return json.loads(error.read())


def names() -> list[str]:
    found = []
    for dataset in request("GET", "/datasets").get("datasets", []):
        dataset_id = dataset["datasetReference"]["datasetId"]
        tables = request("GET", f"/datasets/{dataset_id}/tables").get("tables", [])
        found += [
            dataset_id,
            *(f"{dataset_id}.{t['tableReference']['tableId']}" for t in tables),
        ]
    return found


def cell(value) -> str:
    if isinstance(value, dict):
        return json.dumps([cell(v["v"]) for v in value.get("f", [])])
    if isinstance(value, list):
        return json.dumps([cell(v["v"]) for v in value])
    return "NULL" if value is None else str(value)


def show(response: dict):
    if error := response.get("error"):
        display(f"Error: {error['message']}")
        return
    fields = [f["name"] for f in response.get("schema", {}).get("fields", [])]
    rows = [[cell(c["v"]) for c in row["f"]] for row in response.get("rows", [])]
    if not fields:
        display(f"OK ({response.get('numDmlAffectedRows', 0)} rows affected)")
        return
    widths = [max(len(x) for x in column) for column in zip(fields, *rows)]
    line = "+".join("-" * (width + 2) for width in widths)
    for values in [fields, None, *rows]:
        if values is None:
            display(line)
        else:
            display(" | ".join(v.ljust(width) for v, width in zip(values, widths)))
    display(f"({response.get('totalRows', len(rows))} rows)")


def main():
    completer = WordCompleter(KEYWORDS, ignore_case=True, WORD=True)
    session = PromptSession(
        history=FileHistory(settings.data_dir / "repl-history.txt"),
        prompt_continuation="... ",
        lexer=PygmentsLexer(GoogleSqlLexer),
        completer=completer,
        complete_while_typing=True,
    )
    text = session.default_buffer
    session.multiline = Condition(
        lambda: (
            not text.text.strip().endswith(";") and text.text.strip() not in COMMANDS
        )
    )
    display("Local BigQuery REPL. Type 'help' for commands.")
    while True:
        completer.words = KEYWORDS + names()
        try:
            sql = session.prompt("--> ").strip().rstrip(";")
        except KeyboardInterrupt:
            continue
        except EOFError:
            return
        if sql in ("exit", "quit"):
            return
        if sql == "help":
            display("Enter SQL terminated by ';'. Commands: help, clear, exit.")
        elif sql == "clear":
            prompt_toolkit.shortcuts.clear()
        elif sql:
            body = {
                "query": sql,
                "useLegacySql": False,
                "defaultDataset": {
                    "projectId": settings.default_project_id,
                    "datasetId": settings.default_dataset_id,
                },
            }
            show(request("POST", "/queries", body))
