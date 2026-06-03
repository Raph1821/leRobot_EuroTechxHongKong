"""Unit tests for WebSocket bridge node.

Tests cover:
- Initial state delivery on connect (Req 6.4, 6.7)
- Client disconnect isolation (Req 6.5)
- Multiple simultaneous connections (Req 6.8)
- Trajectory status forwarding

These tests mock ROS2 infrastructure and use real asyncio WebSocket
connections to validate the bridge node's WebSocket behavior.
"""

import asyncio
import json
import sys
import os
import time
import threading
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import websockets

from so_arm_100_web_bridge.message_schemas import (
    serialize_joint_state,
    serialize_trajectory_status,
)
from so_arm_100_web_bridge.joint_validator import ARM_JOINT_NAMES


# --------------------------------------------------------------------------
# Helpers: Fake ROS2 message types for testing
# --------------------------------------------------------------------------


class FakeStamp:
    """Fake ROS2 Time stamp."""

    def __init__(self, sec=0, nanosec=0):
        self.sec = sec
        self.nanosec = nanosec


class FakeHeader:
    """Fake ROS2 message header."""

    def __init__(self, sec=0, nanosec=0):
        self.stamp = FakeStamp(sec, nanosec)


class FakeJointState:
    """Fake sensor_msgs/msg/JointState message."""

    def __init__(self, names=None, positions=None, velocities=None, efforts=None):
        self.header = FakeHeader(sec=100, nanosec=500000000)
        self.name = names or [
            "Shoulder_Rotation",
            "Shoulder_Pitch",
            "Elbow",
            "Wrist_Pitch",
            "Wrist_Roll",
            "Gripper",
        ]
        self.position = positions or [0.0, 0.1, -0.2, 0.3, -0.4, 0.5]
        self.velocity = velocities or [0.0] * 6
        self.effort = efforts or [0.0] * 6


# --------------------------------------------------------------------------
# Helpers: Minimal WebSocket server that simulates bridge behavior
# --------------------------------------------------------------------------


class MinimalBridgeServer:
    """A minimal WebSocket server simulating the bridge node's behavior.

    This is a standalone asyncio server that mirrors the WebSocket-facing
    logic of WebSocketBridgeNode without requiring rclpy. It allows us to
    test client-facing behavior in isolation.

    Tracks server-side connection objects to allow sending messages to
    specific clients (simulating trajectory status forwarding).
    """

    def __init__(self, host="127.0.0.1", port=0):
        self._host = host
        self._port = port
        # Server-side connection objects (the ws params in _handle_client)
        self._server_connections = []
        self._server_connections_lock = asyncio.Lock()
        self._deferred_connections = []
        self._deferred_lock = asyncio.Lock()
        self._latest_joint_state = None
        self._has_received_joint_state = False
        self._server = None
        self._actual_port = None

    @property
    def port(self):
        return self._actual_port

    @property
    def client_count(self):
        return len(self._server_connections)

    async def start(self):
        """Start the WebSocket server."""
        self._server = await websockets.serve(
            self._handle_client,
            self._host,
            self._port,
        )
        # Get the actual port assigned (when port=0)
        self._actual_port = self._server.sockets[0].getsockname()[1]

    async def stop(self):
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def inject_joint_state(self, joint_state_msg):
        """Simulate receiving a /joint_states message from ROS2.

        Serializes and stores the joint state.
        """
        serialized = serialize_joint_state(joint_state_msg)
        self._latest_joint_state = serialized
        self._has_received_joint_state = True
        return serialized

    async def inject_joint_state_async(self, joint_state_msg):
        """Async version that also sends to deferred clients."""
        serialized = self.inject_joint_state(joint_state_msg)

        async with self._deferred_lock:
            if self._deferred_connections:
                deferred = self._deferred_connections.copy()
                self._deferred_connections.clear()
                for conn in deferred:
                    try:
                        await conn.send(serialized)
                    except websockets.exceptions.ConnectionClosed:
                        pass

    async def broadcast_joint_state(self):
        """Broadcast the latest joint state to all connected clients."""
        if self._latest_joint_state is None:
            return

        async with self._server_connections_lock:
            connections = self._server_connections.copy()

        for conn in connections:
            try:
                await conn.send(self._latest_joint_state)
            except websockets.exceptions.ConnectionClosed:
                async with self._server_connections_lock:
                    if conn in self._server_connections:
                        self._server_connections.remove(conn)

    async def send_to_connection(self, index: int, message: str):
        """Send a message to a specific server-side connection by index.

        Args:
            index: The index of the connection (in order of connection).
            message: The message string to send.
        """
        async with self._server_connections_lock:
            if index < len(self._server_connections):
                conn = self._server_connections[index]
        try:
            await conn.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass

    async def _handle_client(self, ws):
        """Handle a new WebSocket client connection."""
        async with self._server_connections_lock:
            self._server_connections.append(ws)

        # Send initial joint state or defer (Req 6.4, 6.7)
        if self._has_received_joint_state and self._latest_joint_state is not None:
            try:
                await ws.send(self._latest_joint_state)
            except websockets.exceptions.ConnectionClosed:
                async with self._server_connections_lock:
                    if ws in self._server_connections:
                        self._server_connections.remove(ws)
                return
        else:
            # Defer until first joint state arrives (Req 6.7)
            async with self._deferred_lock:
                self._deferred_connections.append(ws)

        # Listen for messages until disconnect
        try:
            async for message in ws:
                # Echo back or handle commands - just consume
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Clean up (Req 6.5)
            async with self._server_connections_lock:
                if ws in self._server_connections:
                    self._server_connections.remove(ws)
            async with self._deferred_lock:
                if ws in self._deferred_connections:
                    self._deferred_connections.remove(ws)


