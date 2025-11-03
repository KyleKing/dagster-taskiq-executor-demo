#!/bin/sh
set -euo pipefail

ROLE="${SERVICE_ROLE:-api}"

case "${ROLE}" in
  api)
    exec taskiq-demo-api "$@"
    ;;
  worker)
    exec taskiq-demo-worker "$@"
    ;;
  *)
    echo "Unknown SERVICE_ROLE: ${ROLE}" >&2
    exit 1
    ;;
esac

