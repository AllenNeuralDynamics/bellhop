from collections.abc import Mapping
from typing import Any, Protocol

import requests
from bellhop_models.specifications import (
    DeleteDataParams,
    HTTPRequestParams,
    RunCommandParams,
    RunProgramParams,
    SendMessageParams,
    TaskTypes,
    TransferDataListParams,
    TransferDataParams,
)
from bellhop_trolley.data_transfer import delete_data, transfer_data

from bellhop.message_utils import send_email
from bellhop.subprocess_utils import run_live_process

__all__ = ["task_executor_registry"]


class LogQueue(Protocol):
    """Structural type for anything that accepts log lines via put()."""

    def put(self, item: str) -> None: ...


class TaskExecutorFn(Protocol):
    def __call__(self, params: Any, log_queue: LogQueue) -> None: ...


def _move_data(params: TransferDataParams | TransferDataListParams, log_queue: LogQueue) -> None:
    if isinstance(params, TransferDataParams):
        transfer_data(params.source, params.destination)
    else:
        transfers = params.construct_individual_transfers()
        if params.parallel:
            raise NotImplementedError("Parallel transfer not yet implemented")
        for individual_params in transfers:
            transfer_data(individual_params.source, individual_params.destination)


def _delete_data(params: DeleteDataParams, log_queue: LogQueue) -> None:
    delete_data(path=params.source)


def _send_message(params: SendMessageParams, log_queue: LogQueue) -> None:
    send_email(**params.model_dump())


# def _run_subprocess(params: RunSubprocessParams, log_queue: LogQueue) -> None:
#     run_live_process(params.command, log_queue, params.program)


def _run_command(params: RunCommandParams | RunProgramParams, log_queue: LogQueue) -> None:
    if isinstance(params, RunProgramParams):
        run_live_process([params.program] + params.arguments, log_queue, shell=False, cwd=params.cwd)
    elif isinstance(params, RunCommandParams):
        if isinstance(params.command, list):
            for cmd in params.command:
                run_live_process(cmd, log_queue, shell=True, cwd=params.cwd)
        else:
            run_live_process(params.command, log_queue, shell=True, cwd=params.cwd)


def _http_request(params: HTTPRequestParams, log_queue: LogQueue) -> None:
    response = requests.request(method=params.method, url=params.url, headers=params.headers, json=params.data)
    response.raise_for_status()


### Task Executor Registry

task_executor_registry: Mapping[TaskTypes, TaskExecutorFn] = {
    "Move Data": _move_data,
    "Delete Data": _delete_data,
    "Send Message": _send_message,
    # "Subprocess": _run_subprocess,
    "Command": _run_command,
    "HTTP Request": _http_request,
}
