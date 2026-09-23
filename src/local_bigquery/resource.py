from pydantic import BaseModel, ConfigDict


class Resource(BaseModel):
    model_config = ConfigDict(
        extra="allow", validate_by_name=True, coerce_numbers_to_str=True
    )
