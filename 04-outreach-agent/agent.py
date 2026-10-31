"""Human-in-the-loop outreach agent.

Chases site contacts for inputs on payment-dispute tickets before the SLA runs
out. The agent does the reading, matching and drafting; a person approves
before anything is sent.

Pipeline
--------
1. Queue      load the export, filter to the severity, drop duplicates
2. Details    fetch each ticket (retry once, else "Could not process")
3. Comments   find the contacts the ops team tagged, the latest comment glimpse,
              and any rejection of the dispute
4. Chat       check what was already sent and whether the contact replied
5. Buckets    every ticket lands in exactly one bucket (counts must reconcile)
   CHECKPOINT a person reviews the buckets
6. Drafts     locked templates, 7 pre-send checks per message
   APPROVAL   nothing is sent without it
7. Send       re-check the never-message list immediately before each send
8. Log        Markdown audit log of the run
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

import rules

MENTION_RE = re.compile(r"@([a-z][a-z0-9-]+)")


# ------------------------------------------------------------------ interfaces
class TicketClient(Protocol):
    def get_ticket(self, ticket_id: str) -> dict: ...


class ChatClient(Protocol):
    def history_since(self, since: datetime) -> list[dict]: ...
    def send_group_dm(self, users: list[str], text: str) -> dict: ...


# ------------------------------------------------------------------ data
@dataclass
class TicketWork:
    ticket_id: str
    row: dict
    ref: str = ""
    station: str = ""
    partner: str = ""
    country: str = ""
    contacts: list[str] = field(default_factory=list)
    excluded_tags: list[str] = field(default_factory=list)
    dropped_tags: list[str] = field(default_factory=list)   # team members and bots tagged
    team_copy: str | None = None
    glimpse: str = "No team comment found"
    rejection: str = "none"        # none | all | partial | unclear
    bucket: str = ""
    reason: str = ""
    flags: list[str] = field(default_factory=list)


@dataclass
class Draft:
    work: TicketWork
    recipients: list[str]
    text: str
    checks: dict[str, bool]

    @property
    def ok(self) -> bool:
        return all(self.checks.values())


@dataclass
class RunResult:
    severity: str
    run: str
    total: int
    duplicates_removed: int
    work: list[TicketWork]
    drafts: list[Draft] = field(default_factory=list)
    sent: list[dict] = field(default_factory=list)

    def bucket_counts(self) -> dict[str, int]:
        counts = {b: 0 for b in rules.BUCKETS}
        for w in self.work:
            counts[w.bucket] += 1
        return counts


# ------------------------------------------------------------------ steps
def check_schedule(severity: str, run: str) -> str:
    if (severity, run) not in rules.SCHEDULE:
        raise ValueError(f"No scheduled {run} run for {severity}. Ask before running.")
    return rules.SCHEDULE[(severity, run)]


def load_queue(path: Path, severity: str) -> tuple[list[dict], int]:
    """Step 1: find columns by header name, filter, de-duplicate."""
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["Severity"].strip().upper() == severity]
    seen, unique = set(), []
    for r in rows:
        if r["Ticket ID"] not in seen:
            seen.add(r["Ticket ID"])
            unique.append(r)
    return unique, len(rows) - len(unique)


def fetch_details(work: TicketWork, client: TicketClient) -> dict | None:
    """Step 2: one retry, then park the ticket with the reason."""
    for attempt in (1, 2):
        try:
            t = client.get_ticket(work.ticket_id)
            work.ref, work.station, work.partner, work.country = t["ref"], t["station"], t["partner"], t["country"]
            return t
        except Exception as exc:  # noqa: BLE001 (any failure parks the ticket)
            if attempt == 2:
                work.bucket, work.reason = "Could not process", f"Ticket lookup failed twice: {exc}"
    return None


def glimpse(comment: dict | None) -> str:
    if not comment:
        return "No team comment found"
    text = comment["text"]
    cut = text if len(text) <= rules.GLIMPSE_CHARS else text[: rules.GLIMPSE_CHARS].rstrip() + "…"
    return f'{comment["author"]} ({comment["date"]}): {cut}'


def read_comments(work: TicketWork, ticket: dict, severity: str) -> None:
    """Step 3: contacts, SEV-1 copy, glimpse, rejection."""
    comments = sorted(ticket.get("comments", []), key=lambda c: c["date"])
    team_tagging = [c for c in comments if c["author"] in rules.TEAM and MENTION_RE.search(c["text"])]
    if team_tagging:
        latest = team_tagging[-1]  # different comments tag different people: use the latest tag set
        tags = list(dict.fromkeys(MENTION_RE.findall(latest["text"])))
        work.contacts = [t for t in tags if rules.allowed_contact(t)]
        work.excluded_tags = [t for t in tags if t in rules.NEVER_MESSAGE]
        work.dropped_tags = [t for t in tags if not rules.allowed_contact(t) and t not in rules.NEVER_MESSAGE]
        if severity == "SEV-1":
            work.team_copy = latest["author"]
    work.glimpse = glimpse(comments[-1] if comments else None)

    text = " ".join(c["text"].lower() for c in comments)
    if any(p in text for p in rules.REJECTION_PHRASES):
        if any(m in text for m in rules.UNCLEAR_MARKERS):
            work.rejection = "unclear"
            work.flags.append("Rejection mentioned but the ticket was reopened: please decide.")
        elif any(m in text for m in rules.PARTIAL_MARKERS):
            work.rejection = "partial"
            work.flags.append("Partly rejected: message contacts only for the items still open.")
        else:
            work.rejection = "all"


def link_for(ref: str) -> str:
    return rules.LINK_FORMAT.format(ref=ref)


def chat_status(work: TicketWork, history: list[dict]) -> str:
    """Step 4: 'replied', 'messaged-no-reply' or 'none'. Only a contact's reply counts."""
    link = link_for(work.ref)
    status = "none"
    for msg in history:
        if link in msg["text"] and set(msg["to"]) & set(work.contacts):
            if set(msg.get("replies_from", [])) & set(work.contacts):
                return "replied"
            status = "messaged-no-reply"
    return status