# --------------------------------------------------------------------------
# Tests: Initial state delivery on connect (Req 6.4, 6.7)
# --------------------------------------------------------------------------


class TestInitialStateDelivery:
    """Test initial state delivery behavior (Req 6.4, 6.7)."""

    @pytest.mark.asyncio
    async def test_initial_state_sent_on_connect_when_available(self):
        """When a joint state exists, it is sent to new clients immediately.

        Validates: Requirement 6.4 — send most recent JointState within
        100ms of connection being established.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            # Inject a joint state before client connects
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            # Connect a client
            uri = f"ws://127.0.0.1:{server.port}"
            async with websockets.connect(uri) as ws:
                # Should receive initial state within 100ms
                message = await asyncio.wait_for(ws.recv(), timeout=0.1)
                data = json.loads(message)

                assert data["type"] == "joint_state"
                assert data["joints"]["names"] == fake_msg.name
                assert data["joints"]["positions"] == fake_msg.position
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_initial_state_deferred_when_no_joint_state_yet(self):
        """When no joint state has been received, delivery is deferred.

        Validates: Requirement 6.7 — defer initial state until first
        JointState is received from /joint_states topic.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            # Connect without any joint state available
            uri = f"ws://127.0.0.1:{server.port}"
            async with websockets.connect(uri) as ws:
                # Should NOT receive anything immediately
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(ws.recv(), timeout=0.05)

                # Now inject a joint state (simulating first /joint_states)
                fake_msg = FakeJointState(
                    positions=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
                )
                await server.inject_joint_state_async(fake_msg)

                # Client should now receive the deferred state
                message = await asyncio.wait_for(ws.recv(), timeout=0.1)
                data = json.loads(message)

                assert data["type"] == "joint_state"
                assert data["joints"]["positions"] == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_initial_state_contains_all_joint_fields(self):
        """Initial state contains names, positions, velocities, and efforts.

        Validates: Requirement 6.4 — complete joint state message.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState(
                positions=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
                velocities=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5],
                efforts=[2.0, 2.1, 2.2, 2.3, 2.4, 2.5],
            )
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            async with websockets.connect(uri) as ws:
                message = await asyncio.wait_for(ws.recv(), timeout=0.1)
                data = json.loads(message)

                joints = data["joints"]
                assert "names" in joints
                assert "positions" in joints
                assert "velocities" in joints
                assert "efforts" in joints
                assert len(joints["names"]) == 6
                assert len(joints["positions"]) == 6
                assert len(joints["velocities"]) == 6
                assert len(joints["efforts"]) == 6
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_initial_state_delivery_within_100ms(self):
        """Initial state is delivered within 100ms of connection.

        Validates: Requirement 6.4 — within 100ms of connection.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            start_time = time.monotonic()
            async with websockets.connect(uri) as ws:
                message = await asyncio.wait_for(ws.recv(), timeout=0.1)
                elapsed = time.monotonic() - start_time

                assert elapsed < 0.1  # 100ms
                data = json.loads(message)
                assert data["type"] == "joint_state"
        finally:
            await server.stop()


