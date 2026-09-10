import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from bellhop_models.database import Job, TaskExecution
from bellhop_models.specifications import JobSpecification
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from bellhop.config import Config
from bellhop.dropbox import JobDropbox
from bellhop.engine import Engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Bellhop API...")
    config = app.state.config
    app.state.engine = Engine(db_file=str(config.database_file)).start()
    app.state.dropbox = JobDropbox(app.state.engine, config.dropbox_dir).start()
    yield
    app.state.dropbox.stop()
    app.state.engine.shutdown()
    logger.info("Shutting down Bellhop API...")


app = FastAPI(
    root_path="/bellhop",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


@app.get("/", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/environment")
def get_environment() -> dict[str, str]:
    return {var: os.getenv(var, "") for var in app.state.config.env_vars_to_show}


def get_engine() -> Engine:
    return app.state.engine


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@app.get("/jobs", tags=["Jobs"])
def list_jobs(engine: Annotated[Engine, Depends(get_engine)]) -> list[Job]:
    return engine.db.list_jobs()


@app.post("/jobs", tags=["Jobs"], status_code=201)
def submit_job(job_spec: JobSpecification, engine: Annotated[Engine, Depends(get_engine)]) -> uuid.UUID:
    return engine.submit_job(job_spec)


@app.get("/jobs/{job_id}", tags=["Jobs"])
def get_job(job_id: uuid.UUID, engine: Annotated[Engine, Depends(get_engine)]) -> Job:
    job = engine.db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.put("/jobs/{job_id}", tags=["Jobs"])
def update_job(job_id: uuid.UUID, job: Job, engine: Annotated[Engine, Depends(get_engine)]) -> None:
    if job.id != job_id:
        raise HTTPException(status_code=422, detail="Body job ID must match path job ID")
    try:
        engine.update_job(job)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.delete("/jobs/{job_id}", tags=["Jobs"], status_code=204)
def abort_job(job_id: uuid.UUID, engine: Annotated[Engine, Depends(get_engine)]) -> None:
    try:
        engine.abort_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.post("/jobs/{job_id}/execute-now", tags=["Jobs"], status_code=204)
def execute_now(job_id: uuid.UUID, engine: Annotated[Engine, Depends(get_engine)]) -> None:
    try:
        engine.execute_now(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.post("/jobs/{job_id}/retry", tags=["Jobs"], status_code=204)
def retry_job(job_id: uuid.UUID, engine: Annotated[Engine, Depends(get_engine)]) -> None:
    try:
        engine.retry_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


# ---------------------------------------------------------------------------
# Task executions
# ---------------------------------------------------------------------------


@app.get("/executions/{execution_id}", tags=["Executions"])
def get_execution(execution_id: uuid.UUID, engine: Annotated[Engine, Depends(get_engine)]) -> TaskExecution:
    execution = engine.db.get_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@app.get("/executions/{execution_id}/logs", tags=["Executions"])
async def stream_execution_logs(
    execution_id: uuid.UUID, engine: Annotated[Engine, Depends(get_engine)]
) -> StreamingResponse:
    """Stream live logs for a running task execution as Server-Sent Events."""
    if engine.db.get_execution(execution_id) is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    async def generate():
        sent_length = 0
        while True:
            execution = engine.db.get_execution(execution_id)
            new = execution.logs[sent_length:]
            if new:
                yield f"data: {new}\n\n"
                sent_length += len(new)
            if execution.success is not None:
                yield f"event: done\ndata: {execution.success}\n\n"
                return
            await asyncio.sleep(0.1)

    return StreamingResponse(generate(), media_type="text/event-stream")


def main() -> None:
    app.state.config = Config()
    uvicorn.run(app, host="0.0.0.0", port=app.state.config.api_port)
