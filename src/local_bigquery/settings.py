from pathlib import Path

from pydantic import Field

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bigquery_port: int = Field(9050)
    bigquery_host: str = Field("0.0.0.0")
    grpc_port: int = Field(9060)
    data_dir: Path = Field("/data")
    default_project_id: str = Field("local")
    default_dataset_id: str = Field("local")
    postgres_connection_id: str = Field("us.default")
    gcs_local_root: Path | None = Field(None)
    postgres_uri: str = Field("postgresql://postgres:example@db:5432/postgres")


settings = Settings()
