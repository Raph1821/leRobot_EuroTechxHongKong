from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    name: str
    description: str
    required_fields: tuple[str, ...]


MEDICINE_SCANNING = Feature(
    name="MEDICINE_SCANNING",
    description="Medicines recognized by the robot camera (inventory/recognition data)",
    required_fields=("scanned_medicines",),
)

MEDICINE_SCHEDULE = Feature(
    name="MEDICINE_SCHEDULE",
    description="What the patient should take and when (prescribed or added schedule)",
    required_fields=("medicine_schedule", "next_dose"),
)

DOSE_HISTORY = Feature(
    name="DOSE_HISTORY",
    description="What the patient has actually taken",
    required_fields=("dose_history", "taken_today"),
)

REMINDERS = Feature(
    name="REMINDERS",
    description="Active medication reminders",
    required_fields=("medicine_schedule", "active_reminders"),
)

EMERGENCIES = Feature(
    name="EMERGENCIES",
    description="Emergency events detected by voice or camera",
    required_fields=("emergencies", "recent_events"),
)

WELLBEING = Feature(
    name="WELLBEING",
    description="Automated health risk assessment and observed patterns",
    required_fields=("wellbeing_status", "wellbeing_reports", "health_concerns", "recent_events"),
)

PROFILE = Feature(
    name="PROFILE",
    description="Patient and caregiver profile information",
    required_fields=("profile",),
)

DAILY_SUMMARY = Feature(
    name="DAILY_SUMMARY",
    description="Summary of the day's events, doses, scans, and activities",
    required_fields=("daily_summaries", "recent_events", "scanned_medicines", "emergencies", "dose_history"),
)

MORNING_BRIEFING = Feature(
    name="MORNING_BRIEFING",
    description="Morning overview: who the patient is, what they should take, and current wellbeing",
    required_fields=("profile", "medicine_schedule", "next_dose", "wellbeing_status"),
)

ALL_FEATURES: tuple[Feature, ...] = (
    MEDICINE_SCANNING,
    MEDICINE_SCHEDULE,
    DOSE_HISTORY,
    REMINDERS,
    EMERGENCIES,
    WELLBEING,
    PROFILE,
    DAILY_SUMMARY,
    MORNING_BRIEFING,
)
