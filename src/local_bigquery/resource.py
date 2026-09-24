from typing import Self

from pydantic import BaseModel, ConfigDict


def merge(target: dict, patch: dict) -> dict:
    merged = dict(target)
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class Resource(BaseModel):
    model_config = ConfigDict(
        extra="allow", validate_by_name=True, coerce_numbers_to_str=True
    )

    def dump(self) -> dict:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)

    def given(self) -> dict:
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)

    def only(self, *keys: str) -> Self:
        return self.model_validate({k: v for k, v in self.dump().items() if k in keys})

    def without(self, *keys: str) -> Self:
        return self.model_validate(
            {k: v for k, v in self.dump().items() if k not in keys}
        )

    def replace(self, **changes) -> Self:
        return self.model_validate(self.dump() | changes)

    def merged(self, patch: "Resource") -> Self:
        return self.model_validate(merge(self.dump(), patch.given()))
