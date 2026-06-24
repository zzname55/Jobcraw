from __future__ import annotations

from matching.keywords import AI_SKILLS
from matching.skills import term_in_text


# An AI signal: the niche is fundamentally AI-centric, so an AI/LLM/agent term is
# the strongest relevance marker. Reuses the project's AI vocabulary. Note: bare
# "agent"/"agents" are deliberately excluded -- they match human roles like
# "Customer Service Agent"; genuine AI-agent roles still match via "ai"/"agentic"/
# the "ai agents" phrase already in AI_SKILLS.
AI_SIGNALS = list(dict.fromkeys(AI_SKILLS + ["machine learning", "ml", "agentic", "mcp", "model context protocol"]))

# Specific automation-tool signals. Deliberately NOT the generic word "automation"
# (that floods in DevOps/SRE/industrial roles); only the no-code/workflow-automation
# tooling that defines this niche.
AUTOMATION_TOOL_SIGNALS = [
    "n8n",
    "zapier",
    "make.com",
    "no-code",
    "low-code",
    "no code",
    "low code",
    "workflow automation",
    "process automation",
    "rpa",
    "robotic process automation",
    "ai automation",
    "ki automatisierung",
    "workflow automatisierung",
]


def is_relevant_text(text: str) -> bool:
    """True when the text shows an AI signal or a specific automation-tool signal.

    Broad job feeds (RemoteOK, Arbeitnow, RSS) return everything a board has, so
    this keeps only on-topic postings instead of spending the per-source budget on
    unrelated jobs. It requires a real AI/agent term or no-code/workflow-automation
    tooling -- generic "automation" alone (DevOps, industrial) does not qualify.
    Scoring still ranks what survives; this is just a cheap, recall-friendly gate.
    """
    return any(term_in_text(text, term) for term in AI_SIGNALS) or any(
        term_in_text(text, term) for term in AUTOMATION_TOOL_SIGNALS
    )
