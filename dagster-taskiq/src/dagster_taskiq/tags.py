"""Tag constants for dagster-taskiq.

This module defines tag keys used to configure Taskiq executor behavior
for Dagster runs and steps.
"""

# Used to set the taskiq task_id for run monitoring
DAGSTER_TASKIQ_TASK_ID_TAG = "dagster-taskiq/task_id"
