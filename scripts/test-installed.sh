#!/usr/bin/env bash
set -euo pipefail
dist=$(mktemp -d) env=$(mktemp -d) data=$(mktemp -d)
uv build -q -o "$dist"
uv venv -q -p 3.13 "$env"
VIRTUAL_ENV="$env" uv pip install -q "$dist"/*.whl
"$env/bin/local-bigquery" --port 9151 --grpc-port 9152 --data-dir "$data" &
server=$!
trap 'kill $server' EXIT
for _ in $(seq 60); do
  curl -sf http://127.0.0.1:9151/bigquery/v2/projects >/dev/null && break
  sleep 0.5
done
uv run --frozen pytest tests --endpoint http://127.0.0.1:9151 "$@"
