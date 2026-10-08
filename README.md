# Bellhop

Bellhop is a system designed to manage the transfer of scientific data from experimental computing environments once acquisition is complete. 

See [architecture docs](docs/architecture.md)

## Usage

Install bellhop on your lab computer on which you're collecting data, and it will run as a service in the background. For each dataset, submit a **Job** detailing the steps to deal with the data (for instance, 1. transfer data to the cloud, 2. notify your LIMS, 3. send an email, 4. delete data off the instrument). This job will get executed by bellhop at the scheduled time. You can open the bellhop UI or query the API to see progress and past/upcoming jobs. 

If there are any errors during the handoff process (like maybe the LIMS handshake goes awry), the job can be tweaked and retried, and it will execute the rest of the job from the failed task.

## Features


## Demo

