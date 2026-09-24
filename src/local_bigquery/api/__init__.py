import json

from fastapi import APIRouter, Response

from local_bigquery.resource import Resource


class Router(APIRouter):
    def add_api_route(self, path, endpoint, **kwargs):
        super().add_api_route(
            path, endpoint, **kwargs | {"response_model_exclude_unset": True}
        )


def paginate(
    items: list, max_results: int | None, page_token: str | None
) -> tuple[list, str | None]:
    start = int(page_token or 0)
    end = len(items) if max_results is None else start + max_results
    return items[start:end], str(end) if end < len(items) else None


def with_rows(payload: dict, rows: list[str]) -> Response:
    body = json.dumps(
        {key: value for key, value in payload.items() if value is not None},
        default=Resource.dump,
    )
    if rows:
        body = f'{body[:-1]}, "rows": [{",".join(rows)}]}}'
    return Response(body, media_type="application/json")
