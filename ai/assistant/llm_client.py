import os
from pathlib import Path
from typing import Optional

from assistant.prompts import SYSTEM_PROMPT

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _load_env() -> None:
    if not _ENV_PATH.exists():
        return
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _format_context(context: dict) -> str:
    """Format CareContext into a concise text block for the LLM."""
    parts = ["[CareContext]"]

    if date := context.get("current_date"):
        parts.append(f"Date: {date}")

    if profile := context.get("profile"):
        if name := profile.get("name"):
            parts.append(f"Patient: {name}")
        if age := profile.get("age"):
            parts.append(f"Age: {age}")
        if caregiver := profile.get("caregiver_name"):
            parts.append(f"Caregiver: {caregiver}")

    # Support both CareContextBuilder key (medicine_schedule) and legacy terminal key (active_schedules)
    schedules = context.get("medicine_schedule") or context.get("active_schedules")
    if schedules:
        parts.append("Medicine schedule:")
        for s in schedules:
            times_str = ", ".join(s.get("times", []))
            note = f" ({s['notes']})" if s.get("notes") else ""
            mock = " [demo]" if s.get("source") == "demo_mock" else ""
            parts.append(f"  - {s.get('medicine_name', '?')} {s.get('dose', '')} at {times_str}{note}{mock}")
    else:
        parts.append("Medicine schedule: none on record")

    if next_dose := context.get("next_dose"):
        if next_dose.get("has_next"):
            note = f" ({next_dose['notes']})" if next_dose.get("notes") else ""
            parts.append(
                f"Next dose: {next_dose['medicine_name']} at {next_dose['time']}"
                f" — {next_dose['dose']}{note}"
            )
        else:
            parts.append("Next dose: none scheduled")

    taken = context.get("taken_today", [])
    if taken:
        parts.append("Taken today:")
        for r in taken:
            t = r.get("scheduled_time") or r.get("recorded_at", "")[:16]
            parts.append(f"  - {r.get('medicine_name', '?')} at {t}")
    else:
        parts.append("Taken today: none recorded")

    if history := context.get("dose_history"):
        recent = history[-5:]
        parts.append(f"Dose history (last {len(recent)} records):")
        for r in recent:
            parts.append(
                f"  - {r.get('medicine_name', '?')} {r.get('status', '?')}"
                f" at {r.get('recorded_at', '')[:16]}"
            )

    if medicines := context.get("scanned_medicines"):
        parts.append("Scanned medicines:")
        for m in medicines:
            parts.append(
                f"  - {m.get('name', '?')}"
                f" (expires {m.get('expiration_date', '?')},"
                f" status: {m.get('status', 'unknown')})"
            )
    else:
        parts.append("Scanned medicines: none on record")

    if ws := context.get("wellbeing_status"):
        if ws.get("risk_level"):
            reasons = "; ".join(ws.get("reasons", [])) or "none"
            parts.append(
                f"Wellbeing: {ws['risk_level']} (score {ws.get('score')}/100)"
                f" — {reasons}"
            )

    if concerns := context.get("health_concerns"):
        parts.append("Health concerns: " + "; ".join(concerns))

    # Support both CareContextBuilder key (emergencies) and legacy key (recent_emergencies)
    emergencies = context.get("emergencies") or context.get("recent_emergencies")
    if emergencies:
        parts.append(f"Emergencies ({len(emergencies)} total, showing last 3):")
        for e in emergencies[-3:]:
            parts.append(f"  - [{e.get('source', '?')}] {e.get('message', '')}")

    if events := context.get("recent_events"):
        parts.append("Recent events:")
        for e in events[-5:]:
            parts.append(f"  - [{e.get('type', e.get('event_type', '?'))}] {e.get('message', '')}")

    # Legacy terminal assistant fields
    if mode := context.get("current_mode"):
        parts.append(f"Current mode: {mode}")
    if status := context.get("patrol_status"):
        parts.append(f"Patrol status: {status}")

    return "\n".join(parts)


class LLMClient:
    def __init__(self) -> None:
        _load_env()
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._disabled = True
            return
        self._disabled = False
        self._model = os.environ.get("CLAUDE_MODEL", _DEFAULT_MODEL)
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def ask(self, user_message: str, context: Optional[dict] = None) -> str:
        if self._disabled:
            return "CareAI Assistant disabled: ANTHROPIC_API_KEY not set"

        full_message = user_message
        if context:
            full_message = f"{_format_context(context)}\n\n{user_message}"

        import anthropic
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": full_message}],
        )
        return response.content[0].text

    def look_at_many(self, images_jpeg: list[bytes], user_message: str) -> str:
        """Answer a question about several images using Claude's vision.

        images_jpeg: list of raw JPEG frames the robot saw (best matches first).
        Lets Claude describe ALL relevant items it sees, not just one.
        """
        if self._disabled:
            return "CareAI vision disabled: ANTHROPIC_API_KEY not set"
        images_jpeg = [img for img in images_jpeg if img]
        if not images_jpeg:
            return self.ask(user_message)

        import base64
        content = []
        for img in images_jpeg:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(img).decode(),
                },
            })
        content.append({"type": "text", "text": (
            f'The user asked: "{user_message}".\n'
            "These are snapshots of things you saw while looking around the room. "
            "Look at them and reply in ONE or TWO short, warm sentences listing the "
            "items that match the request, mentioning each object specifically "
            "(type/colour). Ignore images that don't match. If none match, say you "
            "couldn't find anything suitable."
        )})

        response = self._client.messages.create(
            model=self._model,
            max_tokens=400,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text

    def look_at(self, image_jpeg: bytes, user_message: str) -> str:
        """Answer a question about an image using Claude's vision.

        image_jpeg: raw JPEG bytes (e.g. a frame the robot saw during exploration).
        user_message: the user's request, e.g. "I need something I can drink".
        """
        if self._disabled:
            return "CareAI vision disabled: ANTHROPIC_API_KEY not set"
        if not image_jpeg:
            return self.ask(user_message)

        import base64
        b64 = base64.b64encode(image_jpeg).decode()
        prompt = (
            f'The user asked: "{user_message}".\n'
            "This image is something you saw while looking around the room that "
            "best matches their request. Look at it and reply in ONE short, warm "
            "sentence telling them what you see that fits, mentioning the object "
            "specifically (e.g. its type/color). If nothing in the image actually "
            "matches, say you could not find it."
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return response.content[0].text
