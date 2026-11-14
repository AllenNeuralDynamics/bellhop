# Bellhop

Bellhop is a system designed to manage the transfer of scientific data from experimental computing environments once acquisition is complete. 

See [architecture docs](docs/architecture.md)

## Installation

Run the following in an elevated (**Administrator**) terminal on Windows to install the latest release to `C:\Program Files\AllenInstitute\bellhop`:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://github.com/AllenNeuralDynamics/bellhop/releases/latest/download/install_bellhop.ps1 | iex"
```

To install a specific version (including pre-releases) or customize the target directory with `-InstallDir`, pass parameters to the script:

```powershell
powershell -ExecutionPolicy ByPass -c "& ([scriptblock]::Create((irm https://github.com/AllenNeuralDynamics/bellhop/releases/download/v0.1.0.dev1/install_bellhop.ps1))) -Version v0.1.0.dev1"
```

> [!NOTE]
> GitHub's `/releases/latest/download/` URL only resolves once a stable (non-prerelease) release exists. While only pre-releases are published, use `/releases/download/<tag>/install_bellhop.ps1` instead.

Once installed, run Bellhop with:

```powershell
& "C:\Program Files\AllenInstitute\bellhop\bellhop.exe"
```

## Usage

Install bellhop on your lab computer on which you're collecting data, and it will run as a service in the background. For each dataset, submit a **Job** detailing the steps to deal with the data (for instance, 1. transfer data to the cloud, 2. notify your LIMS, 3. send an email, 4. delete data off the instrument). This job will get executed by bellhop at the scheduled time. You can open the bellhop UI or query the API to see progress and past/upcoming jobs. 

If there are any errors during the handoff process (like maybe the LIMS handshake goes awry), the job can be tweaked and retried, and it will execute the rest of the job from the failed task.

## Features



## Demo

## Contributing

### Building from source
Bellhop uses pyinstaller to bundle itself as a portable executable.

Run `just build` to compile and build this, and `just test_exe` for a simple build test or `just run_exe` to run the compiled result.