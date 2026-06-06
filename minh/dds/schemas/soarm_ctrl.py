"""SO-ARM101 Control Input schema for DDS."""

from dataclasses import field
from typing import Sequence

import rti.idl as idl


@idl.struct
class SOARM101CtrlInput:
    joint_positions: Sequence[float] = field(default_factory=idl.array_factory(float))
    joint_velocities: Sequence[float] = field(default_factory=idl.array_factory(float))
    joint_efforts: Sequence[float] = field(default_factory=idl.array_factory(float))
