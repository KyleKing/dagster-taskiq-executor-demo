from pathlib import Path
from threading import Thread
from unittest import mock

import pytest
from dagster._core.definitions.reconstruct import ReconstructableJob  # noqa: PLC2701
from dagster._core.errors import DagsterSubprocessError  # noqa: PLC2701
from dagster._core.events import DagsterEventType  # noqa: PLC2701
from dagster._core.execution.api import execute_job, execute_run_iterator  # noqa: PLC2701
from dagster._core.instance import DagsterInstance
from dagster._utils import send_interrupt  # noqa: PLC2701

from tests.utils import (
    REPO_FILE,
    events_of_type,
    execute_eagerly_on_taskiq,
    execute_job_on_taskiq,
)


def test_execute_on_taskiq_default(dagster_taskiq_worker):
    with execute_job_on_taskiq("test_job") as result:
        assert result.output_for_node("simple") == 1
        assert len(result.all_node_events) == 4
        assert len(events_of_type(result, "STEP_START")) == 1
        assert len(events_of_type(result, "STEP_OUTPUT")) == 1
        assert len(events_of_type(result, "HANDLED_OUTPUT")) == 1
        assert len(events_of_type(result, "STEP_SUCCESS")) == 1


def test_execute_serial_on_taskiq(dagster_taskiq_worker):
    with execute_job_on_taskiq("test_serial_job") as result:
        assert result.output_for_node("simple") == 1
        assert result.output_for_node("add_one") == 2
        assert len(result.all_node_events) == 10
        assert len(events_of_type(result, "STEP_START")) == 2
        assert len(events_of_type(result, "STEP_INPUT")) == 1
        assert len(events_of_type(result, "STEP_OUTPUT")) == 2
        assert len(events_of_type(result, "HANDLED_OUTPUT")) == 2
        assert len(events_of_type(result, "LOADED_INPUT")) == 1
        assert len(events_of_type(result, "STEP_SUCCESS")) == 2


def test_execute_diamond_job_on_taskiq(dagster_taskiq_worker):
    with execute_job_on_taskiq("test_diamond_job") as result:
        assert result.output_for_node("emit_values", "value_one") == 1
        assert result.output_for_node("emit_values", "value_two") == 2
        assert result.output_for_node("add_one") == 2
        assert result.output_for_node("renamed") == 3
        assert result.output_for_node("subtract") == -1


def test_execute_parallel_job_on_taskiq(dagster_taskiq_worker):
    with execute_job_on_taskiq("test_parallel_job") as result:
        assert len(result.get_step_success_events()) == 11


def test_execute_composite_job_on_taskiq(dagster_taskiq_worker):
    with execute_job_on_taskiq("composite_job") as result:
        assert result.success
        assert len(result.get_step_success_events()) == 16


def test_execute_optional_outputs_job_on_taskiq(dagster_taskiq_worker):
    with execute_job_on_taskiq("test_optional_outputs") as result:
        assert len(result.get_step_success_events()) == 2
        assert len(result.get_step_skipped_events()) == 2


def test_execute_fails_job_on_taskiq(dagster_taskiq_worker):
    with execute_job_on_taskiq("test_fails") as result:
        assert len(result.get_step_failure_events()) == 1
        assert result.is_node_failed("fails")
        assert "Exception: argjhgjh\n" in result.failure_data_for_node("fails").error.cause.message  # pyright: ignore[reportOptionalMemberAccess]
        assert result.is_node_untouched("should_never_execute")


def test_terminate_job_on_taskiq(dagster_taskiq_worker, instance: DagsterInstance, tempdir: str):
    recon_job = ReconstructableJob.for_file(REPO_FILE, "interrupt_job")

    run_config = {
        "resources": {"io_manager": {"config": {"base_dir": tempdir}}},
    }

    results = []
    result_types = []
    interrupt_thread = None

    dagster_run = instance.create_run_for_job(
        job_def=recon_job.get_definition(),
        run_config=run_config,
    )

    for event in execute_run_iterator(
        recon_job,
        dagster_run,
        instance=instance,
    ):
        # Interrupt once the first step starts
        if event.event_type == DagsterEventType.STEP_START and not interrupt_thread:
            interrupt_thread = Thread(target=send_interrupt, args=())
            interrupt_thread.start()

        results.append(event)
        result_types.append(event.event_type)

    interrupt_thread.join()  # type: ignore[union-attr]

    # At least one step succeeded (the one that was running when the interrupt fired)
    assert DagsterEventType.STEP_SUCCESS in result_types

    # Cancellation requests are issued for in-flight tasks; ensure interrupt is logged.
    interrupt_events = [
        result
        for result in results
        if result.event_type == DagsterEventType.ENGINE_EVENT and "termination signal" in result.message
    ]

    assert len(interrupt_events) > 0

    # The overall job failed
    assert DagsterEventType.PIPELINE_FAILURE in result_types


