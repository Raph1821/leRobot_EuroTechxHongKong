"""Camera stream handler for the SO-100 WebSocket bridge.

This module implements camera frame subscription, JPEG compression,
base64 encoding, and per-client frame queuing with drop-oldest policy
for streaming viewport camera images from Isaac Sim to WebSocket clients.

Subscribes to: /{namespace}/viewport_camera/image_raw (sensor_msgs/Image)

Requirements: 1.2, 1.5, 1.6, 1.7, 1.9
"""

import asyncio
import base64
import time
import threading
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional, Set

import cv2
import numpy as np

from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image

from so_arm_100_web_bridge.message_schemas import serialize_camera_frame


# Timeout in seconds after which the camera topic is considered unavailable.
_CAMERA_UNAVAILABLE_TIMEOUT = 2.0

# Default JPEG compression quality.
_DEFAULT_JPEG_QUALITY = 75

# Valid JPEG quality range.
_MIN_JPEG_QUALITY = 10
_MAX_JPEG_QUALITY = 100

# Maximum number of frames queued per client before dropping oldest.
_MAX_FRAME_QUEUE_SIZE = 2


class CameraStreamHandler:
    """Handles camera image subscription, compression, and per-client streaming.

    This class subscribes to a ROS2 image topic, compresses incoming frames
    to JPEG format, encodes them as base64, and distributes them to connected
    WebSocket clients that have camera streaming enabled.

    Each client maintains an independent frame queue (max 2 frames). When a
    new frame arrives and the queue is full, the oldest frame is dropped
    (drop-oldest policy per Requirement 1.9).

    If no frames are received for more than 2 seconds, the handler notifies
    all streaming clients that the camera feed is unavailable (Requirement 1.7).

    Args:
        node: The ROS2 node used for creating subscriptions and timers.
        namespace: The robot namespace prefix (e.g., "/robot1").
        jpeg_quality: JPEG compression quality (10-100, default 75).
        send_callback: Async callback to send a message to a specific client.
            Signature: async def callback(client, message: str) -> None
    """

    def __init__(
        self,
        node: Node,
        namespace: str = "",
        jpeg_quality: int = _DEFAULT_JPEG_QUALITY,
        send_callback: Optional[Callable] = None,
    ):
        self._node = node
        self._namespace = namespace.rstrip("/")
        self._jpeg_quality = self._clamp_quality(jpeg_quality)
        self._send_callback = send_callback

        # Per-client frame queues: client -> deque of serialized frame strings.
        self._client_queues: Dict[Any, Deque[str]] = {}
        self._client_queues_lock = threading.Lock()

        # Track which clients have camera streaming enabled.
        self._streaming_clients: Set[Any] = set()
        self._streaming_clients_lock = threading.Lock()

        # Camera availability tracking.
        self._last_frame_time: Optional[float] = None
        self._last_frame_time_lock = threading.Lock()
        self._camera_available = False
        self._camera_available_lock = threading.Lock()

        # Asyncio event loop reference (set externally by the bridge node).
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Create the ROS2 subscription to the camera image topic.
        topic_name = f"{self._namespace}/viewport_camera/image_raw"
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self._image_sub = node.create_subscription(
            Image,
            topic_name,
            self._image_callback,
            qos_profile,
        )

        # Timer to check camera availability (runs every 1 second).
        self._availability_timer = node.create_timer(
            1.0, self._check_camera_availability
        )

        node.get_logger().info(
            f"CameraStreamHandler: subscribed to '{topic_name}' "
            f"with JPEG quality {self._jpeg_quality}"
        )

    @staticmethod
    def _clamp_quality(quality: int) -> int:
        """Clamp JPEG quality to valid range [10, 100]."""
        return max(_MIN_JPEG_QUALITY, min(_MAX_JPEG_QUALITY, int(quality)))

    @property
    def jpeg_quality(self) -> int:
        """Current JPEG compression quality setting."""
        return self._jpeg_quality

    @jpeg_quality.setter
    def jpeg_quality(self, value: int) -> None:
        """Set JPEG compression quality (clamped to [10, 100])."""
        self._jpeg_quality = self._clamp_quality(value)

    @property
    def camera_available(self) -> bool:
        """Whether the camera topic is currently publishing frames."""
        with self._camera_available_lock:
            return self._camera_available

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the asyncio event loop for scheduling async send operations."""
        self._loop = loop

    def enable_streaming(self, client: Any) -> None:
        """Enable camera streaming for a client.

        Creates a frame queue for the client and marks them as streaming.

        Args:
            client: The WebSocket client object.
        """
        with self._streaming_clients_lock:
            self._streaming_clients.add(client)
        with self._client_queues_lock:
            if client not in self._client_queues:
                self._client_queues[client] = deque(maxlen=_MAX_FRAME_QUEUE_SIZE)

    def disable_streaming(self, client: Any) -> None:
        """Disable camera streaming for a client.

        Removes the client from the streaming set and clears their queue.

        Args:
            client: The WebSocket client object.
        """
        with self._streaming_clients_lock:
            self._streaming_clients.discard(client)
        with self._client_queues_lock:
            self._client_queues.pop(client, None)

    def remove_client(self, client: Any) -> None:
        """Remove a client entirely (on disconnect).

        Cleans up both streaming state and frame queue for the client.

        Args:
            client: The WebSocket client object.
        """
        self.disable_streaming(client)

    def is_streaming(self, client: Any) -> bool:
        """Check whether a client has camera streaming enabled."""
        with self._streaming_clients_lock:
            return client in self._streaming_clients

    def get_queue_size(self, client: Any) -> int:
        """Get the current frame queue size for a client."""
        with self._client_queues_lock:
            queue = self._client_queues.get(client)
            return len(queue) if queue is not None else 0

    def _image_callback(self, msg: Image) -> None:
        """Handle incoming camera image messages from ROS2.

        Compresses the image to JPEG, encodes to base64, and enqueues
        the serialized frame for all streaming clients.
        """
        now = time.time()

        # Update last frame time for availability tracking.
        with self._last_frame_time_lock:
            self._last_frame_time = now

        # Mark camera as available if it was previously unavailable.
        with self._camera_available_lock:
            was_unavailable = not self._camera_available
            self._camera_available = True

        # Compress and encode the frame.
        frame_json = self._compress_and_encode(msg, now)
        if frame_json is None:
            return

        # Get the set of clients currently streaming.
        with self._streaming_clients_lock:
            streaming = self._streaming_clients.copy()

        if not streaming:
            return

        # Enqueue the frame for each streaming client.
        with self._client_queues_lock:
            for client in streaming:
                queue = self._client_queues.get(client)
                if queue is not None:
                    # deque(maxlen=2) automatically drops oldest when full.
                    queue.append(frame_json)

        # Schedule sending frames to clients.
        if self._loop is not None and self._send_callback is not None:
            for client in streaming:
                asyncio.run_coroutine_threadsafe(
                    self._send_queued_frames(client), self._loop
                )

        # If camera just recovered, notify streaming clients.
        if was_unavailable and self._loop is not None and self._send_callback is not None:
            for client in streaming:
                asyncio.run_coroutine_threadsafe(
                    self._notify_camera_status(client, available=True),
                    self._loop,
                )

    def _compress_and_encode(self, msg: Image, timestamp: float) -> Optional[str]:
        """Compress a ROS2 Image message to JPEG and encode as base64.

        Args:
            msg: The ROS2 sensor_msgs/Image message.
            timestamp: Frame timestamp in seconds.

        Returns:
            JSON string of the camera frame message, or None if compression fails.
        """
        try:
            # Convert ROS2 Image to numpy array.
            height = msg.height
            width = msg.width
            encoding = msg.encoding

            # Handle common image encodings.
            if encoding in ("rgb8", "RGB8"):
                channels = 3
                np_arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (height, width, channels)
                )
                # Convert RGB to BGR for OpenCV.
                np_arr = cv2.cvtColor(np_arr, cv2.COLOR_RGB2BGR)
            elif encoding in ("bgr8", "BGR8"):
                channels = 3
                np_arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (height, width, channels)
                )
            elif encoding in ("rgba8", "RGBA8"):
                channels = 4
                np_arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (height, width, channels)
                )
                np_arr = cv2.cvtColor(np_arr, cv2.COLOR_RGBA2BGR)
            elif encoding in ("bgra8", "BGRA8"):
                channels = 4
                np_arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (height, width, channels)
                )
                np_arr = cv2.cvtColor(np_arr, cv2.COLOR_BGRA2BGR)
            elif encoding in ("mono8", "MONO8"):
                np_arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (height, width)
                )
            else:
                # Unsupported encoding — attempt basic 3-channel interpretation.
                self._node.get_logger().warn(
                    f"CameraStreamHandler: unsupported encoding '{encoding}', "
                    f"attempting 3-channel interpretation"
                )
                np_arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                    (height, width, 3)
                )

            # Compress to JPEG.
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
            success, jpeg_buffer = cv2.imencode(".jpg", np_arr, encode_params)

            if not success:
                self._node.get_logger().warn(
                    "CameraStreamHandler: JPEG encoding failed"
                )
                return None

            # Encode to base64.
            data_base64 = base64.b64encode(jpeg_buffer.tobytes()).decode("ascii")

            # Serialize to JSON message.
            return serialize_camera_frame(
                timestamp=timestamp,
                width=width,
                height=height,
                quality=self._jpeg_quality,
                data_base64=data_base64,
            )

        except Exception as e:
            self._node.get_logger().warn(
                f"CameraStreamHandler: frame processing error: {e}"
            )
            return None

    async def _send_queued_frames(self, client: Any) -> None:
        """Send all queued frames to a client.

        Drains the client's frame queue and sends each frame. If a frame
        cannot be sent (client disconnected), stops sending.

        Args:
            client: The WebSocket client to send frames to.
        """
        if self._send_callback is None:
            return

        frames_to_send = []
        with self._client_queues_lock:
            queue = self._client_queues.get(client)
            if queue:
                # Drain all frames from the queue.
                while queue:
                    frames_to_send.append(queue.popleft())

        for frame in frames_to_send:
            await self._send_callback(client, frame)

    async def _notify_camera_status(self, client: Any, available: bool) -> None:
        """Send a camera status notification to a client.

        Args:
            client: The WebSocket client to notify.
            available: Whether the camera is currently available.
        """
        if self._send_callback is None:
            return

        import json
        status_msg = json.dumps({
            "type": "camera_status",
            "available": available,
        })
        await self._send_callback(client, status_msg)

    def _check_camera_availability(self) -> None:
        """Timer callback to detect camera topic unavailability.

        If no frames have been received for more than 2 seconds, marks
        the camera as unavailable and notifies all streaming clients.
        """
        now = time.time()

        with self._last_frame_time_lock:
            last_time = self._last_frame_time

        # If we've never received a frame, or if it's been too long.
        if last_time is None:
            # No frames ever received — camera is unavailable.
            with self._camera_available_lock:
                if not self._camera_available:
                    return  # Already marked unavailable, no notification needed.
                self._camera_available = False
        elif (now - last_time) > _CAMERA_UNAVAILABLE_TIMEOUT:
            with self._camera_available_lock:
                if not self._camera_available:
                    return  # Already notified.
                self._camera_available = False
        else:
            # Camera is still receiving frames — nothing to do.
            return

        # Notify all streaming clients that camera is unavailable.
        with self._streaming_clients_lock:
            streaming = self._streaming_clients.copy()

        if streaming and self._loop is not None and self._send_callback is not None:
            for client in streaming:
                asyncio.run_coroutine_threadsafe(
                    self._notify_camera_status(client, available=False),
                    self._loop,
                )

    def destroy(self) -> None:
        """Clean up ROS2 resources.

        Cancels the availability timer and destroys the subscription.
        Should be called when the bridge node shuts down.
        """
        if self._availability_timer is not None:
            self._availability_timer.cancel()
        if self._image_sub is not None:
            self._node.destroy_subscription(self._image_sub)
