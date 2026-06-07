from datetime import datetime, timedelta, timezone


class MorningBriefing:
    def __init__(self, memory, llm_client=None) -> None:
        self._memory = memory
        self._llm = llm_client

    def generate(self) -> str:
        data = self._collect()
        llm_available = self._llm and not getattr(self._llm, "_disabled", True)
        text = self._generate_llm(data) if llm_available else self._generate_fallback(data)
        self._store(text)
        return text

    # ------------------------------------------------------------------

    def _collect(self) -> dict:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        mem = self._memory._data
        profile = self._memory.get_profile()

        all_events = mem.get("events", [])
        all_emergencies = mem.get("emergencies", [])

        yesterday_scans = [
            e for e in all_events
            if e.get("type") == "medicine_scanned"
            and e.get("timestamp", "").startswith(yesterday)
        ]
        yesterday_emergencies = [
            e for e in all_emergencies
            if e.get("timestamp", "").startswith(yesterday)
        ]

        yesterday_summary = next(
            (s.get("summary") for s in mem.get("daily_summaries", [])
             if s.get("date") == yesterday),
            None,
        )

        return {
            "name": profile.get("name", ""),
            "schedules": self._memory.get_active_schedules(),
            "yesterday_scan_count": len(yesterday_scans),
            "yesterday_emergency_count": len(yesterday_emergencies),
            "yesterday_summary": yesterday_summary,
        }

    def _generate_llm(self, data: dict) -> str:
        name_line = f"Patient name: {data['name']}\n" if data.get("name") else ""
        schedules_str = "\n".join(
            f"  - {s['medicine_name'].title()} at {', '.join(s['times'])}"
            for s in data["schedules"]
        ) or "  (none scheduled)"
        yesterday_note = (
            data["yesterday_summary"]
            or (
                f"{data['yesterday_scan_count']} medicine(s) scanned, "
                f"{data['yesterday_emergency_count']} emergency event(s)."
            )
        )
        prompt = (
            "Generate a short, warm morning briefing for a care assistant app.\n"
            f"{name_line}"
            f"Today's medicine schedule:\n{schedules_str}\n"
            f"Yesterday: {yesterday_note}\n\n"
            "Write 3-5 sentences. Greet by name if provided. "
            "List today's medicines. Briefly mention yesterday. End warmly."
        )
        try:
            return self._llm.ask(prompt)
        except Exception:
            return self._generate_fallback(data)

    def _generate_fallback(self, data: dict) -> str:
        name = data.get("name", "")
        lines = [f"Good morning {name}." if name else "Good morning.", ""]

        schedules = data["schedules"]
        if schedules:
            lines.append("Today you have:")
            for s in schedules:
                times_str = ", ".join(s["times"])
                lines.append(f"- {s['medicine_name'].title()} at {times_str}")
        else:
            lines.append("No medicine reminders scheduled for today.")

        lines += ["", "Yesterday:"]
        count = data["yesterday_scan_count"]
        lines.append(f"- {count} medicine(s) were scanned." if count else "- No medicines were scanned.")
        if data["yesterday_emergency_count"]:
            lines.append(f"- {data['yesterday_emergency_count']} emergency event(s) detected.")
        else:
            lines.append("- No confirmed falls were detected.")

        lines += ["", "Have a good day."]
        return "\n".join(lines)

    def _store(self, text: str) -> None:
        self._memory._data["briefings"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "text": text,
        })
        self._memory.save()
