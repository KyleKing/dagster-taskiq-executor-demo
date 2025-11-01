#!/usr/bin/env bash
set -euo pipefail

# Database initialization script for Dagster schema
# This script sets up the PostgreSQL database with proper configuration for Dagster workloads

PROJECT_NAME="dagster-taskiq-demo"
ENVIRONMENT="dev"
DB_IDENTIFIER="${PROJECT_NAME}-rds-${ENVIRONMENT}"
DB_NAME="dagster"
DB_USER="dagster"
DB_PASSWORD="dagster"

log() {
    echo "[localstack:db-init] $*"
}

get_rds_endpoint() {
    awslocal rds describe-db-instances \
        --db-instance-identifier "${DB_IDENTIFIER}" \
        --query "DBInstances[0].Endpoint.Address" \
        --output text 2>/dev/null || echo ""
}

wait_for_postgres() {
    local endpoint=$1
    local max_attempts=30
    local attempt=1
    
    log "Waiting for PostgreSQL to accept connections on ${endpoint}..."
    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "${endpoint}" -p 5432 -U "${DB_USER}" >/dev/null 2>&1; then
            log "PostgreSQL is ready"
            return 0
        fi
        log "Attempt $attempt/$max_attempts: PostgreSQL not ready yet"
        sleep 2
        ((attempt++))
    done
    
    log "ERROR: PostgreSQL failed to become ready after $max_attempts attempts"
    return 1
}

create_dagster_extensions() {
    local endpoint=$1
    
    log "Creating PostgreSQL extensions for Dagster..."
    
    # Create extensions that Dagster might use
    PGPASSWORD="${DB_PASSWORD}" psql -h "${endpoint}" -p 5432 -U "${DB_USER}" -d "${DB_NAME}" -c "
        -- Create extensions if they don't exist
        CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";
        CREATE EXTENSION IF NOT EXISTS \"pg_stat_statements\";
        
        -- Set optimal configuration for Dagster workloads
        -- These would normally be in postgresql.conf, but we'll set them per session
        -- Note: Some settings may not persist in LocalStack
        
        -- Increase work memory for complex queries
        SET work_mem = '16MB';
        
        -- Increase shared buffers (this won't persist but shows intent)
        -- SET shared_buffers = '128MB';  -- Can't set this at runtime
        
        -- Enable query logging for debugging
        SET log_statement = 'all';
        SET log_min_duration_statement = 1000;  -- Log queries taking > 1s
        
        -- Optimize for Dagster's access patterns
        SET random_page_cost = 1.1;  -- Assume SSD storage
        SET effective_cache_size = '256MB';
        
        -- Create a simple health check function
        CREATE OR REPLACE FUNCTION dagster_health_check() 
        RETURNS TEXT AS \$\$
        BEGIN
            RETURN 'Dagster database is healthy at ' || NOW();
        END;
        \$\$ LANGUAGE plpgsql;
        
        -- Grant necessary permissions
        GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
        
        -- Create a schema for Dagster if it doesn't exist
        CREATE SCHEMA IF NOT EXISTS dagster AUTHORIZATION ${DB_USER};
        GRANT ALL PRIVILEGES ON SCHEMA dagster TO ${DB_USER};
    " || {
        log "WARNING: Failed to create extensions or configure database"
        return 1
    }
    
    log "Database extensions and configuration completed"
    return 0
}

verify_database_setup() {
    local endpoint=$1
    
    log "Verifying database setup..."
    
    PGPASSWORD="${DB_PASSWORD}" psql -h "${endpoint}" -p 5432 -U "${DB_USER}" -d "${DB_NAME}" -c "
        SELECT 
            'Database: ' || current_database() as info
        UNION ALL
        SELECT 
            'User: ' || current_user
        UNION ALL
        SELECT 
            'Extensions: ' || string_agg(extname, ', ') 
        FROM pg_extension 
        WHERE extname IN ('uuid-ossp', 'pg_stat_statements')
        UNION ALL
        SELECT 
            'Health Check: ' || dagster_health_check();
    " || {
        log "WARNING: Database verification failed"
        return 1
    }
    
    log "Database verification completed successfully"
    return 0
}

main() {
    log "Starting Dagster database initialization"
    
    # Check if PostgreSQL client tools are available
    if ! command -v psql >/dev/null 2>&1; then
        log "WARNING: psql not available, skipping database initialization"
        log "Database schema will be created by Dagster daemon on first startup"
        return 0
    fi
    
    if ! command -v pg_isready >/dev/null 2>&1; then
        log "WARNING: pg_isready not available, skipping connection check"
    fi
    
    # Get RDS endpoint
    local endpoint=$(get_rds_endpoint)
    if [ -z "$endpoint" ]; then
        log "WARNING: Could not get RDS endpoint, skipping database initialization"
        return 1
    fi
    
    log "Found RDS endpoint: ${endpoint}"
    
    # Wait for PostgreSQL to be ready (if pg_isready is available)
    if command -v pg_isready >/dev/null 2>&1; then
        if ! wait_for_postgres "${endpoint}"; then
            log "WARNING: PostgreSQL not ready, skipping initialization"
            return 1
        fi
    fi
    
    # Initialize database
    if create_dagster_extensions "${endpoint}"; then
        verify_database_setup "${endpoint}"
    fi
    
    log "Dagster database initialization completed"
}

# Only run if executed directly (not sourced)
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi