import threading
import time

import pytest

from dagster._core.test_utils import instance_for_test
from dagster_taskiq.make_app import make_app

from tests.utils import execute_on_thread, start_taskiq_worker


def test_multiqueue(localstack):
    with instance_for_test() as instance:
        done = threading.Event()
        with start_taskiq_worker():
            execute_thread = threading.Thread(
                target=execute_on_thread,
                args=("multiqueue_job", done, instance.get_ref()),
                daemon=True,
            )
            execute_thread.start()
            time.sleep(1)
            assert not done.is_set()
            with start_taskiq_worker(queue="fooqueue"):
                execute_thread.join()
                assert done.is_set()


@pytest.mark.parametrize(
    ('queue_url', 'override', 'expected', 'expect_warning'),
    [
        ('https://sqs.us-east-1.amazonaws.com/123/example.fifo', None, True, False),
        ('https://sqs.us-east-1.amazonaws.com/123/example', None, False, False),
        ('https://sqs.us-east-1.amazonaws.com/123/example', True, False, True),
        ('https://sqs.us-east-1.amazonaws.com/123/example.fifo', False, False, False),
        ('https://sqs.us-east-1.amazonaws.com/123/example.fifo', True, True, False),
    ],
)
def test_make_app_fair_queue_detection(
    queue_url: str, override: bool | None, expected: bool, expect_warning: bool, monkeypatch
) -> None:
    recorded = {}

    def _capture_broker(self, *, result_backend=None):
        recorded['is_fair_queue'] = self.is_fair_queue

        class _DummyBroker:
            async def startup(self):
                return None

            async def shutdown(self):
                return None

        return _DummyBroker()

    monkeypatch.setattr('dagster_taskiq.broker.SqsBrokerConfig.create_broker', _capture_broker)

    config = {'queue_url': queue_url}
    if override is not None:
        config['config_source'] = {'is_fair_queue': override}

    if expect_warning:
        with pytest.warns(UserWarning):
            make_app(config)
    else:
        make_app(config)

    assert recorded['is_fair_queue'] is expected
