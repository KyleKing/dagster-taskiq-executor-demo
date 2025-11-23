package infrastructure.security

# Infrastructure security policies for Dagster + TaskIQ deployment
#
# Validates:
# - Database encryption
# - Queue security
# - IAM least privilege
# - Network security
# - Resource tagging

import future.keywords.if
import future.keywords.in

# Default deny
default allow := false

# Allow if no security violations
allow if {
    count(deny) == 0
}

# ============================================================================
# Database Security Policies
# ============================================================================

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:rds/cluster:Cluster"
    not resource.properties.storageEncrypted
    msg := sprintf("RDS cluster '%s' must have encryption at rest enabled", [resource.name])
}

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:rds/cluster:Cluster"
    resource.properties.deletionProtection == false
    contains(input.environment, "prod")
    msg := sprintf("RDS cluster '%s' must have deletion protection enabled in production", [resource.name])
}

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:rds/cluster:Cluster"
    resource.properties.backupRetentionPeriod < 7
    msg := sprintf("RDS cluster '%s' must have backup retention >= 7 days, got %d", [
        resource.name,
        resource.properties.backupRetentionPeriod,
    ])
}

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:rds/cluster:Cluster"
    resource.properties.publiclyAccessible == true
    contains(input.environment, "prod")
    msg := sprintf("RDS cluster '%s' must not be publicly accessible in production", [resource.name])
}

# ============================================================================
# Queue Security Policies
# ============================================================================

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:sqs/queue:Queue"
    not endswith(resource.name, ".fifo")
    msg := sprintf("SQS queue '%s' must be FIFO queue for message ordering", [resource.name])
}

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:sqs/queue:Queue"
    resource.properties.messageRetentionSeconds < 86400  # 1 day
    msg := sprintf("SQS queue '%s' must retain messages for at least 1 day, got %d seconds", [
        resource.name,
        resource.properties.messageRetentionSeconds,
    ])
}

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:sqs/queue:Queue"
    not has_dead_letter_queue(resource)
    msg := sprintf("SQS queue '%s' must have a dead-letter queue configured", [resource.name])
}

has_dead_letter_queue(queue) if {
    queue.properties.redrivePolicy
    queue.properties.redrivePolicy != ""
}

# ============================================================================
# IAM Security Policies
# ============================================================================

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:iam/role:Role"
    policy := json.unmarshal(resource.properties.assumeRolePolicy)
    statement := policy.Statement[_]
    statement.Effect == "Allow"
    statement.Principal.AWS == "*"
    msg := sprintf("IAM role '%s' must not allow assumption by all AWS principals (*)", [resource.name])
}

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:iam/rolePolicy:RolePolicy"
    policy := json.unmarshal(resource.properties.policy)
    statement := policy.Statement[_]
    statement.Effect == "Allow"
    statement.Action == "*"
    statement.Resource == "*"
    msg := sprintf("IAM policy '%s' must not grant full access (*:*)", [resource.name])
}

# ============================================================================
# Network Security Policies
# ============================================================================

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:ec2/securityGroup:SecurityGroup"
    rule := resource.properties.ingress[_]
    rule.fromPort == 0
    rule.toPort == 65535
    msg := sprintf("Security group '%s' must not allow all ports (0-65535)", [resource.name])
}

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:ec2/securityGroup:SecurityGroup"
    rule := resource.properties.ingress[_]
    cidr := rule.cidrBlocks[_]
    cidr == "0.0.0.0/0"
    not is_allowed_public_port(rule.fromPort)
    msg := sprintf("Security group '%s' must not allow unrestricted access (0.0.0.0/0) on port %d", [
        resource.name,
        rule.fromPort,
    ])
}

# Allowed public ports (typically load balancer)
is_allowed_public_port(port) if port == 80
is_allowed_public_port(port) if port == 443

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:ec2/securityGroupRule:SecurityGroupRule"
    resource.properties.type == "ingress"
    resource.properties.fromPort == 22
    cidr := resource.properties.cidrBlocks[_]
    cidr == "0.0.0.0/0"
    msg := sprintf("Security group rule '%s' must not allow SSH (port 22) from internet", [resource.name])
}

# ============================================================================
# ECS Security Policies
# ============================================================================

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:ecs/taskDefinition:TaskDefinition"
    container := json.unmarshal(resource.properties.containerDefinitions)[_]
    container.privileged == true
    msg := sprintf("ECS task definition '%s' must not use privileged containers", [resource.name])
}

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:ecs/service:Service"
    resource.properties.launchType == "FARGATE"
    network_config := resource.properties.networkConfiguration
    network_config.assignPublicIp == true
    contains(input.environment, "prod")
    msg := sprintf("ECS service '%s' should not assign public IPs in production", [resource.name])
}

# ============================================================================
# Resource Tagging Policies
# ============================================================================

deny[msg] {
    resource := input.resources[_]
    requires_tags(resource.type)
    not has_required_tags(resource)
    msg := sprintf("Resource '%s' of type '%s' must have required tags: Environment, Project, ManagedBy", [
        resource.name,
        resource.type,
    ])
}

requires_tags(resource_type) if {
    taggable_types := {
        "aws:rds/cluster:Cluster",
        "aws:sqs/queue:Queue",
        "aws:ec2/securityGroup:SecurityGroup",
        "aws:ecs/cluster:Cluster",
        "aws:ecs/service:Service",
        "aws:lb/loadBalancer:LoadBalancer",
    }
    resource_type in taggable_types
}

has_required_tags(resource) if {
    resource.properties.tags
    resource.properties.tags.Environment
    resource.properties.tags.Project
    resource.properties.tags.ManagedBy
}

# ============================================================================
# Load Balancer Security Policies
# ============================================================================

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:lb/loadBalancer:LoadBalancer"
    resource.properties.internal == false
    not has_ssl_listener(resource.name)
    contains(input.environment, "prod")
    msg := sprintf("Internet-facing load balancer '%s' should have HTTPS listener in production", [resource.name])
}

has_ssl_listener(lb_name) if {
    resource := input.resources[_]
    resource.type == "aws:lb/listener:Listener"
    contains(resource.name, lb_name)
    resource.properties.protocol == "HTTPS"
}

# ============================================================================
# Service Configuration Policies
# ============================================================================

deny[msg] {
    resource := input.resources[_]
    resource.type == "aws:ecs/service:Service"
    resource.properties.desiredCount < 2
    contains(input.environment, "prod")
    not is_singleton_service(resource.name)
    msg := sprintf("ECS service '%s' should have at least 2 instances in production for HA", [resource.name])
}

# Singleton services that are allowed to have 1 instance
is_singleton_service(name) if contains(name, "daemon")
is_singleton_service(name) if contains(name, "auto-scaler")

# ============================================================================
# Helper Functions
# ============================================================================

# Check if a string contains a substring
contains(str, substr) if {
    indexof(str, substr) >= 0
}
