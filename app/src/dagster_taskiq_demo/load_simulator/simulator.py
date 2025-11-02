"""Load testing and simulation framework for Dagster TaskIQ LocalStack demo."""

import asyncio
import random
import time
from typing import Any, Dict, List, Optional

import structlog
from dagster_graphql import DagsterGraphQLClient, DagsterGraphQLClientError

from dagster_taskiq_demo.config.metrics import get_metrics_collector
from dagster_taskiq_demo.config.settings import settings

logger = structlog.get_logger(__name__)


class LoadSimulator:
    """Load simulator for submitting Dagster runs asynchronously."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = settings.dagster_webserver_port,
        repository_location_name: Optional[str] = None,
        repository_name: Optional[str] = None,
    ) -> None:
        """Initialize the load simulator.

        Args:
            host: Dagster webserver host
            port: Dagster webserver port
            repository_location_name: Name of the repository location (optional)
            repository_name: Name of the repository (optional)
        """
        self.client = DagsterGraphQLClient(host, port_number=port)
        self.repository_location_name = repository_location_name
        self.repository_name = repository_name

        # Available job configurations
        self.job_configs = {
            "fast_job": {},
            "slow_job": {},
            "mixed_job": {},
            "parallel_fast_job": {},
            "sequential_slow_job": {},
        }

    async def submit_run(
        self,
        job_name: str,
        run_config: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Submit a single Dagster run asynchronously.

        Args:
            job_name: Name of the job to run
            run_config: Run configuration for the job
            tags: Tags to apply to the run

        Returns:
            Run ID if successful, None if failed
        """
        if run_config is None:
            run_config = {}

        if tags is None:
            tags = {}

        # Add load simulator tag
        tags["load_simulator"] = "true"
        tags["submitted_at"] = str(int(time.time()))

        try:
            logger.info(
                "submitting_run",
                job_name=job_name,
                run_config=run_config,
                tags=tags,
            )

            # Call submit_job_execution with appropriate parameters
            if self.repository_location_name and self.repository_name:
                run_id = self.client.submit_job_execution(
                    job_name=job_name,
                    repository_location_name=self.repository_location_name,
                    repository_name=self.repository_name,
                    run_config=run_config,
                    tags=tags,
                )
            elif self.repository_location_name:
                run_id = self.client.submit_job_execution(
                    job_name=job_name,
                    repository_location_name=self.repository_location_name,
                    run_config=run_config,
                    tags=tags,
                )
            else:
                run_id = self.client.submit_job_execution(
                    job_name=job_name,
                    run_config=run_config,
                    tags=tags,
                )

            logger.info("run_submitted", job_name=job_name, run_id=run_id)

            # Record metrics
            metrics = get_metrics_collector()
            metrics.increment_counter("runs_submitted", dimensions={"job_name": job_name, "scenario": getattr(self, "_current_scenario", "unknown")})

            return run_id

        except DagsterGraphQLClientError as exc:
            logger.error(
                "run_submission_failed",
                job_name=job_name,
                error=str(exc),
                exc_info=True,
            )
            return None

    async def submit_scenario(
        self,
        scenario: Dict[str, Any],
        duration_seconds: int = 300,  # 5 minutes default
    ) -> List[str]:
        """Submit runs according to a scenario configuration.

        Args:
            scenario: Scenario configuration dict
            duration_seconds: How long to run the scenario

        Returns:
            List of submitted run IDs
        """
        submitted_runs = []
        start_time = time.time()
        end_time = start_time + duration_seconds

        logger.info("starting_scenario", scenario=scenario, duration_seconds=duration_seconds)

        while time.time() < end_time:
            # Select job based on scenario weights
            job_name = self._select_job_from_scenario(scenario)

            # Submit the run
            run_id = await self.submit_run(job_name)
            if run_id:
                submitted_runs.append(run_id)

            # Wait before next submission
            interval = scenario.get("interval_seconds", 10)
            await asyncio.sleep(interval)

        logger.info("scenario_completed", submitted_runs=len(submitted_runs))
        return submitted_runs

    def _select_job_from_scenario(self, scenario: Dict[str, Any]) -> str:
        """Select a job name based on scenario configuration.

        Args:
            scenario: Scenario dict with job weights

        Returns:
            Selected job name
        """
        job_weights = scenario.get("job_weights", {})
        if not job_weights:
            # Default to equal weights for all jobs
            jobs = list(self.job_configs.keys())
            return random.choice(jobs)

        # Weighted random selection
        jobs = list(job_weights.keys())
        weights = list(job_weights.values())

        return random.choices(jobs, weights=weights, k=1)[0]

    async def steady_load_scenario(
        self,
        jobs_per_minute: int = 6,
        duration_seconds: int = 300,
    ) -> List[str]:
        """Run a steady load scenario.

        Args:
            jobs_per_minute: Number of jobs to submit per minute
            duration_seconds: How long to run the scenario

        Returns:
            List of submitted run IDs
        """
        interval_seconds = 60 / jobs_per_minute

        scenario = {
            "name": "steady_load",
            "interval_seconds": interval_seconds,
            "job_weights": {
                "fast_job": 0.7,  # 70% fast jobs
                "slow_job": 0.2,  # 20% slow jobs
                "mixed_job": 0.1,  # 10% mixed jobs
            },
        }

        return await self.submit_scenario(scenario, duration_seconds)

    async def burst_load_scenario(
        self,
        burst_size: int = 10,
        burst_interval_minutes: int = 5,
        duration_seconds: int = 600,
    ) -> List[str]:
        """Run a burst load scenario.

        Args:
            burst_size: Number of jobs in each burst
            burst_interval_minutes: Minutes between bursts
            duration_seconds: How long to run the scenario

        Returns:
            List of submitted run IDs
        """
        submitted_runs = []
        start_time = time.time()
        end_time = start_time + duration_seconds

        logger.info(
            "starting_burst_scenario",
            burst_size=burst_size,
            burst_interval_minutes=burst_interval_minutes,
            duration_seconds=duration_seconds,
        )

        while time.time() < end_time:
            # Submit burst of jobs
            burst_tasks = []
            for _ in range(burst_size):
                job_name = random.choice(["fast_job", "parallel_fast_job"])
                task = self.submit_run(job_name)
                burst_tasks.append(task)

            # Wait for all burst jobs to be submitted
            burst_results = await asyncio.gather(*burst_tasks, return_exceptions=True)
            for result in burst_results:
                if isinstance(result, str):
                    submitted_runs.append(result)
                elif isinstance(result, Exception):
                    logger.error("burst_job_submission_error", error=str(result))

            logger.info("burst_completed", jobs_submitted=len(burst_results))

            # Wait for next burst
            await asyncio.sleep(burst_interval_minutes * 60)

        logger.info("burst_scenario_completed", total_runs=len(submitted_runs))
        return submitted_runs

    async def mixed_workload_scenario(
        self,
        duration_seconds: int = 600,
    ) -> List[str]:
        """Run a mixed workload scenario with various job types.

        Args:
            duration_seconds: How long to run the scenario

        Returns:
            List of submitted run IDs
        """
        scenario = {
            "name": "mixed_workload",
            "interval_seconds": 30,  # Every 30 seconds
            "job_weights": {
                "fast_job": 0.4,
                "slow_job": 0.2,
                "mixed_job": 0.2,
                "parallel_fast_job": 0.1,
                "sequential_slow_job": 0.1,
            },
        }

        return await self.submit_scenario(scenario, duration_seconds)

    async def worker_failure_scenario(
        self,
        failure_burst_size: int = 20,
        recovery_interval_minutes: int = 2,
        duration_seconds: int = 600,
    ) -> List[str]:
        """Run a worker failure scenario that submits bursts that may overwhelm workers.

        Args:
            failure_burst_size: Number of jobs in each failure burst
            recovery_interval_minutes: Minutes between failure bursts
            duration_seconds: How long to run the scenario

        Returns:
            List of submitted run IDs
        """
        submitted_runs = []
        start_time = time.time()
        end_time = start_time + duration_seconds

        logger.info(
            "starting_worker_failure_scenario",
            failure_burst_size=failure_burst_size,
            recovery_interval_minutes=recovery_interval_minutes,
            duration_seconds=duration_seconds,
        )

        while time.time() < end_time:
            # Submit a burst that might cause worker overload/failure
            burst_tasks = []
            for _ in range(failure_burst_size):
                # Mix of jobs that could overwhelm workers
                job_name = random.choice(["parallel_fast_job", "sequential_slow_job", "mixed_job"])
                task = self.submit_run(job_name)
                burst_tasks.append(task)

            # Wait for all burst jobs to be submitted
            burst_results = await asyncio.gather(*burst_tasks, return_exceptions=True)
            for result in burst_results:
                if isinstance(result, str):
                    submitted_runs.append(result)
                elif isinstance(result, Exception):
                    logger.error("failure_burst_job_submission_error", error=str(result))

            logger.info("failure_burst_completed", jobs_submitted=len(burst_results))

            # Wait for system recovery
            await asyncio.sleep(recovery_interval_minutes * 60)

        logger.info("worker_failure_scenario_completed", total_runs=len(submitted_runs))
        return submitted_runs

    async def network_partition_scenario(
        self,
        max_burst_size: int = 5,
        duration_seconds: int = 600,
    ) -> List[str]:
        """Run a network partition scenario with intermittent submissions.

        Args:
            max_burst_size: Maximum jobs in each burst
            duration_seconds: How long to run the scenario

        Returns:
            List of submitted run IDs
        """
        submitted_runs = []
        start_time = time.time()
        end_time = start_time + duration_seconds

        logger.info(
            "starting_network_partition_scenario",
            max_burst_size=max_burst_size,
            duration_seconds=duration_seconds,
        )

        while time.time() < end_time:
            # Random burst size (simulating intermittent connectivity)
            burst_size = random.randint(1, max_burst_size)

            # Submit burst of jobs
            burst_tasks = []
            for _ in range(burst_size):
                job_name = self._select_job_from_scenario({
                    "job_weights": {
                        "fast_job": 0.5,
                        "slow_job": 0.3,
                        "mixed_job": 0.2,
                    }
                })
                task = self.submit_run(job_name)
                burst_tasks.append(task)

            # Wait for all burst jobs to be submitted
            burst_results = await asyncio.gather(*burst_tasks, return_exceptions=True)
            for result in burst_results:
                if isinstance(result, str):
                    submitted_runs.append(result)
                elif isinstance(result, Exception):
                    logger.error("network_burst_job_submission_error", error=str(result))

            logger.info("network_burst_completed", jobs_submitted=len(burst_results))

            # Random silence period (simulating network partition)
            silence_seconds = random.uniform(10, 120)  # 10 seconds to 2 minutes
            logger.info("network_partition_silence", silence_seconds=silence_seconds)
            await asyncio.sleep(silence_seconds)

        logger.info("network_partition_scenario_completed", total_runs=len(submitted_runs))
        return submitted_runs


