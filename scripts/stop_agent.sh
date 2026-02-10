#!/usr/bin/env bash
#
# Stop trading agents
#
# Usage:
#   ./scripts/stop_agent.sh          # Stop all agents
#   ./scripts/stop_agent.sh AAPL     # Stop agent for specific symbol
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

cd "$PROJECT_ROOT"

SYMBOL="$1"

if [[ -n "$SYMBOL" ]]; then
    # Stop specific agent
    PID_FILE="logs/agent_${SYMBOL}.pid"
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            log_info "Stopping agent for $SYMBOL (PID: $PID)"
            kill "$PID"
            rm -f "$PID_FILE"
        else
            log_warn "Agent for $SYMBOL is not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        log_warn "No PID file found for $SYMBOL"
    fi
else
    # Stop all agents
    FOUND=false
    for PID_FILE in logs/agent_*.pid; do
        if [[ -f "$PID_FILE" ]]; then
            FOUND=true
            PID=$(cat "$PID_FILE")
            AGENT_NAME=$(basename "$PID_FILE" .pid)
            if kill -0 "$PID" 2>/dev/null; then
                log_info "Stopping $AGENT_NAME (PID: $PID)"
                kill "$PID"
            else
                log_warn "$AGENT_NAME is not running (stale PID file)"
            fi
            rm -f "$PID_FILE"
        fi
    done

    # Also kill any running agent processes not tracked by PID files
    AGENT_PIDS=$(pgrep -f "python -m src.agent.main" 2>/dev/null || true)
    if [[ -n "$AGENT_PIDS" ]]; then
        FOUND=true
        for PID in $AGENT_PIDS; do
            log_info "Stopping untracked agent (PID: $PID)"
            kill "$PID" 2>/dev/null || true
        done
    fi

    if [[ "$FOUND" = false ]]; then
        log_warn "No running agents found"
    fi
fi

log_info "Done"
