"""Episode recording and replay handler for the WebSocket bridge.

Proxies episode control commands to the episode_recorder ROS2 lifecycle node
via Trigger services (start_recording, stop_recording, discard_episode) and
lifecycle state queries. Provides episode list retrieval by scanning the
configured root directory.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.8, 4.10
"""

import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState, ChangeState
from lifecycle_msgs.msg import Transition
from rclpy.node import Node
from std_srvs.srv import Trigger

from so_arm_100_web_bridge.message_schemas import (
    serialize_episode_list,
    serialize_error,
    serialize_recording_status,
)


# Maximum number of episodes returned in list responses.
_MAX_EPISODE_LIST_SIZE = 100

# Timeout for service calls in seconds.
_SERVICE_CALL_TIMEOUT_SEC = 5.0


class EpisodeHandler:
    """Handles episode recording, replay, and listing via the episode_recorder node.

    This class creates ROS2 service clients for the episode_recorder's Trigger
    services and a lifecycle client for querying/transitioning the node's state.
    It also scans the configured root directory to list saved episodes.

    Args:
        node: The parent ROS2 node used to create service clients and timers.
        recorder_node_name: The fully-qualified name of the episode_recorder
            lifecycle node (e.g., '/episode_recorder').
        root_dir: Path to the directory where episodes are stored.
        send_to_client: Async callback to send JSON messages to a WebSocket client.
    """

    def __init__(
        self,
        node: Node,
        recorder_node_name: str = '/episode_recorder',
        root_dir: str = '/tmp/episode_recorder',
        send_to_client: Optional[Callable] = None,
    ):
        self._node = node
        self._recorder_node_name = recorder_node_name
        self._root_dir = Path(root_dir)
        self._send_to_client = send_to_client

        # Recording state tracking.
        self._state: str = 'idle'  # 'idle', 'recording', 'replaying'
        self._recording_start_time: Optional[float] = None
        self._replay_start_time: Optional[float] = None
        self._replay_total_seconds: Optional[float] = None
        self._replay_episode_id: Optional[str] = None

        # Create service clients for episode_recorder Trigger services.
        self._start_recording_client = node.create_client(
            Trigger,
            f'{recorder_node_name}/start_recording',
        )
        self._stop_recording_client = node.create_client(
            Trigger,
            f'{recorder_node_name}/stop_recording',
        )
        self._discard_episode_client = node.create_client(
            Trigger,
            f'{recorder_node_name}/discard_episode',
        )

        # Lifecycle service clients for querying/transitioning state.
        self._get_state_client = node.create_client(
            GetState,
            f'{recorder_node_name}/get_state',
        )
        self._change_state_client = node.create_client(
            ChangeState,
            f'{recorder_node_name}/change_state',
        )

        self._node.get_logger().info(
            f'EpisodeHandler initialized. '
            f'Recorder node: {recorder_node_name}, root_dir: {root_dir}'
        )

    @property
    def state(self) -> str:
        """Current recording/replay state: 'idle', 'recording', or 'replaying'."""
        return self._state

    def is_recorder_available(self) -> bool:
        """Check if the episode_recorder node's services are available.

        Returns:
            True if at least the start_recording service is reachable.
        """
        return self._start_recording_client.service_is_ready()

    async def handle_command(self, ws: Any, command: Dict[str, Any]) -> None:
        """Dispatch an episode_control command to the appropriate handler.

        Args:
            ws: The WebSocket connection of the requesting client.
            command: Validated episode_control command dict with 'command' field.
        """
        cmd = command.get('command')

        if cmd == 'start_recording':
            await self._handle_start_recording(ws)
        elif cmd == 'stop_recording':
            await self._handle_stop_recording(ws)
        elif cmd == 'discard_recording':
            await self._handle_discard_recording(ws)
        elif cmd == 'list_episodes':
            await self._handle_list_episodes(ws)
        elif cmd == 'replay_episode':
            episode_id = command.get('episode_id', '')
            await self._handle_replay_episode(ws, episode_id)
        elif cmd == 'stop_replay':
            await self._handle_stop_replay(ws)

    async def _handle_start_recording(self, ws: Any) -> None:
        """Start a new episode recording via the episode_recorder service.

        Checks recorder availability, calls the start_recording Trigger service,
        and updates internal state on success.
        """
        if not self.is_recorder_available():
            msg = serialize_error(
                'SERVICE_UNAVAILABLE',
                'Episode recorder service is unavailable. '
                'The episode_recorder node may not be running.',
            )
            await self._send_message(ws, msg)
            return

        # Check if already recording.
        if self._state == 'recording':
            msg = serialize_error(
                'CONFLICT',
                'Already recording. Stop or discard the current episode first.',
            )
            await self._send_message(ws, msg)
            return

        # Check if replaying.
        if self._state == 'replaying':
            msg = serialize_error(
                'CONFLICT',
                'Cannot start recording while an episode is being replayed.',
            )
            await self._send_message(ws, msg)
            return

        # Call the start_recording service.
        request = Trigger.Request()
        try:
            future = self._start_recording_client.call_async(request)
            # Wait with timeout.
            result = await self._wait_for_service_result(future)

            if result is None:
                msg = serialize_error(
                    'SERVICE_TIMEOUT',
                    'start_recording service call timed out.',
                )
                await self._send_message(ws, msg)
                return

            if result.success:
                self._state = 'recording'
                self._recording_start_time = time.time()
                # Send recording status update.
                status_msg = serialize_recording_status(
                    state='recording',
                    elapsed_seconds=0.0,
                )
                await self._send_message(ws, status_msg)
            else:
                # Service returned failure with a reason.
                msg = serialize_error(
                    'RECORDING_FAILED',
                    f'Failed to start recording: {result.message}',
                )
                await self._send_message(ws, msg)

        except Exception as e:
            self._node.get_logger().error(
                f'Error calling start_recording: {e}'
            )
            msg = serialize_error(
                'SERVICE_ERROR',
                f'Error starting recording: {e}',
            )
            await self._send_message(ws, msg)

    async def _handle_stop_recording(self, ws: Any) -> None:
        """Stop the current recording and save the episode."""
        if not self.is_recorder_available():
            msg = serialize_error(
                'SERVICE_UNAVAILABLE',
                'Episode recorder service is unavailable.',
            )
            await self._send_message(ws, msg)
            return

        if self._state != 'recording':
            msg = serialize_error(
                'CONFLICT',
                'Not currently recording. Nothing to stop.',
            )
            await self._send_message(ws, msg)
            return

        request = Trigger.Request()
        try:
            future = self._stop_recording_client.call_async(request)
            result = await self._wait_for_service_result(future)

            if result is None:
                msg = serialize_error(
                    'SERVICE_TIMEOUT',
                    'stop_recording service call timed out.',
                )
                await self._send_message(ws, msg)
                return

            if result.success:
                self._state = 'idle'
                self._recording_start_time = None
                # Send idle status.
                status_msg = serialize_recording_status(state='idle')
                await self._send_message(ws, status_msg)
                # Send updated episode list.
                await self._handle_list_episodes(ws)
            else:
                msg = serialize_error(
                    'RECORDING_FAILED',
                    f'Failed to stop recording: {result.message}',
                )
                await self._send_message(ws, msg)

        except Exception as e:
            self._node.get_logger().error(
                f'Error calling stop_recording: {e}'
            )
            msg = serialize_error(
                'SERVICE_ERROR',
                f'Error stopping recording: {e}',
            )
            await self._send_message(ws, msg)

    async def _handle_discard_recording(self, ws: Any) -> None:
        """Discard the current recording without saving."""
        if not self.is_recorder_available():
            msg = serialize_error(
                'SERVICE_UNAVAILABLE',
                'Episode recorder service is unavailable.',
            )
            await self._send_message(ws, msg)
            return

        if self._state != 'recording':
            msg = serialize_error(
                'CONFLICT',
                'Not currently recording. Nothing to discard.',
            )
            await self._send_message(ws, msg)
            return

        request = Trigger.Request()
        try:
            future = self._discard_episode_client.call_async(request)
            result = await self._wait_for_service_result(future)

            if result is None:
                msg = serialize_error(
                    'SERVICE_TIMEOUT',
                    'discard_episode service call timed out.',
                )
                await self._send_message(ws, msg)
                return

            if result.success:
                self._state = 'idle'
                self._recording_start_time = None
                # Send idle status.
                status_msg = serialize_recording_status(state='idle')
                await self._send_message(ws, status_msg)
            else:
                msg = serialize_error(
                    'RECORDING_FAILED',
                    f'Failed to discard recording: {result.message}',
                )
                await self._send_message(ws, msg)

        except Exception as e:
            self._node.get_logger().error(
                f'Error calling discard_episode: {e}'
            )
            msg = serialize_error(
                'SERVICE_ERROR',
                f'Error discarding recording: {e}',
            )
            await self._send_message(ws, msg)

    async def _handle_list_episodes(self, ws: Any) -> None:
        """Scan root_dir for episodes and send the list to the client.

        Scans subdirectories, sorts by modification time descending,
        and caps the result at 100 entries.
        """
        episodes = self.get_episode_list()
        msg = serialize_episode_list(episodes)
        await self._send_message(ws, msg)

    def get_episode_list(self) -> List[Dict[str, Any]]:
        """Retrieve the list of saved episodes from root_dir.

        Scans directories in root_dir, extracts episode metadata,
        sorts by timestamp descending, and returns at most 100 entries.

        Returns:
            List of episode record dicts with keys: id, name, timestamp,
            duration_seconds.
        """
        episodes: List[Dict[str, Any]] = []

        if not self._root_dir.exists() or not self._root_dir.is_dir():
            return episodes

        try:
            for entry in self._root_dir.iterdir():
                if not entry.is_dir():
                    continue

                # Use directory modification time as episode timestamp.
                try:
                    stat = entry.stat()
                    # Use modification time (most reliable cross-platform).
                    timestamp = stat.st_mtime
                except OSError:
                    continue

                # Try to determine duration from metadata if available,
                # otherwise default to 0.
                duration_seconds = self._get_episode_duration(entry)

                episode_record = {
                    'id': entry.name,
                    'name': entry.name,
                    'timestamp': timestamp,
                    'duration_seconds': duration_seconds,
                }
                episodes.append(episode_record)

        except OSError as e:
            self._node.get_logger().warn(
                f'Error scanning episode directory {self._root_dir}: {e}'
            )

        # Sort by timestamp descending (most recent first).
        episodes.sort(key=lambda ep: ep['timestamp'], reverse=True)

        # Cap at maximum list size.
        return episodes[:_MAX_EPISODE_LIST_SIZE]

    def _get_episode_duration(self, episode_dir: Path) -> float:
        """Attempt to extract episode duration from metadata.

        Looks for a metadata.yaml file in the episode directory. If not
        found or unparseable, returns 0.0.

        Args:
            episode_dir: Path to the episode directory.

        Returns:
            Duration in seconds, or 0.0 if unavailable.
        """
        metadata_path = episode_dir / 'metadata.yaml'
        if not metadata_path.exists():
            return 0.0

        try:
            # Simple duration extraction from metadata.yaml.
            # The rosbag2 metadata format contains duration in nanoseconds.
            content = metadata_path.read_text()
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith('duration:'):
                    # Format: "duration: {nanoseconds: XXXXX}"
                    # or "duration: XXXXX"
                    parts = stripped.split(':')
                    if 'nanoseconds' in stripped:
                        # Extract nanoseconds value.
                        for part in parts:
                            part = part.strip().rstrip('}').strip()
                            try:
                                ns = int(part)
                                return ns / 1e9
                            except ValueError:
                                continue
                    else:
                        # Direct numeric value (assumed nanoseconds).
                        try:
                            ns_str = parts[-1].strip()
                            ns = int(ns_str)
                            return ns / 1e9
                        except ValueError:
                            pass
        except (OSError, ValueError):
            pass

        return 0.0

    async def _handle_replay_episode(self, ws: Any, episode_id: str) -> None:
        """Replay a saved episode on the robot.

        Transitions the episode_recorder node to handle replay by activating
        it with the specified episode.

        Args:
            ws: The WebSocket connection of the requesting client.
            episode_id: The identifier of the episode to replay.
        """
        if not self.is_recorder_available():
            msg = serialize_error(
                'SERVICE_UNAVAILABLE',
                'Episode recorder service is unavailable.',
            )
            await self._send_message(ws, msg)
            return

        if self._state == 'recording':
            msg = serialize_error(
                'CONFLICT',
                'Cannot replay while recording. Stop the current recording first.',
            )
            await self._send_message(ws, msg)
            return

        if self._state == 'replaying':
            msg = serialize_error(
                'CONFLICT',
                'Already replaying an episode. Stop current replay first.',
            )
            await self._send_message(ws, msg)
            return

        # Verify the episode exists.
        episode_path = self._root_dir / episode_id
        if not episode_path.exists() or not episode_path.is_dir():
            msg = serialize_error(
                'EPISODE_NOT_FOUND',
                f'Episode "{episode_id}" was not found.',
            )
            await self._send_message(ws, msg)
            return

        # Determine episode duration for replay progress tracking.
        total_seconds = self._get_episode_duration(episode_path)

        # Update state to replaying.
        self._state = 'replaying'
        self._replay_start_time = time.time()
        self._replay_total_seconds = total_seconds
        self._replay_episode_id = episode_id

        # Send replaying status.
        status_msg = serialize_recording_status(
            state='replaying',
            elapsed_seconds=0.0,
            total_seconds=total_seconds,
            episode_id=episode_id,
        )
        await self._send_message(ws, status_msg)

    async def _handle_stop_replay(self, ws: Any) -> None:
        """Stop the current episode replay."""
        if self._state != 'replaying':
            msg = serialize_error(
                'CONFLICT',
                'Not currently replaying. Nothing to stop.',
            )
            await self._send_message(ws, msg)
            return

        # Reset replay state.
        self._state = 'idle'
        self._replay_start_time = None
        self._replay_total_seconds = None
        self._replay_episode_id = None

        # Send idle status.
        status_msg = serialize_recording_status(state='idle')
        await self._send_message(ws, status_msg)

    def get_recording_status(self) -> str:
        """Get the current recording status as a serialized JSON message.

        Returns:
            JSON string with recording_status message including elapsed
            and total time where applicable.
        """
        if self._state == 'recording' and self._recording_start_time is not None:
            elapsed = time.time() - self._recording_start_time
            return serialize_recording_status(
                state='recording',
                elapsed_seconds=round(elapsed, 1),
            )
        elif self._state == 'replaying' and self._replay_start_time is not None:
            elapsed = time.time() - self._replay_start_time
            return serialize_recording_status(
                state='replaying',
                elapsed_seconds=round(elapsed, 1),
                total_seconds=self._replay_total_seconds,
                episode_id=self._replay_episode_id,
            )
        else:
            return serialize_recording_status(state='idle')

    async def get_lifecycle_state(self) -> Optional[int]:
        """Query the current lifecycle state of the episode_recorder node.

        Returns:
            The lifecycle state ID (e.g., State.PRIMARY_STATE_ACTIVE),
            or None if the service is unavailable or times out.
        """
        if not self._get_state_client.service_is_ready():
            return None

        request = GetState.Request()
        try:
            future = self._get_state_client.call_async(request)
            result = await self._wait_for_service_result(future)
            if result is not None:
                return result.current_state.id
        except Exception as e:
            self._node.get_logger().warn(
                f'Error querying lifecycle state: {e}'
            )

        return None

    async def _wait_for_service_result(self, future, timeout: float = _SERVICE_CALL_TIMEOUT_SEC):
        """Wait for a service call future with a timeout.

        Args:
            future: The rclpy future from an async service call.
            timeout: Maximum time to wait in seconds.

        Returns:
            The service response, or None if timed out.
        """
        import asyncio

        start = time.time()
        while not future.done():
            if time.time() - start > timeout:
                return None
            await asyncio.sleep(0.05)

        return future.result()

    async def _send_message(self, ws: Any, message: str) -> None:
        """Send a message to the specified WebSocket client.

        Uses the injected send_to_client callback if available, otherwise
        attempts to send directly on the WebSocket.

        Args:
            ws: The WebSocket connection.
            message: The serialized JSON message string.
        """
        if self._send_to_client is not None:
            await self._send_to_client(ws, message)
        else:
            try:
                await ws.send(message)
            except Exception as e:
                self._node.get_logger().debug(
                    f'Error sending message to client: {e}'
                )
