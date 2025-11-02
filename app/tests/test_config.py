"""Tests for configuration modules."""

from __future__ import annotations

import pathlib
import tempfile
from unittest.mock import Mock, patch

import pytest
import yaml
from dagster_postgres import DagsterPostgresStorage

from dagster_taskiq.config.dagster import (
    DagsterPostgreSQLConfig,
    RetryablePostgresStorage,
    create_dagster_yaml_file,
    get_dagster_instance_config,
)
from dagster_taskiq.config.exceptions import DagsterDatabaseConnectionError
from dagster_taskiq.config.settings import Settings


class TestSettings:
    """Test settings configuration."""

    def test_settings_defaults(self):
        """Test that settings have reasonable defaults."""
        settings = Settings()
        
        # AWS defaults
        assert settings.aws_region == "us-east-1"
        assert settings.aws_endpoint_url == "http://localhost:4566"
        assert settings.aws_access_key_id == "test"
        assert settings.aws_secret_access_key == "test"
        
        # Database defaults
        assert settings.postgres_host == "localhost"
        assert settings.postgres_port == 5432
        assert settings.postgres_user == "dagster"
        assert settings.postgres_password == "dagster"
        assert settings.postgres_db == "dagster"
        
        # Dagster defaults
        assert settings.dagster_home == "/opt/dagster/dagster_home"
        assert settings.dagster_webserver_host == "0.0.0.0"
        assert settings.dagster_webserver_port == 3000

    def test_postgres_url_property(self):
        """Test postgres_url property construction."""
        settings = Settings(
            postgres_user="testuser",
            postgres_password="testpass",
            postgres_host="testhost",
            postgres_port=5433,
            postgres_db="testdb",
        )
        
        expected_url = "postgresql://testuser:testpass@testhost:5433/testdb"
        assert settings.postgres_url == expected_url

    def test_dagster_postgres_url_property(self):
        """Test dagster_postgres_url property construction."""
        settings = Settings(
            postgres_user="testuser",
            postgres_password="testpass",
            postgres_host="testhost",
            postgres_port=5433,
            postgres_db="testdb",
        )
        
        expected_url = "postgresql+psycopg2://testuser:testpass@testhost:5433/testdb"
        assert settings.dagster_postgres_url == expected_url

    def test_settings_from_env_vars(self):
        """Test that settings can be loaded from environment variables."""
        env_vars = {
            "AWS_DEFAULT_REGION": "us-west-2",
            "AWS_ENDPOINT_URL": "http://custom:4566",
            "POSTGRES_HOST": "custom-host",
            "POSTGRES_PORT": "5433",
            "POSTGRES_USER": "custom-user",
            "POSTGRES_PASSWORD": "custom-pass",
            "POSTGRES_DB": "custom-db",
            "DAGSTER_WEBSERVER_PORT": "3001",
        }
        
        with patch.dict("os.environ", env_vars):
            settings = Settings()
            
            assert settings.aws_region == "us-west-2"
            assert settings.aws_endpoint_url == "http://custom:4566"
            assert settings.postgres_host == "custom-host"
            assert settings.postgres_port == 5433
            assert settings.postgres_user == "custom-user"
            assert settings.postgres_password == "custom-pass"
            assert settings.postgres_db == "custom-db"
            assert settings.dagster_webserver_port == 3001


class TestDagsterPostgreSQLConfig:
    """Test Dagster PostgreSQL configuration helpers."""

    def test_get_postgres_storage_config(self, test_settings: Settings):
        """Test PostgreSQL storage configuration generation."""
        with patch("dagster_taskiq.config.dagster.settings", test_settings):
            config = DagsterPostgreSQLConfig.get_postgres_storage_config()
            
            assert "postgres_url" in config
            assert config["postgres_url"] == test_settings.dagster_postgres_url
            assert config["should_autocreate_tables"] is True

    def test_get_run_storage_config(self, test_settings: Settings):
        """Test run storage configuration generation."""
        with patch("dagster_taskiq.config.dagster.settings", test_settings):
            config = DagsterPostgreSQLConfig.get_run_storage_config()
            
            assert config["module"] == "dagster_postgres.run_storage"
            assert config["class"] == "DagsterPostgresRunStorage"
            assert "config" in config
            assert config["config"]["postgres_url"] == test_settings.dagster_postgres_url

    def test_get_event_log_storage_config(self, test_settings: Settings):
        """Test event log storage configuration generation."""
        with patch("dagster_taskiq.config.dagster.settings", test_settings):
            config = DagsterPostgreSQLConfig.get_event_log_storage_config()
            
            assert config["module"] == "dagster_postgres.event_log"
            assert config["class"] == "DagsterPostgresEventLogStorage"
            assert "config" in config
            assert config["config"]["postgres_url"] == test_settings.dagster_postgres_url

    def test_get_schedule_storage_config(self, test_settings: Settings):
        """Test schedule storage configuration generation."""
        with patch("dagster_taskiq.config.dagster.settings", test_settings):
            config = DagsterPostgreSQLConfig.get_schedule_storage_config()
            
            assert config["module"] == "dagster_postgres.schedule_storage"
            assert config["class"] == "DagsterPostgresScheduleStorage"
            assert "config" in config
            assert config["config"]["postgres_url"] == test_settings.dagster_postgres_url

    def test_get_compute_log_storage_config(self):
        """Test compute log storage configuration generation."""
        config = DagsterPostgreSQLConfig.get_compute_log_storage_config()
        
        assert config["module"] == "dagster._core.storage.noop_compute_log_manager"
        assert config["class"] == "NoOpComputeLogManager"

    def test_get_dagster_yaml_config(self, test_settings: Settings):
        """Test complete Dagster YAML configuration generation."""
        with patch("dagster_taskiq.config.dagster.settings", test_settings):
            config = DagsterPostgreSQLConfig.get_dagster_yaml_config()
            
            # Check top-level structure
            assert "storage" in config
            assert "run_coordinator" in config
            assert "run_launcher" in config
            assert "compute_logs" in config
            
            # Check storage configuration
            storage = config["storage"]
            assert "postgres" in storage
            assert storage["postgres"]["postgres_url"] == test_settings.dagster_postgres_url
            assert storage["postgres"]["should_autocreate_tables"] is True
            
            # Check run coordinator
            assert config["run_coordinator"]["class"] == "DefaultRunCoordinator"
            
            # Check run launcher
            assert config["run_launcher"]["class"] == "DefaultRunLauncher"


