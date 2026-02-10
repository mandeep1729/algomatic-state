#!/usr/bin/env bash
#
# Launch script for trading agents
#
# Usage:
#   ./scripts/start_agent.sh                    # Run with defaults (AAPL, momentum)
#   ./scripts/start_agent.sh TSLA               # Run for TSLA
#   ./scripts/start_agent.sh TSLA --background  # Run in background
#   ./scripts/start_agent.sh --help             # Show help
#
# Environment variables (can be set in .env or overridden):
#   AGENT_SYMBOL             - Trading symbol (default: AAPL)
#   AGENT_INTERVAL_MINUTES   - Loop interval (default: 15)
#   AGENT_DATA_PROVIDER      - Data provider: alpaca or finnhub (default: alpaca)
#   AGENT_LOOKBACK_DAYS      - Days of historical data (default: 5)
#   AGENT_POSITION_SIZE_DOLLARS - Order size in dollars (default: 1)
#   AGENT_PAPER              - Paper trading mode (default: true)
#   AGENT_API_PORT           - Internal API port (default: 8000)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_help() {
    cat << EOF
${BLUE}Trading Agent Launcher${NC}

${YELLOW}Usage:${NC}
  $0 [SYMBOL] [OPTIONS]

${YELLOW}Arguments:${NC}
  SYMBOL              Trading symbol (default: AAPL)

${YELLOW}Options:${NC}
  -b, --background    Run agent in background
  -i, --interval MIN  Set interval in minutes (default: 15)
  -p, --provider PRV  Data provider: alpaca or finnhub (default: alpaca)
  -s, --size DOLLARS  Position size in dollars (default: 1)
  --live              Use live trading (default: paper)
  --port PORT         Internal API port (default: 8000)
  -h, --help          Show this help message

${YELLOW}Examples:${NC}
  $0                          # Trade AAPL with defaults
  $0 TSLA                     # Trade TSLA
  $0 GOOG --interval 5        # Trade GOOG every 5 minutes
  $0 AAPL --background        # Run in background
  $0 MSFT -i 30 -s 100        # Trade MSFT, 30min interval, \$100 position

${YELLOW}Environment Variables:${NC}
  Required:
    ALPACA_API_KEY            Alpaca API key
    ALPACA_SECRET_KEY         Alpaca secret key

  Optional (or use command-line options):
    AGENT_SYMBOL              Trading symbol
    AGENT_INTERVAL_MINUTES    Loop interval
    AGENT_DATA_PROVIDER       Data provider
    AGENT_POSITION_SIZE_DOLLARS  Order size
    AGENT_PAPER               Paper trading mode (true/false)

EOF
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default values
BACKGROUND=false
SYMBOL=""
INTERVAL=""
PROVIDER=""
SIZE=""
PAPER="true"
PORT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -b|--background)
            BACKGROUND=true
            shift
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -p|--provider)
            PROVIDER="$2"
            shift 2
            ;;
        -s|--size)
            SIZE="$2"
            shift 2
            ;;
        --live)
            PAPER="false"
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        -*)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
        *)
            # First non-option argument is the symbol
            if [[ -z "$SYMBOL" ]]; then
                SYMBOL="$1"
            else
                log_error "Unexpected argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

# Load .env file if it exists
if [[ -f .env ]]; then
    log_info "Loading environment from .env"
    set -a
    source .env
    set +a
else
    log_warn ".env file not found"
fi

# Check for required credentials
if [[ -z "$ALPACA_API_KEY" ]] || [[ -z "$ALPACA_SECRET_KEY" ]]; then
    log_error "Missing Alpaca credentials!"
    echo "  Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env or environment"
    exit 1
fi

# Override with command-line arguments
[[ -n "$SYMBOL" ]] && export AGENT_SYMBOL="$SYMBOL"
[[ -n "$INTERVAL" ]] && export AGENT_INTERVAL_MINUTES="$INTERVAL"
[[ -n "$PROVIDER" ]] && export AGENT_DATA_PROVIDER="$PROVIDER"
[[ -n "$SIZE" ]] && export AGENT_POSITION_SIZE_DOLLARS="$SIZE"
[[ -n "$PORT" ]] && export AGENT_API_PORT="$PORT"
export AGENT_PAPER="$PAPER"

# Display configuration
echo ""
echo -e "${BLUE}Agent Configuration:${NC}"
echo "  Symbol:       ${AGENT_SYMBOL:-AAPL}"
echo "  Interval:     ${AGENT_INTERVAL_MINUTES:-15} minutes"
echo "  Provider:     ${AGENT_DATA_PROVIDER:-alpaca}"
echo "  Position:     \$${AGENT_POSITION_SIZE_DOLLARS:-1}"
echo "  Mode:         $([ "$AGENT_PAPER" = "true" ] && echo "Paper" || echo "LIVE")"
echo "  API Port:     ${AGENT_API_PORT:-8000}"
echo ""

# Activate virtual environment
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
else
    log_error "Virtual environment not found at .venv/"
    exit 1
fi

# Create logs directory if needed
mkdir -p logs

# Run the agent
if [[ "$BACKGROUND" = true ]]; then
    LOG_FILE="logs/agent_${AGENT_SYMBOL:-AAPL}_$(date +%Y%m%d_%H%M%S).log"
    log_info "Starting agent in background..."
    log_info "Log file: $LOG_FILE"

    nohup python -m src.agent.main > "$LOG_FILE" 2>&1 &
    PID=$!

    echo "$PID" > "logs/agent_${AGENT_SYMBOL:-AAPL}.pid"
    log_info "Agent started with PID: $PID"
    echo ""
    echo "To monitor: tail -f $LOG_FILE"
    echo "To stop:    kill $PID"
else
    log_info "Starting agent in foreground (Ctrl+C to stop)..."
    echo ""
    python -m src.agent.main
fi
