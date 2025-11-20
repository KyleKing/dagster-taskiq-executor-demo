import asyncio
import os

import pytest
from taskiq.result import TaskiqResult
from taskiq_aio_sqs import S3Backend

from dagster_taskiq.make_app import make_app


@pytest.mark.parametrize(
    ("queue_url", "override", "expected", "expect_warning"),
    [
        ("https://sqs.us-east-1.amazonaws.com/123/example.fifo", None, True, False),
        ("https://sqs.us-east-1.amazonaws.com/123/example", None, False, False),
        ("https://sqs.us-east-1.amazonaws.com/123/example", True, False, True),
        ("https://sqs.us-east-1.amazonaws.com/123/example.fifo", False, False, False),
        ("https://sqs.us-east-1.amazonaws.com/123/example.fifo", True, True, False),
    ],
)
def test_make_app_fair_queue_detection(
    queue_url: str,
    override: bool | None,  # noqa: FBT001
    expected: bool,  # noqa: FBT001
    expect_warning: bool,  # noqa: FBT001
    monkeypatch,
) -> None:
    recorded = {}

    def _capture_broker(self, *, result_backend=None):
        recorded["is_fair_queue"] = self.is_fair_queue

        class _DummyBroker:
            @staticmethod
            async def startup() -> None:
                return None

            @staticmethod
            async def shutdown() -> None:
                return None

        return _DummyBroker()

    monkeypatch.setattr("dagster_taskiq.broker.SqsBrokerConfig.create_broker", _capture_broker)

    config = {"queue_url": queue_url}
    if override is not None:
        config["config_source"] = {"is_fair_queue": override}

    if expect_warning:
        with pytest.warns(UserWarning, match=".*"):
            make_app(config)
    else:
        make_app(config)

    assert recorded["is_fair_queue"] is expected


def test_s3_extended_payload_smoke(localstack):
    async def _exercise() -> None:
        backend = S3Backend(
            bucket_name=os.environ["DAGSTER_TASKIQ_S3_BUCKET_NAME"],
            endpoint_url=os.environ["DAGSTER_TASKIQ_S3_ENDPOINT_URL"],
            region_name="us-east-1",
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        await backend.startup()

        payload = "x" * (256 * 1024 + 2048)
        task_id = "s3-extended-payload-smoke"

        result = TaskiqResult(
            is_err=False,
            return_value=payload,
            execution_time=0.0,
            log=None,
        )

        try:
            await backend.set_result(task_id, result)
            stored = await backend.get_result(task_id)
            assert stored.return_value == payload
        finally:
            await backend.shutdown()

    asyncio.run(_exercise())
