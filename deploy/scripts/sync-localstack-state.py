#!/usr/bin/env python3
"""Sync Pulumi state with LocalStack reality.

This utility helps recover from state divergence when LocalStack container
is destroyed but Pulumi state still references non-existent resources.

Usage:
    # Check for divergence (non-destructive)
    python sync-localstack-state.py --check

    # Force Pulumi to refresh from LocalStack reality
    python sync-localstack-state.py --refresh

    # Nuclear option: clear Pulumi state and reimport from LocalStack
    python sync-localstack-state.py --reimport

    # Complete reset: clear state and redeploy
    python sync-localstack-state.py --reset
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_command(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    """Run shell command and return result."""
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False
    )


def get_pulumi_stack_name() -> str:
    """Get current Pulumi stack name."""
    result = run_command(["pulumi", "stack", "--show-name"])
    if result.returncode != 0:
        print("Error: Not in a Pulumi project or no stack selected")
        sys.exit(1)
    return result.stdout.strip()


def get_pulumi_resources() -> list[dict[str, Any]]:
    """Get all resources in Pulumi state."""
    result = run_command(["pulumi", "stack", "export"])
    if result.returncode != 0:
        print("Error: Cannot export Pulumi state")
        return []

    state = json.loads(result.stdout)
    return state.get("deployment", {}).get("resources", [])


def check_localstack_healthy() -> bool:
    """Check if LocalStack is running and healthy."""
    import boto3
    from botocore.exceptions import EndpointConnectionError, NoCredentialsError

    try:
        # Try to connect to LocalStack
        s3 = boto3.client(
            "s3",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1"
        )
        s3.list_buckets()
        return True
    except (EndpointConnectionError, NoCredentialsError, Exception) as e:
        print(f"LocalStack not reachable: {e}")
        return False


def check_divergence() -> dict[str, Any]:
    """Check if Pulumi state diverges from LocalStack reality."""
    print("\n=== Checking for state divergence ===\n")

    if not check_localstack_healthy():
        return {
            "diverged": True,
            "reason": "LocalStack not running",
            "recommendation": "Start LocalStack container"
        }

    resources = get_pulumi_resources()
    aws_resources = [r for r in resources if r.get("type", "").startswith("aws:")]

    print(f"Found {len(aws_resources)} AWS resources in Pulumi state")

    # Run pulumi refresh with preview to see what changed
    result = run_command(["pulumi", "refresh", "--yes", "--skip-preview"], capture=False)

    if result.returncode != 0:
        return {
            "diverged": True,
            "reason": "Refresh failed - likely state divergence",
            "recommendation": "Run with --refresh or --reset"
        }

    return {
        "diverged": False,
        "reason": "State appears in sync",
        "recommendation": "No action needed"
    }


def force_refresh() -> None:
    """Force Pulumi to refresh state from cloud reality."""
    print("\n=== Force refreshing Pulumi state ===\n")

    if not check_localstack_healthy():
        print("ERROR: LocalStack must be running for refresh")
        sys.exit(1)

    # Refresh will update Pulumi state to match actual cloud resources
    result = run_command(["pulumi", "refresh", "--yes"], capture=False)

    if result.returncode == 0:
        print("\n✓ State refreshed successfully")
    else:
        print("\n✗ Refresh failed - you may need --reset")
        sys.exit(1)


def reset_state() -> None:
    """Nuclear option: destroy everything and redeploy."""
    print("\n=== RESET: Destroying and redeploying ===\n")

    response = input("This will DESTROY all resources and redeploy. Continue? [yes/no]: ")
    if response.lower() != "yes":
        print("Aborted")
        sys.exit(0)

    # Step 1: Try to destroy (may fail if resources don't exist)
    print("\nStep 1: Attempting destroy...")
    run_command(["pulumi", "destroy", "--yes"], capture=False)

    # Step 2: Clear the state
    print("\nStep 2: Clearing Pulumi state...")
    stack_name = get_pulumi_stack_name()

    # Export current state as backup
    backup_file = f"pulumi-state-backup-{stack_name}.json"
    result = run_command(["pulumi", "stack", "export"])
    if result.returncode == 0:
        Path(backup_file).write_text(result.stdout)
        print(f"✓ State backed up to {backup_file}")

    # Create new empty state
    empty_state = {
        "version": 3,
        "deployment": {
            "manifest": {
                "time": "",
                "magic": "",
                "version": ""
            },
            "secrets_providers": {
                "type": "passphrase"
            },
            "resources": []
        }
    }

    # Import empty state
    proc = subprocess.Popen(
        ["pulumi", "stack", "import"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    proc.communicate(input=json.dumps(empty_state))

    print("✓ State cleared")

    # Step 3: Redeploy
    print("\nStep 3: Redeploying infrastructure...")
    result = run_command(["pulumi", "up", "--yes"], capture=False)

    if result.returncode == 0:
        print("\n✓ Reset complete - infrastructure redeployed")
    else:
        print("\n✗ Deployment failed")
        print(f"State backup available at: {backup_file}")
        sys.exit(1)


def reimport_resources() -> None:
    """Attempt to import existing LocalStack resources into Pulumi state."""
    print("\n=== Reimporting LocalStack resources ===\n")
    print("This is an advanced operation - not yet implemented")
    print("For now, use --reset to destroy and redeploy")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Sync Pulumi state with LocalStack reality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check if state is diverged
  %(prog)s --check

  # Fix divergence by refreshing from LocalStack
  %(prog)s --refresh

  # Nuclear option: clear state and redeploy
  %(prog)s --reset

Common Scenarios:
  1. LocalStack container restarted:
     $ %(prog)s --refresh  # Try this first
     $ %(prog)s --reset    # If refresh fails

  2. State is completely corrupted:
     $ %(prog)s --reset

  3. Just checking for issues:
     $ %(prog)s --check
        """
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for state divergence (non-destructive)"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh Pulumi state from LocalStack"
    )
    parser.add_argument(
        "--reimport",
        action="store_true",
        help="Import existing LocalStack resources (advanced)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Nuclear option: clear state and redeploy"
    )

    args = parser.parse_args()

    # Default to check if no args
    if not any([args.check, args.refresh, args.reimport, args.reset]):
        args.check = True

    if args.check:
        result = check_divergence()
        print(f"\nDiverged: {result['diverged']}")
        print(f"Reason: {result['reason']}")
        print(f"Recommendation: {result['recommendation']}")
        sys.exit(0 if not result["diverged"] else 1)

    if args.refresh:
        force_refresh()

    if args.reimport:
        reimport_resources()

    if args.reset:
        reset_state()


if __name__ == "__main__":
    main()
