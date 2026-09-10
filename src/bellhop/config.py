from pathlib import Path

from platformdirs import site_data_dir
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings, validate_default=True):
    data_dir: Path = site_data_dir("bellhop", "AllenInstitute", ensure_exists=True)
    database_file: Path | None = None
    dropbox_dir: Path | None = None

    api_port: int = 8311

    env_vars_to_show: list[str] = ["COMPUTERNAME", "AIBS_COMP_ID"]

    @model_validator(mode="after")
    def _default_database_file(self) -> "Config":
        if self.database_file is None:
            self.database_file = self.data_dir / "bellhop_jobs.sqlite"
        if self.dropbox_dir is None:
            self.dropbox_dir = self.data_dir / "dropbox"
        return self
