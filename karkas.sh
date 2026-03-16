#!/bin/bash
# KARKAS Interactive Game Launcher
# Menu-driven interface for setting up and starting Karkas games

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Configuration ---
SERVER_URL="http://localhost:8080"
GRISHA_URL="http://localhost:8000"
VENV_PATH="./venv/bin/activate"
SESSION_NAME="karkas"

# --- State ---
SELECTED_SCENARIO=""
SELECTED_SCENARIO_NAME=""
BLUE_PLAYER="human"  # human | ai
RED_PLAYER="ai"      # human | ai
SERVER_STATUS="offline"
SERVER_TURN=0
SERVER_PHASE="unknown"

# --- Colors ---
RED_COLOR='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# --- Prerequisites Check ---
check_prerequisites() {
    local missing=0

    # Check jq
    if ! command -v jq &> /dev/null; then
        echo -e "${RED_COLOR}[!]${NC} jq is not installed. Install with: sudo dnf install jq"
        missing=1
    fi

    # Check curl
    if ! command -v curl &> /dev/null; then
        echo -e "${RED_COLOR}[!]${NC} curl is not installed. Install with: sudo dnf install curl"
        missing=1
    fi

    # Check tmux
    if ! command -v tmux &> /dev/null; then
        echo -e "${RED_COLOR}[!]${NC} tmux is not installed. Install with: sudo dnf install tmux"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        echo -e "${RED_COLOR}Prerequisites missing. Please install them and try again.${NC}"
        exit 1
    fi
}

# --- Server Functions ---
check_server_status() {
    local response
    response=$(curl -s -m 2 "$SERVER_URL/health" 2>/dev/null) || true

    if [ -n "$response" ] && echo "$response" | jq -e '.status' &>/dev/null; then
        SERVER_STATUS="online"
        SERVER_TURN=$(echo "$response" | jq -r '.turn // 0')
        SERVER_PHASE=$(echo "$response" | jq -r '.phase // "unknown"')
    else
        SERVER_STATUS="offline"
        SERVER_TURN=0
        SERVER_PHASE="unknown"
    fi
}

start_server_background() {
    echo -e "${YELLOW}Starting server...${NC}"

    # Run karkas-server.sh without attaching
    # The server script normally attaches to tmux at the end, so we run it differently

    # Check if session already exists
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo -e "${YELLOW}Server session already exists, checking health...${NC}"
    else
        # Start the server in background - we'll create the tmux session ourselves
        tmux new-session -d -s "$SESSION_NAME" -n "services"
        tmux set-option -t "$SESSION_NAME" -g mouse on

        # First pane: Grisha API
        tmux send-keys -t "$SESSION_NAME:services" "cd '$SCRIPT_DIR' && source '$VENV_PATH' && echo -e '\\033[1;36m=== GRISHA API (port 8000) ===\\033[0m' && echo '' && python3 grisha_api.py" C-m

        # Split for Karkas Server
        tmux split-window -t "$SESSION_NAME:services" -v

        # Second pane: Karkas Server
        tmux send-keys -t "$SESSION_NAME:services.1" "cd '$SCRIPT_DIR/karkas' && source '$SCRIPT_DIR/$VENV_PATH' && echo -e '\\033[1;36m=== KARKAS SERVER (port 8080) ===\\033[0m' && echo '' && sleep 2 && ./run_server.sh" C-m

        # Even out pane sizes
        tmux select-layout -t "$SESSION_NAME:services" even-vertical
    fi

    # Wait for server to become healthy
    echo -n "Waiting for server"
    local max_wait=60
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        check_server_status
        if [ "$SERVER_STATUS" = "online" ]; then
            echo ""
            echo -e "${GREEN}Server is online!${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done

    echo ""
    echo -e "${RED_COLOR}Server did not become healthy in ${max_wait}s${NC}"
    echo "Check the tmux session: tmux attach -t $SESSION_NAME"
    return 1
}

