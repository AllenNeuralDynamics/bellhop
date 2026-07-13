# Bellhop Models

This package contains pydantic models used by bellhop for specifying jobs/tasks and for tracking them once ingested into the bellhop engine and database.

The main usage pattern is like this:

```python
from bellhop_models.database import Job
from bellhop_models_specifications import JobSpecification, TransferDataTask, TransferDataParams
job = JobSpecification(
    name="My Pipeline",
    tasks=[
        TransferDataTask(
            name="Copy file",
            parameters=TransferDataParams(source="/tmp/result", destination="/archive"),
        ),
        HTTPRequestTask(
            name="Notify tracking service",
            parameters=HTTPRequestParams(url="my-tracking-service/api/", method="POST", data={"action", "experiment_complete"})
        )
    ]
)

# Use bellhop client to submit and monitor job (separate from this models package)
from bellhop_client import bellhop_client

submitted_job: Job = bellhop_client.submit_job(job)

# wait for job to run
time.sleep(5)

updated_job: Job = bellhop_client.get_job_status(submitted_job.id)
print(updated_job.history) # list task execution history
```
