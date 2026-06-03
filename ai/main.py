import logging
import multiprocessing as mp
import sys
import time
import cv2
from paddleocr import PaddleOCR
from core.modes import AppMode
from patrol.patrol_mode import PatrolMode
from sorting.expiration_date_parser import parse_expiration_date
from sorting.medicine_name_parser import find_medicine_name
from sorting.scan_state import MedicineScanState

DEBUG = True

CROP_RATIO = 0.5
MAX_CROP_WIDTH = 640
OCR_MIN_INTERVAL = 1.5


def _center_crop(frame):
    h, w = frame.shape[:2]
    ch, cw = int(h * CROP_RATIO), int(w * CROP_RATIO)
    y, x = (h - ch) // 2, (w - cw) // 2
    crop = frame[y:y + ch, x:x + cw]
    if cw > MAX_CROP_WIDTH:
        scale = MAX_CROP_WIDTH / cw
        crop = cv2.resize(crop, (MAX_CROP_WIDTH, int(ch * scale)))
    return crop


def _put_latest(q: mp.Queue, item) -> None:
    """Replace queue contents with item so only the latest is kept."""
    try:
        q.get_nowait()
    except Exception:
        pass
    try:
        q.put_nowait(item)
    except Exception:
        pass


def _ocr_worker(crop_queue: mp.Queue, result_queue: mp.Queue) -> None:
    logging.getLogger("ppocr").setLevel(logging.ERROR)
    ocr = PaddleOCR(use_textline_orientation=True, lang="en")
    last_text = None

    while True:
        try:
            crop = crop_queue.get(timeout=2.0)
        except Exception:
            continue

        t0 = time.monotonic()

        result = ocr.predict(crop)
        lines = []
        if result and result[0]:
            for item in result[0].get("rec_texts", []):
                if item:
                    lines.append(item)
        text = "\n".join(lines).strip()

        if not text or text != last_text:
            last_text = text
            _put_latest(result_queue, text)

        elapsed = time.monotonic() - t0
        remaining = OCR_MIN_INTERVAL - elapsed
        if remaining > 0:
            time.sleep(remaining)


def main() -> None:
    global DEBUG
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: could not open camera. Check that the camera is connected and that macOS camera permission is granted.", file=sys.stderr)
        sys.exit(1)

    print("Camera opened. Keys: 1=sorting  2=patrol  r=reset  d=debug  p=state  q=quit")

    current_mode: AppMode = AppMode.SORTING
    print("Entered SORTING mode")

    state = MedicineScanState()
    patrol = PatrolMode(debug=DEBUG)
    crop_queue = mp.Queue(maxsize=1)
    result_queue = mp.Queue(maxsize=1)

    proc = mp.Process(target=_ocr_worker, args=(crop_queue, result_queue), daemon=True)
    proc.start()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: failed to read frame from camera.", file=sys.stderr)
            break

        if current_mode == AppMode.SORTING:
            _put_latest(crop_queue, _center_crop(frame))
            try:
                text = result_queue.get_nowait()
                med_name = find_medicine_name(text)
                exp_date = parse_expiration_date(text)
                if DEBUG:
                    print("--- DEBUG OCR RESULT ---")
                    print(f"ocr_text:                 {text[:300]!r}")
                    print(f"parsed_medicine_name:     {med_name!r}")
                    print(f"parsed_expiration_date:   {exp_date!r}")
                    print(f"state_phase:              {state.phase}")
                    print(f"state_current_name:       {state.current_medicine_name!r}")
                    print(f"state_current_expiration: {state.current_expiration_date!r}")
                    print(f"state_no_text_cycles:     {state.no_text_cycles}")
                    print("------------------------")
                if state.update(med_name, exp_date, text):
                    r = state.completed_results[-1]
                    print("\n================ MEDICINE FOUND ================")
                    print(f"medicine_name:   {r['medicine_name']}")
                    print(f"expiration_date: {r['expiration_date']}")
                    print("===============================================\n")
                if state.removal_detected:
                    print("Medicine removed. Ready for next scan.")
            except Exception:
                pass
        elif current_mode == AppMode.PATROL:
            patrol.process_frame(frame)

        cv2.imshow("Carebot AI - Live Feed", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("1") and current_mode != AppMode.SORTING:
            current_mode = AppMode.SORTING
            print("Entered SORTING mode")
        if key == ord("2") and current_mode != AppMode.PATROL:
            current_mode = AppMode.PATROL
            print("Entered PATROL mode")
        if key == ord("r"):
            if current_mode == AppMode.SORTING:
                state.reset_current()
                print("Scan reset.")
            elif current_mode == AppMode.PATROL:
                patrol.reset()
        if key == ord("d"):
            DEBUG = not DEBUG
            print(f"DEBUG {'on' if DEBUG else 'off'}")
            patrol.set_debug(DEBUG)
        if key == ord("p"):
            if current_mode == AppMode.SORTING:
                print(f"\n--- State: {state.phase} | name: {state.current_medicine_name!r} | exp: {state.current_expiration_date!r} ---")
                if state.completed_results:
                    print("Scanned medicines:")
                    for i, r in enumerate(state.completed_results, 1):
                        print(f"  {i}. {r['medicine_name']} | {r['expiration_date']}")
                else:
                    print("No medicines scanned yet.")
                print("-------------------------")
            elif current_mode == AppMode.PATROL:
                patrol.print_debug_state()

    proc.terminate()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
