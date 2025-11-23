package infrastructure.security

# Comprehensive tests for infrastructure security policies
#
# Following opa-testing skill:
# - Test both allow and deny cases
# - Descriptive test names
# - Arrange-Act-Assert pattern
# - Edge cases and null handling

import future.keywords.if

# ============================================================================
# Database Security Tests
# ============================================================================

test_deny_unencrypted_rds_cluster if {
    # Arrange: RDS cluster without encryption
    input := {
        "resources": [{
            "type": "aws:rds/cluster:Cluster",
            "name": "test-cluster",
            "properties": {
                "storageEncrypted": false,
                "backupRetentionPeriod": 7,
            },
        }],
        "environment": "dev",
    }

    # Act: Evaluate policy
    result := deny with input as input

    # Assert: Should deny
    count(result) > 0
    result[_] == "RDS cluster 'test-cluster' must have encryption at rest enabled"
}

test_allow_encrypted_rds_cluster if {
    input := {
        "resources": [{
            "type": "aws:rds/cluster:Cluster",
            "name": "test-cluster",
            "properties": {
                "storageEncrypted": true,
                "backupRetentionPeriod": 7,
                "deletionProtection": false,
                "publiclyAccessible": false,
                "tags": {
                    "Environment": "dev",
                    "Project": "test",
                    "ManagedBy": "Pulumi",
                },
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) == 0
}

test_deny_prod_rds_without_deletion_protection if {
    input := {
        "resources": [{
            "type": "aws:rds/cluster:Cluster",
            "name": "prod-cluster",
            "properties": {
                "storageEncrypted": true,
                "deletionProtection": false,
                "backupRetentionPeriod": 7,
            },
        }],
        "environment": "prod",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "RDS cluster 'prod-cluster' must have deletion protection enabled in production"
}

test_allow_dev_rds_without_deletion_protection if {
    # Deletion protection not required in dev
    input := {
        "resources": [{
            "type": "aws:rds/cluster:Cluster",
            "name": "dev-cluster",
            "properties": {
                "storageEncrypted": true,
                "deletionProtection": false,
                "backupRetentionPeriod": 7,
                "publiclyAccessible": false,
                "tags": {
                    "Environment": "dev",
                    "Project": "test",
                    "ManagedBy": "Pulumi",
                },
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    # Should not deny (deletion protection not required in dev)
    not contains_message(result, "deletion protection")
}

test_deny_insufficient_backup_retention if {
    input := {
        "resources": [{
            "type": "aws:rds/cluster:Cluster",
            "name": "test-cluster",
            "properties": {
                "storageEncrypted": true,
                "backupRetentionPeriod": 3,  # Less than 7 days
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "RDS cluster 'test-cluster' must have backup retention >= 7 days, got 3"
}

test_deny_publicly_accessible_prod_database if {
    input := {
        "resources": [{
            "type": "aws:rds/cluster:Cluster",
            "name": "prod-cluster",
            "properties": {
                "storageEncrypted": true,
                "publiclyAccessible": true,
                "backupRetentionPeriod": 7,
            },
        }],
        "environment": "prod",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "RDS cluster 'prod-cluster' must not be publicly accessible in production"
}

# ============================================================================
# Queue Security Tests
# ============================================================================

test_deny_non_fifo_queue if {
    input := {
        "resources": [{
            "type": "aws:sqs/queue:Queue",
            "name": "standard-queue",
            "properties": {
                "messageRetentionSeconds": 1209600,
                "redrivePolicy": `{"deadLetterTargetArn": "arn", "maxReceiveCount": 3}`,
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "SQS queue 'standard-queue' must be FIFO queue for message ordering"
}

test_allow_fifo_queue if {
    input := {
        "resources": [{
            "type": "aws:sqs/queue:Queue",
            "name": "my-queue.fifo",
            "properties": {
                "messageRetentionSeconds": 1209600,
                "redrivePolicy": `{"deadLetterTargetArn": "arn", "maxReceiveCount": 3}`,
                "tags": {
                    "Environment": "dev",
                    "Project": "test",
                    "ManagedBy": "Pulumi",
                },
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) == 0
}

test_deny_short_message_retention if {
    input := {
        "resources": [{
            "type": "aws:sqs/queue:Queue",
            "name": "queue.fifo",
            "properties": {
                "messageRetentionSeconds": 3600,  # 1 hour, less than 1 day
                "redrivePolicy": `{"deadLetterTargetArn": "arn"}`,
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "SQS queue 'queue.fifo' must retain messages for at least 1 day, got 3600 seconds"
}

test_deny_queue_without_dlq if {
    input := {
        "resources": [{
            "type": "aws:sqs/queue:Queue",
            "name": "queue.fifo",
            "properties": {
                "messageRetentionSeconds": 1209600,
                "redrivePolicy": "",  # No DLQ configured
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "SQS queue 'queue.fifo' must have a dead-letter queue configured"
}

# ============================================================================
# IAM Security Tests
# ============================================================================

test_deny_role_with_wildcard_principal if {
    input := {
        "resources": [{
            "type": "aws:iam/role:Role",
            "name": "bad-role",
            "properties": {
                "assumeRolePolicy": `{
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "sts:AssumeRole"
                    }]
                }`,
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "IAM role 'bad-role' must not allow assumption by all AWS principals (*)"
}

test_allow_role_with_specific_principal if {
    input := {
        "resources": [{
            "type": "aws:iam/role:Role",
            "name": "good-role",
            "properties": {
                "assumeRolePolicy": `{
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                }`,
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) == 0
}

test_deny_policy_with_full_access if {
    input := {
        "resources": [{
            "type": "aws:iam/rolePolicy:RolePolicy",
            "name": "admin-policy",
            "properties": {
                "policy": `{
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": "*",
                        "Resource": "*"
                    }]
                }`,
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "IAM policy 'admin-policy' must not grant full access (*:*)"
}

# ============================================================================
# Network Security Tests
# ============================================================================

test_deny_security_group_all_ports if {
    input := {
        "resources": [{
            "type": "aws:ec2/securityGroup:SecurityGroup",
            "name": "wide-open-sg",
            "properties": {
                "ingress": [{
                    "fromPort": 0,
                    "toPort": 65535,
                    "protocol": "tcp",
                    "cidrBlocks": ["10.0.0.0/8"],
                }],
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "Security group 'wide-open-sg' must not allow all ports (0-65535)"
}

test_deny_unrestricted_access_non_standard_port if {
    input := {
        "resources": [{
            "type": "aws:ec2/securityGroup:SecurityGroup",
            "name": "db-sg",
            "properties": {
                "ingress": [{
                    "fromPort": 5432,
                    "toPort": 5432,
                    "protocol": "tcp",
                    "cidrBlocks": ["0.0.0.0/0"],
                }],
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "Security group 'db-sg' must not allow unrestricted access (0.0.0.0/0) on port 5432"
}

test_allow_unrestricted_access_on_http_port if {
    # HTTP/HTTPS are allowed from internet (for load balancers)
    input := {
        "resources": [{
            "type": "aws:ec2/securityGroup:SecurityGroup",
            "name": "lb-sg",
            "properties": {
                "ingress": [{
                    "fromPort": 80,
                    "toPort": 80,
                    "protocol": "tcp",
                    "cidrBlocks": ["0.0.0.0/0"],
                }],
                "tags": {
                    "Environment": "dev",
                    "Project": "test",
                    "ManagedBy": "Pulumi",
                },
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    # Should not deny HTTP from internet
    not contains_message(result, "unrestricted access")
}

test_deny_ssh_from_internet if {
    input := {
        "resources": [{
            "type": "aws:ec2/securityGroupRule:SecurityGroupRule",
            "name": "ssh-rule",
            "properties": {
                "type": "ingress",
                "fromPort": 22,
                "toPort": 22,
                "protocol": "tcp",
                "cidrBlocks": ["0.0.0.0/0"],
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "Security group rule 'ssh-rule' must not allow SSH (port 22) from internet"
}

# ============================================================================
# ECS Security Tests
# ============================================================================

test_deny_privileged_container if {
    input := {
        "resources": [{
            "type": "aws:ecs/taskDefinition:TaskDefinition",
            "name": "bad-task",
            "properties": {
                "containerDefinitions": `[{
                    "name": "container",
                    "image": "nginx",
                    "privileged": true
                }]`,
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "ECS task definition 'bad-task' must not use privileged containers"
}

test_deny_public_ip_in_prod if {
    input := {
        "resources": [{
            "type": "aws:ecs/service:Service",
            "name": "web-service",
            "properties": {
                "launchType": "FARGATE",
                "networkConfiguration": {
                    "assignPublicIp": true,
                },
            },
        }],
        "environment": "prod",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "ECS service 'web-service' should not assign public IPs in production"
}

test_allow_public_ip_in_dev if {
    input := {
        "resources": [{
            "type": "aws:ecs/service:Service",
            "name": "web-service",
            "properties": {
                "launchType": "FARGATE",
                "networkConfiguration": {
                    "assignPublicIp": true,
                },
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    # Should not deny in dev
    not contains_message(result, "public IPs")
}

# ============================================================================
# Tagging Tests
# ============================================================================

test_deny_cluster_without_tags if {
    input := {
        "resources": [{
            "type": "aws:ecs/cluster:Cluster",
            "name": "my-cluster",
            "properties": {
                "tags": {},  # Missing required tags
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "Resource 'my-cluster' of type 'aws:ecs/cluster:Cluster' must have required tags: Environment, Project, ManagedBy"
}

test_allow_properly_tagged_cluster if {
    input := {
        "resources": [{
            "type": "aws:ecs/cluster:Cluster",
            "name": "my-cluster",
            "properties": {
                "tags": {
                    "Environment": "dev",
                    "Project": "test",
                    "ManagedBy": "Pulumi",
                },
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    count(result) == 0
}

# ============================================================================
# Service HA Tests
# ============================================================================

test_deny_single_instance_in_prod if {
    input := {
        "resources": [{
            "type": "aws:ecs/service:Service",
            "name": "web-service",
            "properties": {
                "desiredCount": 1,
            },
        }],
        "environment": "prod",
    }

    result := deny with input as input
    count(result) > 0
    result[_] == "ECS service 'web-service' should have at least 2 instances in production for HA"
}

test_allow_singleton_daemon_service if {
    # Daemon services are allowed to have 1 instance
    input := {
        "resources": [{
            "type": "aws:ecs/service:Service",
            "name": "daemon-service",
            "properties": {
                "desiredCount": 1,
            },
        }],
        "environment": "prod",
    }

    result := deny with input as input
    # Should not deny daemon service
    not contains_message(result, "at least 2 instances")
}

test_allow_single_instance_in_dev if {
    input := {
        "resources": [{
            "type": "aws:ecs/service:Service",
            "name": "web-service",
            "properties": {
                "desiredCount": 1,
            },
        }],
        "environment": "dev",
    }

    result := deny with input as input
    # Should not deny in dev
    not contains_message(result, "at least 2 instances")
}

# ============================================================================
# Helper Functions for Tests
# ============================================================================

contains_message(result_set, substring) if {
    msg := result_set[_]
    contains(msg, substring)
}

contains(str, substr) if {
    indexof(str, substr) >= 0
}
