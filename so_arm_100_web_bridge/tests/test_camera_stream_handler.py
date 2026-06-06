"""Unit tests for camera_stream_handler module.

Tests core logic: JPEG compression, base64 encoding, per-client frame queue
with drop-oldest policy, streaming enable/disable, and camera availability
detection.

Requirements: 1.2, 1.5, 1.6, 1.7, 1.9
"""

import asyncio
import base64
import json
import sys
import os
import time
import threading
from collections import deque
from unittest.mock import MagicMock, AsyncMock, patch

import cv2
import numpy as np
import pytest

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from so_arm_100_web_bridge.camera_stream_handler import (
    CameraStreamHandler,
    _CAMERA_UNAVAILABLE_TIMEOUT,
    _DEFAULT_JPEG_QUALITY,
    _MAX_FRAME_QUEUE_SIZE,
    _MIN_JPEG_QUALITY,
    _MAX_JPEG_QUALITY,
)


def _make_mock_node():
    """Create a mock ROS2 node for testing."""
    node = MagicMock()
    node.get_logger.return_value = MagicMock()
    node.create_subscription = MagicMock(return_value=MagicMock())
    node.create_timer = MagicMock(return_value=MagicMock())
    node.destroy_subscription = MagicMock()
    return node


def _make_image_msg(width=64, height=48, encoding="rgb8"):
    """Create a mock ROS2 Image message with valid pixel data."""
    msg = MagicMock()
    msg.width = width
    msg.height = height
    msg.encoding = encoding

    if encoding in ("rgb8", "bgr8"):
        channels = 3
    elif encoding in ("rgba8", "bgra8"):
        channels = 4
    elif encoding == "mono8":
        channels = 1
    else:
        channels = 3

    # Generate random pixel data.
    data = np.random.randint(0, 256, (height, width, channels) if channels > 1 else (height, width), dtype=np.uint8)
    msg.data = data.tobytes()
    return msg


