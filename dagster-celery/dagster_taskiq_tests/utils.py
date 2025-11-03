import os
import signal
import subprocess
import tempfile
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, Optional

from dagster._core.definitions.reconstruct import ReconstructableJob
from dagster._core.events import DagsterEvent
from dagster._core.execution.api import execute_job
from dagster._core.execution.execution_result import ExecutionResult
from dagster._core.instance import DagsterInstance
from dagster._core.instance.ref import InstanceRef
from dagster._core.test_utils import instance_for_test

BUILDKITE = os.getenv("BUILDKITE")


REPO_FILE = os.path.join(os.path.dirname(__file__), "repo.py")


@contextmanager
def tempdir_wrapper(tempdir: Optional[str] = None) -> Iterator[str]:
    if tempdir:
        yield tempdir
    else:
        with tempfile.TemporaryDirectory() as t:
            yield t


@contextmanager
def _instance_wrapper(instance: Optional[DagsterInstance]) -> Iterator[DagsterInstance]:
    if instance:
        yield instance
    else:
        with instance_for_test() as instance:
            yield instance


@contextmanager
def execute_job_on_taskiq(
    job_name: str,
    instance: Optional[DagsterInstance] = None,
    run_config: Optional[Mapping[str, Any]] = None,
    tempdir: Optional[str] = None,
    tags: Optional[Mapping[str, str]] = None,
    subset: Optional[Sequence[str]] = None,
) -> Iterator[ExecutionResult]:
    with tempdir_wrapper(tempdir) as tempdir:
        job_def = ReconstructableJob.for_file(REPO_FILE, job_name).get_subset(op_selection=subset)
        with _instance_wrapper(instance) as wrapped_instance:
            run_config = run_config or {
                "resources": {"io_manager": {"config": {"base_dir": tempdir}}},
                # "execution": {"taskiq": {}},
            }
            with execute_job(
                job_def,
                run_config=run_config,
                instance=wrapped_instance,
                tags=tags,
            ) as result:
                yield result


@contextmanager
def execute_eagerly_on_taskiq(
    job_name: str,
    instance: Optional[DagsterInstance] = None,
    tempdir: Optional[str] = None,
    tags: Optional[Mapping[str, str]] = None,
    subset: Optional[Sequence[str]] = None,
) -> Iterator[ExecutionResult]:
    with tempfile.TemporaryDirectory() as tempdir:
        run_config = {
            "resources": {"io_manager": {"config": {"base_dir": tempdir}}},
            "execution": {"config": {"config_source": {"task_always_eager": True}}},
        }

        with execute_job_on_taskiq(
            job_name,
            instance=instance,
            run_config=run_config,
            tempdir=tempdir,
            tags=tags,
            subset=subset,
        ) as result:
            yield result


def execute_on_thread(
    job_name: str,
    done: threading.Event,
    instance_ref: InstanceRef,
    tempdir: Optional[str] = None,
    tags: Optional[Mapping[str, str]] = None,
) -> None:
    with DagsterInstance.from_ref(instance_ref) as instance:
        with execute_job_on_taskiq(job_name, tempdir=tempdir, tags=tags, instance=instance):
            done.set()


@contextmanager
def start_taskiq_worker(queue: Optional[str] = None) -> Iterator[None]:
    # Start a Taskiq worker using the dagster-taskiq CLI
    cmd = ["dagster-taskiq", "worker", "start"]
    if queue:
        # Note: Taskiq doesn't have queue filtering like Celery
        # We'll just start a regular worker
        pass

    process = subprocess.Popen(cmd)

    # Give the worker a moment to start
    import time
    time.sleep(2)

    try:
        yield
    finally:
        # Send interrupt signal to stop the worker
        os.kill(process.pid, signal.SIGINT)
        process.wait(timeout=10)


def events_of_type(result: ExecutionResult, event_type: str) -> Sequence[DagsterEvent]:
    return [event for event in result.all_events if event.event_type_value == event_type]

