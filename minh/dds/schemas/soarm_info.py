"""SO-ARM101 Info schema for DDS."""

from dataclasses import field
from typing import Sequence

import rti.idl as idl


@idl.struct
class SOARM101Info:
    joints_state_positions: Sequence[float] = field(default_factory=idl.array_factory(float))
    joints_state_velocities: Sequence[float] = field(default_factory=idl.array_factory(float))
