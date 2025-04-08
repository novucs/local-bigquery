from pathlib import Path

from pydantic import Field

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bigquery_port: int = Field(9050, validation_alias="bigquery_port")
    bigquery_host: str = Field("0.0.0.0", validation_alias="bigquery_host")
    database_path: Path = Field("/tmp/bigquery.db", validation_alias="database_path")


settings = Settings()
