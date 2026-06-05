from typing import Optional

# Longer/more-specific phrases first so they match before shorter substrings.
CONCERN_KEYWORDS = [
    "chest pain",
    "shortness of breath",
    "cannot breathe",
    "cannot get up",
    "dizzy",
    "weak",
    "pain",
    "headache",
    "nausea",
    "confused",
    "fell",
]

_FALLBACK_CONCERN = (
    "I'm sorry you're not feeling well. "
    "Please sit or lie down safely, and contact a caregiver or medical professional "
    "if your symptoms continue or get worse."
)
_FALLBACK_OK = (
    "Thank you for sharing how you feel. "
    "Please rest and let a caregiver know if you don't feel better soon."
)


class HealthCheck:
    def run(
        self,
        user_input: str,
        llm_client=None,
        memory=None,
        tts=None,
    ) -> str:
        text = user_input.lower()
        triggered = [kw for kw in CONCERN_KEYWORDS if kw in text]
        has_concern = bool(triggered)

        profile = memory.get_profile() if memory else {}
        response = self._respond(user_input, has_concern, llm_client, profile)

        if memory:
            memory.add_event("health_check", f"User reported: {user_input[:120]}")
            if has_concern:
                memory.add_event(
                    "health_concern",
                    f"Concern keywords detected: {', '.join(triggered)}",
                    {"keywords": triggered, "user_input": user_input[:120]},
                )

        if has_concern:
            print("\nHEALTH CONCERN DETECTED")
            if tts:
                tts.speak("I detected a possible health concern. Please seek help if needed.")

        return response

    def _respond(self, user_input: str, has_concern: bool, llm_client, profile: dict) -> str:
        if llm_client and not getattr(llm_client, "_disabled", True):
            name_line = f"Patient name: {profile['name']}\n" if profile.get("name") else ""
            prompt = (
                f"Health check conversation.\n"
                f"{name_line}"
                f"User says: \"{user_input}\"\n\n"
                f"Respond in 2-3 sentences. Do not diagnose. "
                f"If the user mentions serious symptoms (dizziness, pain, chest pain, "
                f"difficulty breathing, confusion, falling), recommend seeking professional help promptly. "
                f"If the patient name is known, address them by name. Be caring and calm."
            )
            try:
                return llm_client.ask(prompt)
            except Exception:
                pass
        return _FALLBACK_CONCERN if has_concern else _FALLBACK_OK
