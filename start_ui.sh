#!/bin/bash
#
# Start SAP Agent Web UI
#
# Usage:
#   ./start_ui.sh           # Start with PRD environment
#   ./start_ui.sh TST       # Start with TST environment
#   ./start_ui.sh PRD 8080  # Start with PRD on port 8080
#

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-PRD}"
PORT="${2:-8080}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           SAP Agent Web UI - Launcher                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
echo -e "${GREEN}Port:${NC} $PORT"
echo -e "${GREEN}URL:${NC} http://localhost:$PORT"
echo ""

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo -e "${YELLOW}Installing Flask dependencies...${NC}"
    pip install -q Flask flask-cors
fi

# Check if port is available
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port $PORT is already in use!${NC}"
    echo -e "${YELLOW}   Trying to use port $((PORT + 1)) instead...${NC}"
    PORT=$((PORT + 1))
fi

echo ""
echo -e "${GREEN}Starting web server...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Start the server
AGENT_ENV=$ENVIRONMENT PORT=$PORT python3 app.py
