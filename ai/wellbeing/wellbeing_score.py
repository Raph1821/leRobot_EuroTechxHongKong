class WellbeingScore:
    def calculate(self, signals: dict) -> dict:
        score = 0
        reasons = []

        # Camera / fall emergency: +30
        if signals.get("camera_emergency_count", 0) > 0:
            score += 30
            reasons.append("Confirmed fall or camera emergency detected")

        # Voice emergencies: +25 each
        voice = signals.get("voice_emergency_count", 0)
        if voice > 0:
            score += 25 * voice
            reasons.append(
                "Voice emergency request detected"
                if voice == 1
                else f"{voice} voice emergency requests detected"
            )

        # Health concerns: +15 each, max 45
        concerns = signals.get("health_concern_count", 0)
        if concerns > 0:
            score += min(concerns * 15, 45)
            reasons.append(
                "1 health concern reported this week"
                if concerns == 1
                else f"{concerns} health concerns reported this week"
            )

        # Missed reminders: +10 each, max 30
        missed = signals.get("missed_reminder_count", 0)
        if missed > 0:
            score += min(missed * 10, 30)
            reasons.append(
                "1 missed medicine reminder"
                if missed == 1
                else f"{missed} missed medicine reminders"
            )

        # Expired medicines: +5 each, max 15
        expired = signals.get("expired_medicine_count", 0)
        if expired > 0:
            score += min(expired * 5, 15)
            reasons.append(
                "1 expired medicine on record"
                if expired == 1
                else f"{expired} expired medicines on record"
            )

        score = min(score, 100)

        if score >= 60:
            risk_level = "HIGH_RISK"
        elif score >= 30:
            risk_level = "CAUTION"
        else:
            risk_level = "NORMAL"

        return {
            "risk_level": risk_level,
            "score": score,
            "reasons": reasons,
        }
