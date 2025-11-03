"""Runtime configuration for the TaskIQ demo."""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="TASKIQ_DEMO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    aws_access_key_id: str = Field(default="localstack")
    aws_secret_access_key: str = Field(default="localstack")
    aws_region: str = Field(default="us-east-1")
    sqs_endpoint_url: str = Field(default="http://localhost:4566")
    sqs_queue_name: str = Field(default="taskiq-demo")
    log_level: str = Field(default="INFO", description="Python logging level.")
    min_duration_seconds: float = Field(default=1.0, ge=0.0)
    max_duration_seconds: float = Field(default=300.0, ge=1.0)
    wait_time_seconds: int = Field(default=10, ge=0, le=20)
    message_delay_seconds: int = Field(default=0, ge=0, le=900)
    worker_processes: int = Field(default=1, ge=1)
    worker_max_async_tasks: int = Field(default=100, ge=1)
    worker_max_prefetch: int = Field(default=0, ge=0)
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalise configured log level to uppercase.

        Args:
            value: The log level string to normalize.

        Returns:
            The uppercase log level string.

        """
        return str(value or "").upper() or "INFO"

    def clamp_duration(self, requested: float) -> float:
        """Clamp the requested sleep duration to the configured bounds.

        Args:
            requested: The requested duration in seconds.

        Returns:
            The clamped duration within min/max bounds.

        """
        return max(self.min_duration_seconds, min(requested, self.max_duration_seconds))

    @property
    def log_level_value(self) -> int:
        """Return the numeric logging level for configured log level."""
        level_names = logging.getLevelNamesMapping()
        return level_names.get(self.log_level, logging.INFO)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance.

    Returns:
        The cached Settings instance.

    """
    return Settings()
