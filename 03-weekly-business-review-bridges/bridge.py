"""Compute week-over-week metric bridges from raw ticket data.

A "bridge" explains *why* a metric moved: it splits the change between two
weeks into the drivers that caused it, so a leadership review gets the reason,
not just the number.

Metrics (per business line)
---------------------------
- Dispute rate   = initial disputes / eligible partner-site combinations
- Invalid rate   = disputes rejected as invalid / resolved initial disputes
- SLA rate       = disputes resolved within 3 business days / disputes with an
                   SLA outcome, by ticket creation week

Driver decomposition: for a rate r = n / base, the change between weeks is
split by category c as   (n_c,cur / base_cur) - (n_c,prev / base_prev).
The contributions add up exactly to the total change, so the bridge always
reconciles to the headline number.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

SLA_BUSINESS_DAYS = 3


def add_business_days(start: datetime, days: int) -> datetime:
    current, added = start, 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def bps(value: float) -> int:
    return round(value * 10000)


@dataclass
class Driver:
    name: str
    prev: int
    cur: int
    contribution_bps: int


@dataclass
class RateBridge:
    metric: str
    line: str
    prev_rate: float | None
    cur_rate: float | None
    prev_n: int
    cur_n: int
    prev_base: int
    cur_base: int
    drivers: list[Driver] = field(default_factory=list)

    @property
    def change_bps(self) -> int | None:
        if self.prev_rate is None or self.cur_rate is None:
            return None
        return bps(self.cur_rate - self.prev_rate)


@dataclass
class SlaMiss:
    ticket_id: str
    station: str
    partner: str
    cause: str
    hours_late: float


@dataclass
class SlaBridge:
    line: str
    week: int
    met: int
    missed: int
    open_in_sla: int
    misses: list[SlaMiss]
    prev_rate: float | None

    @property
    def rate(self) -> float | None:
        decided = self.met + self.missed
        return self.met / decided if decided else None

    def repeat_sites(self, minimum: int = 2) -> list[tuple[str, int]]:
        waiting = Counter(m.station for m in self.misses if m.cause == "Waiting on site input")
        return [(s, n) for s, n in waiting.most_common() if n >= minimum]


def load_tickets(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["week"] = int(r["week"])
        r["quantity"] = int(r["quantity"])
        r["reopened"] = r["reopened"] == "1"
        for k in ("created_at", "first_response_at", "resolved_at"):
            r[k] = datetime.fromisoformat(r[k]) if r[k] else None
    return rows


def load_base(path: Path) -> dict[tuple[int, str], int]:
    with path.open(newline="", encoding="utf-8") as fh:
        return {(int(r["week"]), r["business_line"]): int(r["eligible_combinations"]) for r in csv.DictReader(fh)}


def _decompose(prev_items: list[dict], cur_items: list[dict], key: str, prev_base: int, cur_base: int) -> list[Driver]:
    prev_c, cur_c = Counter(r[key] for r in prev_items), Counter(r[key] for r in cur_items)
    drivers = []
    for name in set(prev_c) | set(cur_c):
        contribution = cur_c[name] / cur_base - prev_c[name] / prev_base
        drivers.append(Driver(name, prev_c[name], cur_c[name], bps(contribution)))
    return sorted(drivers, key=lambda d: abs(d.contribution_bps), reverse=True)


def dispute_rate_bridge(tickets, base, line: str, week: int, by: str = "use_case") -> RateBridge:
    prev = [t for t in tickets if t["business_line"] == line and t["week"] == week - 1 and t["quantity"] == 1]
    cur = [t for t in tickets if t["business_line"] == line and t["week"] == week and t["quantity"] == 1]
    pb, cb = base[(week - 1, line)], base[(week, line)]
    return RateBridge("Dispute rate", line, len(prev) / pb, len(cur) / cb, len(prev), len(cur), pb, cb,
                      _decompose(prev, cur, by, pb, cb))


def invalid_rate_bridge(tickets, line: str, week: int) -> RateBridge:
    def resolved(w):
        return [t for t in tickets if t["business_line"] == line and t["week"] == w
                and t["quantity"] == 1 and t["resolved_at"] is not None]
    prev, cur = resolved(week - 1), resolved(week)
    prev_inv = [t for t in prev if t["classification"] == "invalid"]
    cur_inv = [t for t in cur if t["classification"] == "invalid"]
    return RateBridge("Invalid rate", line,
                      len(prev_inv) / len(prev) if prev else None, len(cur_inv) / len(cur) if cur else None,
                      len(prev_inv), len(cur_inv), len(prev), len(cur),
                      _decompose(prev_inv, cur_inv, "rejection_reason", max(len(prev), 1), max(len(cur), 1)))


def miss_cause(t: dict, deadline: datetime) -> str:
    """One root cause per missed ticket, checked in order of accountability."""
    if t["first_response_at"] is None or t["first_response_at"] > deadline:
        return "Late first response"
    if t["reopened"]:
        return "Reopened after resolution"
    if t["waiting_on"] == "site":
        return "Waiting on site input"
    return "Resolved after deadline"


def sla_bridge(tickets, line: str, week: int, as_of: datetime) -> SlaBridge:
    def outcome(w):
        met = missed = open_ = 0
        misses = []
        for t in tickets:
            if t["business_line"] != line or t["week"] != w or t["quantity"] != 1:
                continue
            deadline = add_business_days(t["created_at"], SLA_BUSINESS_DAYS)
            end = t["resolved_at"]
            if end is not None and end <= deadline:
                met += 1
            elif end is None and as_of <= deadline:
                open_ += 1
            else:
                missed += 1
                late = ((end or as_of) - deadline).total_seconds() / 3600
                misses.append(SlaMiss(t["ticket_id"], t["station"], t["partner"], miss_cause(t, deadline), round(late, 1)))
        return met, missed, open_, misses

    pm, pmi, _, _ = outcome(week - 1)
    met, missed, open_, misses = outcome(week)
    prev_rate = pm / (pm + pmi) if pm + pmi else None
    return SlaBridge(line, week, met, missed, open_, sorted(misses, key=lambda m: -m.hours_late), prev_rate)


def anomalies(tickets, base, week: int) -> list[str]:
    """Data-quality checks worth calling out before the numbers go to leadership."""
    notes = []
    lines = sorted({t["business_line"] for t in tickets})
    for line in lines:
        for w in (week - 1, week):
            if (w, line) not in base:
                notes.append(f"{line}: no eligible-combination base for week {w}; dispute rate not comparable.")
    blank = [t["ticket_id"] for t in tickets
             if t["week"] == week and t["classification"] == "invalid" and not t["rejection_reason"]]
    if blank:
        notes.append(f"{len(blank)} invalid disputes in week {week} have no rejection reason recorded "
                     f"(e.g. {', '.join(blank[:3])}); they are grouped as 'Unspecified'.")
    dupes = [k for k, n in Counter((t["station"], t["partner"], t["week"], t["use_case"]) for t in tickets
                                   if t["week"] == week and t["quantity"] == 1).items() if n > 2]
    if dupes:
        notes.append(f"{len(dupes)} site/partner/use-case combinations have more than two initial disputes "
                     f"in week {week}; check for duplicate submissions.")
    return notes
