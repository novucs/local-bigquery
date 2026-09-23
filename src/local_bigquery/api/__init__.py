from fastapi import APIRouter


class Router(APIRouter):
    def add_api_route(self, path, endpoint, **kwargs):
        super().add_api_route(
            path, endpoint, **kwargs | {"response_model_exclude_unset": True}
        )
