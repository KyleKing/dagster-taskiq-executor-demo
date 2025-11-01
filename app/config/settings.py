"""
Configuration settings for Dagster TaskIQ LocalStack demo.
"""

import os
from typing import Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # AWS/LocalStack Configuration
    aws_region: str = Field(default="us-east-1", env="AWS_DEFAULT_REGION")
    aws_endpoint_url: str = Field(default="http://localhost:4566", env="AWS_ENDPOINT_URL")
    aws_access_key_id: str = Field(default="test", env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="test", env="AWS_SECRET_ACCESS_KEY")
    
    # Database Configuration
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_user: str = Field(default="dagster", env="POSTGRES_USER")
    postgres_password: str = Field(default="dagster", env="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="dagster", env="POSTGRES_DB")
    
    # SQS Configuration
    taskiq_queue_name: str = Field(default="dagster-taskiq-demo-taskiq-dev.fifo", env="TASKIQ_QUEUE_NAME")
    taskiq_dlq_name: str = Field(default="dagster-taskiq-demo-taskiq-dlq-dev.fifo", env="TASKIQ_DLQ_NAME")
    
    # ECS Configuration
    ecs_cluster_name: str = Field(default="dagster-taskiq-demo-dev", env="ECS_CLUSTER_NAME")
    
    # Dagster Configuration
    dagster_home: str = Field(default="/opt/dagster/dagster_home", env="DAGSTER_HOME")
    dagster_webserver_host: str = Field(default="0.0.0.0", env="DAGSTER_WEBSERVER_HOST")
    dagster_webserver_port: int = Field(default=3000, env="DAGSTER_WEBSERVER_PORT")
    
    # TaskIQ Configuration
    taskiq_worker_concurrency: int = Field(default=4, env="TASKIQ_WORKER_CONCURRENCY")
    taskiq_visibility_timeout: int = Field(default=300, env="TASKIQ_VISIBILITY_TIMEOUT")
    
    # Auto Scaler Configuration
    autoscaler_min_workers: int = Field(default=2, env="AUTOSCALER_MIN_WORKERS")
    autoscaler_max_workers: int = Field(default=20, env="AUTOSCALER_MAX_WORKERS")
    autoscaler_scale_up_threshold: int = Field(default=5, env="AUTOSCALER_SCALE_UP_THRESHOLD")
    autoscaler_scale_down_threshold: int = Field(default=2, env="AUTOSCALER_SCALE_DOWN_THRESHOLD")
    autoscaler_cooldown_seconds: int = Field(default=60, env="AUTOSCALER_COOLDOWN_SECONDS")
    
    # Load Simulator Configuration
    load_sim_job_interval_seconds: int = Field(default=600, env="LOAD_SIM_JOB_INTERVAL_SECONDS")  # 10 minutes
    load_sim_fast_job_duration_base: int = Field(default=20, env="LOAD_SIM_FAST_JOB_DURATION_BASE")
    load_sim_fast_job_duration_variance: int = Field(default=10, env="LOAD_SIM_FAST_JOB_DURATION_VARIANCE")
    load_sim_slow_job_duration_base: int = Field(default=300, env="LOAD_SIM_SLOW_JOB_DURATION_BASE")  # 5 minutes
    load_sim_slow_job_duration_variance: int = Field(default=120, env="LOAD_SIM_SLOW_JOB_DURATION_VARIANCE")  # 2 minutes
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def dagster_postgres_url(self) -> str:
        """Get Dagster PostgreSQL connection URL."""
        return f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


# Global settings instance
settings = Settings()