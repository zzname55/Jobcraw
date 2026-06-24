from __future__ import annotations

import re


CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
GERMAN_HINTS = (" der ", " die ", " das ", " und ", " für ", " mit ", "werkstudent", "praktikum", "berufseinsteiger", "ki ")


def detect_language(text: str) -> str:
    lowered = f" {text.lower()} "
    if CYRILLIC_RE.search(text):
        return "ru"
    if any(hint in lowered for hint in GERMAN_HINTS) or any(char in lowered for char in "äöüß"):
        return "de"
    if text.strip():
        return "en"
    return "unknown"
