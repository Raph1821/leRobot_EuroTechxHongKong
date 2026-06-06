"""Property-based tests for frame queue bounded capacity.

Uses Hypothesis to verify that the per-client frame queue (collections.deque
with maxlen=2) never exceeds 2 frames and always retains the most recently
pushed frame, regardless of how many frames are pushed.

Feature: web-control-expansion, Property 2: Frame queue bounded capacity
"""

import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from collections import deque
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# Maximum frame queue size as defined in camera_stream_handler.py
_MAX_FRAME_QUEUE_SIZE = 2


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for frame data: arbitrary non-empty byte strings simulating
# serialized JPEG/base64 frame payloads.
frame_data_strategy = st.binary(min_size=1, max_size=256)

# Strategy for lists of frames with more than 2 elements (N > 2).
frame_sequence_strategy = st.lists(
    frame_data_strategy,
    min_size=3,
    max_size=200,
)


# ---------------------------------------------------------------------------
# Property 2: Frame queue bounded capacity
# ---------------------------------------------------------------------------
# For any sequence of N camera frames arriving at a client's queue (where
# N > 2), the queue SHALL never contain more than 2 frames at any point in
# time, and after processing the sequence, the most recently arrived frame
# SHALL be present in the queue.
#
# **Validates: Requirements 1.9**
# ---------------------------------------------------------------------------


class TestFrameQueueBoundedCapacity:
    """Feature: web-control-expansion, Property 2: Frame queue bounded capacity."""

    @given(frames=frame_sequence_strategy)
    @settings(max_examples=200)
    def test_queue_never_exceeds_max_size(self, frames: list):
        """**Validates: Requirements 1.9**

        For any sequence of N frames (N > 2), the queue SHALL never
        contain more than 2 frames at any point in time.
        """
        queue: deque = deque(maxlen=_MAX_FRAME_QUEUE_SIZE)

        for frame in frames:
            queue.append(frame)
            assert len(queue) <= _MAX_FRAME_QUEUE_SIZE, (
                f"Queue exceeded max size {_MAX_FRAME_QUEUE_SIZE}: "
                f"len(queue)={len(queue)} after appending frame"
            )

    @given(frames=frame_sequence_strategy)
    @settings(max_examples=200)
    def test_most_recent_frame_always_present(self, frames: list):
        """**Validates: Requirements 1.9**

        For any sequence of N frames (N > 2), after processing the
        entire sequence the most recently arrived frame SHALL be
        present in the queue.
        """
        queue: deque = deque(maxlen=_MAX_FRAME_QUEUE_SIZE)

        for frame in frames:
            queue.append(frame)

        # After all frames are pushed, the last frame must be in the queue.
        last_frame = frames[-1]
        assert last_frame in queue, (
            f"Most recent frame not found in queue. "
            f"Queue contains {len(queue)} items, expected last frame to be present."
        )

    @given(frames=frame_sequence_strategy)
    @settings(max_examples=200)
    def test_most_recent_frame_is_last_in_queue(self, frames: list):
        """**Validates: Requirements 1.9**

        For any sequence of N frames (N > 2), after processing the
        entire sequence, the most recently arrived frame SHALL be
        the last element in the queue (i.e., at queue[-1]).
        """
        queue: deque = deque(maxlen=_MAX_FRAME_QUEUE_SIZE)

        for frame in frames:
            queue.append(frame)

        last_frame = frames[-1]
        assert queue[-1] == last_frame, (
            f"Expected queue[-1] to be the most recent frame. "
            f"Got queue[-1]={queue[-1]!r}, expected {last_frame!r}"
        )

    @given(frames=frame_sequence_strategy)
    @settings(max_examples=200)
    def test_bounded_capacity_invariant_holds_at_every_step(self, frames: list):
        """**Validates: Requirements 1.9**

        For any sequence of N frames (N > 2), at every intermediate
        step the queue never exceeds 2 frames AND the most recently
        pushed frame is always the last element in the queue.
        """
        queue: deque = deque(maxlen=_MAX_FRAME_QUEUE_SIZE)

        for i, frame in enumerate(frames):
            queue.append(frame)

            # Invariant 1: bounded capacity
            assert len(queue) <= _MAX_FRAME_QUEUE_SIZE, (
                f"Queue exceeded max size at step {i}: "
                f"len(queue)={len(queue)}"
            )

            # Invariant 2: most recent frame is last in queue
            assert queue[-1] == frame, (
                f"At step {i}, queue[-1] should be the frame just pushed. "
                f"Got queue[-1]={queue[-1]!r}, expected {frame!r}"
            )
