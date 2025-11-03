"""Metrics collection and publishing for observability."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """Collects and publishes metrics for observability."""

    def __init__(self, namespace: str = "DagsterTaskIQ") -> None:
        """Initialize metrics collector."""
        self.namespace = namespace
        self.metrics: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        self.start_time = time.time()

    def increment_counter(self, name: str, value: float = 1.0, dimensions: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        self._record_metric(name, "counter", value, dimensions)

    def gauge(self, name: str, value: float, dimensions: dict[str, str] | None = None) -> None:
        """Record a gauge metric."""
        self._record_metric(name, "gauge", value, dimensions)

    def timing(self, name: str, value: float, dimensions: dict[str, str] | None = None) -> None:
        """Record a timing metric in seconds."""
        self._record_metric(name, "timing", value, dimensions)

    def _record_metric(self, name: str, metric_type: str, value: float, dimensions: dict[str, str] | None = None) -> None:
        """Record a metric."""
        metric = {
            "name": name,
            "type": metric_type,
            "value": value,
            "timestamp": time.time(),
            "dimensions": dimensions or {},
        }
        self.metrics[name].append(metric)

        # Log the metric for observability
        logger.info(
            "metric_recorded",
            name=name,
            type=metric_type,
            value=value,
            dimensions=dimensions,
        )

    def publish_to_cloudwatch(self) -> None:
        """Publish metrics to CloudWatch (LocalStack)."""
        # TODO: Implement CloudWatch publishing using boto3
        # For now, just log that we'd publish
        logger.info("would_publish_metrics_to_cloudwatch", metric_count=sum(len(v) for v in self.metrics.values()))

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        summary: dict[str, Any] = {
            "namespace": self.namespace,
            "collection_duration": time.time() - self.start_time,
            "metrics": {},
        }

        for name, values in self.metrics.items():
            if values:
                summary["metrics"][name] = {
                    "count": len(values),
                    "latest_value": values[-1]["value"],
                    "total": sum(v["value"] for v in values),
                    "avg": sum(v["value"] for v in values) / len(values),
                }

        return summary


# Global metrics collector instance
metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return metrics_collector
