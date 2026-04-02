---
icon: lucide/wrench
---

# Playbook Troubleshooting

If a playbook is not showing up or not executing, work through these checks first.

## The Playbook Is Not Listed

Check:

- the file is inside a configured `PLAYBOOK_DIRS` path
- the file name does not start with `_`
- the module imports successfully
- the API was restarted or reloaded after the file was added

## The Playbook Exists but Does Not Run

Check:

- the playbook is enabled
- the trigger type matches the incoming event
- the conditions match the incoming alert payload
- the worker is running and can discover the same playbook code

## The Playbook Runs Old Code

Check:

- the worker was restarted after the playbook changed
- the mounted playbook directory is the one you expect
- there are not multiple copies of the same module in different paths

## The UI and Worker Disagree

This usually points to discovery drift between processes.

The API and worker should both read from the same playbook directory configuration and the same deployed code version.

## Still Stuck?

Use these verification points:

- application startup logs
- worker logs
- `GET /api/v1/playbooks`
- direct inspection of `PLAYBOOK_DIRS`
