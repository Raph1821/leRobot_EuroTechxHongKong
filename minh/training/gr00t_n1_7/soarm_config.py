"""
SO-ARM embodiment config for GR00T N1.7 fine-tuning.
Registers the modality config so GR00T knows how to interpret SO-ARM data.

This MUST be imported before running training so the config is registered.
"""

from gr00t.configs.data.embodiment_configs import register_modality_config
from gr00t.data.embodiment_tags import EmbodimentTag
from gr00t.data.types import ActionConfig, ActionFormat, ActionRepresentation, ActionType, ModalityConfig

so_arm_config = {
    # Video: current frame only
    "video": ModalityConfig(
        delta_indices=[0],
        modality_keys=["room", "wrist"],
    ),
    # State: current proprioceptive reading
    "state": ModalityConfig(
        delta_indices=[0],
        modality_keys=["single_arm", "gripper"],
    ),
    # Action: 16-step prediction horizon
    "action": ModalityConfig(
        delta_indices=list(range(0, 16)),
        modality_keys=["single_arm", "gripper"],
        action_configs=[
            ActionConfig(
                rep=ActionRepresentation.ABSOLUTE,
                type=ActionType.NON_EEF,
                format=ActionFormat.DEFAULT,
            ),
            ActionConfig(
                rep=ActionRepresentation.ABSOLUTE,
                type=ActionType.NON_EEF,
                format=ActionFormat.DEFAULT,
            ),
        ],
    ),
    # Language: task instruction
    "language": ModalityConfig(
        delta_indices=[0],
        modality_keys=["annotation.human.task_description"],
    ),
}

register_modality_config(so_arm_config, embodiment_tag=EmbodimentTag.NEW_EMBODIMENT)
