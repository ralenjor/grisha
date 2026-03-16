#!/bin/bash
# KARKAS Unified Launcher
# Starts Grisha API + Karkas Server in a tmux session

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
SESSION_NAME="karkas"
VENV_PATH="./venv/bin/activate"
MODEL_NAME="qwen2.5:14b-instruct-q4_K_M"
GRISHA_PORT=8000
KARKAS_PORT=8080
HEALTH_CHECK_TIMEOUT=60
HEALTH_CHECK_INTERVAL=2

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                    KARKAS UNIFIED LAUNCHER                    ║"
    echo "║              Grisha RAG + Military Simulation                 ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_waiting() {
    echo -e "${YELLOW}[○]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    echo -n " "
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

check_prerequisites() {
    local missing=0

    echo "Checking prerequisites..."
    echo ""

    # Check tmux
    if command -v tmux &> /dev/null; then
        print_status "tmux installed"
    else
        print_error "tmux is not installed. Install with: sudo dnf install tmux"
        missing=1
    fi

    # Check virtual environment
    if [ -f "$VENV_PATH" ]; then
        print_status "Virtual environment found"
    else
        print_error "Virtual environment not found at $VENV_PATH"
        print_error "Create with: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        missing=1
    fi

    # Check Ollama
    if command -v ollama &> /dev/null; then
        print_status "Ollama installed"
    else
        print_error "Ollama is not installed. Install from: https://ollama.com"
        missing=1
    fi

    # Check PostgreSQL (optional but recommended)
    if command -v psql &> /dev/null; then
        print_status "PostgreSQL client installed"
    else
        print_warning "PostgreSQL client not found - persistence features may not work"
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        print_error "Prerequisites missing. Please install them and try again."
        exit 1
    fi

    echo ""
}

check_existing_session() {
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo ""
        print_warning "Session '$SESSION_NAME' already exists."
        echo ""
        echo "Options:"
        echo "  1) Attach to existing session: tmux attach -t $SESSION_NAME"
        echo "  2) Kill and restart: ./karkas-stop.sh && ./karkas.sh"
        echo ""
        read -p "Attach to existing session? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            exit 0
        else
            exec tmux attach -t "$SESSION_NAME"
        fi
    fi
}

start_postgresql() {
    echo -n "Checking PostgreSQL..."

    # Check if PostgreSQL is running
    if systemctl is-active --quiet postgresql 2>/dev/null; then
        print_status "PostgreSQL is running"
    else
        # Try to start it
        echo ""
        print_warning "PostgreSQL is not running. Attempting to start..."

        if sudo systemctl start postgresql 2>/dev/null; then
            sleep 2
            if systemctl is-active --quiet postgresql; then
                print_status "PostgreSQL started successfully"
            else
                print_warning "PostgreSQL failed to start - continuing without database"
            fi
        else
            print_warning "Could not start PostgreSQL - continuing without database"
        fi
    fi

    # Check if karkas database exists (optional)
    if command -v psql &> /dev/null && systemctl is-active --quiet postgresql 2>/dev/null; then
        if sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw karkas; then
            print_status "Database 'karkas' exists"
        else
            print_warning "Database 'karkas' not found - Karkas will run without persistence"
            echo "         Create with: sudo -u postgres createdb -O karkas karkas"
        fi
    fi
}

start_ollama() {
    echo -n "Checking Ollama service..."

    if systemctl is-active --quiet ollama 2>/dev/null; then
        echo ""
        print_status "Ollama is running"
    else
        echo ""
        print_warning "Ollama service is inactive. Starting..."
        sudo systemctl start ollama
        sleep 1
    fi

    # Wait for API to be ready
    echo -n "Waiting for Ollama API..."
    local max_retries=15
    local count=0
    while [ $count -lt $max_retries ]; do
        if curl -s -m 2 -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags 2>/dev/null | grep -q "200"; then
            echo ""
            print_status "Ollama API is ready"
            return 0
        fi
        count=$((count + 1))
        echo -n "."
        sleep 1
    done

    echo ""
    print_error "Ollama API not responding after ${max_retries}s"
    exit 1
}

preload_model() {
    echo -n "Pre-loading model ($MODEL_NAME)..."
    ollama run $MODEL_NAME "" --keepalive 30m > /dev/null 2>&1 &
    local pid=$!
    spinner $pid
    print_status "Model loaded"
}

