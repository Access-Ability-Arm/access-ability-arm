#!/bin/bash
# Camera Daemon Control Script
# Manages the Access Ability Arm camera daemon lifecycle

DAEMON_SCRIPT="$(dirname "$0")/aaa_camera_daemon.py"
DAEMON_NAME="aaa_camera_daemon"
PID_FILE="/tmp/${DAEMON_NAME}.pid"
LOG_FILE="/tmp/${DAEMON_NAME}.log"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

function print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

function print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

function check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run with sudo"
        echo "Usage: sudo $0 {start|stop|restart|status}"
        exit 1
    fi
}

function check_realsense_processes() {
    echo ""
    echo "Checking for processes using RealSense camera..."

    # Look for processes with RealSense-related patterns
    RS_PROCS=$(lsof /dev/video* 2>/dev/null | grep -v "COMMAND" | awk '{print $1, $2, $9}' | sort -u)

    if [ -n "$RS_PROCS" ]; then
        print_warning "Found processes accessing camera devices:"
        echo "$RS_PROCS" | while read line; do
            echo "  • $line"
        done
        echo ""

        # Ask if user wants to kill them
        if [ -t 0 ]; then  # Check if running interactively
            read -p "Kill these processes? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo "$RS_PROCS" | awk '{print $2}' | xargs -I {} kill {} 2>/dev/null
                print_status "Processes terminated"
                sleep 1
            fi
        else
            print_warning "Non-interactive mode - not killing processes"
            print_warning "Run 'make daemon-start' manually to be prompted"
        fi
    else
        print_status "No conflicting camera processes found"
    fi
    echo ""
}

function start_daemon() {
    # Check for processes using RealSense camera
    check_realsense_processes

    # Check if already running
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_warning "Daemon already running (PID: $PID)"
            return 0
        else
            print_warning "Stale PID file found, removing..."
            rm -f "$PID_FILE"
        fi
    fi

    # Clean up any stale shared memory
    print_status "Cleaning up stale shared memory..."
    python3 "$(dirname "$0")/cleanup_shared_memory.py" 2>/dev/null

    # Start daemon in background using venv Python
    print_status "Starting camera daemon..."
    SCRIPT_DIR=$(dirname "$0")
    VENV_PYTHON="$SCRIPT_DIR/../venv/bin/python"

    if [ ! -f "$VENV_PYTHON" ]; then
        print_error "Virtual environment Python not found at $VENV_PYTHON"
        print_error "Please create venv: python3.11 -m venv venv"
        return 1
    fi

    nohup "$VENV_PYTHON" -u "$DAEMON_SCRIPT" > "$LOG_FILE" 2>&1 &
    DAEMON_PID=$!
    echo $DAEMON_PID > "$PID_FILE"

    # Wait a moment and check if it's still running
    sleep 1
    if ps -p "$DAEMON_PID" > /dev/null 2>&1; then
        print_status "Camera daemon started successfully (PID: $DAEMON_PID)"
        print_status "Log file: $LOG_FILE"
        return 0
    else
        print_error "Daemon failed to start. Check log file:"
        tail -20 "$LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

function stop_daemon() {
    if [ ! -f "$PID_FILE" ]; then
        print_warning "Daemon is not running (no PID file)"
        return 0
    fi

    PID=$(cat "$PID_FILE")
    if ! ps -p "$PID" > /dev/null 2>&1; then
        print_warning "Daemon is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 0
    fi

    print_status "Stopping camera daemon (PID: $PID)..."
    kill -TERM "$PID"

    # Wait for graceful shutdown (max 5 seconds)
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            print_status "Daemon stopped successfully"
            rm -f "$PID_FILE"

            # Clean up shared memory
            print_status "Cleaning up shared memory..."
            python3 "$(dirname "$0")/cleanup_shared_memory.py" 2>/dev/null
            return 0
        fi
        sleep 0.5
    done

    # Force kill if still running
    print_warning "Daemon did not stop gracefully, forcing kill..."
    kill -KILL "$PID" 2>/dev/null
    rm -f "$PID_FILE"

    # Clean up shared memory
    python3 "$(dirname "$0")/cleanup_shared_memory.py" 2>/dev/null
    print_status "Daemon killed"
}

function restart_daemon() {
    print_status "Restarting camera daemon..."
    stop_daemon
    sleep 1
    start_daemon
}

function show_status() {
    echo "=== Camera Daemon Status ==="

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_status "Daemon is RUNNING (PID: $PID)"

            # Show memory usage
            echo ""
            echo "Process info:"
            ps aux | head -1
            ps aux | grep "$PID" | grep -v grep

            # Check socket
            echo ""
            echo "IPC Socket:"
            if [ -e "/tmp/aaa_camera.sock" ]; then
                ls -lh /tmp/aaa_camera.sock | awk '{print "  ✓ Socket: " $1 " " $3 ":" $4 " (" $9 ")"}'
            else
                echo "  ✗ Socket not found at /tmp/aaa_camera.sock"
            fi

            # Show USB connection info from log
            if [ -f "$LOG_FILE" ]; then
                echo ""
                echo "RealSense Camera:"
                grep -E "Device:|Serial:|Firmware:|USB Type:" "$LOG_FILE" | tail -4 | sed 's/^/  /'

                # Show FPS if available
                FPS_LINE=$(grep "frames captured" "$LOG_FILE" | tail -1)
                if [ -n "$FPS_LINE" ]; then
                    echo "  $FPS_LINE"
                fi
            fi

            # Show recent log entries
            if [ -f "$LOG_FILE" ]; then
                echo ""
                echo "Recent log entries (last 10 lines):"
                tail -10 "$LOG_FILE" | sed 's/^/  /'
            fi

            return 0
        else
            print_error "Daemon is NOT RUNNING (stale PID file)"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        print_error "Daemon is NOT RUNNING (no PID file)"
        return 1
    fi
}

# Main command dispatcher
case "$1" in
    start)
        check_sudo
        start_daemon
        ;;
    stop)
        check_sudo
        stop_daemon
        ;;
    restart)
        check_sudo
        restart_daemon
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the camera daemon (requires sudo)"
        echo "  stop    - Stop the camera daemon (requires sudo)"
        echo "  restart - Restart the camera daemon (requires sudo)"
        echo "  status  - Show daemon status (no sudo required)"
        exit 1
        ;;
esac

exit $?
