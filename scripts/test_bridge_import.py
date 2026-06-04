#!/usr/bin/env python3
"""Test that the bridge node imports and starts correctly."""
import sys

# Test 1: module import
try:
    from so_arm_100_web_bridge.websocket_bridge_node import WebSocketBridgeNode
    print("IMPORT_OK: websocket_bridge_node imported successfully")
except Exception as e:
    print(f"IMPORT_FAIL: {e}")
    sys.exit(1)

# Test 2: check camera availability flag
try:
    import so_arm_100_web_bridge.websocket_bridge_node as mod
    cam = getattr(mod, '_CAMERA_AVAILABLE', 'NOT_SET')
    print(f"CAMERA_AVAILABLE: {cam}")
except Exception as e:
    print(f"CAMERA_CHECK_FAIL: {e}")

# Test 3: rclpy init and node creation (no spin)
try:
    import rclpy
    rclpy.init(args=[])
    node = WebSocketBridgeNode()
    host = node._host
    port = node._port
    print(f"NODE_CREATED_OK: bridge will listen on {host}:{port}")
    node.destroy_node()
    rclpy.shutdown()
except Exception as e:
    print(f"NODE_CREATE_FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("ALL_CHECKS_PASSED")
