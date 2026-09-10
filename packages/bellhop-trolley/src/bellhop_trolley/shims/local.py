import shutil
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

from bellhop_trolley._config_utils import ContextConfig
from .robocopy import RobocopyOptions, robocopy


class LocalTransferSettings(BaseSettings):
    copy_method: Literal["shutil", "robocopy"] = "shutil"

    robocopy_args: RobocopyOptions = RobocopyOptions(subdirectories_including_empty=True)
    # robocopy_args: list[str] = [
    #     "/s",
    #     "/j",
    #     "/r:5",
    #     "/np",
    #     "/mt:8",
    #     "/log+:C:\\ProgramData\\robocopy\\logs\\robocopy.log",
    # ]


context = ContextConfig(LocalTransferSettings)


##


def _shutil_copy(source: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)


def _robocopy_copy(source: Path, destination: Path):
    config = context.config()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        robocopy(source=source, destination=destination, **config.robocopy_args.model_dump())
    else:
        robocopy(
            source=source.parent, destination=destination.parent, files=source.name, **config.robocopy_args.model_dump()
        )


def copy(source: Path, destination: Path):
    config = context.config()
    if config.copy_method == "shutil":
        _shutil_copy(source, destination)
    elif config.copy_method == "robocopy":
        _robocopy_copy(source, destination)
    else:
        raise ValueError(f"Unsupported copy method: {config.copy_method}")


def delete(path: Path):
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)
