"""Configuration utilities for dagster-taskiq.

This module provides default configuration values and utilities for
configuring Taskiq executors and workers.
"""

from typing import Any

from dagster_taskiq.defaults import (
    wait_time_seconds,
    worker_max_messages,
)

DEFAULT_CONFIG = {
    "wait_time_seconds": wait_time_seconds,
    "max_number_of_messages": worker_max_messages,
    "worker_max_messages": worker_max_messages,
    "delay_seconds": 0,
    "is_fair_queue": None,
    "use_task_id_for_deduplication": False,
    "extra_options": {},
    "enable_cancellation": True,
}


class DictWrapper:
    """Wraps a dict to convert `obj['attr']` to `obj.attr`."""

    def __init__(self, dictionary: dict[str, Any]) -> None:
        """Initialize the dictionary wrapper.

        Args:
            dictionary: Dictionary to wrap
        """
        self.__dict__ = dictionary


TASK_EXECUTE_PLAN_NAME = "execute_plan"
TASK_EXECUTE_JOB_NAME = "execute_job"
TASK_RESUME_JOB_NAME = "resume_job"
