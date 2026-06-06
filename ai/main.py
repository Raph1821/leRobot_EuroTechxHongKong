import argparse
import logging
import multiprocessing as mp
import queue
import sys
import time
from datetime import datetime
import cv2
from paddleocr import PaddleOCR
from core.event_log import EventLog
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


def main(camera_index: int = 1) -> None:
    global DEBUG
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Error: could not open camera {camera_index}. Check connection and macOS camera permissions.", file=sys.stderr)
        sys.exit(1)

    # Request native Logitech resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera {camera_index} opened at {actual_w}x{actual_h}")

    print("Camera opened. Keys: 1=sorting  2=patrol  r=reset  d=debug  e=events  m=memory  M=schedules  S=add-sample-schedule  R=check-reminders  T=speaker-test  B=briefing  Y=daily-summary  H=health-check  P=profile  p=state  a=assistant  q=quit")

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
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    parser = argparse.ArgumentParser(description="CareAI — Medicine & Care Assistant")
    parser.add_argument("--camera", type=int, default=1, help="Camera index (default: 1 = Logitech)")
    args = parser.parse_args()
    main(camera_index=args.camera)
