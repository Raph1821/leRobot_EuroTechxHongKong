LIST_MEDICINES = "LIST_MEDICINES"
EXPIRE_SOON = "EXPIRE_SOON"
RECENT_EVENTS = "RECENT_EVENTS"
EMERGENCY_STATUS = "EMERGENCY_STATUS"
FIND_MEDICINE = "FIND_MEDICINE"
TODAY_SCHEDULE = "TODAY_SCHEDULE"
LAST_EMERGENCY = "LAST_EMERGENCY"
WELLBEING_STATUS = "WELLBEING_STATUS"
SWITCH_TO_PATROL = "SWITCH_TO_PATROL"
SWITCH_TO_SORTING = "SWITCH_TO_SORTING"
HELP = "HELP"
UNKNOWN = "UNKNOWN"

# Each entry: (intent, list-of-trigger-phrases).
# Checked top-to-bottom; first match wins.
# Longer/more-specific phrases listed first within each group.
_RULES = [
    (WELLBEING_STATUS,  ["how am i doing", "wellbeing status", "my wellbeing", "health concerns",
                         "am i okay", "am i ok", "any risks", "how is my health", "noticed any concerns",
                         "care status", "overall status"]),
    (SWITCH_TO_PATROL,  ["switch to patrol", "start patrol", "patrol mode", "go to patrol"]),
    (SWITCH_TO_SORTING, ["switch to sorting", "start sorting", "sorting mode", "go to sorting"]),
    (LAST_EMERGENCY,    ["when was the last emergency", "most recent emergency", "last emergency"]),
    (EMERGENCY_STATUS,  ["emergency status", "was there an emergency", "any emergency", "active emergency"]),
    (TODAY_SCHEDULE,    ["what should i take", "today's medicine", "medicine today",
                         "take today", "scheduled today", "today's schedule"]),
    (FIND_MEDICINE,     ["have i scanned", "did i scan", "is there a scan of"]),
    (EXPIRE_SOON,       ["expire soon", "expiring soon", "expires first", "what expires", "which expires",
                         "expire", "expiring", "expiration", "best before", "use by"]),
    (LIST_MEDICINES,    ["what medicines", "which medicines", "medicines do i have", "list medicines",
                         "show medicines", "my medicines", "what do i have", "what have i scanned"]),
    (RECENT_EVENTS,     ["what happened", "recent events", "events today", "show events",
                         "what happened today", "activity log", "event log"]),
    (HELP,              ["what can you do", "what can i ask", "help me", "commands", "how to use"]),
]


def classify_intent(user_message: str) -> dict:
    """
    Keyword-based intent classifier.
    Returns {"intent": str, "confidence": float}.
    Falls back to UNKNOWN when no phrase matches.
    """
    text = user_message.lower().strip()
    for intent, phrases in _RULES:
        for phrase in phrases:
            if phrase in text:
                return {"intent": intent, "confidence": 1.0}
    return {"intent": UNKNOWN, "confidence": 0.0}