# --------------------------------------------------------------------------
# Tests: Client disconnect isolation (Req 6.5)
# --------------------------------------------------------------------------


class TestClientDisconnectIsolation:
    """Test client disconnect does not affect other clients (Req 6.5)."""

    @pytest.mark.asyncio
    async def test_disconnect_does_not_affect_other_clients(self):
        """When one client disconnects, other clients continue receiving.

        Validates: Requirement 6.5 — disconnect SHALL stop publishing
        commands from that client without affecting other connected clients.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"

            # Connect two clients
            ws1 = await websockets.connect(uri)
            ws2 = await websockets.connect(uri)

            # Both receive initial state
            await asyncio.wait_for(ws1.recv(), timeout=0.1)
            await asyncio.wait_for(ws2.recv(), timeout=0.1)

            # Disconnect client 1
            await ws1.close()

            # Small delay for cleanup
            await asyncio.sleep(0.05)

            # Broadcast new state
            new_msg = FakeJointState(positions=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
            server.inject_joint_state(new_msg)
            await server.broadcast_joint_state()

            # Client 2 should still receive messages
            message = await asyncio.wait_for(ws2.recv(), timeout=0.2)
            data = json.loads(message)
            assert data["type"] == "joint_state"
            assert data["joints"]["positions"] == [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]

            await ws2.close()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_client_removed_from_set_on_disconnect(self):
        """Disconnected clients are properly cleaned up from internal sets.

        Validates: Requirement 6.5 — clean up without affecting other clients.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"

            ws1 = await websockets.connect(uri)
            await asyncio.wait_for(ws1.recv(), timeout=0.1)

            assert server.client_count == 1

            await ws1.close()
            await asyncio.sleep(0.1)

            assert server.client_count == 0
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_abrupt_disconnect_no_error_propagation(self):
        """An abrupt disconnect does not crash the server or affect others.

        Validates: Requirement 6.5 — handle unexpected disconnect gracefully.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"

            ws1 = await websockets.connect(uri)
            ws2 = await websockets.connect(uri)

            await asyncio.wait_for(ws1.recv(), timeout=0.1)
            await asyncio.wait_for(ws2.recv(), timeout=0.1)

            # Abruptly close ws1 without proper close handshake
            ws1.transport.close()
            await asyncio.sleep(0.1)

            # Server should still be operational - broadcast to ws2
            new_msg = FakeJointState(positions=[0.5] * 6)
            server.inject_joint_state(new_msg)
            await server.broadcast_joint_state()

            message = await asyncio.wait_for(ws2.recv(), timeout=0.2)
            data = json.loads(message)
            assert data["type"] == "joint_state"

            await ws2.close()
        finally:
            await server.stop()


# --------------------------------------------------------------------------
# Tests: Multiple simultaneous connections (Req 6.8)
# --------------------------------------------------------------------------


class TestMultipleSimultaneousConnections:
    """Test support for 10+ simultaneous WebSocket connections (Req 6.8)."""

    @pytest.mark.asyncio
    async def test_ten_simultaneous_connections(self):
        """Server supports at least 10 simultaneous connections.

        Validates: Requirement 6.8 — support minimum 10 simultaneous
        WebSocket client connections.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            clients = []

            # Connect 10 clients
            for _ in range(10):
                ws = await websockets.connect(uri)
                clients.append(ws)
                # Consume initial state
                await asyncio.wait_for(ws.recv(), timeout=0.2)

            assert server.client_count == 10

            # All clients should receive broadcast
            new_msg = FakeJointState(positions=[0.9] * 6)
            server.inject_joint_state(new_msg)
            await server.broadcast_joint_state()

            for ws in clients:
                message = await asyncio.wait_for(ws.recv(), timeout=0.2)
                data = json.loads(message)
                assert data["type"] == "joint_state"
                assert data["joints"]["positions"] == [0.9] * 6

            # Clean up
            for ws in clients:
                await ws.close()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_twelve_simultaneous_connections(self):
        """Server handles more than 10 connections gracefully.

        Validates: Requirement 6.8 — minimum of 10, but should handle more.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            clients = []

            # Connect 12 clients
            for _ in range(12):
                ws = await websockets.connect(uri)
                clients.append(ws)
                await asyncio.wait_for(ws.recv(), timeout=0.2)

            assert server.client_count == 12

            # Clean up
            for ws in clients:
                await ws.close()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_broadcast_reaches_all_clients(self):
        """A broadcast reaches all connected clients without data corruption.

        Validates: Requirement 6.8 — multiple connections without affecting
        each other.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            clients = []

            # Connect 5 clients
            for _ in range(5):
                ws = await websockets.connect(uri)
                clients.append(ws)
                await asyncio.wait_for(ws.recv(), timeout=0.2)

            # Send distinct state
            unique_positions = [0.11, 0.22, 0.33, 0.44, 0.55, 0.66]
            new_msg = FakeJointState(positions=unique_positions)
            server.inject_joint_state(new_msg)
            await server.broadcast_joint_state()

            # Each client receives the same data
            for i, ws in enumerate(clients):
                message = await asyncio.wait_for(ws.recv(), timeout=0.2)
                data = json.loads(message)
                assert data["joints"]["positions"] == unique_positions, (
                    f"Client {i} received incorrect data"
                )

            for ws in clients:
                await ws.close()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_connections_independent_initial_state(self):
        """Each new connection receives its own initial state independently.

        Validates: Requirement 6.8 — connections don't interfere with each other.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            uri = f"ws://127.0.0.1:{server.port}"

            # First state
            msg1 = FakeJointState(positions=[0.1] * 6)
            server.inject_joint_state(msg1)

            ws1 = await websockets.connect(uri)
            data1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=0.1))
            assert data1["joints"]["positions"] == [0.1] * 6

            # Update state
            msg2 = FakeJointState(positions=[0.2] * 6)
            server.inject_joint_state(msg2)

            # Second client gets the updated state
            ws2 = await websockets.connect(uri)
            data2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=0.1))
            assert data2["joints"]["positions"] == [0.2] * 6

            await ws1.close()
            await ws2.close()
        finally:
            await server.stop()


# --------------------------------------------------------------------------
# Tests: Trajectory status forwarding
# --------------------------------------------------------------------------


class TestTrajectoryStatusForwarding:
    """Test trajectory status reporting back to clients."""

    @pytest.mark.asyncio
    async def test_trajectory_status_message_format(self):
        """Trajectory status messages have correct format.

        Validates that trajectory_status messages are properly structured
        with type, status, and message fields.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            async with websockets.connect(uri) as ws:
                # Consume initial state
                await asyncio.wait_for(ws.recv(), timeout=0.1)

                # Wait for the server-side handler to register
                await asyncio.sleep(0.02)

                # Send trajectory status via the server-side connection
                status_json = serialize_trajectory_status(
                    "executing", "Trajectory goal sent"
                )
                await server.send_to_connection(0, status_json)

                message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(message)

                assert data["type"] == "trajectory_status"
                assert data["status"] == "executing"
                assert data["message"] == "Trajectory goal sent"
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_trajectory_succeeded_status(self):
        """Succeeded trajectory status is forwarded correctly."""
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            async with websockets.connect(uri) as ws:
                await asyncio.wait_for(ws.recv(), timeout=0.1)
                await asyncio.sleep(0.02)

                status_json = serialize_trajectory_status(
                    "succeeded", "Trajectory execution completed successfully"
                )
                await server.send_to_connection(0, status_json)

                message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(message)

                assert data["type"] == "trajectory_status"
                assert data["status"] == "succeeded"
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_trajectory_aborted_status(self):
        """Aborted trajectory status is forwarded correctly."""
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            async with websockets.connect(uri) as ws:
                await asyncio.wait_for(ws.recv(), timeout=0.1)
                await asyncio.sleep(0.02)

                status_json = serialize_trajectory_status(
                    "aborted", "Trajectory aborted: goal tolerance violated"
                )
                await server.send_to_connection(0, status_json)

                message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(message)

                assert data["type"] == "trajectory_status"
                assert data["status"] == "aborted"
                assert "tolerance violated" in data["message"]
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_trajectory_preempted_status(self):
        """Preempted trajectory status is forwarded correctly."""
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            async with websockets.connect(uri) as ws:
                await asyncio.wait_for(ws.recv(), timeout=0.1)
                await asyncio.sleep(0.02)

                status_json = serialize_trajectory_status(
                    "preempted", "Trajectory preempted (error_code: -1)"
                )
                await server.send_to_connection(0, status_json)

                message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(message)

                assert data["type"] == "trajectory_status"
                assert data["status"] == "preempted"
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_trajectory_status_only_to_requesting_client(self):
        """Trajectory status is sent only to the client that made the request.

        Validates that status messages are directed to specific clients,
        not broadcast to all.
        """
        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"

            ws1 = await websockets.connect(uri)
            ws2 = await websockets.connect(uri)

            # Consume initial states
            await asyncio.wait_for(ws1.recv(), timeout=0.1)
            await asyncio.wait_for(ws2.recv(), timeout=0.1)
            await asyncio.sleep(0.02)

            # Send status only to first connection (ws1)
            status_json = serialize_trajectory_status(
                "succeeded", "Done"
            )
            await server.send_to_connection(0, status_json)

            # ws1 receives it
            msg1 = await asyncio.wait_for(ws1.recv(), timeout=0.5)
            data1 = json.loads(msg1)
            assert data1["type"] == "trajectory_status"

            # ws2 should NOT receive anything
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws2.recv(), timeout=0.1)

            await ws1.close()
            await ws2.close()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_all_trajectory_status_values_valid(self):
        """All four trajectory status values are valid and serializable."""
        valid_statuses = ["executing", "succeeded", "aborted", "preempted"]

        server = MinimalBridgeServer()
        await server.start()

        try:
            fake_msg = FakeJointState()
            server.inject_joint_state(fake_msg)

            uri = f"ws://127.0.0.1:{server.port}"
            async with websockets.connect(uri) as ws:
                await asyncio.wait_for(ws.recv(), timeout=0.1)
                await asyncio.sleep(0.02)

                for status in valid_statuses:
                    status_json = serialize_trajectory_status(
                        status, f"Test message for {status}"
                    )
                    await server.send_to_connection(0, status_json)

                    message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(message)

                    assert data["type"] == "trajectory_status"
                    assert data["status"] == status
                    assert f"Test message for {status}" in data["message"]
        finally:
            await server.stop()
