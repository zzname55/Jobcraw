from __future__ import annotations

import re

from matching.keywords import REGION_KEYWORDS


COUNTRY_HINTS = {
    "germany": ["germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne", "köln", "düsseldorf", "stuttgart", "germering"],
    "austria": ["austria", "österreich", "vienna", "wien"],
    "switzerland": ["switzerland", "schweiz", "zurich", "zürich"],
    "usa": ["usa", "united states", "new york", "san francisco"],
    "canada": ["canada", "toronto", "vancouver"],
    "brazil": ["brazil", "brasil", "cabedelo", "são paulo", "sao paulo", "rio de janeiro"],
    "egypt": ["egypt", "cairo"],
    "philippines": ["philippines", "manila"],
    "united kingdom": ["united kingdom", "uk", "london", "england"],
    "spain": ["spain", "madrid", "barcelona"],
    "portugal": ["portugal", "lisbon", "porto"],
    "france": ["france", "paris"],
    "netherlands": ["netherlands", "amsterdam"],
}


CITY_HINTS = {
    "Berlin": ("germany", "dach"),
    "Munich": ("germany", "dach"),
    "München": ("germany", "dach"),
    "Hamburg": ("germany", "dach"),
    "Frankfurt": ("germany", "dach"),
    "Cologne": ("germany", "dach"),
    "Köln": ("germany", "dach"),
    "Düsseldorf": ("germany", "dach"),
    "Stuttgart": ("germany", "dach"),
    "Germering": ("germany", "dach"),
    "Vienna": ("austria", "dach"),
    "Wien": ("austria", "dach"),
    "Zurich": ("switzerland", "dach"),
    "Zürich": ("switzerland", "dach"),
    "London": ("united kingdom", "europe"),
    "Amsterdam": ("netherlands", "europe"),
    "Paris": ("france", "europe"),
    "Madrid": ("spain", "europe"),
    "Barcelona": ("spain", "europe"),
    "Lisbon": ("portugal", "europe"),
    "Cabedelo": ("brazil", "america"),
    "Cairo": ("egypt", "unknown"),
    "Manila": ("philippines", "asia"),
}


# Geographic words that must never be mistaken for a company name. Built from the
# country/city hint tables plus the generic region words used across the project.
GEOGRAPHIC_NAMES: set[str] = (
    set(COUNTRY_HINTS.keys())
    | {hint for hints in COUNTRY_HINTS.values() for hint in hints}
    | {city.lower() for city in CITY_HINTS}
    | {"dach", "europe", "europa", "worldwide", "remote", "hybrid", "onsite", "asia", "america", "emea", "anywhere"}
)


def is_location_name(value: str) -> bool:
    """True when ``value`` is purely a place name (country, city, or region word).

    Used to stop the search scraper from turning a location such as
    ``"Cairo, Egypt"`` or ``"Egypt"`` into a company name. A value counts as a
    location only when every comma/slash separated part is itself a known place,
    so legitimate names like ``"London Fintech Ltd"`` are left untouched.
    """
    cleaned = " ".join((value or "").split()).strip(" ,-–—|").lower()
    if not cleaned:
        return False
    if cleaned in GEOGRAPHIC_NAMES:
        return True
    parts = [part.strip() for part in re.split(r"[,/]", cleaned) if part.strip()]
    return len(parts) > 1 and all(part in GEOGRAPHIC_NAMES for part in parts)


def detect_region(text: str) -> tuple[str, str]:
    details = detect_location_details(text)
    return details["region"], details["country"]


def detect_location_details(text: str) -> dict[str, str]:
    lowered = (text or "").lower()
    city = ""
    city_country = ""
    city_region = ""
    for candidate, (country, region) in CITY_HINTS.items():
        if candidate.lower() in lowered:
            city = candidate
            city_country = country
            city_region = region
            break

    country = ""
    for candidate, hints in COUNTRY_HINTS.items():
        if any(hint in lowered for hint in hints):
            country = candidate
            break
    country = country or city_country

    for region, hints in REGION_KEYWORDS.items():
        if any(hint in lowered for hint in hints):
            if region == "dach":
                return {"region": "dach", "country": country, "city": city}
            return {"region": region, "country": country, "city": city}
    if city_region:
        return {"region": city_region, "country": country, "city": city}
    if "remote" in lowered:
        return {"region": "worldwide", "country": country, "city": city}
    return {"region": "unknown", "country": country, "city": city}
