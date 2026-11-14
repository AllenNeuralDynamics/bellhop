import time
from pathlib import Path

import yaml
from bellhop_models.specifications import JobSpecification
from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from bellhop.engine import Engine


class _DropboxHandler(FileSystemEventHandler):
    def __init__(self, engine: Engine, submitted_dir: Path, failed_dir: Path):
        self._engine = engine
        self._submitted_dir = submitted_dir
        self._failed_dir = failed_dir

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix not in (".yml", ".yaml"):
            return
        self._process(path)

    def _read_spec_data(self, path: Path, retries: int = 20, delay: float = 0.1) -> object:
        # on_created can fire before the writer flushes; wait for non-empty content.
        for _ in range(retries):
            try:
                data = yaml.safe_load(path.read_text())
            except yaml.YAMLError:
                data = None
            if data is not None:
                return data
            time.sleep(delay)
        return yaml.safe_load(path.read_text())

    def _process(self, path: Path) -> None:
        try:
            spec = JobSpecification.model_validate(self._read_spec_data(path))
            job_id = self._engine.submit_job(spec)
            logger.info(f"Dropbox: submitted '{spec.name}' ({job_id}) from {path.name}")
            path.rename(self._submitted_dir / path.name)
        except Exception as e:
            logger.error(f"Dropbox: failed to process {path.name}: {e}")
            dest = self._failed_dir / path.name
            path.rename(dest)
            dest.with_suffix(".error.txt").write_text(str(e))


class JobDropbox:
    def __init__(self, engine: Engine, dropbox_dir: Path):
        self._engine = engine
        self._dropbox_dir = dropbox_dir
        self._submitted_dir = dropbox_dir / "submitted"
        self._failed_dir = dropbox_dir / "failed_submissions"
        self._observer = Observer()

    def start(self) -> "JobDropbox":
        self._dropbox_dir.mkdir(parents=True, exist_ok=True)
        self._submitted_dir.mkdir(exist_ok=True)
        self._failed_dir.mkdir(exist_ok=True)
        handler = _DropboxHandler(self._engine, self._submitted_dir, self._failed_dir)
        self._observer.schedule(handler, str(self._dropbox_dir), recursive=False)
        self._observer.start()
        logger.info(f"Dropbox watching {self._dropbox_dir}")
        return self

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()