# --- Scenario Functions ---
fetch_scenarios() {
    local response
    response=$(curl -s -m 5 "$SERVER_URL/api/scenarios" 2>/dev/null) || true

    if [ -n "$response" ]; then
        echo "$response" | jq -r '.scenarios[] | "\(.id)|\(.name)|\(.description)|\(.red_faction_name)|\(.blue_faction_name)"' 2>/dev/null
    fi
}

load_scenario() {
    local scenario_id="$1"
    local response
    response=$(curl -s -X POST "$SERVER_URL/api/scenarios/$scenario_id/load" 2>/dev/null) || true

    if echo "$response" | jq -e '.scenario' &>/dev/null; then
        return 0
    else
        echo -e "${RED_COLOR}Failed to load scenario${NC}"
        echo "$response" | jq -r '.detail // .message // "Unknown error"' 2>/dev/null
        return 1
    fi
}

# --- AI Control Functions ---
configure_ai() {
    # Enable/disable AI for each faction based on player selections

    if [ "$BLUE_PLAYER" = "ai" ]; then
        curl -s -X POST "$SERVER_URL/api/grisha/enable/blue" >/dev/null 2>&1
    else
        curl -s -X POST "$SERVER_URL/api/grisha/disable/blue" >/dev/null 2>&1
    fi

    if [ "$RED_PLAYER" = "ai" ]; then
        curl -s -X POST "$SERVER_URL/api/grisha/enable/red" >/dev/null 2>&1
    else
        curl -s -X POST "$SERVER_URL/api/grisha/disable/red" >/dev/null 2>&1
    fi
}

# --- Display Functions ---
clear_screen() {
    printf '\033[2J\033[H'
}

draw_box_top() {
    echo -e "${CYAN}+-----------------------------------------------------------------------+${NC}"
}

draw_box_bottom() {
    echo -e "${CYAN}+-----------------------------------------------------------------------+${NC}"
}

