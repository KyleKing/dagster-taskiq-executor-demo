from dagster_taskiq.defaults import (
    task_default_priority,
    task_default_queue,
    worker_max_messages,
    wait_time_seconds,
)

DEFAULT_CONFIG = {
    "task_default_priority": task_default_priority,
    "task_default_queue": task_default_queue,
    "wait_time_seconds": wait_time_seconds,
    "max_number_of_messages": worker_max_messages,
    "worker_max_messages": worker_max_messages,
    "delay_seconds": 0,
    "is_fair_queue": None,
    "use_task_id_for_deduplication": False,
    "extra_options": {},
    "enable_cancellation": True,
}


class dict_wrapper:
    """Wraps a dict to convert `obj['attr']` to `obj.attr`."""

    def __init__(self, dictionary):
        self.__dict__ = dictionary


TASK_EXECUTE_PLAN_NAME = "execute_plan"
TASK_EXECUTE_JOB_NAME = "execute_job"
TASK_RESUME_JOB_NAME = "resume_job"
