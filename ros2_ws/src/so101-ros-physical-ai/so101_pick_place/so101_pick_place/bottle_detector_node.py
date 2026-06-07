"""
CareAI medicine bottle detector — overhead RealSense camera.

Detection: HSV colour contour (no external model needed).
  Default preset: amber  H=[10,25]  S=[100,255]  V=[50,230]
  Override via ROS 2 parameters or launch arguments to match your bottle.

Subscriptions
-------------
  /static_camera/color/image_raw       sensor_msgs/Image   (required)
  /static_camera/depth/image_rect_raw  sensor_msgs/Image   (optional, enables depth Z)
  /static_camera/color/camera_info     sensor_msgs/CameraInfo (optional, enables 3-D point)

Publications
------------
  /medicine_bottle_detected    std_msgs/Bool
  /medicine_bottle_center      geometry_msgs/PointStamped
      With camera_info:    x,y,z in optical frame (metres).
      Without camera_info: x=col_px, y=row_px, z=depth_m (0.0 if no depth).
  /bottle_detector/debug_image sensor_msgs/Image   (annotated colour frame)

Parameters
----------
  color_topic        str   /static_camera/color/image_raw
  depth_topic        str   /static_camera/depth/image_rect_raw
  camera_info_topic  str   /static_camera/color/camera_info
  hsv_h_low          int   10     ╮
  hsv_h_high         int   25     │  Amber preset — tune for your bottle.
  hsv_s_low          int   100    │  Run with debug_image:=true and
  hsv_s_high         int   255    │  view /bottle_detector/debug_image in
  hsv_v_low          int   50     │  rqt_image_view to tune these.
  hsv_v_high         int   230    ╯
  min_area_px        int   500    Ignore contours smaller than this (pixels²).
  max_area_px        int   80000  Ignore contours larger than this (pixels²).
  min_aspect_ratio   float 0.25   Ignore very thin contours.
  max_aspect_ratio   float 4.0    Ignore very flat contours.
  depth_patch_px     int   5      Half-size of patch used to median-sample depth.
  publish_debug      bool  true   Publish annotated image.

Launch
------
  ros2 launch so101_pick_place bottle_detector.launch.py
  ros2 launch so101_pick_place bottle_detector.launch.py debug:=true
"""

import signal

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Bool


