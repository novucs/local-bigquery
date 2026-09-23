import argparse
import pathlib

import uvicorn

from local_bigquery.settings import settings


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        "local-bigquery", description="Run BigQuery locally"
    )
    parser.add_argument(
        "command", nargs="?", default="serve", choices=["serve", "repl", "reset"]
    )
    parser.add_argument("--host", default=settings.bigquery_host)
    parser.add_argument("--port", type=int, default=settings.bigquery_port)
    parser.add_argument("--project", default=settings.default_project_id)
    parser.add_argument("--dataset", default=settings.default_dataset_id)
    parser.add_argument("--data-dir", type=pathlib.Path, default=settings.data_dir)
    args = parser.parse_args(argv)
    settings.bigquery_host = args.host
    settings.bigquery_port = args.port
    settings.default_project_id = args.project
    settings.default_dataset_id = args.dataset
    settings.data_dir = args.data_dir
    if args.command == "reset":
        from local_bigquery import db

        db.reset()
    elif args.command == "repl":
        from local_bigquery import repl

        repl.main()
    else:
        uvicorn.run("local_bigquery:app", host=args.host, port=args.port)
