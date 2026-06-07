"""Dosage verification — count pills poured from a bottle (Track B).

Uses the Intel RealSense D405 overhead color stream + classic computer vision
(contour/blob detection) to count individual pills on a tray. No ML model or
training needed — pills are detected as distinct blobs against the tray.

This verifies the dose: e.g. the doctor's prescription says "2 tablets",
the patient pours pills out, and the robot confirms the count matches.

Run:
    python ai/dosage_counter.py                 # count live, no target
    python ai/dosage_counter.py --expected 2    # verify against prescription
    python ai/dosage_counter.py --webcam 2      # use a normal webcam instead of RealSense

Keys (in the window):
    +/- : raise/lower the minimum blob size (filter noise vs small pills)
    [/] : lower/raise the brightness threshold
    v   : print verification result
    q   : quit

TUNING TIP: place pills on a plain, contrasting background (dark tray for
light pills, white paper for dark pills). Adjust thresholds with the keys
until the count is stable.
"""
import argparse
import sys

import numpy as np
import cv2


def count_pills(frame, min_area=150, max_area=8000, thresh_val=0,
                invert=False, use_adaptive=False):
    """Detect pill-like blobs and return (count, annotated_frame, binary_mask).

    Strategy:
      1. Grayscale + blur
      2. Threshold (Otsu / manual / adaptive) to separate pills from background
      3. Morphological cleanup
      4. Contour detection, filtered by area AND circularity (pills are roundish)
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    if use_adaptive:
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 51, 5)
    elif thresh_val > 0:
        _, binary = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
    else:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if invert:
        binary = cv2.bitwise_not(binary)

    # Morphological cleanup: remove specks, fill pill interiors
    kernel = np.ones((3, 3), np.uint8)
    clean = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel, iterations=2)

    cnts, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    annotated = frame.copy()
    kept = 0
    for c in cnts:
        area = cv2.contourArea(c)
        if not (min_area < area < max_area):
            continue
        # Circularity filter: 4*pi*area / perimeter^2 ~ 1.0 for a circle.
        # Pills/candies are roundish (>0.5); rejects elongated background junk.
        perim = cv2.arcLength(c, True)
        if perim == 0:
            continue
        circularity = 4 * np.pi * area / (perim * perim)
        if circularity < 0.5:
            continue
        kept += 1
        (x, y), r = cv2.minEnclosingCircle(c)
        cv2.circle(annotated, (int(x), int(y)), int(r), (0, 255, 0), 2)
        cv2.putText(annotated, str(kept), (int(x) - 8, int(y) + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # Return the binary mask too (for the debug view)
    mask_bgr = cv2.cvtColor(clean, cv2.COLOR_GRAY2BGR)
    return kept, annotated, mask_bgr


def realsense_frames(width=640, height=480):
    """Yield BGR color frames from the RealSense."""
    import pyrealsense2 as rs
    ctx = rs.context()
    if len(ctx.query_devices()) == 0:
        print("No RealSense detected.")
        return
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, 30)
    pipeline.start(config)
    try:
        while True:
            frames = pipeline.wait_for_frames()
            cf = frames.get_color_frame()
            if not cf:
                continue
            yield np.asanyarray(cf.get_data())
    finally:
        pipeline.stop()


def webcam_frames(index):
    """Yield BGR frames from a normal webcam."""
    import platform
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    cap = cv2.VideoCapture(index, backend) if backend != cv2.CAP_ANY else cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"Could not open webcam {index}")
        return
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            yield frame
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description="Dosage pill counter")
    parser.add_argument("--expected", type=int, default=None,
                        help="Prescribed number of pills to verify against")
    parser.add_argument("--webcam", type=int, default=None,
                        help="Use a normal webcam index instead of the RealSense")
    parser.add_argument("--min-area", type=int, default=150,
                        help="Minimum blob area to count as a pill (px)")
    args = parser.parse_args()

    min_area = args.min_area
    thresh_val = 0  # 0 = Otsu auto
    invert = False
    use_adaptive = False

    source = webcam_frames(args.webcam) if args.webcam is not None else realsense_frames()
    src_name = f"webcam {args.webcam}" if args.webcam is not None else "RealSense"
    print(f"Counting pills from {src_name}.")
    print("Keys: +/- size | [/] threshold | i=invert | a=adaptive | v=verify | q=quit")
    print("Watch the 'Mask' window: pills should be WHITE blobs on BLACK. "
          "If reversed, press 'i'.")

    last_count = 0
    for frame in source:
        count, annotated, mask = count_pills(
            frame, min_area=min_area, thresh_val=thresh_val,
            invert=invert, use_adaptive=use_adaptive)
        last_count = count

        # HUD
        cv2.putText(annotated, f"PILLS: {count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 2)
        if args.expected is not None:
            ok = count == args.expected
            msg = f"Expected {args.expected} -> {'OK' if ok else 'MISMATCH'}"
            color = (0, 200, 0) if ok else (0, 0, 255)
            cv2.putText(annotated, msg, (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        mode = "adaptive" if use_adaptive else (f"thresh={thresh_val or 'auto'}")
        cv2.putText(annotated, f"min_area={min_area} {mode} invert={invert}",
                    (10, annotated.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow("Dosage Counter", annotated)
        cv2.imshow("Mask (pills should be white blobs)", mask)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key in (ord("+"), ord("=")):
            min_area += 50
        elif key in (ord("-"), ord("_")):
            min_area = max(20, min_area - 50)
        elif key == ord("]"):
            thresh_val = min(255, (thresh_val or 127) + 10)
            use_adaptive = False
        elif key == ord("["):
            thresh_val = max(0, (thresh_val or 127) - 10)
            use_adaptive = False
        elif key == ord("i"):
            invert = not invert
        elif key == ord("a"):
            use_adaptive = not use_adaptive
        elif key == ord("v"):
            if args.expected is not None:
                ok = count == args.expected
                print(f"Verify: expected {args.expected}, counted {count} -> "
                      f"{'CORRECT' if ok else 'MISMATCH'}")
            else:
                print(f"Counted {count} pills.")

    cv2.destroyAllWindows()
    print(f"Final count: {last_count}")


if __name__ == "__main__":
    main()