draw_box_line() {
    local content="$1"
    local width=71
    local padding=$((width - ${#content}))
    echo -e "${CYAN}|${NC} ${content}$(printf '%*s' $padding '')${CYAN}|${NC}"
}

draw_box_empty() {
    echo -e "${CYAN}|${NC}$(printf '%*s' 71 '')${CYAN}|${NC}"
}

draw_box_separator() {
    echo -e "${CYAN}+-----------------------------------------------------------------------+${NC}"
}

display_menu() {
    clear_screen

    # Header
    echo -e "${CYAN}${BOLD}"
    echo "+-----------------------------------------------------------------------+"
    echo "|                          KARKAS LAUNCHER                             |"
    echo "+-----------------------------------------------------------------------+"
    echo -e "${NC}"

    # Server status
    local status_color="$RED_COLOR"
    local status_icon="x"
    local status_text="Offline"

    if [ "$SERVER_STATUS" = "online" ]; then
        status_color="$GREEN"
        status_icon="*"
        status_text="Online (Turn $SERVER_TURN, Phase: $SERVER_PHASE)"
    fi

    echo -e "${CYAN}|${NC}  Server Status: ${status_color}${status_icon} ${status_text}${NC}"
    printf '%*s' $((54 - ${#status_text})) ''
    echo -e "${CYAN}|${NC}"
    echo -e "${CYAN}+-----------------------------------------------------------------------+${NC}"
    echo -e "${CYAN}|${NC}                                                                       ${CYAN}|${NC}"

    # Menu options
    # 1. Select Scenario
    local scenario_display="(none selected)"
    if [ -n "$SELECTED_SCENARIO_NAME" ]; then
        scenario_display="$SELECTED_SCENARIO_NAME"
    fi
    echo -e "${CYAN}|${NC}  ${BOLD}1.${NC} Select Scenario                                                   ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}     ${DIM}>${NC} ${GREEN}${scenario_display}${NC}"
    printf '%*s' $((60 - ${#scenario_display})) ''
    echo -e "${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                                       ${CYAN}|${NC}"

    # 2. Blue Force
    local blue_human="Human Player"
    local blue_ai="AI (Grisha)"
    local blue_human_marker=""
    local blue_ai_marker=""
    if [ "$BLUE_PLAYER" = "human" ]; then
        blue_human_marker="${BOLD}[${NC}${BLUE}${blue_human}${NC}${BOLD}]${NC}"
        blue_ai_marker="${DIM}${blue_ai}${NC}"
    else
        blue_human_marker="${DIM}${blue_human}${NC}"
        blue_ai_marker="${BOLD}[${NC}${BLUE}${blue_ai}${NC}${BOLD}]${NC}"
    fi
    echo -e "${CYAN}|${NC}  ${BOLD}2.${NC} Blue Force (NATO)                                                 ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}     ${DIM}>${NC} ${blue_human_marker}  /  ${blue_ai_marker}                       ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                                       ${CYAN}|${NC}"

    # 3. Red Force
    local red_human="Human Player"
    local red_ai="AI (General Svistunov)"
    local red_human_marker=""
    local red_ai_marker=""
    if [ "$RED_PLAYER" = "human" ]; then
        red_human_marker="${BOLD}[${NC}${RED_COLOR}${red_human}${NC}${BOLD}]${NC}"
        red_ai_marker="${DIM}${red_ai}${NC}"
    else
        red_human_marker="${DIM}${red_human}${NC}"
        red_ai_marker="${BOLD}[${NC}${RED_COLOR}${red_ai}${NC}${BOLD}]${NC}"
    fi
    echo -e "${CYAN}|${NC}  ${BOLD}3.${NC} Red Force (Warsaw Pact)                                           ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}     ${DIM}>${NC} ${red_human_marker}  /  ${red_ai_marker}                       ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                                       ${CYAN}|${NC}"

    # 4. Start Game
    echo -e "${CYAN}|${NC}  ${BOLD}4.${NC} ${GREEN}Start Game${NC}                                                        ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                                       ${CYAN}|${NC}"

    # Server management
    echo -e "${CYAN}|${NC}  ${BOLD}S.${NC} Start Server                                                       ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}  ${BOLD}A.${NC} Attach to Server (tmux)                                            ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                                       ${CYAN}|${NC}"

    # Quit
    echo -e "${CYAN}|${NC}  ${BOLD}Q.${NC} Quit                                                               ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                                       ${CYAN}|${NC}"
    echo -e "${CYAN}+-----------------------------------------------------------------------+${NC}"
    echo ""
}

select_scenario_menu() {
    clear_screen
    echo -e "${CYAN}${BOLD}"
    echo "+-----------------------------------------------------------------------+"
    echo "|                         SELECT SCENARIO                              |"
    echo "+-----------------------------------------------------------------------+"
    echo -e "${NC}"

    if [ "$SERVER_STATUS" != "online" ]; then
        echo -e "${RED_COLOR}Server is offline. Start the server first.${NC}"
        echo ""
        read -p "Press Enter to continue..."
        return
    fi

    echo "Fetching scenarios..."
    local scenarios
    scenarios=$(fetch_scenarios)

    if [ -z "$scenarios" ]; then
        echo -e "${RED_COLOR}No scenarios available or failed to fetch.${NC}"
        echo ""
        read -p "Press Enter to continue..."
        return
    fi

    echo ""
    local i=1
    local ids=()
    local names=()

    while IFS='|' read -r id name desc red_name blue_name; do
        ids+=("$id")
        names+=("$name")
        echo -e "  ${BOLD}$i.${NC} ${GREEN}$name${NC}"
        echo -e "     ${DIM}$desc${NC}"
        echo -e "     ${BLUE}Blue:${NC} $blue_name  ${RED_COLOR}Red:${NC} $red_name"
        echo ""
        ((i++))
    done <<< "$scenarios"

    echo -e "  ${BOLD}0.${NC} Cancel"
    echo ""
    read -p "Select scenario (1-$((i-1))): " choice

    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#ids[@]}" ]; then
        SELECTED_SCENARIO="${ids[$((choice-1))]}"
        SELECTED_SCENARIO_NAME="${names[$((choice-1))]}"
        echo -e "${GREEN}Selected: $SELECTED_SCENARIO_NAME${NC}"
        sleep 1
    fi
}

toggle_blue_player() {
    if [ "$BLUE_PLAYER" = "human" ]; then
        BLUE_PLAYER="ai"
    else
        BLUE_PLAYER="human"
    fi
}

toggle_red_player() {
    if [ "$RED_PLAYER" = "human" ]; then
        RED_PLAYER="ai"
    else
        RED_PLAYER="human"
    fi
}

get_local_ip() {
    # Try to get the primary local IP
    ip route get 1 2>/dev/null | awk '{print $7; exit}' || hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP"
}

start_game() {
    clear_screen

    # Start server if not running
    if [ "$SERVER_STATUS" != "online" ]; then
        echo -e "${YELLOW}Server is offline. Starting server...${NC}"
        echo ""
        if ! start_server_background; then
            echo -e "${RED_COLOR}Failed to start server.${NC}"
            read -p "Press Enter to continue..."
            return
        fi
        echo ""
    fi

    if [ -z "$SELECTED_SCENARIO" ]; then
        echo -e "${RED_COLOR}No scenario selected. Select a scenario first.${NC}"
        read -p "Press Enter to continue..."
        return
    fi

    echo -e "${CYAN}${BOLD}Starting Game${NC}"
    echo "============="
    echo ""

    # Load scenario
    echo -n "Loading scenario: $SELECTED_SCENARIO_NAME... "
    if load_scenario "$SELECTED_SCENARIO"; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED_COLOR}FAILED${NC}"
        read -p "Press Enter to continue..."
        return
    fi

    # Configure AI
    echo -n "Configuring AI players... "
    configure_ai
    echo -e "${GREEN}OK${NC}"

    echo ""
    echo -e "Blue: $([ "$BLUE_PLAYER" = "human" ] && echo "${BLUE}Human${NC}" || echo "${DIM}AI${NC}")"
    echo -e "Red:  $([ "$RED_PLAYER" = "human" ] && echo "${RED_COLOR}Human${NC}" || echo "${DIM}AI${NC}")"
    echo ""

    # Determine launch mode
    if [ "$BLUE_PLAYER" = "ai" ] && [ "$RED_PLAYER" = "ai" ]; then
        # Both AI - watch mode
        echo -e "${YELLOW}Both factions are AI-controlled.${NC}"
        echo "The game will run automatically. Watch the server logs or attach to tmux."
        echo ""
        echo "To view the game:"
        echo "  tmux attach -t $SESSION_NAME"
        echo ""
        read -p "Press Enter to continue..."

    elif [ "$BLUE_PLAYER" = "human" ] && [ "$RED_PLAYER" = "human" ]; then
        # Both human
        echo -e "${YELLOW}Both players are human.${NC}"
        echo ""
        echo "Are both players on the same machine?"
        echo "  1. Same machine (launch two tmux windows)"
        echo "  2. Different machines (show connection instructions)"
        echo ""
        read -p "Choice (1/2): " same_machine

        if [ "$same_machine" = "1" ]; then
            # Launch two client windows in tmux
            echo ""
            echo "Launching both clients in tmux..."

            # Create windows for both clients
            tmux new-window -t "$SESSION_NAME" -n "blue-client"
            tmux send-keys -t "$SESSION_NAME:blue-client" "cd '$SCRIPT_DIR/karkas' && source '$SCRIPT_DIR/$VENV_PATH' && python client/cli.py --faction blue" C-m

            tmux new-window -t "$SESSION_NAME" -n "red-client"
            tmux send-keys -t "$SESSION_NAME:red-client" "cd '$SCRIPT_DIR/karkas' && source '$SCRIPT_DIR/$VENV_PATH' && python client/cli.py --faction red" C-m

            echo ""
            echo -e "${GREEN}Clients launched!${NC}"
            echo ""
            echo "Tmux controls:"
            echo "  Ctrl-B n     Next window"
            echo "  Ctrl-B p     Previous window"
            echo "  Ctrl-B D     Detach (keep running)"
            echo ""
            read -p "Press Enter to attach to tmux..."
            exec tmux attach -t "$SESSION_NAME"

        else
            # Different machines
            local_ip=$(get_local_ip)
            clear_screen
            echo -e "${CYAN}${BOLD}"
            echo "+-----------------------------------------------------------------------+"
            echo "|                    REMOTE PLAYER INSTRUCTIONS                        |"
            echo "+-----------------------------------------------------------------------+"
            echo -e "${NC}"
            echo ""
            echo "  The remote player should run:"
            echo ""
            echo -e "    ${GREEN}cd $SCRIPT_DIR${NC}"
            echo -e "    ${GREEN}source venv/bin/activate${NC}"
            echo -e "    ${GREEN}python karkas/client/cli.py --server http://${local_ip}:8080 \\${NC}"
            echo -e "    ${GREEN}                            --faction red${NC}"
            echo ""
            echo -e "  ${BOLD}Your IP address: ${CYAN}${local_ip}${NC}"
            echo ""
            echo "+-----------------------------------------------------------------------+"
            echo ""
            read -p "Press Enter to launch your Blue client..."

            # Launch local blue client in tmux
            tmux new-window -t "$SESSION_NAME" -n "blue-client"
            tmux send-keys -t "$SESSION_NAME:blue-client" "cd '$SCRIPT_DIR/karkas' && source '$SCRIPT_DIR/$VENV_PATH' && python client/cli.py --faction blue" C-m

            exec tmux attach -t "$SESSION_NAME"
        fi

    else
        # One human, one AI
        local human_faction
        if [ "$BLUE_PLAYER" = "human" ]; then
            human_faction="blue"
        else
            human_faction="red"
        fi

        echo "Launching client for ${human_faction} faction..."
        echo ""

        # Launch client in tmux
        tmux new-window -t "$SESSION_NAME" -n "${human_faction}-client"
        tmux send-keys -t "$SESSION_NAME:${human_faction}-client" "cd '$SCRIPT_DIR/karkas' && source '$SCRIPT_DIR/$VENV_PATH' && python client/cli.py --faction $human_faction" C-m

        echo -e "${GREEN}Client launched!${NC}"
        echo ""
        echo "Tmux controls:"
        echo "  Ctrl-B n     Next window"
        echo "  Ctrl-B D     Detach (keep running)"
        echo ""
        read -p "Press Enter to attach to tmux..."
        exec tmux attach -t "$SESSION_NAME"
    fi
}

# --- Main ---
main() {
    check_prerequisites

    while true; do
        check_server_status
        display_menu

        read -p "Choice: " -n 1 choice
        echo ""

        case "$choice" in
            1)
                select_scenario_menu
                ;;
            2)
                toggle_blue_player
                ;;
            3)
                toggle_red_player
                ;;
            4)
                start_game
                ;;
            [sS])
                if [ "$SERVER_STATUS" = "offline" ]; then
                    start_server_background
                    read -p "Press Enter to continue..."
                else
                    echo -e "${YELLOW}Server is already running.${NC}"
                    sleep 1
                fi
                ;;
            [aA])
                if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
                    exec tmux attach -t "$SESSION_NAME"
                else
                    echo -e "${RED_COLOR}No server session found.${NC}"
                    sleep 1
                fi
                ;;
            [qQ])
                echo ""
                echo "Goodbye!"
                exit 0
                ;;
            *)
                # Invalid choice, just redraw menu
                ;;
        esac
    done
}

main "$@"
