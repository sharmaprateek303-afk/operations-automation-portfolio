"""Rule engine: validate every invoice line against operational feeds.

Each invoice line is classified, then matched against the feed that should
explain it:

| Line type            | Evidence feed                | Rule                                             |
|----------------------|------------------------------|--------------------------------------------------|
| Capacity (routes)    | capacity_log.csv             | row count per station/partner/service/duration,  |
|                      | conversions.csv              | netted for routes converted between service types|
| Late cancellation    | late_cancellations.csv       | sum of cancellation counts for station/partner   |
| Coverage bonus       | coverage_audit.csv           | sum of coverage added; fallback adds coverage    |
|                      |                              | still pending a quality check                    |
| Training day         | training_log.csv             | one row per trained associate                    |
| Fuel allowance       | none                         | excluded (pass-through cost, not validated)      |

A line matches when the evidence quantity equals the invoiced quantity.
An invoice is:
  - "Y"            every checkable line matches on primary evidence
  - "Y (fallback)" every line matches, at least one needed the fallback rule
  - "N"            at least one line is unexplained (goes to manual review)
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

DURATION_RE = re.compile(r"Block of (\d+) Hours?(?: (\d+) Minutes?)?", re.I)


def duration_code(text: str) -> str:
    """'Block of 8 Hours 15 Minutes' -> '8H15M'; 'Block of 9 Hours' -> '9H'."""
    m = DURATION_RE.search(text)
    if not m:
        return ""
    hours, minutes = int(m.group(1)), int(m.group(2) or 0)
    return f"{hours}H{minutes}M" if minutes else f"{hours}H"


def classify(reason: str) -> str:
    r = reason.lower()
    if r.startswith("fuel"):
        return "fuel"
    if r.startswith("late cancellation"):
        return "late_cancel"
    if r.startswith("coverage bonus"):
        return "coverage"
    if r.startswith("training day"):
        return "training"
    return "capacity"


def service_name(reason: str) -> str:
    return reason.split(" - Block of")[0].strip()


@dataclass
class LineResult:
    reason: str
    kind: str
    invoiced: int
    found: int | None
    matched: bool | None          # None = not validated (fuel)
    evidence: str
    used_fallback: bool = False


@dataclass
class InvoiceResult:
    invoice: dict
    lines: list[LineResult] = field(default_factory=list)

    @property
    def status(self) -> str:
        checkable = [l for l in self.lines if l.matched is not None]
        if not checkable:
            return "N/A"
        if not all(l.matched for l in checkable):
            return "N"
        return "Y (fallback)" if any(l.used_fallback for l in checkable) else "Y"

    @property
    def open_lines(self) -> list[LineResult]:
        return [l for l in self.lines if l.matched is False]


class Feeds:
    """Loads the evidence feeds once and indexes them for fast lookups."""

    def __init__(self, feed_dir: Path):
        self.capacity = Counter()
        for r in _read_csv(feed_dir / "capacity_log.csv"):
            self.capacity[(r["station"], r["partner"], r["service_type"], r["planned_duration"])] += 1

        self.conversions_out = Counter()
        self.conversions_in = Counter()
        for r in _read_csv(feed_dir / "conversions.csv"):
            key = (r["station"], r["partner"])
            self.conversions_out[key + (r["from_service"], r["planned_duration"])] += 1
            self.conversions_in[key + (r["to_service"], r["planned_duration"])] += 1

        self.late_cancel = Counter()
        for r in _read_csv(feed_dir / "late_cancellations.csv"):
            self.late_cancel[(r["station"], r["partner"])] += int(r["count"])

        self.coverage_added = Counter()
        self.coverage_pending_qc = Counter()
        for r in _read_csv(feed_dir / "coverage_audit.csv"):
            key = (r["station"], r["partner"])
            added, to_add = int(r["added_to_system"]), int(r["to_be_added"])
            self.coverage_added[key] += added
            if r["quality_check"].strip().upper() == "FALSE":
                self.coverage_pending_qc[key] += max(0, to_add - added)

        self.training = Counter()
        for r in _read_csv(feed_dir / "training_log.csv"):
            self.training[(r["station"], r["partner"])] += 1


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def validate_line(inv: dict, reason: str, qty: int, feeds: Feeds) -> LineResult:
    key = (inv["station"], inv["partner"])
    kind = classify(reason)

    if kind == "fuel":
        return LineResult(reason, kind, qty, None, None, "Not validated (pass-through)")

    if kind == "late_cancel":
        found = feeds.late_cancel[key]
        return LineResult(reason, kind, qty, found, found == qty, f"{found} in late-cancellation log")

    if kind == "training":
        found = feeds.training[key]
        return LineResult(reason, kind, qty, found, found == qty, f"{found} in training log")

    if kind == "coverage":
        primary = feeds.coverage_added[key]
        if primary == qty:
            return LineResult(reason, kind, qty, primary, True, f"{primary} coverage added")
        pending = feeds.coverage_pending_qc[key]
        if pending and primary + pending == qty:
            return LineResult(reason, kind, qty, qty, True,
                              f"{primary} added + {pending} pending quality check", used_fallback=True)
        return LineResult(reason, kind, qty, primary, False,
                          f"{primary} added, {pending} pending QC, short by {qty - primary - pending}")

    # Capacity line: count routes, then net routes converted to/from this service type.
    service, dur = service_name(reason), duration_code(reason)
    ckey = key + (service, dur)
    base = feeds.capacity[ckey]
    net = base - feeds.conversions_out[ckey] + feeds.conversions_in[ckey]
    note = f"{base} routes in capacity log"
    if net != base:
        note += f", net {net} after conversions"
    if net != qty:
        note += f" (gap {qty - net:+d})"
    return LineResult(reason, kind, qty, net, net == qty, note)


def reconcile(invoices: list[dict], feeds: Feeds) -> list[InvoiceResult]:
    results = []
    for inv in invoices:
        res = InvoiceResult(inv)
        # Aggregate repeated reasons (an invoice lists one line per day).
        totals: dict[str, int] = defaultdict(int)
        for line in inv["lines"]:
            reason = line["reason"]
            if classify(reason) == "late_cancel":
                reason = "Late Cancellation (all)"
            totals[reason] += line["qty"]
        for reason, qty in sorted(totals.items()):
            res.lines.append(validate_line(inv, reason, qty, feeds))
        results.append(res)
    return results


def load_invoices(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))
