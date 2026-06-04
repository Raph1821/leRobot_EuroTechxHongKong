import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from assistant.llm_client import LLMClient

context = {
    "scanned_medicines": [
        {"medicine_name": "vitamin d", "expiration_date": "01/2026"},
        {"medicine_name": "omega 3",   "expiration_date": "10/2026"},
    ],
    "recent_events": [
        {"event_type": "medicine_scanned", "message": "Medicine scanned: vitamin d - 01/2026"},
        {"event_type": "voice_emergency",  "message": "Emergency detected by voice request"},
    ],
    "patrol_status": "normal",
}

question = "What medicines expire soon and were there any emergencies?"

client = LLMClient()
answer = client.ask(question, context=context)
print(answer)
