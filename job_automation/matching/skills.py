from __future__ import annotations

import re

from matching.keywords import AI_SKILLS, AUTOMATION_SKILLS

ENGINEERING_SKILLS = [
    "python",
    "javascript",
    "typescript",
    "sql",
    "fastapi",
    "node.js",
    "git",
    "docker",
    "aws",
    "gcp",
    "azure",
    "ci/cd",
    "scraping",
    "data pipelines",
    "api",
    "apis",
]


def term_in_text(text: str, term: str) -> bool:
    lowered = text.lower()
    term_lower = term.lower()
    if len(term_lower) <= 3 and term_lower.isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(term_lower)}(?![a-z0-9])", lowered))
    return term_lower in lowered


def extract_skills(text: str) -> str:
    candidates = AI_SKILLS + AUTOMATION_SKILLS + ENGINEERING_SKILLS
    found = []
    for skill in candidates:
        if term_in_text(text, skill) and skill not in found:
            found.append(skill)
    return ", ".join(found[:18])
