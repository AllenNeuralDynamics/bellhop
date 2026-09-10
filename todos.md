Self tests and demos
- automated test
- showcase with demo data, lots of jobs in a temp db
- Demo with intentionally failing job, prompt user to go use the web UI to update the job and rerun it

UI
- Submit new job
- Job writer form (autofill fields and stuff)
- Edit task/job and send update to engine
- Show job/task history, maybe integrated with execution history
- Filter table
- paginate table
- Run self test/demo from ui
- view/edit config?
- Not sure the auto-refresh is the best UX yet, may need to revisit
- Maybe separate job detail component from job table in code, like different file
- More visual separation between job table and detail
- Clicking on task badge in table row should open task detail
- Currently selected task should more clearly visually align with task detail

DB
- handle/normalize timezones
- Handle editing jobs/tasks, keeping track of history, probably with history table
  - Also task executions should keep track of the task params they ran with - maybe instead of linking to task, it contains an immutable field of the task data
- Pagination? need to see how it handles lots of jobs going back years
- DB archive or something, possibly transfer db data from multiple computers into one central db so someone can control/view multiple rigs
- User editable notes for TaskExecutions, e.g. to make notes on why something failed or interpret the error message
- Rename TaskExecution logs to outputs

Tasks:
- Fully test data transfer functions and make really solid and clean
- Integrate good outputs from each task executor so task executions are verbose
- Maybe clean up engine.py, it's somewhat hard to understand looking at it fresh

General:
- Job/task templates
  - For a dataset of type X, the job will always do the same set of tasks but small things will differ.
  - For instance, "transfer data from C://data/{{ barcode }}/data.tif to s3://{{ bucket }}/data/{{ barcode }}.tif"
  - Templates should be saveable/updateable per bellhop instance, and jobs can be submitted by referencing the template and providing the necessary kwargs to fill it in
- Integrate apprise for notifications
- Rename dropbox to mailbox

Docs:
- Update docs and diagrams with new terminology
- Make docs and examples for each package (especially bellhop-trolley)

Workflow:
- Commit all as prototype
- Stacked PR with each component/feature