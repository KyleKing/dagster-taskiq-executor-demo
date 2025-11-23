.PHONY: help test test-unit test-integration test-all test-opa localstack-start localstack-sync localstack-reset clean

# Default target
help:
	@echo "Pulumi Infrastructure Test Commands"
	@echo "===================================="
	@echo ""
	@echo "LocalStack Management:"
	@echo "  localstack-start    Start LocalStack container"
	@echo "  localstack-sync     Sync Pulumi state with LocalStack"
	@echo "  localstack-reset    Nuclear option: destroy everything and redeploy"
	@echo "  localstack-status   Show LocalStack and Pulumi status"
	@echo ""
	@echo "Testing:"
	@echo "  test-unit           Run unit tests (fast, with mocks)"
	@echo "  test-integration    Run integration tests (deploy to LocalStack)"
	@echo "  test-opa            Run OPA policy tests"
	@echo "  test-all            Run all tests"
	@echo "  test-coverage       Run tests with coverage report"
	@echo ""
	@echo "Development:"
	@echo "  clean               Remove test artifacts and cache"
	@echo "  deploy-local        Deploy to LocalStack (with state sync)"
	@echo "  destroy-local       Destroy LocalStack infrastructure"
	@echo ""
	@echo "Examples:"
	@echo "  make localstack-start test-integration"
	@echo "  make localstack-sync deploy-local"
	@echo "  make test-all test-coverage"

# ============================================================================
# LocalStack Management
# ============================================================================

localstack-start:
	@echo "Starting LocalStack..."
	./scripts/localstack-dev.sh start

localstack-sync:
	@echo "Syncing Pulumi state with LocalStack..."
	./scripts/localstack-dev.sh sync

localstack-reset:
	@echo "Resetting LocalStack and Pulumi state..."
	./scripts/localstack-dev.sh fresh-start

localstack-status:
	@echo "Checking LocalStack and Pulumi status..."
	./scripts/localstack-dev.sh status

# ============================================================================
# Testing
# ============================================================================

test-unit:
	@echo "Running unit tests..."
	PULUMI_CONFIG_PASSPHRASE="" pytest tests/ -m "unit" -v

test-integration: localstack-sync
	@echo "Running integration tests..."
	@echo "NOTE: This will deploy infrastructure to LocalStack"
	PULUMI_CONFIG_PASSPHRASE="" pytest tests/integration/ -m "integration" -v

test-opa:
	@echo "Running OPA policy tests..."
	@if command -v opa >/dev/null 2>&1; then \
		opa test tests/policies/ -v; \
		echo ""; \
		echo "Checking OPA coverage..."; \
		opa test --coverage tests/policies/; \
	else \
		echo "ERROR: OPA not installed"; \
		echo "Install: curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64"; \
		echo "         chmod +x opa && sudo mv opa /usr/local/bin/"; \
		exit 1; \
	fi

test-all: localstack-sync test-unit test-integration test-opa
	@echo "All tests completed!"

test-coverage: localstack-sync
	@echo "Running tests with coverage..."
	PULUMI_CONFIG_PASSPHRASE="" pytest tests/ \
		--cov=components \
		--cov=modules \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml

# ============================================================================
# Development Commands
# ============================================================================

deploy-local: localstack-sync
	@echo "Deploying to LocalStack..."
	pulumi up --yes

destroy-local:
	@echo "Destroying LocalStack infrastructure..."
	pulumi destroy --yes
	./scripts/localstack-dev.sh sync

clean:
	@echo "Cleaning test artifacts..."
	rm -rf .pytest_cache __pycache__ .coverage htmlcov *.pyc
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ============================================================================
# CI/CD Helpers
# ============================================================================

ci-test: localstack-start test-all
	@echo "CI tests completed!"

ci-validate:
	@echo "Validating infrastructure policies..."
	@$(MAKE) test-opa
	@echo "Running pulumi preview..."
	pulumi preview

# ============================================================================
# Quick Development Workflows
# ============================================================================

# Quick test workflow for development
quick-test: localstack-sync test-unit
	@echo "Quick tests completed!"

# Full validation workflow
validate: localstack-start test-all ci-validate
	@echo "Full validation completed!"