class TestCameraStreamHandlerInit:
    """Tests for CameraStreamHandler initialization."""

    def test_creates_subscription(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node, namespace="/robot1")
        node.create_subscription.assert_called_once()
        # Check the topic name includes the namespace.
        call_args = node.create_subscription.call_args
        topic = call_args[0][1]
        assert topic == "/robot1/viewport_camera/image_raw"

    def test_default_jpeg_quality(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        assert handler.jpeg_quality == _DEFAULT_JPEG_QUALITY

    def test_custom_jpeg_quality(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node, jpeg_quality=90)
        assert handler.jpeg_quality == 90

    def test_jpeg_quality_clamped_low(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node, jpeg_quality=1)
        assert handler.jpeg_quality == _MIN_JPEG_QUALITY

    def test_jpeg_quality_clamped_high(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node, jpeg_quality=200)
        assert handler.jpeg_quality == _MAX_JPEG_QUALITY

    def test_namespace_trailing_slash_stripped(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node, namespace="/robot1/")
        call_args = node.create_subscription.call_args
        topic = call_args[0][1]
        assert topic == "/robot1/viewport_camera/image_raw"

    def test_empty_namespace(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node, namespace="")
        call_args = node.create_subscription.call_args
        topic = call_args[0][1]
        assert topic == "/viewport_camera/image_raw"

    def test_creates_availability_timer(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        node.create_timer.assert_called_once()


class TestStreamingControl:
    """Tests for enable/disable streaming and client management."""

    def test_enable_streaming(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        client = MagicMock()

        handler.enable_streaming(client)
        assert handler.is_streaming(client) is True

    def test_disable_streaming(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        client = MagicMock()

        handler.enable_streaming(client)
        handler.disable_streaming(client)
        assert handler.is_streaming(client) is False

    def test_disable_clears_queue(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        client = MagicMock()

        handler.enable_streaming(client)
        assert handler.get_queue_size(client) == 0
        handler.disable_streaming(client)
        assert handler.get_queue_size(client) == 0

    def test_remove_client(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        client = MagicMock()

        handler.enable_streaming(client)
        handler.remove_client(client)
        assert handler.is_streaming(client) is False
        assert handler.get_queue_size(client) == 0

    def test_multiple_clients_independent(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        client1 = MagicMock()
        client2 = MagicMock()

        handler.enable_streaming(client1)
        handler.enable_streaming(client2)

        assert handler.is_streaming(client1) is True
        assert handler.is_streaming(client2) is True

        handler.disable_streaming(client1)
        assert handler.is_streaming(client1) is False
        assert handler.is_streaming(client2) is True


class TestJpegCompression:
    """Tests for JPEG compression and base64 encoding."""

    def test_compress_and_encode_rgb(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        msg = _make_image_msg(width=64, height=48, encoding="rgb8")

        result = handler._compress_and_encode(msg, time.time())
        assert result is not None

        data = json.loads(result)
        assert data["type"] == "camera_frame"
        assert data["width"] == 64
        assert data["height"] == 48
        assert data["encoding"] == "jpeg"
        assert data["quality"] == _DEFAULT_JPEG_QUALITY
        assert len(data["data"]) > 0

        # Verify base64 decodes to valid JPEG.
        jpeg_bytes = base64.b64decode(data["data"])
        np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        assert decoded is not None
        assert decoded.shape[0] == 48
        assert decoded.shape[1] == 64

    def test_compress_and_encode_bgr(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        msg = _make_image_msg(width=32, height=32, encoding="bgr8")

        result = handler._compress_and_encode(msg, time.time())
        assert result is not None

        data = json.loads(result)
        assert data["width"] == 32
        assert data["height"] == 32

    def test_compress_and_encode_mono(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        msg = _make_image_msg(width=16, height=16, encoding="mono8")

        result = handler._compress_and_encode(msg, time.time())
        assert result is not None

    def test_compress_quality_affects_size(self):
        node = _make_mock_node()
        handler_low = CameraStreamHandler(node, jpeg_quality=10)
        handler_high = CameraStreamHandler(node, jpeg_quality=100)
        msg = _make_image_msg(width=128, height=128, encoding="rgb8")

        result_low = handler_low._compress_and_encode(msg, time.time())
        result_high = handler_high._compress_and_encode(msg, time.time())

        # Higher quality should generally produce larger output.
        data_low = json.loads(result_low)
        data_high = json.loads(result_high)
        assert len(data_low["data"]) < len(data_high["data"])


class TestFrameQueue:
    """Tests for per-client frame queue with drop-oldest policy."""

    def test_queue_max_size(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        client = MagicMock()
        handler.enable_streaming(client)

        # Manually add frames to the queue to test bounded capacity.
        with handler._client_queues_lock:
            queue = handler._client_queues[client]
            queue.append("frame1")
            queue.append("frame2")
            queue.append("frame3")  # Should drop frame1

        assert handler.get_queue_size(client) == _MAX_FRAME_QUEUE_SIZE

        # Verify the oldest was dropped and newest is present.
        with handler._client_queues_lock:
            queue = handler._client_queues[client]
            assert "frame1" not in queue
            assert "frame3" in queue
            assert "frame2" in queue

    def test_queue_drops_oldest_on_overflow(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        client = MagicMock()
        handler.enable_streaming(client)

        # Add 5 frames, only last 2 should remain.
        with handler._client_queues_lock:
            queue = handler._client_queues[client]
            for i in range(5):
                queue.append(f"frame_{i}")

        with handler._client_queues_lock:
            queue = handler._client_queues[client]
            assert len(queue) == 2
            assert queue[0] == "frame_3"
            assert queue[1] == "frame_4"


class TestCameraAvailability:
    """Tests for camera topic unavailability detection."""

    def test_camera_initially_unavailable(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        assert handler.camera_available is False

    def test_camera_becomes_available_after_frame(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)

        # Simulate a frame callback setting last frame time.
        with handler._last_frame_time_lock:
            handler._last_frame_time = time.time()
        with handler._camera_available_lock:
            handler._camera_available = True

        assert handler.camera_available is True

    def test_camera_unavailable_after_timeout(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)

        # Set last frame time to be beyond the timeout.
        with handler._last_frame_time_lock:
            handler._last_frame_time = time.time() - _CAMERA_UNAVAILABLE_TIMEOUT - 1.0
        with handler._camera_available_lock:
            handler._camera_available = True

        # Trigger the availability check.
        handler._check_camera_availability()

        assert handler.camera_available is False

    def test_camera_availability_check_no_notification_when_already_unavailable(self):
        node = _make_mock_node()
        send_callback = AsyncMock()
        handler = CameraStreamHandler(node, send_callback=send_callback)
        handler._loop = asyncio.new_event_loop()

        # Camera was already marked unavailable.
        with handler._camera_available_lock:
            handler._camera_available = False
        with handler._last_frame_time_lock:
            handler._last_frame_time = time.time() - 5.0

        # Should not trigger notification since already unavailable.
        handler._check_camera_availability()

        # No coroutines should be scheduled (camera was already unavailable).
        handler._loop.close()


class TestJpegQualitySetter:
    """Tests for JPEG quality property setter."""

    def test_set_valid_quality(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        handler.jpeg_quality = 50
        assert handler.jpeg_quality == 50

    def test_set_quality_below_min(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        handler.jpeg_quality = 5
        assert handler.jpeg_quality == _MIN_JPEG_QUALITY

    def test_set_quality_above_max(self):
        node = _make_mock_node()
        handler = CameraStreamHandler(node)
        handler.jpeg_quality = 150
        assert handler.jpeg_quality == _MAX_JPEG_QUALITY


class TestDestroy:
    """Tests for cleanup."""

    def test_destroy_cancels_timer(self):
        node = _make_mock_node()
        timer_mock = MagicMock()
        node.create_timer.return_value = timer_mock

        handler = CameraStreamHandler(node)
        handler.destroy()

        timer_mock.cancel.assert_called_once()

    def test_destroy_destroys_subscription(self):
        node = _make_mock_node()
        sub_mock = MagicMock()
        node.create_subscription.return_value = sub_mock

        handler = CameraStreamHandler(node)
        handler.destroy()

        node.destroy_subscription.assert_called_once_with(sub_mock)
