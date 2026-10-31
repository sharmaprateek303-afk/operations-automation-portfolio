"""Guardrails and configuration for the outreach agent.

Everything the agent is *not allowed* to decide lives here, in one reviewable
file. The agent code reads these rules; it never improvises around them.
"""
from __future__ import annotations

# Ops team members. They write the comments that tag site contacts; they are
# never messaged as a site contact themselves (SEV-1 copies the last one).
TEAM = {"ops-anna", "ops-ravi", "ops-meera", "ops-tom", "ops-lena", "ops-kai"}

# People who must never be messaged or @mentioned, in any run, for any reason.
NEVER_MESSAGE = {"finance-lead", "regional-director"}

# Automated authors. Anything matching these is ignored as a contact.
BOT_MARKERS = ("bot-", "automation", "rules-engine", "label-sync")

# Run schedule (local time). The agent refuses runs that don't match.
SCHEDULE = {
    ("SEV-1", "first"): "14:00",
    ("SEV-1", "follow-up"): "20:00",   # non-responders only
    ("SEV-2", "first"): "13:00",
    ("SEV-3", "first"): "18:00",
}

# Locked message templates: only {link} may change. The agent never rewords them.
TEMPLATES = {
    "first": ("Hi, hope you are having a great day! Reaching out about this ticket to get your inputs: {link} "
              "We need all inputs within 72 hours of the SLA so the partner is paid on time. Thank you in advance."),
    "follow-up": "Hi, following up on this, we still need your inputs please: {link} ",
}
LINK_FORMAT = "https://tickets.example.com/{ref}/communication"

# Phrases that mean a dispute (or part of it) was rejected.
REJECTION_PHRASES = ("request rejected", "dispute rejected", "dispute is denied", "not approved", "rejected as per")
PARTIAL_MARKERS = ("partially", "remaining", "except")
UNCLEAR_MARKERS = ("reopen", "re-open", "reconsider")

GLIMPSE_CHARS = 250

# Buckets, in priority order. A ticket lands in the FIRST bucket that matches.
BUCKETS = ("Could not process", "Rejected", "Already covered", "Needs outreach")


def is_bot(author: str) -> bool:
    a = author.lower()
    return any(m in a for m in BOT_MARKERS)


def allowed_contact(alias: str) -> bool:
    return alias not in TEAM and alias not in NEVER_MESSAGE and not is_bot(alias)
