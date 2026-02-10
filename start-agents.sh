#!/bin/bash
# Start trading agents with proper user permissions
#
# This script ensures log directories exist with correct ownership
# before Docker Compose creates them as root.

set -e

# Get current user's UID/GID (UID is readonly in bash, so use different names)
export DOCKER_UID=$(id -u)
export DOCKER_GID=$(id -g)

# Log directory base (must match docker-compose.agents.yml volume mounts)
LOG_BASE="/home/mandeep/projects/algomatic/logs"

# Create log directories with current user ownership
mkdir -p "$LOG_BASE"/{momentum-agent-logs,contrarian-agent-logs,breakout-agent-logs,vwap-agent-logs}

echo "Log directories ready at $LOG_BASE (owned by $DOCKER_UID:$DOCKER_GID)"
echo "Starting agents..."

# Pass through any arguments (e.g., "momentum-agent" to start specific agent)
exec docker compose -f docker-compose.agents.yml up "$@"
