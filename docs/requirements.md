# Bellhop

General purpose distributed data management tool, enabling and encouraging reliable and observable protocols for post-acquisition data upload and tracking

Like lims_scheduler and aind-watchdog-service, but decouples the backend utilities from the platform-specific procedures.

## Design

- Task execution engine 
  - Runs as a service
  - Executes tasks passed via messaging layer or manifest files
  - Tracks task execution with moving manifest files a la lims_scheduler
  - Simple domain-specific-language for specifying manifests with control flow
    - If a task fails, options to log warning and continue, stop manifest execution, or maybe do a special task
  - Publishes status channel so apps can monitor Bellhop processes
- A collection of plugin tasks with unified observability
  - Builtin Tasks
    - Arbitrary file copy (shutil/robocopy/rsync/s3/googlecloud)
      - Matched protocols, chooses backend based on src/dest or config
    - HTTP requests
    - File deletion
    - Run subprocesses (choose from a configured list)
  - Simple plugin pattern for adding options (somewhat parallel to just calling exes)
  - All tasks log the same - enable easy monitoring of data movement and distributed processing
- Interaction
  - CLI
    - Start/stop service
    - Run self-tests
    - Execute tasks (e.g. `bellhop copy --source path/to/file --destination path/to/file`)
  - Importable python library to create manifests for scheduling or to run tasks "manually"
    - `import bellhop`
    - `bellhop.copy(source=Path(...), destination=S3Path(...))`
    - Python functions would message to the service engine which would execute the tasks

## Use Cases

### Potential Task Sequences

- AIND SciComp Protocol
  - Copy data files to VAST
  - Copy schematized metadata files to VAST
  - Post to http data-transfer-service endpoint

- VS200
  - Copy files to AWS
  - Copy files to Isilon
  - Write Trigger file on Isilon
  - Run subprocess or plugin to register data in DATS
  - Run subprocess or plugin to update PTS Process to indicate completion
  - If all successful, move src files to "handed off" folder

- Merscope
  - Run a processing step on source files (local plugin/exe)
  - Upload to AWS
  - Register with DATS
  - Update PTS Process to indicate completion
  - Delete source files if previous successful

- Deletion
  - Check criteria
    - files older than x
    - Checksum match to cloud files
    - Confirmation that downstream processes completed successfully
    - Check a database (docDB or DATS) for session existence
  - Delete local files

- Recurring tasks
  - schedule local_delete every x days

  - sw_update_checker (maybe this is better in ESM)

- Recoverable failures
  - Sequence:
    - Upload data
    - Update database (could fail)
    - Delete data (not if upload failed, but database post ok to fail)
  - Failed database upload can be easily retried later or on another machine

### CLI
```
> bellhop status

    Currently processing manifest "12345" - task "Upload to AWS"
    3 manifests waiting

> bellhop process-manifest path/to/manifest

    Copying manifest file to internal tracking directory
    Processing manifest ...
    ...
    Manifest completed ...

> bellhop execute-task copy --source path/to/file --destination path/to/destination

    ...
```

### Python Usage
```python
import bellhop

# Execute a task immediately, via messaging to the execution engine
#   Identical logs from the engine as if executed via manifest
bellhop.copy(source=Path(...), destination=Path(...))

# Create manifest for scheduled execution
manifest = bellhop.Manifest(name="12345", schedule_time=...)
manifest.add_task(bellhop.tasks.Copy(source=Path(...), destination=Path(...)))
manifest.add_task(bellhop.tasks.Subprocess(process=Path("something.exe"), args=[...]))
manifest.write()
```

### Plugins
```python
import bellhop

# Create plugin class, overriding required methods
class MyPlugin(bellhop.PluginBase):
    def execute(self,...): ...
    
# Register with bellhop - not quite sure how this works yet...
bellhop.register_plugin(MyPlugin) # magic occurs here
```

## Maintainability

- Execution engine doesn't care about tasks, will update rarely
- Separate/individual versioning/deployment for plugins, cli, python bindings
- Builtin task utilities can be updated and deployed without requiring changes to user software

