from __future__ import annotations

from matching.keywords import JUNIOR_SIGNALS, SENIOR_NEGATIVE_SIGNALS


def detect_seniority(text: str) -> str:
    lowered = text.lower()
    if any(signal in lowered for signal in SENIOR_NEGATIVE_SIGNALS):
        if any(signal in lowered for signal in JUNIOR_SIGNALS):
            return "junior"
        return "senior"
    if "working student" in lowered or "werkstudent" in lowered:
        return "working_student"
    if "intern" in lowered or "praktikum" in lowered or "стаж" in lowered:
        return "internship"
    if "graduate" in lowered or "trainee" in lowered or "associate" in lowered:
        return "entry_level"
    if any(signal in lowered for signal in JUNIOR_SIGNALS):
        return "junior"
    return "unknown"
