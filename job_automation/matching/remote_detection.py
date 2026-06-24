from __future__ import annotations

from matching.keywords import HYBRID_SIGNALS, REMOTE_SIGNALS


def detect_remote_type(text: str) -> str:
    lowered = text.lower()
    if any(signal in lowered for signal in REMOTE_SIGNALS):
        return "remote"
    if any(signal in lowered for signal in HYBRID_SIGNALS):
        return "hybrid"
    if "onsite" in lowered or "on-site" in lowered or "office" in lowered or "büro" in lowered:
        return "onsite"
    return "unknown"
