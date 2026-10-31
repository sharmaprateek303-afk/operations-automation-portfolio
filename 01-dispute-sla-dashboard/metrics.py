"""KPI engine for the dispute SLA dashboard.

All metrics are derived from raw ticket rows, so the dashboard never needs
hand-computed numbers. Pure standard library.

Definitions
-----------
- SLA deadline: 3 business days (Mon-Fri) after the ticket is created.
- Resolution Rate in SLA (RRS): tickets resolved on or before their deadline,
  divided by tickets with a final SLA outcome (met or missed). Open tickets that
  are still inside their SLA window are excluded until they resolve or breach.
- Re-dispute rate: re-disputes (a partner disputing the same invoice again)
  divided by initial disputes in the same week.
- Backlog: open tickets at the "as of" time, split by SLA health.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

SLA_BUSINESS_DAYS = 3
TARGET_RRS = 0.95
AT_RISK_HOURS = 24


def parse_ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def add_business_days(start: datetime, days: int) -> datetime:
    """Return start + `days` business days, keeping the time of day."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon=0 .. Fri=4
            added += 1
    return current


def sla_deadline(ticket: dict) -> datetime:
    return add_business_days(parse_ts(ticket["created_at"]), SLA_BUSINESS_DAYS)


def sla_status(ticket: dict, as_of: datetime) -> str:
    """One of: met, missed, at_risk, on_track."""
    deadline = sla_deadline(ticket)
    resolved = parse_ts(ticket.get("resolved_at"))
    if resolved:
        return "met" if resolved <= deadline else "missed"
    if as_of > deadline:
        return "missed"
    if deadline - as_of <= timedelta(hours=AT_RISK_HOURS):
        return "at_risk"
    return "on_track"


def week_label(ts: datetime) -> str:
    iso = ts.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def enrich(tickets: list[dict], as_of: datetime) -> list[dict]:
    """Add derived fields used by the dashboard table."""
    rows = []
    for t in tickets:
        deadline = sla_deadline(t)
        status = sla_status(t, as_of)
        hours_left = round((deadline - as_of).total_seconds() / 3600, 1) if not t.get("resolved_at") else None
        rows.append({
            **t,
            "week": week_label(parse_ts(t["created_at"])),
            "sla_deadline": deadline.isoformat(timespec="minutes"),
            "sla_status": status,
            "hours_to_deadline": hours_left,
        })
    return rows


def weekly_metrics(rows: list[dict]) -> list[dict]:
    """Per region and week: volumes, resolution rate in SLA, re-dispute rate."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["region"], r["week"])].append(r)
        groups[("All", r["week"])].append(r)

    out = []
    for (region, week), items in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        initial = [r for r in items if r["kind"] == "initial"]
        redisputes = [r for r in items if r["kind"] == "re-dispute"]
        status = Counter(r["sla_status"] for r in initial)
        decided = status["met"] + status["missed"]
        out.append({
            "region": region,
            "week": week,
            "initial_disputes": len(initial),
            "re_disputes": len(redisputes),
            "met": status["met"],
            "missed": status["missed"],
            "open_in_sla": status["on_track"] + status["at_risk"],
            "resolution_rate_in_sla": round(status["met"] / decided, 4) if decided else None,
            "re_dispute_rate": round(len(redisputes) / len(initial), 4) if initial else None,
        })
    return out


def dispute_mix(rows: list[dict], week: str) -> dict[str, dict[str, int]]:
    mix: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if r["week"] == week and r["kind"] == "initial":
            mix[r["region"]][r["dispute_type"]] += 1
            mix["All"][r["dispute_type"]] += 1
    return {region: dict(c.most_common()) for region, c in mix.items()}


def build_payload(raw: dict) -> dict:
    """Everything the dashboard needs, in one response."""
    as_of = parse_ts(raw["as_of"])
    rows = enrich(raw["tickets"], as_of)
    weeks = sorted({r["week"] for r in rows})
    current = week_label(as_of) if week_label(as_of) in weeks else weeks[-1]
    # The latest week is still in progress, so the headline uses the last full week.
    headline = weeks[weeks.index(current) - 1] if weeks.index(current) > 0 else current
    open_rows = [r for r in rows if not r.get("resolved_at")]
    return {
        "as_of": raw["as_of"],
        "target_rrs": TARGET_RRS,
        "sla_business_days": SLA_BUSINESS_DAYS,
        "regions": ["All"] + sorted({r["region"] for r in rows}),
        "weeks": weeks,
        "current_week": current,
        "headline_week": headline,
        "metrics": weekly_metrics(rows),
        "mix": dispute_mix(rows, headline),
        "open_tickets": sorted(open_rows, key=lambda r: r["sla_deadline"]),
    }