class TestRetryablePostgresStorage:
    """Test retryable PostgreSQL storage."""

    def test_create_storage_success_first_try(self):
        """Test successful storage creation on first attempt."""
        postgres_url = "postgresql://test:test@localhost:5432/test"
        storage = RetryablePostgresStorage(postgres_url, max_retries=3, retry_delay=0.1)
        
        with patch("dagster_taskiq.config.dagster.DagsterPostgresStorage") as mock_storage_class:
            mock_instance = Mock()
            mock_storage_class.return_value = mock_instance
            
            result = storage.create_storage()
            
            assert result == mock_instance
            mock_storage_class.assert_called_once_with(
                postgres_url=postgres_url,
                should_autocreate_tables=True,
            )

    def test_create_storage_success_after_retries(self):
        """Test successful storage creation after retries."""
        postgres_url = "postgresql://test:test@localhost:5432/test"
        storage = RetryablePostgresStorage(postgres_url, max_retries=3, retry_delay=0.01)
        
        with patch("dagster_taskiq.config.dagster.DagsterPostgresStorage") as mock_storage_class:
            mock_instance = Mock()
            # Fail twice, then succeed
            mock_storage_class.side_effect = [
                ConnectionError("Connection failed"),
                ConnectionError("Connection failed"),
                mock_instance,
            ]
            
            with patch("time.sleep") as mock_sleep:
                result = storage.create_storage()
                
                assert result == mock_instance
                assert mock_storage_class.call_count == 3
                assert mock_sleep.call_count == 2  # Sleep after first two failures

    def test_create_storage_failure_after_max_retries(self):
        """Test storage creation failure after max retries."""
        postgres_url = "postgresql://test:test@localhost:5432/test"
        storage = RetryablePostgresStorage(postgres_url, max_retries=2, retry_delay=0.01)
        
        with patch("dagster_taskiq.config.dagster.DagsterPostgresStorage") as mock_storage_class:
            mock_storage_class.side_effect = ConnectionError("Connection failed")
            
            with patch("time.sleep"):
                with pytest.raises(DagsterDatabaseConnectionError) as exc_info:
                    storage.create_storage()
                
                assert "Failed to connect to PostgreSQL after 2 attempts" in str(exc_info.value)
                assert mock_storage_class.call_count == 2


class TestConfigurationFiles:
    """Test configuration file generation."""

    def test_create_dagster_yaml_file(self, test_settings: Settings):
        """Test creation of dagster.yaml file."""
        with patch("dagster_taskiq.config.dagster.settings", test_settings):
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = pathlib.Path(temp_dir) / "test_dagster.yaml"
                
                create_dagster_yaml_file(output_path)
                
                assert output_path.exists()
                
                # Verify file contents
                with output_path.open("r", encoding="utf-8") as file:
                    config = yaml.safe_load(file)
                
                assert "storage" in config
                assert "postgres" in config["storage"]
                assert config["storage"]["postgres"]["postgres_url"] == test_settings.dagster_postgres_url

    def test_get_dagster_instance_config(self, test_settings: Settings):
        """Test programmatic Dagster instance configuration."""
        with patch("dagster_taskiq.config.dagster.settings", test_settings):
            config = get_dagster_instance_config()
            
            # Should have same structure as YAML config
            assert "storage" in config
            assert "run_coordinator" in config
            assert "run_launcher" in config
            assert "compute_logs" in config
            
            # Should use test settings
            assert config["storage"]["postgres"]["postgres_url"] == test_settings.dagster_postgres_url