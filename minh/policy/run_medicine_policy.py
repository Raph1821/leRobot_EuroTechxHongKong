"""
Medicine Pick & Place Policy Runner

Adapted from the SO-ARM Starter's run_policy.py for medicine handling tasks.
Supports dynamic task descriptions for different medicine operations:
  - "Pick up the red bottle and place it in tray A"
  - "Pick up the blue pill box and place it in the morning slot"
  - "Grip the medicine bottle and bring it closer for reading"

Usage:
    python -m policy.run_medicine_policy \
        --ckpt_path /path/to/model \
        --task_description "Pick up the medicine and place it in the correct slot"
"""

import argparse
import os

os.environ.pop("LD_PRELOAD", None)

import numpy as np
from dds.publisher import Publisher
from dds.schemas.camera_info import CameraInfo
from dds.schemas.soarm_ctrl import SOARM101CtrlInput
from dds.schemas.soarm_info import SOARM101Info
from dds.subscriber import SubscriberWithCallback
from PIL import Image
from policy.gr00tn1_7.runners import GR00TN1_7_PolicyRunner

os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

current_state = {
    "room_cam": None,
    "wrist_cam": None,
    "joint_pos": None,
}


def main():
    parser = argparse.ArgumentParser(description="Run medicine pick-and-place policy")
    parser.add_argument(
        "--ckpt_path",
        type=str,
        default="/root/models/SO_ARM_Starter_Gr00tN17",
        help="Checkpoint path for the GR00T N1.7 model.",
    )
    parser.add_argument(
        "--task_description",
        type=str,
        default="Pick up the medicine and place it in the correct slot",
        help="Natural language task description.",
    )
    parser.add_argument(
        "--embodiment_tag",
        type=str,
        default="new_embodiment",
        help="The embodiment tag for the model.",
    )
    parser.add_argument(
        "--rti_license_file", type=str, default=os.getenv("RTI_LICENSE_FILE"),
    )
    parser.add_argument("--domain_id", type=int, default=0)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--topic_in_room_camera", type=str, default="topic_room_camera_data_rgb")
    parser.add_argument("--topic_in_wrist_camera", type=str, default="topic_wrist_camera_data_rgb")
    parser.add_argument("--topic_in_soarm_pos", type=str, default="topic_soarm_info")
    parser.add_argument("--topic_out", type=str, default="topic_soarm_ctrl")
    parser.add_argument("--verbose", type=bool, default=False)
    parser.add_argument("--chunk_length", type=int, default=16)
    parser.add_argument("--trt_engine_path", type=str, default=None)
    parser.add_argument(
        "--trt_mode", type=str, default="n17_full_pipeline",
        choices=["n17_full_pipeline", "vit_llm_only", "action_head", "dit_only"],
    )
    args = parser.parse_args()

    policy = GR00TN1_7_PolicyRunner(
        ckpt_path=args.ckpt_path,
        embodiment_tag=args.embodiment_tag,
        task_description=args.task_description,
        trt_engine_path=args.trt_engine_path,
        trt_mode=args.trt_mode,
    )

    if args.rti_license_file is not None:
        if not os.path.isabs(args.rti_license_file):
            raise ValueError("RTI license file must be an existing absolute path.")
        os.environ["RTI_LICENSE_FILE"] = args.rti_license_file

    hz = 60

    class MedicinePolicyPublisher(Publisher):
        def __init__(self, topic: str, domain_id: int):
            super().__init__(topic, SOARM101CtrlInput, 1 / hz, domain_id)

        def produce(self, dt: float, sim_time: float):
            r_cam_buffer = np.frombuffer(current_state["room_cam"], dtype=np.uint8)
            room_img = Image.fromarray(r_cam_buffer.reshape(args.height, args.width, 3), "RGB")
            w_cam_buffer = np.frombuffer(current_state["wrist_cam"], dtype=np.uint8)
            wrist_img = Image.fromarray(w_cam_buffer.reshape(args.height, args.width, 3), "RGB")
            joint_pos = current_state["joint_pos"]

            actions = policy.infer(
                room_img=np.array(room_img),
                wrist_img=np.array(wrist_img),
                current_state=np.array(joint_pos[:6]),
            )
            i = SOARM101CtrlInput()
            i.joint_positions = (
                np.array(actions)
                .astype(np.float32)
                .reshape(args.chunk_length * 6,)
                .tolist()
            )
            return i

    writer = MedicinePolicyPublisher(args.topic_out, args.domain_id)

    def dds_callback(topic, data):
        if args.verbose:
            print(f"[INFO]: Received data from {topic}")
        if topic == args.topic_in_room_camera:
            o: CameraInfo = data
            current_state["room_cam"] = o.data
        if topic == args.topic_in_wrist_camera:
            o: CameraInfo = data
            current_state["wrist_cam"] = o.data
        if topic == args.topic_in_soarm_pos:
            o: SOARM101Info = data
            current_state["joint_pos"] = o.joints_state_positions

        if (
            current_state["room_cam"] is not None
            and current_state["wrist_cam"] is not None
            and current_state["joint_pos"] is not None
        ):
            writer.write(0.1, 1.0)
            if args.verbose:
                print(f"[INFO]: Published joint position to {args.topic_out}")
            current_state["room_cam"] = current_state["wrist_cam"] = current_state["joint_pos"] = None

    SubscriberWithCallback(dds_callback, args.domain_id, args.topic_in_room_camera, CameraInfo, 1 / hz).start()
    SubscriberWithCallback(dds_callback, args.domain_id, args.topic_in_wrist_camera, CameraInfo, 1 / hz).start()
    SubscriberWithCallback(dds_callback, args.domain_id, args.topic_in_soarm_pos, SOARM101Info, 1 / hz).start()


if __name__ == "__main__":
    main()
