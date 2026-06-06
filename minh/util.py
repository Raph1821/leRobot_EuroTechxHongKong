"""Utility functions for the medicine robot workflow."""

import os


def resolve_recording_path(recording_path: str) -> str:
    """Resolve HDF5 teleoperation recording path.
    
    If an absolute path is given, returns as-is.
    Otherwise, resolves relative to the data directory.
    """
    if os.path.isabs(recording_path):
        return recording_path
    parent_output_dir = os.getenv("HOLOHUB_DATA_PATH", "") or os.path.abspath("./data")
    default_output_dir = os.path.join(parent_output_dir, "medicine_robot", "recordings")
    return os.path.normpath(os.path.join(default_output_dir, recording_path))
