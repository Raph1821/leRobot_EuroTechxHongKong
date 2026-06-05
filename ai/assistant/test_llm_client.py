import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from assistant.llm_client import LLMClient

context = {
    "scanned_medicines": [
        {"medicine_name": "vitamin d", "expiration_date": "01/2026", "status": "expired"},
        {"medicine_name": "omega 3",   "expiration_date": "10/2026", "status": "valid"},
    ],
    "recent_events": [
        {"event_type": "medicine_scanned", "message": "vitamin d - 01/2026"},
        {"event_type": "voice_emergency",  "message": "Emergency detected by voice request"},
    ],
    "patrol_status": "NORMAL",
}

question = "Can I use vitamin D?"

client = LLMClient()
answer = client.ask(question, context=context)
print(answer)
