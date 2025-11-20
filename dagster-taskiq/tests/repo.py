import time

from dagster import Int, Output, RetryRequested, job
from dagster._core.definitions.decorators import op
from dagster._core.definitions.output import Out
from dagster._core.test_utils import nesting_graph

from dagster_taskiq import taskiq_executor

# test_execute jobs


@op
def simple(_):
    return 1


@op
def add_one(_, num):
    return num + 1


@job(executor_def=taskiq_executor)
def test_job():
    simple()


@job(executor_def=taskiq_executor)
def test_serial_job():
    add_one(simple())


@op(out={"value_one": Out(), "value_two": Out()})
def emit_values(_context):
    yield Output(1, "value_one")
    yield Output(2, "value_two")


@op
def subtract(num_one, num_two):
    return num_one - num_two


@job(executor_def=taskiq_executor)
def test_diamond_job():
    value_one, value_two = emit_values()
    subtract(num_one=add_one(num=value_one), num_two=add_one.alias("renamed")(num=value_two))


@job(executor_def=taskiq_executor)
def test_parallel_job():
    value = simple()
    for i in range(10):
        add_one.alias("add_one_" + str(i))(value)


COMPOSITE_DEPTH = 3


def composite_job():
    return nesting_graph(COMPOSITE_DEPTH, 2).to_job(executor_def=taskiq_executor)


@op(
    out={
        "out_1": Out(Int, is_required=False),
        "out_2": Out(Int, is_required=False),
        "out_3": Out(Int, is_required=False),
    }
)
def foo(_):
    yield Output(1, "out_1")


@op
def bar(_, input_arg):
    return input_arg


@job(executor_def=taskiq_executor)
def test_optional_outputs():
    foo_res = foo()
    bar.alias("first_consumer")(input_arg=foo_res.out_1)
    bar.alias("second_consumer")(input_arg=foo_res.out_2)
    bar.alias("third_consumer")(input_arg=foo_res.out_3)


class TestFailureError(Exception):
    """Custom exception for test failures."""


@op
def fails():
    raise TestFailureError("argjhgjh")


@op
def should_never_execute(foo):
    raise AssertionError  # should never execute


@job(executor_def=taskiq_executor)
def test_fails():
    should_never_execute(fails())


@op
def retry_request():
    raise RetryRequested


@job(executor_def=taskiq_executor)
def test_retries():
    retry_request()


@op(config_schema=str)
def destroy(context, x):
    raise ValueError


@job(executor_def=taskiq_executor)
def engine_error():
    a = simple()
    b = destroy(a)

    subtract(a, b)


@op(
    tags={
        "dagster-k8s/resource_requirements": {
            "requests": {"cpu": "250m", "memory": "64Mi"},
            "limits": {"cpu": "500m", "memory": "2560Mi"},
        }
    }
)
def resource_req_op(context):
    context.log.info("running")


@job(executor_def=taskiq_executor)
def test_resources_limit():
    resource_req_op()


@op
def sleep_op(_):
    time.sleep(0.5)
    return True


@job(executor_def=taskiq_executor)
def interrupt_job():
    for i in range(50):
        sleep_op.alias("sleep_" + str(i))()


@op
def bar_solid():
    return "bar"
