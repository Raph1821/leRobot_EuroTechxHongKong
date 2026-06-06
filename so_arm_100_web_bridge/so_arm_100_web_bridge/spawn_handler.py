"""Object spawn and delete handler for the WebSocket bridge.

This module implements the SpawnHandler class that manages object
spawning and deletion in the Isaac Sim environment via ROS2 services.
It validates incoming spawn requests, calls the appropriate services,
tracks spawned objects per client, and sends confirmations or errors
back to the requesting client.

Requirements: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8, 2.9
"""

import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from rclpy.node import Node
from rclpy.client import Client

from so_arm_100_web_bridge.message_schemas import (
    SPAWN_BOUNDS,
    SpawnBounds,
    serialize_delete_confirm,
    serialize_error,
    serialize_spawn_confirm,
    validate_spawn_request,
)


class SpawnHandler:
    """Handles object spawn and delete requests from WebSocket clients.

    This handler:
    - Validates spawn requests against SpawnBounds
    - Validates dimension array length matches object type
    - Calls /spawn_object and /delete_object ROS2 services
    - Tracks spawned objects per client with assigned IDs
    - Handles service unavailability with SERVICE_UNAVAILABLE error
    - Handles delete of unknown object ID with OBJECT_NOT_FOUND error
    - Sends spawn/delete confirmations back to requesting client

    Args:
        node: The ROS2 node used to create service clients.
        spawn_service_type: The ROS2 service type for /spawn_object.
        delete_service_type: The ROS2 service type for /delete_object.
        send_to_client: Async callable to send a message string to a client.
        bounds: SpawnBounds instance for validation. Defaults to SPAWN_BOUNDS.
        service_timeout_sec: Timeout in seconds when waiting for service
            availability. Defaults to 1.0.
    """

    def __init__(
        self,
        node: Node,
        spawn_service_type: Any,
        delete_service_type: Any,
        send_to_client: Callable[[Any, str], Coroutine],
        bounds: Optional[SpawnBounds] = None,
        service_timeout_sec: float = 1.0,
    ):
        self._node = node
        self._send_to_client = send_to_client
        self._bounds = bounds if bounds is not None else SPAWN_BOUNDS
        self._service_timeout_sec = service_timeout_sec

        # Create ROS2 service clients.
        self._spawn_client: Client = node.create_client(
            spawn_service_type, '/spawn_object'
        )
        self._delete_client: Client = node.create_client(
            delete_service_type, '/delete_object'
        )

        # Store service types for constructing requests.
        self._spawn_service_type = spawn_service_type
        self._delete_service_type = delete_service_type

        # Track spawned objects per client.
        # Key: client identifier (websocket), Value: set of object IDs.
        self._client_objects: Dict[Any, Set[str]] = {}

        # Global object registry: object_id -> client that spawned it.
        self._object_registry: Dict[str, Any] = {}

        self._node.get_logger().info('SpawnHandler initialized.')

    async def handle_spawn(self, ws: Any, data: Dict[str, Any]) -> None:
        """Handle a spawn_object request from a WebSocket client.

        Validates the request, calls the /spawn_object service, and sends
        a confirmation or error back to the client.

        Args:
            ws: The WebSocket connection of the requesting client.
            data: Validated spawn request data containing object_type,
                  dimensions, position, orientation, color, and mass.
        """
        # Validate spawn request against bounds.
        is_valid, error_msg = validate_spawn_request(data, self._bounds)
        if not is_valid:
            error_json = serialize_error('VALIDATION_ERROR', error_msg)
            await self._send_to_client(ws, error_json)
            return

        # Check if the spawn service is available.
        if not self._spawn_client.service_is_ready():
            if not self._spawn_client.wait_for_service(
                timeout_sec=self._service_timeout_sec
            ):
                error_json = serialize_error(
                    'SERVICE_UNAVAILABLE',
                    'Spawn service (/spawn_object) is not available',
                )
                await self._send_to_client(ws, error_json)
                return

        # Construct the service request.
        request = self._spawn_service_type.Request()
        request.object_type = data['object_type']
        request.dimensions = [float(d) for d in data['dimensions']]
        request.position = [float(p) for p in data['position']]
        request.orientation = [float(o) for o in data['orientation']]
        request.color = [float(c) for c in data['color']]
        request.mass = float(data['mass'])

        # Call the service asynchronously.
        try:
            future = self._spawn_client.call_async(request)
            response = await asyncio.wrap_future(future)
        except Exception as e:
            error_json = serialize_error(
                'SERVICE_UNAVAILABLE',
                f'Spawn service call failed: {e}',
            )
            await self._send_to_client(ws, error_json)
            return

        # Process the response.
        if not response.success:
            error_json = serialize_error(
                'SPAWN_FAILED',
                response.error_message or 'Spawn request failed',
            )
            await self._send_to_client(ws, error_json)
            return

        # Track the spawned object for this client.
        object_id = response.object_id
        if ws not in self._client_objects:
            self._client_objects[ws] = set()
        self._client_objects[ws].add(object_id)
        self._object_registry[object_id] = ws

        # Send spawn confirmation to the requesting client.
        confirm_json = serialize_spawn_confirm(
            object_id=object_id,
            object_type=data['object_type'],
            dimensions=[float(d) for d in data['dimensions']],
            position=[float(p) for p in data['position']],
            orientation=[float(o) for o in data['orientation']],
            color=[float(c) for c in data['color']],
            mass=float(data['mass']),
        )
        await self._send_to_client(ws, confirm_json)

        self._node.get_logger().info(
            f'Object spawned: {object_id} (type={data["object_type"]})'
        )

    async def handle_delete(self, ws: Any, data: Dict[str, Any]) -> None:
        """Handle a delete_object request from a WebSocket client.

        Validates the object ID exists, calls the /delete_object service,
        and sends a confirmation or error back to the client.

        Args:
            ws: The WebSocket connection of the requesting client.
            data: Validated delete request data containing object_id.
        """
        object_id = data.get('object_id', '')

        # Check if the object ID is known.
        if object_id not in self._object_registry:
            error_json = serialize_error(
                'OBJECT_NOT_FOUND',
                f'Object with ID \'{object_id}\' was not found',
            )
            await self._send_to_client(ws, error_json)
            return

        # Check if the delete service is available.
        if not self._delete_client.service_is_ready():
            if not self._delete_client.wait_for_service(
                timeout_sec=self._service_timeout_sec
            ):
                error_json = serialize_error(
                    'SERVICE_UNAVAILABLE',
                    'Delete service (/delete_object) is not available',
                )
                await self._send_to_client(ws, error_json)
                return

        # Construct the service request.
        request = self._delete_service_type.Request()
        request.object_id = object_id

        # Call the service asynchronously.
        try:
            future = self._delete_client.call_async(request)
            response = await asyncio.wrap_future(future)
        except Exception as e:
            error_json = serialize_error(
                'SERVICE_UNAVAILABLE',
                f'Delete service call failed: {e}',
            )
            await self._send_to_client(ws, error_json)
            return

        # Process the response.
        if not response.success:
            error_json = serialize_error(
                'DELETE_FAILED',
                response.error_message or 'Delete request failed',
            )
            await self._send_to_client(ws, error_json)
            return

        # Remove the object from tracking.
        owner_ws = self._object_registry.pop(object_id, None)
        if owner_ws is not None and owner_ws in self._client_objects:
            self._client_objects[owner_ws].discard(object_id)

        # Send delete confirmation to the requesting client.
        confirm_json = serialize_delete_confirm(object_id)
        await self._send_to_client(ws, confirm_json)

        self._node.get_logger().info(f'Object deleted: {object_id}')

    def get_client_objects(self, ws: Any) -> List[str]:
        """Get the list of object IDs spawned by a specific client.

        Args:
            ws: The WebSocket connection of the client.

        Returns:
            List of object ID strings spawned by this client.
        """
        return list(self._client_objects.get(ws, set()))

    def remove_client(self, ws: Any) -> None:
        """Clean up tracking data when a client disconnects.

        Note: This does NOT delete the objects from the simulation.
        Objects persist until explicitly deleted or the simulation resets.

        Args:
            ws: The WebSocket connection of the disconnecting client.
        """
        if ws in self._client_objects:
            for object_id in self._client_objects[ws]:
                self._object_registry.pop(object_id, None)
            del self._client_objects[ws]
