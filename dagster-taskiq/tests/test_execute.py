from typing import Any

from dagster._core.instance import DagsterInstance

from tests.utils import (
    events_of_type,
    execute_eagerly_on_taskiq,
    execute_job_on_taskiq,
)


def test_execute_on_taskiq_default(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_job") as result:
        assert result.output_for_node("simple") == 1
        assert len(result.all_node_events) == 4
        assert len(events_of_type(result, "STEP_START")) == 1
        assert len(events_of_type(result, "STEP_OUTPUT")) == 1
        assert len(events_of_type(result, "HANDLED_OUTPUT")) == 1
        assert len(events_of_type(result, "STEP_SUCCESS")) == 1


def test_execute_serial_on_taskiq(aws_mock: str) -> None:
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


def test_execute_diamond_job_on_taskiq(dagster_taskiq_worker: Any) -> None:
    with execute_job_on_taskiq("test_diamond_job") as result:
        assert result.output_for_node("emit_values", "value_one") == 1
        assert result.output_for_node("emit_values", "value_two") == 2
        assert result.output_for_node("add_one") == 2
        assert result.output_for_node("renamed") == 3
        assert result.output_for_node("subtract") == -1


def test_execute_composite_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("composite_job") as result:
        assert result.success
        assert len(result.get_step_success_events()) == 16


def test_execute_optional_outputs_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_optional_outputs") as result:
        assert len(result.get_step_success_events()) == 2
        assert len(result.get_step_skipped_events()) == 2


def test_execute_fails_job_on_taskiq(dagster_taskiq_worker: Any) -> None:
    with execute_job_on_taskiq("test_fails") as result:
        assert len(result.get_step_failure_events()) == 1
        assert result.is_node_failed("fails")
        assert "TestFailureError: argjhgjh\n" in result.failure_data_for_node("fails").error.cause.message  # pyright: ignore[reportOptionalMemberAccess]
        assert result.is_node_untouched("should_never_execute")


def test_execute_eagerly_on_taskiq(aws_mock: str, instance: DagsterInstance) -> None:
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


def test_execute_eagerly_serial_on_taskiq(aws_mock: str) -> None:
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


def test_execute_eagerly_diamond_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_diamond_job") as result:
        assert result.output_for_node("emit_values", "value_one") == 1
        assert result.output_for_node("emit_values", "value_two") == 2
        assert result.output_for_node("add_one") == 2
        assert result.output_for_node("renamed") == 3
        assert result.output_for_node("subtract") == -1


def test_execute_eagerly_diamond_job_subset_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_diamond_job", subset=["emit_values"]) as result:
        assert result.output_for_node("emit_values", "value_one") == 1
        assert result.output_for_node("emit_values", "value_two") == 2
        assert len(result.get_step_success_events()) == 1


def test_execute_eagerly_parallel_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_parallel_job") as result:
        assert len(result.get_step_success_events()) == 11


def test_execute_eagerly_composite_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("composite_job") as result:
        assert result.success
        assert len(result.get_step_success_events()) == 16


def test_execute_eagerly_optional_outputs_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_optional_outputs") as result:
        assert len(result.get_step_success_events()) == 2
        assert len(result.get_step_skipped_events()) == 2


def test_execute_eagerly_resources_limit_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_resources_limit") as result:
        assert result.is_node_success("resource_req_op")
        assert result.success


def test_execute_eagerly_fails_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_fails") as result:
        assert len(result.get_step_failure_events()) == 1
        assert result.is_node_failed("fails")
        assert "TestFailureError: argjhgjh\n" in result.failure_data_for_node("fails").error.cause.message  # pyright: ignore[reportOptionalMemberAccess]
        assert result.is_node_untouched("should_never_execute")


def test_execute_eagerly_retries_job_on_taskiq(aws_mock: str) -> None:
    with execute_eagerly_on_taskiq("test_retries") as result:
        assert len(events_of_type(result, "STEP_START")) == 1
        assert len(events_of_type(result, "STEP_UP_FOR_RETRY")) == 1
        assert len(events_of_type(result, "STEP_RESTARTED")) == 1
        assert len(events_of_type(result, "STEP_FAILURE")) == 1
