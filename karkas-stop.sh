#!/bin/bash
# KARKAS Stop Script
# Stops all services by killing the tmux session

SESSION_NAME="karkas"
GRISHA_PORT=8000
KARKAS_PORT=8080

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                      KARKAS SHUTDOWN                          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check current service status
echo "Current status:"

# Check Grisha API
if curl -s -m 1 "http://localhost:${GRISHA_PORT}/search?q=test" > /dev/null 2>&1; then
    echo -e "  Grisha API (port $GRISHA_PORT):  ${GREEN}running${NC}"
    grisha_was_running=true
else
    echo -e "  Grisha API (port $GRISHA_PORT):  ${YELLOW}not responding${NC}"
    grisha_was_running=false
fi

# Check Karkas Server
if curl -s -m 1 "http://localhost:${KARKAS_PORT}/health" > /dev/null 2>&1; then
    echo -e "  Karkas Server (port $KARKAS_PORT): ${GREEN}running${NC}"
    karkas_was_running=true
else
    echo -e "  Karkas Server (port $KARKAS_PORT): ${YELLOW}not responding${NC}"
    karkas_was_running=false
fi

# Check tmux session
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "  tmux session '$SESSION_NAME':    ${GREEN}active${NC}"
    session_exists=true
else
    echo -e "  tmux session '$SESSION_NAME':    ${YELLOW}not found${NC}"
    session_exists=false
fi

echo ""

# Kill the session if it exists
if [ "$session_exists" = true ]; then
    echo -e "${YELLOW}Stopping services...${NC}"
    tmux kill-session -t "$SESSION_NAME"

    # Brief wait for processes to terminate
    sleep 1

    echo ""
    echo -e "${GREEN}[✓]${NC} tmux session '$SESSION_NAME' terminated"

    if [ "$grisha_was_running" = true ]; then
        echo -e "${GREEN}[✓]${NC} Grisha API stopped"
    fi
    if [ "$karkas_was_running" = true ]; then
        echo -e "${GREEN}[✓]${NC} Karkas Server stopped"
    fi
else
    echo -e "${YELLOW}[!]${NC} No tmux session '$SESSION_NAME' to stop"

    # Check if ports are still in use (orphaned processes)
    if [ "$grisha_was_running" = true ] || [ "$karkas_was_running" = true ]; then
        echo ""
        echo -e "${YELLOW}Warning:${NC} Services appear to be running outside of tmux."
        echo "You may need to manually kill them:"

        if [ "$grisha_was_running" = true ]; then
            pid=$(lsof -ti:$GRISHA_PORT 2>/dev/null)
            if [ -n "$pid" ]; then
                echo "  kill $pid  # Grisha API on port $GRISHA_PORT"
            fi
        fi

        if [ "$karkas_was_running" = true ]; then
            pid=$(lsof -ti:$KARKAS_PORT 2>/dev/null)
            if [ -n "$pid" ]; then
                echo "  kill $pid  # Karkas Server on port $KARKAS_PORT"
            fi
        fi
    fi
fi

echo ""
echo "Note: PostgreSQL and Ollama remain running (managed by systemd)"
echo ""
