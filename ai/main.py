import argparse
import logging
import multiprocessing as mp
import os
import queue
import sys
import time
from datetime import datetime

# Fix PaddlePaddle oneDNN crash on Windows
os.environ.setdefault("PADDLE_INFERENCE_DISABLE_ONEDNN", "1")
os.environ.setdefault("FLAGS_use_mkldnn", "0")

import cv2
from paddleocr import PaddleOCR
from core.event_log import EventLog
from core.shared_frame import set_latest_frame
from core.modes import AppMode
from patrol.patrol_mode import PatrolMode
from sorting.expiration_date_parser import parse_expiration_date
from sorting.medicine_name_parser import find_medicine_name
from sorting.scan_state import MedicineScanState
from speech.speech_listener import SpeechListener
from assistant.llm_client import LLMClient
from assistant.intents import classify_intent
from assistant.assistant_actions import handle_intent, ActionResult
from memory.care_memory import CareMemory
from memory.memory_recall import MemoryRecall
from reminders.reminder_checker import ReminderChecker
from speech.tts_engine import TTSEngine
from summary.daily_summary import DailySummary
from summary.morning_briefing import MorningBriefing
from health.health_check import HealthCheck
from wellbeing.wellbeing_report import WellbeingReport

DEBUG = True


def _expiration_status(expiration_date: str) -> str:
    try:
        month, year = expiration_date.split("/")
        now = datetime.now()
        if (int(year), int(month)) < (now.year, now.month):
            return "expired"
        return "valid"
    except Exception:
        return "unknown"

CROP_RATIO = 0.5
MAX_CROP_WIDTH = 960   # Logitech 1080p gives enough detail at 960px
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
    # Must set these in the subprocess too (Windows spawns a fresh process)
    import os
    os.environ["PADDLE_INFERENCE_DISABLE_ONEDNN"] = "1"
    os.environ["FLAGS_use_mkldnn"] = "0"

    logging.getLogger("ppocr").setLevel(logging.ERROR)
    # enable_mkldnn=False avoids the PIR+oneDNN crash on Windows
    try:
        ocr = PaddleOCR(use_textline_orientation=True, lang="en", enable_mkldnn=False)
    except TypeError:
        # Older/newer API fallback
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


def _open_camera(index: int, width: int = 1920, height: int = 1080):
    """Open a camera by index, platform-agnostic. Returns (cap, label) or (None, msg).

    Includes a warm-up: some USB cameras (e.g. the HBV wrist cam) return black
    frames for the first ~1s, so we grab a few frames until a real one arrives.
    """
    import platform
    system = platform.system()
    if system == "Darwin":
        cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    elif system == "Windows":
        # DirectShow is far more reliable than the default MSMF backend on Windows
        # (MSMF fails to grab frames from many USB cameras).
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(index)  # fallback to default
    else:
        cap = cv2.VideoCapture(index)

    if not cap.isOpened():
        return None, f"could not open camera {index}"

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return cap, f"Camera {index} ({aw}x{ah})"


