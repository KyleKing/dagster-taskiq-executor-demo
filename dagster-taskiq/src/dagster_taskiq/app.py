"""Taskiq application broker instance.

The taskiq worker points to a broker instance (via the broker path argument).
This file exists to be a target for that argument.

Examples:
  - See `worker_start_command` in dagster_taskiq.cli
  - Taskiq worker CLI: taskiq worker dagster_taskiq.app:broker
"""

import asyncio

from dagster_taskiq.make_app import make_app
from dagster_taskiq.tasks import create_execute_job_task, create_resume_job_task, create_task

broker = make_app()

# Start the broker and result backend
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    loop.run_until_complete(broker.startup())
    if hasattr(broker, "result_backend") and broker.result_backend:
        loop.run_until_complete(broker.result_backend.startup())
finally:
    loop.close()

execute_plan = create_task(broker)

execute_job = create_execute_job_task(broker)

resume_job = create_resume_job_task(broker)
