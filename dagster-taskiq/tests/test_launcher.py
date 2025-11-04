import logging
import os
import time
from collections.abc import Iterator, Mapping
from typing import Any

import pytest
from dagster import DagsterInstance, DagsterRunStatus, file_relative_path, instance_for_test
from dagster._core.workspace.context import WorkspaceProcessContext, WorkspaceRequestContext  # noqa: PLC2701
from dagster._core.workspace.load_target import PythonFileTarget  # noqa: PLC2701
from dagster._daemon import execute_run_monitoring_iteration  # noqa: PLC2701
from dagster_shared import seven

from dagster_taskiq.defaults import sqs_queue_url
from tests.repo_runner import crashy_job, exity_job, noop_job, sleepy_job
from tests.utils import start_taskiq_worker
from tests.utils_launcher import poll_for_finished_run, poll_for_step_start


@pytest.fixture
def instance(tempdir):
    with instance_for_test(
        temp_dir=tempdir,
        overrides={
            "run_launcher": {
                "module": "dagster_taskiq.launcher",
                "class": "TaskiqRunLauncher",
                "config": {
                    "queue_url": sqs_queue_url,
                    "endpoint_url": os.getenv("DAGSTER_TASKIQ_SQS_ENDPOINT_URL"),
                    "region_name": "us-east-1",
                    "default_queue": "custom-queue",
                },
            },
            "run_monitoring": {
                "enabled": True,
                "start_timeout_seconds": 8,
                "cancel_timeout_seconds": 8,
                "poll_interval_seconds": 4,
            },
        },
    ) as test_instance:
        yield test_instance


@pytest.fixture
def workspace_process_context(instance) -> Iterator[WorkspaceProcessContext]:
    with WorkspaceProcessContext(
        instance,
        PythonFileTarget(
            python_file=file_relative_path(__file__, "repo_runner.py"),
            attribute="taskiq_test_repository",
            working_directory=None,
            location_name="test",
        ),
    ) as workspace_process_context:
        yield workspace_process_context


@pytest.fixture
def workspace(instance, workspace_process_context: WorkspaceProcessContext) -> Iterator[WorkspaceRequestContext]:
    return workspace_process_context.create_request_context()


@pytest.fixture
def dagster_taskiq_worker(localstack, instance: DagsterInstance) -> Iterator[None]:
    with start_taskiq_worker(queue="custom-queue"):
        yield


def run_configs():
    return [
        {"execution": {"config": {"in_process": {}}}},
    ]


@pytest.mark.parametrize(
    "run_config",
    run_configs(),
)
def test_successful_run(
    dagster_taskiq_worker,
    instance: DagsterInstance,
    workspace: WorkspaceRequestContext,
    run_config,
):
    remote_job = workspace.get_code_location("test").get_repository("taskiq_test_repository").get_full_job("noop_job")

    dagster_run = instance.create_run_for_job(
        job_def=noop_job,
        run_config=run_config,
        remote_job_origin=remote_job.get_remote_origin(),
        job_code_origin=remote_job.get_python_origin(),
    )
    run_id = dagster_run.run_id

    run = instance.get_run_by_id(run_id)
    assert run
    assert run.status == DagsterRunStatus.NOT_STARTED

    instance.launch_run(run_id=dagster_run.run_id, workspace=workspace)

    dagster_run = instance.get_run_by_id(run_id)
    assert dagster_run
    assert dagster_run.run_id == run_id

    dagster_run = poll_for_finished_run(instance, run_id)
    assert dagster_run.status == DagsterRunStatus.SUCCESS