def _rotate_frame(frame, rotate: int):
    """Rotate a frame by 90/180/270 degrees to correct a mismounted camera."""
    if rotate == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotate == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotate == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def main(ocr_camera: int = 1, patrol_camera: int | None = None,
         use_realsense: bool = False, expected_pills: int | None = None,
         patrol_rotate: int = 270) -> None:
    """Run the CareAI loop.

    Three-camera setup (full hackathon plan):
      - ocr_camera:    clear webcam → medicine identification + expiration (SORTING mode)
      - patrol_camera: wrist camera → patrol + fall detection (PATROL mode)
      - RealSense:     overhead → pill counting / dose verification (DOSAGE mode)

    patrol_rotate: degrees (0/90/180/270) to rotate the wrist camera frame to
    correct its physical mounting. Applied only to the patrol camera.
    If patrol_camera is None, the same camera is used for both (single-cam fallback).
    """
    global DEBUG

    # Open the OCR/medicine camera (the clear webcam)
    cap_ocr, label_ocr = _open_camera(ocr_camera)
    if cap_ocr is None:
        print(f"Error: {label_ocr}. Check the webcam connection.", file=sys.stderr)
        sys.exit(1)
    print(f"OCR/medicine camera: {label_ocr}")

    # Open the patrol camera (the wrist camera), if a separate one is given
    cap_patrol = None
    if patrol_camera is not None and patrol_camera != ocr_camera:
        cap_patrol, label_patrol = _open_camera(patrol_camera, width=1280, height=720)
        if cap_patrol is None:
            print(f"Warning: {label_patrol}. Patrol will fall back to the OCR camera.", file=sys.stderr)
            cap_patrol = None
        else:
            print(f"Patrol/fall-detection camera: {label_patrol}")
    else:
        print("Single-camera mode: same camera used for both sorting and patrol.")

    # Set up the RealSense + pill detector (DOSAGE mode), if requested.
    rs_pipeline = None
    pill_model = None
    if use_realsense:
        try:
            import pyrealsense2 as rs
            from pill_detect_yolo import load_model, detect_pills, draw, _BATCH  # noqa
            rs_ctx = rs.context()
            if len(rs_ctx.query_devices()) == 0:
                print("Warning: RealSense requested but none detected. DOSAGE mode disabled.", file=sys.stderr)
            else:
                rs_pipeline = rs.pipeline()
                rs_config = rs.config()
                rs_config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
                rs_pipeline.start(rs_config)
                pill_model = load_model()
                dev = rs_ctx.query_devices()[0]
                print(f"DOSAGE camera: {dev.get_info(rs.camera_info.name)} + pills YOLO model")
        except Exception as e:
            print(f"Warning: could not start RealSense/pill model: {e}. DOSAGE mode disabled.", file=sys.stderr)
            rs_pipeline = None
            pill_model = None

    print("Camera opened. Keys: 1=sorting  2=patrol  3=dosage  r=reset  d=debug  e=events  m=memory  M=schedules  S=add-sample-schedule  R=check-reminders  D=record-dose  X=dose-history  T=speaker-test  B=briefing  Y=daily-summary  H=health-check  P=profile  p=state  a=assistant  q=quit")

    current_mode: AppMode = AppMode.SORTING
    print("Entered SORTING mode")

    event_log = EventLog()
    memory = CareMemory()
    tts = TTSEngine()
    reminder_checker = ReminderChecker(memory, tts=tts)
    reminder_checker.start()
    llm_client = LLMClient()
    recall = MemoryRecall(memory)
    daily_summary = DailySummary(memory, llm_client=llm_client)
    morning_briefing = MorningBriefing(memory, llm_client=llm_client)
    health_check = HealthCheck()
    wellbeing_reporter = WellbeingReport(memory, llm_client=llm_client)

    def on_voice_emergency(text: str) -> None:
        print("EMERGENCY DETECTED: voice help request")
        print(f'Heard: "{text}"')
        event_log.add_event("voice_emergency", "Emergency detected by voice request", {"heard": text})
        memory.add_emergency("voice", f'Emergency detected by voice: "{text}"', {"heard": text})
        memory.add_event("voice_emergency", f'Heard: "{text}"')
        tts.speak("Emergency detected. Help may be needed.")

    def on_camera_emergency() -> None:
        event_log.add_event("camera_emergency", "Emergency detected by fall detection")
        memory.add_emergency("camera", "Emergency detected by fall detection")
        memory.add_event("camera_emergency", "Emergency detected by fall detection")
        tts.speak("Emergency detected. Help may be needed.")

    voice_queue: queue.Queue = queue.Queue()
    speech = SpeechListener(voice_queue, on_voice_emergency=on_voice_emergency, debug=DEBUG)
    speech.start()

    state = MedicineScanState()
    patrol = PatrolMode(debug=DEBUG, on_camera_emergency=on_camera_emergency)
    crop_queue = mp.Queue(maxsize=1)
    result_queue = mp.Queue(maxsize=1)

    proc = mp.Process(target=_ocr_worker, args=(crop_queue, result_queue), daemon=True)
    proc.start()

    while True:
        # DOSAGE uses the RealSense; SORTING uses the OCR webcam; PATROL the wrist cam.
        if current_mode == AppMode.DOSAGE and rs_pipeline is not None:
            import pyrealsense2 as rs
            rs_frames = rs_pipeline.wait_for_frames()
            cf = rs_frames.get_color_frame()
            if not cf:
                continue
            import numpy as _np
            frame = _np.asanyarray(cf.get_data())
            set_latest_frame(frame)

            from pill_detect_yolo import detect_pills, draw
            dets = detect_pills(pill_model, frame, conf=0.4)
            frame, counts = draw(frame, dets)
            total = len(dets)
            cv2.putText(frame, f"PILLS: {total}  (tab {counts.get('tablets',0)} / cap {counts.get('capsules',0)})",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            if expected_pills is not None:
                ok = total == expected_pills
                cv2.putText(frame, f"Expected {expected_pills} -> {'OK' if ok else 'MISMATCH'}",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 200, 0) if ok else (0, 0, 255), 2)

            cv2.imshow("Carebot AI - Live Feed", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("1"):
                current_mode = AppMode.SORTING
                print("Entered SORTING mode")
            if key == ord("2"):
                current_mode = AppMode.PATROL
                print("Entered PATROL mode")
            continue  # DOSAGE handled, skip the rest of the loop body

        # SORTING uses the clear OCR webcam; PATROL uses the wrist camera if available.
        if current_mode == AppMode.PATROL and cap_patrol is not None:
            active_cap = cap_patrol
            is_patrol_cam = True
        else:
            active_cap = cap_ocr
            is_patrol_cam = False

        ret, frame = active_cap.read()
        if not ret:
            print("Error: failed to read frame from camera.", file=sys.stderr)
            break
        # Rotate only the patrol/wrist camera to correct its mounting.
        if is_patrol_cam and patrol_rotate:
            frame = _rotate_frame(frame, patrol_rotate)
        set_latest_frame(frame)

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
                    event_log.add_event(
                        "medicine_scanned",
                        f"{r['medicine_name']} - {r['expiration_date']}",
                        {"medicine_name": r["medicine_name"], "expiration_date": r["expiration_date"]},
                    )
                    _status = _expiration_status(r["expiration_date"])
                    memory.add_medicine(r["medicine_name"], r["expiration_date"], status=_status)
                    memory.add_event("medicine_scanned", f"{r['medicine_name']} - {r['expiration_date']}")
                if state.removal_detected:
                    print("Medicine removed. Ready for next scan.")
            except Exception:
                pass
        elif current_mode == AppMode.PATROL:
            patrol.process_frame(frame)

        try:
            cmd = voice_queue.get_nowait()
            if cmd == "sorting mode" and current_mode != AppMode.SORTING:
                current_mode = AppMode.SORTING
                print("Switching to SORTING mode")
            elif cmd == "patrol mode" and current_mode != AppMode.PATROL:
                current_mode = AppMode.PATROL
                print("Switching to PATROL mode")
            elif cmd == "show medicines":
                if state.completed_results:
                    for i, r in enumerate(state.completed_results, 1):
                        print(f"  {i}. {r['medicine_name']} | {r['expiration_date']}")
                else:
                    print("No medicines scanned yet.")
            elif cmd == "reset":
                if current_mode == AppMode.SORTING:
                    state.reset_current()
                    print("Scan reset.")
                elif current_mode == AppMode.PATROL:
                    patrol.reset()
        except queue.Empty:
            pass

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
        if key == ord("3") and current_mode != AppMode.DOSAGE:
            if rs_pipeline is not None:
                current_mode = AppMode.DOSAGE
                print("Entered DOSAGE mode")
            else:
                print("DOSAGE unavailable — run with --realsense and a connected RealSense.")
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
            speech.set_debug(DEBUG)
        if key == ord("e"):
            event_log.print_recent_events()
        if key == ord("a"):
            print("\n================ CAREAI ASSISTANT ================")
            print("Ask CareAI:")
            try:
                question = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                question = ""
            if question:
                mem_ctx = memory.get_context()
                enriched = [
                    {
                        "medicine_name": m["name"],
                        "expiration_date": m["expiration_date"],
                        "status": m.get("status") or _expiration_status(m.get("expiration_date", "")),
                    }
                    for m in mem_ctx["scanned_medicines"]
                ]
                events = [
                    {"event_type": e["type"], "message": e["message"]}
                    for e in recall.get_recent_events(10)
                ]
                intent = classify_intent(question)["intent"]
                result: ActionResult = handle_intent(
                    intent=intent,
                    scanned_medicines=enriched,
                    recent_events=events,
                    patrol_status=patrol._emergency.phase,
                    current_mode=current_mode.value,
                    llm_client=llm_client,
                    user_message=question,
                    profile=mem_ctx.get("profile"),
                    active_schedules=recall.get_today_schedules(),
                    recent_emergencies=recall.get_recent_emergencies(),
                    wellbeing_reporter=wellbeing_reporter,
                )
                print("\n================ CAREAI RESPONSE ================")
                print(result.message)
                print("=================================================\n")
                if result.switch_mode == "PATROL" and current_mode != AppMode.PATROL:
                    current_mode = AppMode.PATROL
                    print("Entered PATROL mode")
                elif result.switch_mode == "SORTING" and current_mode != AppMode.SORTING:
                    current_mode = AppMode.SORTING
                    print("Entered SORTING mode")
        if key == ord("B"):
            briefing = morning_briefing.generate()
            print("\n================ MORNING BRIEFING ================")
            print(briefing)
            print("=================================================\n")
            tts.speak(briefing)
        if key == ord("H"):
            print("\nCareAI Health Check started.")
            print("How are you feeling right now?")
            try:
                answer = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer:
                response = health_check.run(answer, llm_client=llm_client, memory=memory, tts=tts)
                print(f"\nCareAI: {response}\n")
        if key == ord("Y"):
            summary = daily_summary.generate_summary()
            print("\n================ DAILY CARE SUMMARY ================")
            print(summary)
            print("====================================================\n")
            tts.speak("Daily care summary generated.")
        if key == ord("D"):
            now_hhmm = __import__("datetime").datetime.now().strftime("%H:%M")
            memory.add_dose_record("Vitamin D", "1 tablet", now_hhmm, status="taken", source="manual")
            print(f"Sample dose recorded: Vitamin D at {now_hhmm}")
        if key == ord("X"):
            history = memory.get_dose_history(days=7)
            print("\n================ DOSE HISTORY (last 7 days) ================")
            if not history:
                print("  (no dose records)")
            for r in history:
                print(f"  [{r['recorded_at'][:16]}] {r['medicine_name']} {r['dose']} "
                      f"@ {r['scheduled_time']} — {r['status']} ({r['source']})")
            print("=============================================================\n")
        if key == ord("T"):
            tts.speak("CareAI speaker test.")
            print("Speaker test: speaking 'CareAI speaker test.'")
        if key == ord("R"):
            reminder_checker.check_now()
        if key == ord("S"):
            sid = memory.add_medicine_schedule("vitamin d", "1 tablet", ["09:00"], notes="take with food")
            print(f"Sample schedule added (id={sid}): vitamin d - 1 tablet - 09:00")
        if key == ord("M"):
            schedules = memory.get_active_schedules()
            print("\n================ MEDICINE SCHEDULE ================")
            if not schedules:
                print("  (no active schedules)")
            for i, s in enumerate(schedules, 1):
                times_str = ", ".join(s["times"])
                print(f"  {i}. {s['medicine_name']} - {s['dose']} - {times_str}")
            print("===================================================\n")
        if key == ord("m"):
            print("\n================ CARE MEMORY ================")
            print(f"Medicines:   {len(memory._data['scanned_medicines'])}")
            print(f"Events:      {len(memory._data['events'])}")
            print(f"Emergencies: {len(memory._data['emergencies'])}")
            print("=============================================\n")
        if key == ord("P"):
            profile = memory.get_profile()
            print("\n================ CARE PROFILE ================")
            print(f"Name:              {profile['name'] or '(not set)'}")
            print(f"Age:               {profile['age'] if profile['age'] is not None else '(not set)'}")
            print(f"Caregiver:         {profile['caregiver_name'] or '(not set)'}")
            print(f"Caregiver contact: {profile['caregiver_contact'] or '(not set)'}")
            if profile["notes"]:
                print(f"Notes ({len(profile['notes'])}):")
                for i, note in enumerate(profile["notes"], 1):
                    print(f"  {i}. {note}")
            else:
                print("Notes:             (none)")
            print("==============================================")
            print("Update field? (name / age / caregiver_name / caregiver_contact / note / skip)")
            try:
                field = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                field = "skip"
            if field in ("skip", ""):
                pass
            elif field == "name":
                val = input("Name: ").strip()
                memory.update_profile(name=val)
                print("Saved.")
            elif field == "age":
                val = input("Age: ").strip()
                try:
                    memory.update_profile(age=int(val))
                    print("Saved.")
                except ValueError:
                    print("Invalid age — not saved.")
            elif field == "caregiver_name":
                val = input("Caregiver name: ").strip()
                memory.update_profile(caregiver_name=val)
                print("Saved.")
            elif field == "caregiver_contact":
                val = input("Caregiver contact: ").strip()
                memory.update_profile(caregiver_contact=val)
                print("Saved.")
            elif field == "note":
                val = input("Note: ").strip()
                if val:
                    memory.add_profile_note(val)
                    print("Saved.")
            else:
                print(f"Unknown field: {field!r} — skipped.")
            print()
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
    cap_ocr.release()
    if cap_patrol is not None:
        cap_patrol.release()
    if rs_pipeline is not None:
        try:
            rs_pipeline.stop()
        except Exception:
            pass
    cv2.destroyAllWindows()


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    parser = argparse.ArgumentParser(description="CareAI — Medicine & Care Assistant")
    parser.add_argument("--ocr-camera", type=int, default=1,
                        help="Camera index for medicine ID + expiration (clear webcam). Default: 1")
    parser.add_argument("--patrol-camera", type=int, default=None,
                        help="Camera index for patrol + fall detection (wrist camera). "
                             "If omitted, the OCR camera is used for both.")
    # Backward-compat: --camera still works as the OCR camera
    parser.add_argument("--camera", type=int, default=None,
                        help="(deprecated) alias for --ocr-camera")
    parser.add_argument("--realsense", action="store_true",
                        help="Enable DOSAGE mode (Intel RealSense + pill counting). Press 3 to use it.")
    parser.add_argument("--expected-pills", type=int, default=None,
                        help="Prescribed pill count to verify against in DOSAGE mode.")
    parser.add_argument("--patrol-rotate", type=int, default=270, choices=[0, 90, 180, 270],
                        help="Rotate the patrol/wrist camera frame (degrees) to correct mounting. Default 270.")
    args = parser.parse_args()

    ocr_cam = args.camera if args.camera is not None else args.ocr_camera
    main(ocr_camera=ocr_cam, patrol_camera=args.patrol_camera,
         use_realsense=args.realsense, expected_pills=args.expected_pills,
         patrol_rotate=args.patrol_rotate)
