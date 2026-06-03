#!/bin/bash
# Verify web interface: start bridge + HTTP server, test connectivity
set -e

source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

echo "=== Starting WebSocket bridge ==="
ros2 run so_arm_100_web_bridge websocket_bridge > /tmp/bridge.log 2>&1 &
BRIDGE_PID=$!
echo "Bridge PID: $BRIDGE_PID"

echo "=== Waiting for bridge to init (4s) ==="
sleep 4

# Check bridge still running
if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    echo "FAIL: Bridge crashed. Log:"
    cat /tmp/bridge.log
    exit 1
fi
echo "OK: Bridge is running"

echo "=== Starting HTTP server on port 8080 ==="
python3 -m http.server 8080 --directory /workspace/web_interface/dist > /tmp/http.log 2>&1 &
HTTP_PID=$!
sleep 1

echo "=== Testing HTTP endpoint ==="
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/)
if [ "$HTTP_STATUS" = "200" ]; then
    echo "OK: HTTP 200 from localhost:8080"
else
    echo "FAIL: HTTP status $HTTP_STATUS"
fi

HTML_TITLE=$(curl -s http://localhost:8080/ | grep -o '<title>[^<]*</title>' | head -1)
echo "Page title: $HTML_TITLE"

echo "=== Testing index.html assets ==="
curl -s http://localhost:8080/ | grep -o 'src="[^"]*"' | head -5

echo "=== Testing WebSocket bridge port 9090 ==="
if python3 - <<'PYEOF'
import socket, sys
try:
    s = socket.create_connection(("localhost", 9090), timeout=3)
    # Send WebSocket upgrade request
    s.send(b"GET / HTTP/1.1\r\nHost: localhost:9090\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n")
    resp = s.recv(1024).decode('utf-8', errors='replace')
    s.close()
    if '101' in resp or 'Switching Protocols' in resp:
        print("OK: WebSocket handshake succeeded (101 Switching Protocols)")
        sys.exit(0)
    else:
        print(f"WARN: Got response (bridge is listening): {resp[:200]}")
        sys.exit(0)
except Exception as e:
    print(f"FAIL: Cannot connect to port 9090: {e}")
    sys.exit(1)
PYEOF
then
    echo "OK: WebSocket port 9090 is reachable"
else
    echo "FAIL: WebSocket port 9090 not reachable"
fi

echo "=== Bridge log (last 10 lines) ==="
tail -10 /tmp/bridge.log

echo "=== Cleanup ==="
kill $BRIDGE_PID $HTTP_PID 2>/dev/null || true

echo "=== VERIFICATION COMPLETE ==="