@pytest.mark.parametrize(
    "run_config",
    run_configs(),
)
@pytest.mark.skipif(
    seven.IS_WINDOWS,
    reason="Crashy jobs leave resources open on windows, causing filesystem contention",
)
def test_crashy_run(
    dagster_taskiq_worker,
    instance: DagsterInstance,
    workspace: WorkspaceRequestContext,
    workspace_process_context: WorkspaceProcessContext,
    run_config: Mapping[str, Any],
):
    logger = logging.getLogger()

    remote_job = workspace.get_code_location("test").get_repository("taskiq_test_repository").get_full_job("crashy_job")

    run = instance.create_run_for_job(
        job_def=crashy_job,
        run_config=run_config,
        remote_job_origin=remote_job.get_remote_origin(),
        job_code_origin=remote_job.get_python_origin(),
    )

    run_id = run.run_id

    run = instance.get_run_by_id(run_id)
    assert run
    assert run.status == DagsterRunStatus.NOT_STARTED

    instance.launch_run(run.run_id, workspace)

    failed_run = instance.get_run_by_id(run_id)

    assert failed_run
    assert failed_run.run_id == run_id

    poll_for_step_start(instance, run_id, timeout=5)
    time.sleep(5)
    # Monitoring reads failed status from taskiq backend
    list(execute_run_monitoring_iteration(workspace_process_context, logger))

    failed_run = poll_for_finished_run(instance, run_id, timeout=10)
    assert failed_run.status == DagsterRunStatus.FAILURE


@pytest.mark.parametrize("run_config", run_configs())
@pytest.mark.skipif(
    seven.IS_WINDOWS,
    reason="Crashy jobs leave resources open on windows, causing filesystem contention",
)
def test_exity_run(
    dagster_taskiq_worker,
    instance: DagsterInstance,
    workspace: WorkspaceRequestContext,
    run_config: Mapping[str, Any],
):
    remote_job = workspace.get_code_location("test").get_repository("taskiq_test_repository").get_full_job("exity_job")

    run = instance.create_run_for_job(
        job_def=exity_job,
        run_config=run_config,
        remote_job_origin=remote_job.get_remote_origin(),
        job_code_origin=remote_job.get_python_origin(),
    )

    run_id = run.run_id

    run = instance.get_run_by_id(run_id)
    assert run
    assert run.status == DagsterRunStatus.NOT_STARTED

    instance.launch_run(run.run_id, workspace)

    failed_run = instance.get_run_by_id(run_id)

    assert failed_run
    assert failed_run.run_id == run_id

    poll_for_step_start(instance, run_id, timeout=5)
    time.sleep(5)

    failed_run = poll_for_finished_run(instance, run_id, timeout=5)
    assert failed_run.status == DagsterRunStatus.FAILURE

    event_records = instance.all_logs(run_id)

    assert _message_exists(event_records, 'Execution of step "exity_op" failed.')
    assert _message_exists(
        event_records,
        "Execution of run for \"exity_job\" failed. Steps failed: ['exity_op']",
    )


@pytest.mark.parametrize(
    "run_config",
    run_configs(),
)
def test_terminated_run(
    dagster_taskiq_worker,
    instance: DagsterInstance,
    workspace: WorkspaceRequestContext,
    run_config: Mapping[str, Any],
):
    remote_job = workspace.get_code_location("test").get_repository("taskiq_test_repository").get_full_job("sleepy_job")
    run = instance.create_run_for_job(
        job_def=sleepy_job,
        run_config=run_config,
        remote_job_origin=remote_job.get_remote_origin(),
        job_code_origin=remote_job.get_python_origin(),
    )

    run_id = run.run_id

    run = instance.get_run_by_id(run_id)
    assert run
    assert run.status == DagsterRunStatus.NOT_STARTED

    instance.launch_run(run.run_id, workspace)

    poll_for_step_start(instance, run_id)

    launcher = instance.run_launcher
    assert launcher.terminate(run_id)

    terminated_run = poll_for_finished_run(instance, run_id, timeout=30)
    assert terminated_run
    assert terminated_run.status == DagsterRunStatus.FAILURE

    event_records = list(instance.all_logs(run_id))
    assert _message_exists(event_records, "Requested Taskiq task cancellation."), (
        "Expected cancellation event to be logged for terminated run"
    )


def _message_exists(event_records, message_text):
    return any(message_text in event_record.message for event_record in event_records)
