from local_bigquery import db
from local_bigquery.api import Router
from local_bigquery.db import timestamp_now
from local_bigquery.models import (
    Table,
    TableDataInsertAllRequest,
    TableDataInsertAllResponse,
    TableList,
    TableListTablesItem,
    TableReference,
)

router = Router(tags=["tables"])


@router.get("/projects/{project_id}/datasets/{dataset_id}/tables")
def list_tables(project_id: str, dataset_id: str) -> TableList:
    tables = db.list_tables(project_id, dataset_id)
    return TableList(
        kind="bigquery#tableList",
        tables=[
            TableListTablesItem(
                creationTime=timestamp_now(),
                id=f"{project_id}:{dataset_id}.{table_id}",
                kind="bigquery#table",
                tableReference=TableReference(
                    projectId=project_id, datasetId=dataset_id, tableId=table_id
                ),
                type="TABLE",
            )
            for table_id in tables
        ],
        totalItems=len(tables),
    )


@router.post("/projects/{project_id}/datasets/{dataset_id}/tables")
def insert_table(project_id: str, dataset_id: str, body: Table) -> Table:
    db.create_table(project_id, dataset_id, body.tableReference.tableId, body.schema_)
    return body


@router.delete(
    "/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}", status_code=204
)
def delete_table(project_id: str, dataset_id: str, table_id: str):
    db.delete_table(project_id, dataset_id, table_id)


@router.post("/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}/insertAll")
def insert_all(
    project_id: str, dataset_id: str, table_id: str, body: TableDataInsertAllRequest
) -> TableDataInsertAllResponse:
    if body.rows:
        db.tabledata_insert_all(project_id, dataset_id, table_id, body.rows)
    return TableDataInsertAllResponse()
