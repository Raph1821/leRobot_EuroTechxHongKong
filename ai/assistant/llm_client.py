import os
from pathlib import Path
from typing import Optional

from assistant.prompts import SYSTEM_PROMPT

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _load_env() -> None:
    """Load key=value pairs from .env into os.environ (does not overwrite existing vars)."""
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
    parts = ["[Current system context]"]

    if profile := context.get("profile"):
        if name := profile.get("name"):
            parts.append(f"Patient name: {name}")
        if age := profile.get("age"):
            parts.append(f"Patient age: {age}")
        if caregiver := profile.get("caregiver_name"):
            parts.append(f"Caregiver: {caregiver}")

    if mode := context.get("current_mode"):
        parts.append(f"Current mode: {mode}")

    if medicines := context.get("scanned_medicines"):
        parts.append("Scanned medicines:")
        for m in medicines:
            parts.append(
                f"  - {m.get('medicine_name', '?')}"
                f" (expires {m.get('expiration_date', '?')},"
                f" status: {m.get('status', 'unknown')})"
            )

    if events := context.get("recent_events"):
        parts.append("Recent events:")
        for e in events:
            parts.append(f"  - [{e.get('event_type', '?')}] {e.get('message', '')}")

    if status := context.get("patrol_status"):
        parts.append(f"Patrol status: {status}")

    if schedules := context.get("active_schedules"):
        parts.append("Active medicine schedule:")
        for s in schedules:
            times_str = ", ".join(s.get("times", []))
            parts.append(f"  - {s.get('medicine_name', '?')} {s.get('dose', '')} at {times_str}")

    if emergencies := context.get("recent_emergencies"):
        parts.append("Recent emergencies:")
        for e in emergencies[-3:]:
            parts.append(f"  - [{e.get('source', '?')}] {e.get('message', '')}")

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
