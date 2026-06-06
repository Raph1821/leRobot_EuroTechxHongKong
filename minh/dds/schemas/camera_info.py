"""Camera Info schema for DDS."""

from dataclasses import field
from typing import Sequence

import rti.idl as idl


@idl.struct
class CameraInfo:
    focal_len: float = 0.0
    stream_id: int = 0
    frame_num: int = 0
    width: int = 0
    height: int = 0
    data: Sequence[idl.uint8] = field(default_factory=idl.array_factory(idl.uint8))