class BottleDetectorNode(Node):

    def __init__(self) -> None:
        super().__init__("bottle_detector_node")

        # ── Parameters ────────────────────────────────────────────────── #
        self.declare_parameter("color_topic",       "/static_camera/color/image_raw")
        self.declare_parameter("depth_topic",       "/static_camera/depth/image_rect_raw")
        self.declare_parameter("camera_info_topic", "/static_camera/color/camera_info")
        self.declare_parameter("hsv_h_low",   10)
        self.declare_parameter("hsv_h_high",  25)
        self.declare_parameter("hsv_s_low",   100)
        self.declare_parameter("hsv_s_high",  255)
        self.declare_parameter("hsv_v_low",   50)
        self.declare_parameter("hsv_v_high",  230)
        self.declare_parameter("min_area_px",      500)
        self.declare_parameter("max_area_px",      80000)
        self.declare_parameter("min_aspect_ratio", 0.25)
        self.declare_parameter("max_aspect_ratio", 4.0)
        self.declare_parameter("depth_patch_px",   5)
        self.declare_parameter("publish_debug",    True)

        self._bridge = CvBridge()
        self._latest_depth: np.ndarray | None = None
        self._fx: float | None = None
        self._fy: float | None = None
        self._cx: float | None = None
        self._cy: float | None = None

        # ── Subscriptions ─────────────────────────────────────────────── #
        color_t = self.get_parameter("color_topic").value
        depth_t = self.get_parameter("depth_topic").value
        info_t  = self.get_parameter("camera_info_topic").value

        self.create_subscription(Image,      color_t, self._color_cb,       10)
        self.create_subscription(Image,      depth_t, self._depth_cb,       10)
        self.create_subscription(CameraInfo, info_t,  self._camera_info_cb,  1)

        # ── Publishers ────────────────────────────────────────────────── #
        self._pub_detected = self.create_publisher(Bool,         "/medicine_bottle_detected", 10)
        self._pub_center   = self.create_publisher(PointStamped, "/medicine_bottle_center",   10)
        self._pub_debug    = self.create_publisher(Image,        "/bottle_detector/debug_image", 2)

        self.get_logger().info(
            f"Bottle detector ready — subscribed to {color_t}\n"
            "  → /medicine_bottle_detected  /medicine_bottle_center\n"
            "  → /bottle_detector/debug_image (debug overlay)"
        )

    # ── Camera info ────────────────────────────────────────────────────── #

    def _camera_info_cb(self, msg: CameraInfo) -> None:
        if self._fx is not None:
            return  # already have intrinsics
        self._fx = msg.k[0]
        self._fy = msg.k[4]
        self._cx = msg.k[2]
        self._cy = msg.k[5]
        self.get_logger().info(
            f"Camera intrinsics: fx={self._fx:.1f} fy={self._fy:.1f} "
            f"cx={self._cx:.1f} cy={self._cy:.1f}"
        )

    # ── Depth ──────────────────────────────────────────────────────────── #

    def _depth_cb(self, msg: Image) -> None:
        self._latest_depth = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

    # ── Colour / detection ─────────────────────────────────────────────── #

    def _color_cb(self, msg: Image) -> None:
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        h_img, w_img = frame.shape[:2]

        p = self.get_parameter
        hsv_lower = np.array([p("hsv_h_low").value,  p("hsv_s_low").value,  p("hsv_v_low").value])
        hsv_upper = np.array([p("hsv_h_high").value, p("hsv_s_high").value, p("hsv_v_high").value])
        min_area  = p("min_area_px").value
        max_area  = p("max_area_px").value
        min_ar    = p("min_aspect_ratio").value
        max_ar    = p("max_aspect_ratio").value
        do_debug  = p("publish_debug").value

        # ── HSV mask ──────────────────────────────────────────────────── #
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, hsv_lower, hsv_upper)

        # Morphological cleanup: close small holes, remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel, iterations=1)

        # ── Find best contour ─────────────────────────────────────────── #
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_area = 0.0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            ar = w / h if h > 0 else 0.0
            if ar < min_ar or ar > max_ar:
                continue
            if area > best_area:
                best_area = area
                best = cnt

        detected = best is not None

        # ── Depth sample ──────────────────────────────────────────────── #
        col_px = row_px = 0
        depth_m = 0.0
        if detected:
            M = cv2.moments(best)
            if M["m00"] > 0:
                col_px = int(M["m10"] / M["m00"])
                row_px = int(M["m01"] / M["m00"])
            else:
                x, y, w, h = cv2.boundingRect(best)
                col_px = x + w // 2
                row_px = y + h // 2

            if self._latest_depth is not None:
                ph = p("depth_patch_px").value
                r0 = max(0, row_px - ph)
                r1 = min(h_img, row_px + ph + 1)
                c0 = max(0, col_px - ph)
                c1 = min(w_img, col_px + ph + 1)
                patch = self._latest_depth[r0:r1, c0:c1]
                vals  = patch[patch > 0]
                if vals.size > 0:
                    depth_m = float(np.median(vals)) * 1e-3  # mm → m

        # ── Publish ───────────────────────────────────────────────────── #
        self._pub_detected.publish(Bool(data=detected))

        pt_msg = PointStamped()
        pt_msg.header.stamp    = msg.header.stamp
        pt_msg.header.frame_id = msg.header.frame_id or "static_camera_color_optical_frame"
        if detected:
            if self._fx is not None and depth_m > 0.0:
                # Proper 3-D backproject
                pt_msg.point.x = (col_px - self._cx) * depth_m / self._fx
                pt_msg.point.y = (row_px - self._cy) * depth_m / self._fy
                pt_msg.point.z = depth_m
            else:
                # Pixel coordinates fallback (x=col, y=row, z=depth_m)
                pt_msg.point.x = float(col_px)
                pt_msg.point.y = float(row_px)
                pt_msg.point.z = depth_m
        self._pub_center.publish(pt_msg)

        # ── Debug image ───────────────────────────────────────────────── #
        if do_debug:
            dbg = frame.copy()
            # Tint the detection mask blue
            tint = np.zeros_like(dbg)
            tint[mask > 0] = (160, 80, 0)
            dbg = cv2.addWeighted(dbg, 0.8, tint, 0.4, 0)

            if detected:
                cv2.drawContours(dbg, [best], -1, (0, 255, 0), 2)
                cv2.circle(dbg, (col_px, row_px), 8, (0, 255, 255), -1)
                label = f"bottle  d={depth_m:.3f}m" if depth_m > 0 else "bottle"
                cv2.putText(dbg, label, (col_px + 12, row_px - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            else:
                cv2.putText(dbg, "no bottle", (12, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

            self._pub_debug.publish(
                self._bridge.cv2_to_imgmsg(dbg, encoding="bgr8")
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = BottleDetectorNode()

    def _shutdown(sig, frame):  # noqa: ARG001
        node.get_logger().info("Bottle detector shutting down.")
        rclpy.shutdown()

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()


if __name__ == "__main__":
    main()
