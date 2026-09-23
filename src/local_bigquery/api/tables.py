from fastapi import Body, Header, Query

from local_bigquery.api import Router, paginate, with_rows
from local_bigquery.catalog import tables
from local_bigquery.jobs.query import translate_view
from local_bigquery.models import Table, TableDataInsertAllResponse, TableList

router = Router(tags=["tables"])
TABLE = "/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}"


@router.get("/projects/{project_id}/datasets/{dataset_id}/tables")
def list_tables(
    project_id: str,
    dataset_id: str,
    maxResults: int | None = None,
    pageToken: str | None = None,
) -> TableList:
    summaries = tables.list_(project_id, dataset_id)
    page, token = paginate(summaries, maxResults, pageToken)
    return TableList(
        kind="bigquery#tableList",
        tables=page,
        nextPageToken=token,
        totalItems=len(summaries),
    )


@router.post("/projects/{project_id}/datasets/{dataset_id}/tables")
def insert_table(project_id: str, dataset_id: str, body: dict = Body()) -> Table:
    return tables.create(project_id, dataset_id, body, translate_view)


@router.get(TABLE)
def get_table(project_id: str, dataset_id: str, table_id: str) -> Table:
    return tables.get(project_id, dataset_id, table_id)


@router.patch(TABLE)
def patch_table(
    project_id: str,
    dataset_id: str,
    table_id: str,
    body: dict = Body(),
    if_match: str | None = Header(None),
) -> Table:
    return tables.update(project_id, dataset_id, table_id, body, if_match, False)


@router.put(TABLE)
def update_table(
    project_id: str,
    dataset_id: str,
    table_id: str,
    body: dict = Body(),
    if_match: str | None = Header(None),
) -> Table:
    return tables.update(project_id, dataset_id, table_id, body, if_match, True)


@router.delete(TABLE, status_code=204)
def delete_table(project_id: str, dataset_id: str, table_id: str):
    tables.delete(project_id, dataset_id, table_id)


@router.post(f"{TABLE}/insertAll")
def insert_all(
    project_id: str, dataset_id: str, table_id: str, body: dict = Body()
) -> TableDataInsertAllResponse:
    response = tables.insert_all(project_id, dataset_id, table_id, body)
    return TableDataInsertAllResponse(
        kind="bigquery#tableDataInsertAllResponse", **response
    )


@router.get(f"{TABLE}/data")
def list_rows(
    project_id: str,
    dataset_id: str,
    table_id: str,
    maxResults: int | None = None,
    pageToken: str | None = None,
    startIndex: int = 0,
    selectedFields: str | None = None,
    int64_timestamps: bool = Query(False, alias="formatOptions.useInt64Timestamp"),
):
    start = int(pageToken) if pageToken else startIndex
    page, _ = tables.list_rows(
        project_id,
        dataset_id,
        table_id,
        maxResults,
        start,
        selectedFields,
        int64_timestamps,
    )
    return with_rows(
        {
            "kind": "bigquery#tableDataList",
            "totalRows": str(page.total),
            "pageToken": page.next_token,
        },
        page.rows,
    )
