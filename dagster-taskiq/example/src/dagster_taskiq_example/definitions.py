import random
import time

from dagster import (
    AssetExecutionContext,
    Definitions,
    asset,
    define_asset_job,
    job,
    op,
)
from dagster._core.definitions.partitions.definition import StaticPartitionsDefinition  # noqa: PLC2701
from dagster_taskiq import taskiq_executor

example_partition_def = StaticPartitionsDefinition(
    partition_keys=[str(i) for i in range(1, 32)],
)


@asset(
    partitions_def=example_partition_def,
)
def partitioned_asset(context: AssetExecutionContext) -> None:
    """This asset is partitioned."""
    context.log.info("Preparing to greet the world!")
    time.sleep(10)
    context.log.info("Hello world!!")


partitioned_job_long = define_asset_job(
    name="partitioned_job_long",
    partitions_def=example_partition_def,
    selection=[partitioned_asset],
)


@op
def start() -> int:
    """This op returns a simple value.

    Returns:
        The integer value 1
    """
    return 1


class ReliabilityError(Exception):
    """Exception raised when an operation fails reliability check."""


@op
def unreliable(num: int) -> int:
    """This op is unreliable and will fail 50% of the time.

    Args:
        num: Input number

    Returns:
        The input number if reliable

    Raises:
        ReliabilityError: If the operation fails the reliability check
    """
    failure_rate = 0.5
    if random.random() < failure_rate:  # noqa: S311
        msg = "Failed to be reliable."
        raise ReliabilityError(msg)

    return num


@op
def end(_num: int) -> None:
    """This op does nothing."""


@job(
    executor_def=taskiq_executor,
    tags={"dagster-taskiq/queue": "short-queue"},
)
def unreliable_job_short() -> None:
    """This job is unreliable and will fail 50% of the time."""
    end(unreliable(start()))


definitions = Definitions(
    assets=[partitioned_asset],
    jobs=[partitioned_job_long, unreliable_job_short],
    executor=taskiq_executor,
)
