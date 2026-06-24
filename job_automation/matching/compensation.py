from __future__ import annotations

import re


YEARLY_MIN_EUR = 50_000
MONTHLY_MIN_EUR = 4_200
WEEKLY_HOURS_MAX = 36


def analyze_compensation_and_hours(text: str, salary: str = "") -> dict[str, str]:
    # Keep this heuristic conservative: unknown is better than inventing salary or hours.
    combined = f"{salary} {text}".lower()
    salary_values = _extract_salary_values(combined)
    hours_values = _extract_weekly_hours(combined)

    yearly_matches = [value for value, period in salary_values if period == "year"]
    monthly_matches = [value for value, period in salary_values if period == "month"]
    salary_found = bool(salary_values)
    salary_ok = any(value >= YEARLY_MIN_EUR for value in yearly_matches) or any(
        value >= MONTHLY_MIN_EUR for value in monthly_matches
    )

    hours_found = bool(hours_values)
    hours_ok = any(value <= WEEKLY_HOURS_MAX for value in hours_values)

    return {
        "salary_found": "yes" if salary_found else "unknown",
        "salary_target_met": "yes" if salary_ok else ("no" if salary_found else "unknown"),
        "hours_found": "yes" if hours_found else "unknown",
        "hours_target_met": "yes" if hours_ok else ("no" if hours_found else "unknown"),
        "salary_hour_notes": _build_notes(salary_found, salary_ok, hours_found, hours_ok),
    }


def _extract_salary_values(text: str) -> list[tuple[int, str]]:
    values: list[tuple[int, str]] = []
    for match in re.finditer(
        r"(\d{2,3})(?:[.,](\d{3}))?\s?k?\s?(?:eur|euro|brutto)?\s?(year|jahr|jaehrlich|p\.a\.|per year|annum)",
        text,
    ):
        values.append((_normalize_salary_number(match.group(1), match.group(2)), "year"))
    for match in re.finditer(
        r"(\d{1,2})(?:[.,](\d{3}))?\s?k?\s?(?:eur|euro|brutto)?\s?(month|monat|monatlich|monthly)",
        text,
    ):
        values.append((_normalize_salary_number(match.group(1), match.group(2)), "month"))
    for match in re.finditer(r"(?:eur|euro)\s?(\d{2,3})(?:[.,](\d{3}))?\s?k", text):
        values.append((_normalize_salary_number(match.group(1), match.group(2)), "year"))
    return values


def _normalize_salary_number(first: str, thousands: str | None) -> int:
    if thousands:
        return int(f"{first}{thousands}")
    value = int(first)
    return value * 1000 if value < 1000 else value


def _extract_weekly_hours(text: str) -> list[int]:
    values: list[int] = []
    patterns = [
        r"(\d{2})\s?(?:h|std\.?|stunden)\s?(?:/|pro|per)?\s?(?:woche|week|weekly)",
        r"(\d{2})\s?(?:stunden|hours)",
    ]
    for pattern in patterns:
        values.extend(int(match.group(1)) for match in re.finditer(pattern, text))
    return values


def _build_notes(salary_found: bool, salary_ok: bool, hours_found: bool, hours_ok: bool) -> str:
    notes: list[str] = []
    notes.append("salary target met" if salary_ok else "salary not found" if not salary_found else "salary target not met")
    notes.append("weekly hours target met" if hours_ok else "weekly hours not found" if not hours_found else "weekly hours target not met")
    return "; ".join(notes)