def assign_bucket(work: TicketWork, history: list[dict]) -> None:
    """Step 5: first matching bucket wins."""
    if work.bucket:  # already parked in Could not process
        return
    if not work.contacts:
        work.bucket, work.reason = "Could not process", "No contact identified: ask before guessing"
    elif work.rejection == "all":
        work.bucket, work.reason = "Rejected", "Every item on the dispute was rejected"
    elif chat_status(work, history) == "replied":
        work.bucket, work.reason = "Already covered", "Contact replied in chat"
    else:
        work.bucket = "Needs outreach"
        work.reason = ("Messaged before, no reply yet" if chat_status(work, history) == "messaged-no-reply"
                       else "No outreach yet")


def make_draft(work: TicketWork, kind: str, already_sent_links: set[str]) -> Draft:
    """Step 6: locked template + 7 checks."""
    link = link_for(work.ref)
    text = rules.TEMPLATES[kind].format(link=link)
    recipients = list(dict.fromkeys(work.contacts + ([work.team_copy] if work.team_copy else [])))
    expected = rules.TEMPLATES[kind].format(link=link)
    checks = {
        "Link is https and uses the ticket reference, followed by a space": f"{link} " in text and link.startswith("https://"),
        "Recipients present, no duplicates, no bots": bool(recipients) and len(recipients) == len(set(recipients))
                                                       and not any(rules.is_bot(r) for r in recipients),
        "No team member except the SEV-1 copy": all(r not in rules.TEAM or r == work.team_copy for r in recipients),
        "No never-message person anywhere": not any(p in text or p in recipients for p in rules.NEVER_MESSAGE),
        "Text matches the locked template exactly": text == expected and "@" not in text,
        "Not already messaged in this window": link not in already_sent_links,
        "Latest comment glimpse shown to the approver": bool(work.glimpse),
    }
    return Draft(work, recipients, text, checks)


def send(drafts: list[Draft], chat: ChatClient, approved: Callable[[list[Draft]], bool]) -> list[dict]:
    """Step 7: only after approval; re-check the never-message list before every send."""
    if not approved(drafts):
        return []
    results = []
    for d in drafts:
        if not d.ok or set(d.recipients) & rules.NEVER_MESSAGE:
            results.append({"ticket": d.work.ticket_id, "status": "blocked", "reason": "failed a pre-send check"})
            continue
        try:
            chat.send_group_dm(d.recipients, d.text)
            results.append({"ticket": d.work.ticket_id, "status": "sent", "to": d.recipients})
        except Exception as exc:  # noqa: BLE001
            results.append({"ticket": d.work.ticket_id, "status": "failed", "reason": str(exc)})
    return results


def run_agent(queue_csv: Path, severity: str, run: str, tickets: TicketClient, chat: ChatClient,
              window_start: datetime, run_start: datetime) -> RunResult:
    """Steps 1-6. Stops at the approval gate: call send() separately."""
    check_schedule(severity, run)
    rows, dupes = load_queue(queue_csv, severity)
    history = chat.history_since(window_start)
    result = RunResult(severity, run, len(rows), dupes, [TicketWork(r["Ticket ID"], r) for r in rows])
    for w in result.work:
        ticket = fetch_details(w, tickets)
        if ticket:
            read_comments(w, ticket, severity)
        assign_bucket(w, history)
    counts = result.bucket_counts()
    assert sum(counts.values()) == result.total, "every ticket must land in exactly one bucket"

    # Links already sent in *this* run window (e.g. a re-run at the same slot) must not be sent twice.
    sent_this_window = {l for m in history if datetime.fromisoformat(m["sent_at"]) >= run_start
                        for l in re.findall(r"https://\S+", m["text"])}
    kind = "follow-up" if run == "follow-up" else "first"
    for w in result.work:
        if w.bucket == "Needs outreach" and w.rejection != "unclear":
            result.drafts.append(make_draft(w, kind, sent_this_window))
    return result


def write_log(result: RunResult, path: Path, now: datetime) -> Path:
    """Step 8: append a run section to today's log."""
    c = result.bucket_counts()
    sent = sum(s["status"] == "sent" for s in result.sent)
    lines = [f"## {result.severity} {result.run} run, {now:%Y-%m-%d %H:%M}", "",
             f"Total {result.total} · duplicates removed {result.duplicates_removed} · "
             + " · ".join(f"{k} {v}" for k, v in c.items()) + f" · sent {sent}", "",
             "| Ticket | Site | Partner | Bucket | Contacts | Excluded tags | Team copy | Status |",
             "|---|---|---|---|---|---|---|---|"]
    status = {s["ticket"]: s["status"] for s in result.sent}
    for w in result.work:
        lines.append(f"| {w.ticket_id} | {w.station} | {w.partner} | {w.bucket} | {', '.join(w.contacts) or '-'} | "
                     f"{', '.join(w.excluded_tags) or '-'} | {w.team_copy or '-'} | {status.get(w.ticket_id, w.reason)} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")
    return path