# Convenience functions for common scenarios
async def run_steady_load(
    jobs_per_minute: int = 6,
    duration_seconds: int = 300,
    host: str = "localhost",
    port: int = settings.dagster_webserver_port,
) -> List[str]:
    """Run a steady load scenario.

    Args:
        jobs_per_minute: Jobs to submit per minute
        duration_seconds: How long to run
        host: Dagster webserver host
        port: Dagster webserver port

    Returns:
        List of submitted run IDs
    """
    simulator = LoadSimulator(host=host, port=port)
    return await simulator.steady_load_scenario(jobs_per_minute, duration_seconds)


async def run_burst_load(
    burst_size: int = 10,
    burst_interval_minutes: int = 5,
    duration_seconds: int = 600,
    host: str = "localhost",
    port: int = settings.dagster_webserver_port,
) -> List[str]:
    """Run a burst load scenario.

    Args:
        burst_size: Jobs per burst
        burst_interval_minutes: Minutes between bursts
        duration_seconds: How long to run
        host: Dagster webserver host
        port: Dagster webserver port

    Returns:
        List of submitted run IDs
    """
    simulator = LoadSimulator(host=host, port=port)
    return await simulator.burst_load_scenario(burst_size, burst_interval_minutes, duration_seconds)


async def run_mixed_workload(
    duration_seconds: int = 600,
    host: str = "localhost",
    port: int = settings.dagster_webserver_port,
) -> List[str]:
    """Run a mixed workload scenario.

    Args:
        duration_seconds: How long to run
        host: Dagster webserver host
        port: Dagster webserver port

    Returns:
        List of submitted run IDs
    """
    simulator = LoadSimulator(host=host, port=port)
    return await simulator.mixed_workload_scenario(duration_seconds)


async def run_worker_failure(
    failure_burst_size: int = 20,
    recovery_interval_minutes: int = 2,
    duration_seconds: int = 600,
    host: str = "localhost",
    port: int = settings.dagster_webserver_port,
) -> List[str]:
    """Run a worker failure scenario.

    Args:
        failure_burst_size: Jobs per failure burst
        recovery_interval_minutes: Minutes between bursts
        duration_seconds: How long to run
        host: Dagster webserver host
        port: Dagster webserver port

    Returns:
        List of submitted run IDs
    """
    simulator = LoadSimulator(host=host, port=port)
    return await simulator.worker_failure_scenario(failure_burst_size, recovery_interval_minutes, duration_seconds)


async def run_network_partition(
    max_burst_size: int = 5,
    duration_seconds: int = 600,
    host: str = "localhost",
    port: int = settings.dagster_webserver_port,
) -> List[str]:
    """Run a network partition scenario.

    Args:
        max_burst_size: Maximum jobs per burst
        duration_seconds: How long to run
        host: Dagster webserver host
        port: Dagster webserver port

    Returns:
        List of submitted run IDs
    """
    simulator = LoadSimulator(host=host, port=port)
    return await simulator.network_partition_scenario(max_burst_size, duration_seconds)