def test_execute_eagerly_on_taskiq(instance: DagsterInstance):
    with execute_eagerly_on_taskiq("test_job", instance=instance) as result:
        assert result.output_for_node("simple") == 1
        assert len(result.all_node_events) == 4
        assert len(events_of_type(result, "STEP_START")) == 1
        assert len(events_of_type(result, "STEP_OUTPUT")) == 1
        assert len(events_of_type(result, "HANDLED_OUTPUT")) == 1
        assert len(events_of_type(result, "STEP_SUCCESS")) == 1

        events = instance.all_logs(result.run_id)
        start_markers = {}
        end_markers = {}
        for event in events:
            dagster_event = event.dagster_event
            if dagster_event and dagster_event.is_engine_event:
                if dagster_event.engine_event_data.marker_start:
                    key = f"{event.step_key}.{dagster_event.engine_event_data.marker_start}"
                    start_markers[key] = event.timestamp
                if dagster_event.engine_event_data.marker_end:
                    key = f"{event.step_key}.{dagster_event.engine_event_data.marker_end}"
                    end_markers[key] = event.timestamp

        seen = set()
        assert set(start_markers.keys()) == set(end_markers.keys())
        for key, end_time in end_markers.items():
            assert end_time - start_markers[key] > 0
            seen.add(key)


def test_execute_eagerly_serial_on_taskiq():
    with execute_eagerly_on_taskiq("test_serial_job") as result:
        assert result.output_for_node("simple") == 1
        assert result.output_for_node("add_one") == 2
        assert len(result.all_node_events) == 10
        assert len(events_of_type(result, "STEP_START")) == 2
        assert len(events_of_type(result, "STEP_INPUT")) == 1
        assert len(events_of_type(result, "STEP_OUTPUT")) == 2
        assert len(events_of_type(result, "HANDLED_OUTPUT")) == 2
        assert len(events_of_type(result, "LOADED_INPUT")) == 1
        assert len(events_of_type(result, "STEP_SUCCESS")) == 2


def test_execute_eagerly_diamond_job_on_taskiq():
    with execute_eagerly_on_taskiq("test_diamond_job") as result:
        assert result.output_for_node("emit_values", "value_one") == 1
        assert result.output_for_node("emit_values", "value_two") == 2
        assert result.output_for_node("add_one") == 2
        assert result.output_for_node("renamed") == 3
        assert result.output_for_node("subtract") == -1


def test_execute_eagerly_diamond_job_subset_on_taskiq():
    with execute_eagerly_on_taskiq("test_diamond_job", subset=["emit_values"]) as result:
        assert result.output_for_node("emit_values", "value_one") == 1
        assert result.output_for_node("emit_values", "value_two") == 2
        assert len(result.get_step_success_events()) == 1


def test_execute_eagerly_parallel_job_on_taskiq():
    with execute_eagerly_on_taskiq("test_parallel_job") as result:
        assert len(result.get_step_success_events()) == 11


def test_execute_eagerly_composite_job_on_taskiq():
    with execute_eagerly_on_taskiq("composite_job") as result:
        assert result.success
        assert len(result.get_step_success_events()) == 16


def test_execute_eagerly_optional_outputs_job_on_taskiq():
    with execute_eagerly_on_taskiq("test_optional_outputs") as result:
        assert len(result.get_step_success_events()) == 2
        assert len(result.get_step_skipped_events()) == 2


def test_execute_eagerly_resources_limit_job_on_taskiq():
    with execute_eagerly_on_taskiq("test_resources_limit") as result:
        assert result.is_node_success("resource_req_op")
        assert result.success


def test_execute_eagerly_fails_job_on_taskiq():
    with execute_eagerly_on_taskiq("test_fails") as result:
        assert len(result.get_step_failure_events()) == 1
        assert result.is_node_failed("fails")
        assert "Exception: argjhgjh\n" in result.failure_data_for_node("fails").error.cause.message  # pyright: ignore[reportOptionalMemberAccess]
        assert result.is_node_untouched("should_never_execute")


def test_execute_eagerly_retries_job_on_taskiq():
    with execute_eagerly_on_taskiq("test_retries") as result:
        assert len(events_of_type(result, "STEP_START")) == 1
        assert len(events_of_type(result, "STEP_UP_FOR_RETRY")) == 1
        assert len(events_of_type(result, "STEP_RESTARTED")) == 1
        assert len(events_of_type(result, "STEP_FAILURE")) == 1


def test_engine_error(instance: DagsterInstance, tempdir: str):
    storage = str(Path(tempdir) / "flakey_storage")
    with (
        mock.patch(
            "dagster._core.execution.context.system.PlanData.raise_on_error",
            return_value=True,
        ),
        pytest.raises(DagsterSubprocessError),
    ):
        execute_job(
            ReconstructableJob.for_file(REPO_FILE, "engine_error"),
            run_config={
                "resources": {"io_manager": {"config": {"base_dir": storage}}},
                "execution": {"config": {"config_source": {"task_always_eager": True}}},
                "ops": {"destroy": {"config": storage}},
            },
            instance=instance,
        )
