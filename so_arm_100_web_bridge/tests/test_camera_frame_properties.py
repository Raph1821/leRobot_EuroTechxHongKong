"""Property-based tests for camera frame serialization round-trip.

Uses Hypothesis to verify that for any valid image dimensions (1×1 to 4096×4096
RGB) and JPEG quality [10, 100], compressing the image to JPEG and encoding to
base64 produces a non-empty string that, when decoded from base64 and
decompressed, yields a valid image with the same dimensions as the original.

Feature: web-control-expansion, Property 1: Camera frame serialization round-trip
"""

import base64
import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Valid JPEG quality range (matches camera_stream_handler.py)
MIN_JPEG_QUALITY = 10
MAX_JPEG_QUALITY = 100

# Image dimension bounds
MIN_DIMENSION = 1
MAX_DIMENSION = 4096


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for image width (1 to 4096)
image_width_strategy = st.integers(min_value=MIN_DIMENSION, max_value=MAX_DIMENSION)

# Strategy for image height (1 to 4096)
image_height_strategy = st.integers(min_value=MIN_DIMENSION, max_value=MAX_DIMENSION)

# Strategy for JPEG quality (10 to 100)
jpeg_quality_strategy = st.integers(min_value=MIN_JPEG_QUALITY, max_value=MAX_JPEG_QUALITY)


# ---------------------------------------------------------------------------
# Helper: compress and encode (mirrors camera_stream_handler logic)
# ---------------------------------------------------------------------------


def compress_and_encode(image: np.ndarray, quality: int) -> str:
    """Compress an image to JPEG and encode as base64.

    This mirrors the logic in CameraStreamHandler._compress_and_encode:
    1. cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    2. base64.b64encode(buffer.tobytes()).decode('ascii')

    Args:
        image: BGR or grayscale numpy array (H×W×3 uint8 for RGB).
        quality: JPEG compression quality in [10, 100].

    Returns:
        Base64-encoded string of the JPEG-compressed image.
    """
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    success, jpeg_buffer = cv2.imencode(".jpg", image, encode_params)
    assert success, "JPEG encoding should succeed for valid input"
    data_base64 = base64.b64encode(jpeg_buffer.tobytes()).decode("ascii")
    return data_base64


def decode_from_base64(data_base64: str) -> np.ndarray:
    """Decode a base64 JPEG string back to an image.

    Args:
        data_base64: Base64-encoded JPEG string.

    Returns:
        Decoded image as a numpy array.
    """
    jpeg_bytes = base64.b64decode(data_base64)
    jpeg_array = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    image = cv2.imdecode(jpeg_array, cv2.IMREAD_COLOR)
    return image


# ---------------------------------------------------------------------------
# Property 1: Camera frame serialization round-trip
# ---------------------------------------------------------------------------
# For any valid image buffer with dimensions between 1×1 and 4096×4096 pixels
# (RGB format) and for any JPEG quality setting in the range [10, 100],
# compressing the image to JPEG and encoding to base64 SHALL produce a
# non-empty string that, when decoded from base64 and decompressed, yields
# a valid image with the same dimensions as the original.
#
# **Validates: Requirements 1.2**
# ---------------------------------------------------------------------------


class TestCameraFrameSerializationRoundTrip:
    """Feature: web-control-expansion, Property 1: Camera frame serialization round-trip."""

    @given(
        width=image_width_strategy,
        height=image_height_strategy,
        quality=jpeg_quality_strategy,
    )
    @settings(max_examples=100)
    def test_compress_base64_encode_produces_non_empty_string(
        self, width: int, height: int, quality: int
    ):
        """**Validates: Requirements 1.2**

        For any valid RGB image dimensions and JPEG quality, compress+base64encode
        produces a non-empty string.
        """
        # Generate a random RGB image of the given dimensions
        image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)

        # Compress and encode
        data_base64 = compress_and_encode(image, quality)

        # Assert non-empty string
        assert isinstance(data_base64, str), "Result should be a string"
        assert len(data_base64) > 0, "Base64 encoded data should be non-empty"

    @given(
        width=image_width_strategy,
        height=image_height_strategy,
        quality=jpeg_quality_strategy,
    )
    @settings(max_examples=100)
    def test_base64_decodes_to_valid_image(
        self, width: int, height: int, quality: int
    ):
        """**Validates: Requirements 1.2**

        For any valid RGB image, the base64 string decodes back to a valid
        image (not None).
        """
        # Generate a random RGB image of the given dimensions
        image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)

        # Compress and encode
        data_base64 = compress_and_encode(image, quality)

        # Decode back
        decoded_image = decode_from_base64(data_base64)

        assert decoded_image is not None, (
            f"Decoding base64 JPEG should produce a valid image, "
            f"got None for {width}×{height} quality={quality}"
        )

    @given(
        width=image_width_strategy,
        height=image_height_strategy,
        quality=jpeg_quality_strategy,
    )
    @settings(max_examples=100)
    def test_round_trip_preserves_dimensions(
        self, width: int, height: int, quality: int
    ):
        """**Validates: Requirements 1.2**

        For any valid RGB image dimensions (1×1 to 4096×4096) and JPEG quality
        [10, 100], the full round-trip (compress → base64 encode → base64
        decode → decompress) produces an image with the same height and width
        as the original.
        """
        # Generate a random RGB image of the given dimensions
        image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)

        # Compress and encode
        data_base64 = compress_and_encode(image, quality)

        # Verify non-empty
        assert len(data_base64) > 0, "Base64 data must be non-empty"

        # Decode back
        decoded_image = decode_from_base64(data_base64)

        # Verify dimensions match
        assert decoded_image is not None, "Decoded image must not be None"
        decoded_height, decoded_width = decoded_image.shape[:2]

        assert decoded_height == height, (
            f"Height mismatch: original={height}, decoded={decoded_height}"
        )
        assert decoded_width == width, (
            f"Width mismatch: original={width}, decoded={decoded_width}"
        )
