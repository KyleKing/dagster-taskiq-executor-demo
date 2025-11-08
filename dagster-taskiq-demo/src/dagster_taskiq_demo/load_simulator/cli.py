"""CLI entry point for the load simulator."""

import asyncio
import logging
import sys
from pathlib import Path

import click
import structlog

from dagster_taskiq_demo.config.settings import settings
from dagster_taskiq_demo.load_simulator import (
    run_burst_load,
    run_mixed_workload,
    run_network_partition,
    run_steady_load,
    run_worker_failure,
)
from dagster_taskiq_demo.load_simulator.verification import ExactlyOnceVerifier


@click.group()
@click.option(
    "--host",
    default="localhost",
    help="Dagster webserver host",
)
@click.option(
    "--port",
    default=settings.dagster_webserver_port,
    type=int,
    help="Dagster webserver port",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="Logging level",
)
@click.pass_context
def cli(ctx: click.Context, host: str, port: int, log_level: str) -> None:
    """Load simulator CLI for Dagster TaskIQ LocalStack demo."""
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set log level

    logging.getLogger().setLevel(getattr(logging, log_level))

    # Store common options in context
    ctx.ensure_object(dict)
    ctx.obj["host"] = host
    ctx.obj["port"] = port


@cli.command()
@click.option(
    "--jobs-per-minute",
    default=6,
    type=int,
    help="Number of jobs to submit per minute",
)
@click.option(
    "--duration",
    default=300,
    type=int,
    help="Duration to run the scenario in seconds",
)
@click.pass_context
def steady_load(ctx: click.Context, jobs_per_minute: int, duration: int) -> None:
    """Run a steady load scenario."""
    click.echo(f"Starting steady load scenario: {jobs_per_minute} jobs/minute for {duration} seconds")

    try:
        submitted_runs = asyncio.run(
            run_steady_load(
                jobs_per_minute=jobs_per_minute,
                duration_seconds=duration,
                host=ctx.obj["host"],
                port=ctx.obj["port"],
            )
        )
        click.echo(f"Scenario completed. Submitted {len(submitted_runs)} runs.")
        for run_id in submitted_runs:
            click.echo(f"  - {run_id}")

    except Exception as exc:
        click.echo(f"Error running scenario: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--burst-size",
    default=10,
    type=int,
    help="Number of jobs in each burst",
)
@click.option(
    "--burst-interval",
    default=5,
    type=int,
    help="Minutes between bursts",
)
@click.option(
    "--duration",
    default=600,
    type=int,
    help="Duration to run the scenario in seconds",
)
@click.pass_context
def burst_load(ctx: click.Context, burst_size: int, burst_interval: int, duration: int) -> None:
    """Run a burst load scenario."""
    click.echo(f"Starting burst load scenario: {burst_size} jobs every {burst_interval} minutes for {duration} seconds")

    try:
        submitted_runs = asyncio.run(
            run_burst_load(
                burst_size=burst_size,
                burst_interval_minutes=burst_interval,
                duration_seconds=duration,
                host=ctx.obj["host"],
                port=ctx.obj["port"],
            )
        )
        click.echo(f"Scenario completed. Submitted {len(submitted_runs)} runs.")
        for run_id in submitted_runs:
            click.echo(f"  - {run_id}")

    except Exception as exc:
        click.echo(f"Error running scenario: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--duration",
    default=600,
    type=int,
    help="Duration to run the scenario in seconds",
)
@click.pass_context
def mixed_workload(ctx: click.Context, duration: int) -> None:
    """Run a mixed workload scenario."""
    click.echo(f"Starting mixed workload scenario for {duration} seconds")

    try:
        submitted_runs = asyncio.run(
            run_mixed_workload(
                duration_seconds=duration,
                host=ctx.obj["host"],
                port=ctx.obj["port"],
            )
        )
        click.echo(f"Scenario completed. Submitted {len(submitted_runs)} runs.")
        for run_id in submitted_runs:
            click.echo(f"  - {run_id}")

    except Exception as exc:
        click.echo(f"Error running scenario: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--failure-burst-size",
    default=20,
    type=int,
    help="Number of jobs in each failure burst",
)
@click.option(
    "--recovery-interval",
    default=2,
    type=int,
    help="Minutes between failure bursts",
)
@click.option(
    "--duration",
    default=600,
    type=int,
    help="Duration to run the scenario in seconds",
)
@click.pass_context
def worker_failure(ctx: click.Context, failure_burst_size: int, recovery_interval: int, duration: int) -> None:
    """Run a worker failure scenario."""
    click.echo(
        f"Starting worker failure scenario: {failure_burst_size} jobs "
        f"every {recovery_interval} minutes for {duration} seconds"
    )

    try:
        submitted_runs = asyncio.run(
            run_worker_failure(
                failure_burst_size=failure_burst_size,
                recovery_interval_minutes=recovery_interval,
                duration_seconds=duration,
                host=ctx.obj["host"],
                port=ctx.obj["port"],
            )
        )
        click.echo(f"Scenario completed. Submitted {len(submitted_runs)} runs.")
        for run_id in submitted_runs:
            click.echo(f"  - {run_id}")

    except Exception as exc:
        click.echo(f"Error running scenario: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--max-burst-size",
    default=5,
    type=int,
    help="Maximum number of jobs in each burst",
)
@click.option(
    "--duration",
    default=600,
    type=int,
    help="Duration to run the scenario in seconds",
)
@click.pass_context
def network_partition(ctx: click.Context, max_burst_size: int, duration: int) -> None:
    """Run a network partition scenario."""
    click.echo(f"Starting network partition scenario: max {max_burst_size} jobs per burst for {duration} seconds")

    try:
        submitted_runs = asyncio.run(
            run_network_partition(
                max_burst_size=max_burst_size,
                duration_seconds=duration,
                host=ctx.obj["host"],
                port=ctx.obj["port"],
            )
        )
        click.echo(f"Scenario completed. Submitted {len(submitted_runs)} runs.")
        for run_id in submitted_runs:
            click.echo(f"  - {run_id}")

    except Exception as exc:
        click.echo(f"Error running scenario: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--scenario-tag",
    default=None,
    help="Optional scenario tag to filter verification",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output file path for verification report",
)
@click.option(
    "--format",
    default="json",
    type=click.Choice(["json", "csv"]),
    help="Output format for verification report",
)
@click.pass_context
def verify(_ctx: click.Context, scenario_tag: str | None, output: str | None, output_format: str) -> None:
    """Verify exactly-once execution semantics."""
    click.echo("Running exactly-once verification...")

    try:
        verifier = ExactlyOnceVerifier(settings)
        result = verifier.verify_idempotency_records(scenario_tag)

        click.echo("Verification Results:")
        click.echo(f"  Total runs: {result.total_runs}")
        click.echo(f"  Completed runs: {result.completed_runs}")
        click.echo(f"  Failed runs: {result.failed_runs}")
        click.echo(f"  Pending runs: {result.pending_runs}")
        click.echo(f"  Duplicate executions: {result.duplicate_executions}")
        click.echo(f"  Missing executions: {result.missing_executions}")

        if output:
            output_path = Path(output)
            verifier.export_report(result, output_path, output_format)
            click.echo(f"Report exported to {output_path}")

    except Exception as exc:
        click.echo(f"Error running verification: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
