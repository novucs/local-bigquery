from pathlib import Path

from pydantic import Field

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bigquery_port: int = Field(9050)
    bigquery_host: str = Field("0.0.0.0")
    database_path: Path = Field("/data")
    default_project_id: str = Field("main")
    default_dataset_id: str = Field("main")
    internal_project_id: str = Field("internal")
    internal_dataset_id: str = Field("internal")


settings = Settings()
