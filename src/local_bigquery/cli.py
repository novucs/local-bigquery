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
    parser.add_argument("--grpc-port", type=int, default=settings.grpc_port)
    parser.add_argument("--project", default=settings.default_project_id)
    parser.add_argument("--dataset", default=settings.default_dataset_id)
    parser.add_argument("--data-dir", type=pathlib.Path, default=settings.data_dir)
    args = parser.parse_args(argv)
    settings.bigquery_host = args.host
    settings.bigquery_port = args.port
    settings.grpc_port = args.grpc_port
    settings.default_project_id = args.project
    settings.default_dataset_id = args.dataset
    settings.data_dir = args.data_dir
    if args.command == "reset":
        from local_bigquery.engine import database

        database.reset()
    elif args.command == "repl":
        from local_bigquery import repl

        repl.main()
    else:
        from local_bigquery.grpc import server

        grpc_server, _ = server.start(args.host, args.grpc_port)
        uvicorn.run("local_bigquery:app", host=args.host, port=args.port)
        grpc_server.stop(None)
