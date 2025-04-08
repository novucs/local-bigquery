#!/bin/bash

set -e

SCRIPT_DIR=$(dirname -- "$(readlink -f -- "$BASH_SOURCE")")
SRC_DIR="${SCRIPT_DIR}/.."
SPECS_DIR="${SRC_DIR}/../specs"
GOOGLE_PATH="${SPECS_DIR}/google.json"
SWAGGER_PATH="${SPECS_DIR}/swagger.yaml"
OPENAPI_PATH="${SPECS_DIR}/openapi.yaml"
OUTPUT_DIR="${SRC_DIR}/pybigquery"
OUTPUT_MAIN="${OUTPUT_DIR}/main.py"

curl https://bigquery.googleapis.com/discovery/v1/apis/bigquery/v2/rest -o $GOOGLE_PATH
api-spec-converter --from=google --to=swagger_2 --syntax=json $GOOGLE_PATH > $SWAGGER_PATH
api-spec-converter --from=swagger_2 --to=openapi_3 --syntax=yaml $SWAGGER_PATH > $OPENAPI_PATH
fastapi-codegen --input $OPENAPI_PATH --output pybigquery --output-model-type pydantic_v2.BaseModel
sed -i '' -E 's/[0-9]+]/]/g' $OUTPUT_MAIN
