#!/bin/bash

# 1. Environment & Config
VENV_PATH="./venv/bin/activate"
MODEL_NAME="qwen2.5:14b-instruct-q4_K_M" # Ensure this matches 'ollama list'

echo "======================================================="
echo "        INITIALIZING GRISHA: TACTICAL ADVISOR          "
echo "======================================================="

# Function for the loading spinner
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

# 2. Virtual Environment Check
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
else
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# 3. Service Check
if ! systemctl is-active --quiet ollama; then
    echo "Ollama service is inactive. Starting..."
    sudo systemctl start ollama
fi

# 4. API Readiness Loop
MAX_RETRIES=10
COUNT=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    STATUS=$(curl -s -m 5 -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags)
    if [ "$STATUS" -eq 200 ]; then
        break
    else
        COUNT=$((COUNT + 1))
        echo "Waiting for API... ($COUNT/$MAX_RETRIES)"
        sleep 2
    fi
done

# 5. Pre-loading the Model (The "Warm-up" with Spinner)
echo -n "Synchronizing Grisha's memory (Pre-loading Model)..."
# Run the pre-load in the background
ollama run $MODEL_NAME "" --keepalive 10m > /dev/null 2>&1 &
# Capture the PID of the background process
LOAD_PID=$!
# Start the spinner for that PID
spinner $LOAD_PID

echo " DONE."
echo "------------------------------------------------"
echo " Grisha is fully operational."
echo "------------------------------------------------"

# 6. Execute Query Engine
python3 grisha_query.py