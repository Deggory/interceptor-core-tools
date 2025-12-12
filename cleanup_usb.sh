#!/bin/bash
# Kill all stale USB device processes

echo "Killing stale processes accessing USB devices..."

# Kill user processes (no sudo needed for your own processes)
pkill -9 -f "stm_flash_config.py" 2>/dev/null
pkill -9 -f "monitor_interceptor.py" 2>/dev/null  
pkill -9 -f "send_test_input.py" 2>/dev/null
pkill -9 -f "debug_console.py" 2>/dev/null

sleep 1

# Check if any are still running
REMAINING=$(ps aux | grep -E "(monitor_interceptor|send_test_input|stm_flash_config|debug_console)" | grep -v grep | wc -l)

if [ $REMAINING -gt 0 ]; then
    echo ""
    echo "Some processes are still running (possibly as root). You may need to run:"
    echo "  sudo pkill -9 -f 'stm_flash_config|monitor_interceptor|send_test_input'"
    echo ""
    echo "Remaining processes:"
    ps aux | grep -E "(monitor_interceptor|send_test_input|stm_flash_config|debug_console)" | grep -v grep
else
    echo "✓ All processes killed successfully!"
fi

echo ""
echo "Waiting for USB devices to reset..."
sleep 2
echo "✓ Ready to run monitoring scripts"
