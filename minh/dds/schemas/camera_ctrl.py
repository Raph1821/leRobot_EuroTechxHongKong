"""Camera Control schema for DDS."""

import rti.idl as idl


@idl.struct
class CameraCtrlInput:
    focal_len: float = 0.0
