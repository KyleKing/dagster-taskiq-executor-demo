"""Configuration settings for Dagster TaskIQ LocalStack demo."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # AWS/LocalStack Configuration
    aws_region: str = Field(default="us-east-1", validation_alias="AWS_DEFAULT_REGION")
    aws_endpoint_url: str = Field(
        default="http://localhost:4566",
        validation_alias="AWS_ENDPOINT_URL",
    )
    aws_access_key_id: str = Field(default="test", validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="test", validation_alias="AWS_SECRET_ACCESS_KEY")

    # Database Configuration
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_user: str = Field(default="dagster", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="dagster", validation_alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="dagster", validation_alias="POSTGRES_DB")

    # SQS Configuration
    taskiq_queue_name: str = Field(
        default="dagster-taskiq-demo-taskiq-dev.fifo",
        validation_alias="TASKIQ_QUEUE_NAME",
    )
    taskiq_dlq_name: str = Field(
        default="dagster-taskiq-demo-taskiq-dlq-dev.fifo",
        validation_alias="TASKIQ_DLQ_NAME",
    )

    # ECS Configuration
    ecs_cluster_name: str = Field(default="dagster-taskiq-demo-dev", validation_alias="ECS_CLUSTER_NAME")
    ecs_worker_service_name: str = Field(
        default="dagster-taskiq-demo-workers-dev", validation_alias="ECS_WORKER_SERVICE_NAME"
    )

    # Dagster Configuration
    dagster_home: str = Field(default="/opt/dagster/dagster_home", validation_alias="DAGSTER_HOME")
    dagster_webserver_host: str = Field(
        default="0.0.0.0",  # noqa: S104 - exposed for container access
        validation_alias="DAGSTER_WEBSERVER_HOST",
    )
    dagster_webserver_port: int = Field(default=3000, validation_alias="DAGSTER_WEBSERVER_PORT")

    # TaskIQ Configuration
    taskiq_worker_concurrency: int = Field(default=4, validation_alias="TASKIQ_WORKER_CONCURRENCY")
    taskiq_visibility_timeout: int = Field(default=300, validation_alias="TASKIQ_VISIBILITY_TIMEOUT")
    taskiq_worker_health_port: int = Field(default=8080, validation_alias="TASKIQ_WORKER_HEALTH_PORT")

    # Auto Scaler Configuration
    autoscaler_min_workers: int = Field(default=2, validation_alias="AUTOSCALER_MIN_WORKERS")
    autoscaler_max_workers: int = Field(default=20, validation_alias="AUTOSCALER_MAX_WORKERS")
    autoscaler_scale_up_threshold: int = Field(
        default=5,
        validation_alias="AUTOSCALER_SCALE_UP_THRESHOLD",
    )
    autoscaler_scale_down_threshold: int = Field(
        default=2,
        validation_alias="AUTOSCALER_SCALE_DOWN_THRESHOLD",
    )
    autoscaler_cooldown_seconds: int = Field(default=60, validation_alias="AUTOSCALER_COOLDOWN_SECONDS")

    # Load Simulator Configuration
    load_sim_job_interval_seconds: int = Field(
        default=600,
        validation_alias="LOAD_SIM_JOB_INTERVAL_SECONDS",
    )  # 10 minutes
    load_sim_fast_job_duration_base: int = Field(
        default=20,
        validation_alias="LOAD_SIM_FAST_JOB_DURATION_BASE",
    )
    load_sim_fast_job_duration_variance: int = Field(
        default=10,
        validation_alias="LOAD_SIM_FAST_JOB_DURATION_VARIANCE",
    )
    load_sim_slow_job_duration_base: int = Field(
        default=300,
        validation_alias="LOAD_SIM_SLOW_JOB_DURATION_BASE",
    )  # 5 minutes
    load_sim_slow_job_duration_variance: int = Field(
        default=120,
        validation_alias="LOAD_SIM_SLOW_JOB_DURATION_VARIANCE",
    )  # 2 minutes

    # Logging Configuration
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def dagster_postgres_url(self) -> str:
        """Get Dagster PostgreSQL connection URL."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


# Global settings instance
settings = Settings()
