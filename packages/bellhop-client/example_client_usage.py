import time

from bellhop_models.specifications import JobSpecification, RunSubprocessParams, SubprocessTask

from bellhop_client import client

print("Health Check: ", client.health_check())

job_spec = JobSpecification(
    name="Test Job",
    tasks=[
        SubprocessTask(
            name="Run script",
            parameters=RunSubprocessParams(program="echo", command=["hello world"]),
        ),
    ],
)
job_id = client.submit_job(job_spec)

time.sleep(1)

completed_job = client.get_job(job_id)
print(completed_job)