start_services() {
    echo ""
    echo "Starting services in tmux session '$SESSION_NAME'..."

    # Create new tmux session with Grisha API in first pane
    tmux new-session -d -s "$SESSION_NAME" -n "services"

    # Configure the session
    tmux set-option -t "$SESSION_NAME" -g mouse on

    # First pane: Grisha API
    tmux send-keys -t "$SESSION_NAME:services" "cd '$SCRIPT_DIR' && source '$VENV_PATH' && echo -e '\\033[1;36m=== GRISHA API (port $GRISHA_PORT) ===\\033[0m' && echo '' && python3 grisha_api.py" C-m

    # Split horizontally for Karkas Server
    tmux split-window -t "$SESSION_NAME:services" -v

    # Second pane: Karkas Server (small delay to let Grisha start first)
    tmux send-keys -t "$SESSION_NAME:services.1" "cd '$SCRIPT_DIR/karkas' && source '$SCRIPT_DIR/$VENV_PATH' && echo -e '\\033[1;36m=== KARKAS SERVER (port $KARKAS_PORT) ===\\033[0m' && echo '' && sleep 2 && ./run_server.sh" C-m

    # Set pane titles (if terminal supports it)
    tmux select-pane -t "$SESSION_NAME:services.0" -T "Grisha API"
    tmux select-pane -t "$SESSION_NAME:services.1" -T "Karkas Server"

    # Even out pane sizes
    tmux select-layout -t "$SESSION_NAME:services" even-vertical
}

wait_for_services() {
    echo ""
    echo -e "${BOLD}Waiting for services to become healthy...${NC}"
    echo ""

    local grisha_ready=false
    local karkas_ready=false
    local elapsed=0

    while [ $elapsed -lt $HEALTH_CHECK_TIMEOUT ]; do
        # Check Grisha API
        if [ "$grisha_ready" = false ]; then
            if curl -s -m 2 "http://localhost:${GRISHA_PORT}/search?q=test" > /dev/null 2>&1; then
                grisha_ready=true
                print_status "Grisha API is ready (port $GRISHA_PORT)"
            fi
        fi

        # Check Karkas Server
        if [ "$karkas_ready" = false ]; then
            local health_response
            health_response=$(curl -s -m 2 "http://localhost:${KARKAS_PORT}/health" 2>/dev/null)
            if echo "$health_response" | grep -q '"status"' 2>/dev/null; then
                karkas_ready=true
                print_status "Karkas Server is ready (port $KARKAS_PORT)"

                # Check database status from health response
                if echo "$health_response" | grep -q '"database":.*"healthy"'; then
                    print_status "Database connection healthy"
                elif echo "$health_response" | grep -q '"database":.*"disabled"'; then
                    print_warning "Database persistence is disabled"
                fi
            fi
        fi

        # Both ready?
        if [ "$grisha_ready" = true ] && [ "$karkas_ready" = true ]; then
            echo ""
            echo -e "${GREEN}${BOLD}All services are ready!${NC}"
            return 0
        fi

        # Show waiting status
        if [ "$grisha_ready" = false ]; then
            printf "\r${YELLOW}[○]${NC} Waiting for Grisha API... (%ds)  " "$elapsed"
        elif [ "$karkas_ready" = false ]; then
            printf "\r${YELLOW}[○]${NC} Waiting for Karkas Server... (%ds)  " "$elapsed"
        fi

        sleep $HEALTH_CHECK_INTERVAL
        elapsed=$((elapsed + HEALTH_CHECK_INTERVAL))
    done

    # Timeout reached
    echo ""
    echo ""
    print_warning "Health check timeout reached (${HEALTH_CHECK_TIMEOUT}s)"

    if [ "$grisha_ready" = false ]; then
        print_error "Grisha API did not become ready"
    fi
    if [ "$karkas_ready" = false ]; then
        print_error "Karkas Server did not become ready"
    fi

    echo ""
    echo "Services may still be starting. Check the tmux session for details."
    echo ""
}

print_instructions() {
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────┐"
    echo "│  ${BOLD}ENDPOINTS${NC}                                                      │"
    echo "│    Grisha API:    http://localhost:${GRISHA_PORT}                          │"
    echo "│    Karkas Server: http://localhost:${KARKAS_PORT}                          │"
    echo "│    Karkas Docs:   http://localhost:${KARKAS_PORT}/docs                     │"
    echo "├─────────────────────────────────────────────────────────────────┤"
    echo "│  ${BOLD}TMUX CONTROLS${NC}                                                  │"
    echo "│    Ctrl-B D     Detach (services keep running)                  │"
    echo "│    Ctrl-B ↑/↓   Switch between panes                            │"
    echo "│    Ctrl-B [     Scroll mode (q to exit)                         │"
    echo "│    Ctrl-C       Stop service in current pane                    │"
    echo "├─────────────────────────────────────────────────────────────────┤"
    echo "│  ${BOLD}COMMANDS${NC}                                                       │"
    echo "│    tmux attach -t ${SESSION_NAME}    Reattach to session                 │"
    echo "│    ./karkas-stop.sh          Stop all services                  │"
    echo "└─────────────────────────────────────────────────────────────────┘"
    echo ""
    echo -e "Attaching to tmux session. Press ${BOLD}Ctrl-B D${NC} to detach."
    echo ""
    sleep 2
}

# Main
print_banner
check_prerequisites
check_existing_session
start_postgresql
start_ollama
preload_model
start_services
wait_for_services
print_instructions

# Attach to the session
exec tmux attach -t "$SESSION_NAME"
