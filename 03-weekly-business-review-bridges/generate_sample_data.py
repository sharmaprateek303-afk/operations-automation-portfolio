"""Generate synthetic dispute tickets for the bridge demo.

Two business lines over six weeks. The latest week has two planted stories for
the bridge to find: a late-cancellation spike at two sites in Line A, and SLA
misses at one Line B site that kept tickets waiting on its input.

    python generate_sample_data.py
"""
from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from bridge import add_business_days

WEEKS = range(38, 44)
LINES = {"Line A": {"base": 900, "rate": 0.11, "countries": ["UK", "DE", "FR"]},
         "Line B": {"base": 420, "rate": 0.09, "countries": ["IT", "ES"]}}
USE_CASES = [("Late cancellation", .30), ("Missing route", .18), ("Rate mismatch", .16),
             ("Duration mismatch", .14), ("Training day", .12), ("Coverage bonus", .10)]
REJECTIONS = [("Not supported by route plan", .32), ("Site confirmed no adjustment due", .26),
              ("Already paid", .18), ("Submitted outside dispute window", .14), ("", .10)]
WEEK1_MONDAY = datetime(2026, 9, 14)  # Monday of week 38


def weighted(rng, items):
    r, acc = rng.random(), 0.0
    for name, w in items:
        acc += w
        if r <= acc:
            return name
    return items[-1][0]


def main() -> None:
    rng = random.Random(11)
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    as_of = WEEK1_MONDAY + timedelta(weeks=len(WEEKS), days=4)
    tickets, base_rows, seq = [], [], 5000

    for week in WEEKS:
        start = WEEK1_MONDAY + timedelta(weeks=week - WEEKS.start)
        for line, cfg in LINES.items():
            base = int(rng.gauss(cfg["base"], cfg["base"] * 0.02))
            base_rows.append({"week": week, "business_line": line, "eligible_combinations": base})
            n = int(base * rng.gauss(cfg["rate"], 0.006))
            stations = [f"{c}{i:02d}" for c in cfg["countries"] for i in range(1, 9)]
            spike = week == WEEKS[-1] and line == "Line A"
            slow = week == WEEKS[-1] and line == "Line B"
            if spike:
                n += 22
            if slow:
                n += 6
            for i in range(n):
                seq += 1
                station = rng.choice(stations)
                use_case = weighted(rng, USE_CASES)
                if spike and i >= n - 22:  # the planted late-cancellation spike
                    station, use_case = rng.choice(["UK03", "DE05"]), "Late cancellation"
                if slow and i >= n - 6:    # the planted slow-to-respond site
                    station = "IT04"
                created = start + timedelta(minutes=rng.randint(0, 5 * 24 * 60))
                deadline = add_business_days(created, 3)
                waiting_on = "ops"
                slow_site = week == WEEKS[-1] and line == "Line B" and station == "IT04"
                if slow_site or rng.random() < 0.05:
                    waiting_on = "site"
                    resolved = deadline + timedelta(hours=rng.uniform(3, 40))
                else:
                    resolved = created + timedelta(hours=rng.uniform(4, 64))
                first = created + timedelta(hours=rng.uniform(1, 30))
                if rng.random() < 0.02:
                    first = deadline + timedelta(hours=2)
                    resolved = max(resolved, first + timedelta(hours=4))
                if resolved > as_of:
                    resolved = None
                invalid = resolved is not None and rng.random() < 0.34
                tickets.append({
                    "ticket_id": f"D-{seq}", "week": week, "business_line": line,
                    "country": station[:2], "station": station, "partner": f"Partner {station}-{rng.choice('XYZ')}",
                    "use_case": use_case, "quantity": 2 if rng.random() < 0.07 else 1,
                    "classification": "invalid" if invalid else ("valid" if resolved else "open"),
                    "rejection_reason": weighted(rng, REJECTIONS) if invalid else "",
                    "created_at": created.isoformat(timespec="minutes"),
                    "first_response_at": first.isoformat(timespec="minutes"),
                    "resolved_at": resolved.isoformat(timespec="minutes") if resolved else "",
                    "waiting_on": waiting_on, "reopened": "1" if rng.random() < 0.015 else "0",
                })

    with (out / "tickets.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tickets[0]))
        w.writeheader()
        w.writerows(tickets)
    with (out / "base.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["week", "business_line", "eligible_combinations"])
        w.writeheader()
        w.writerows(base_rows)
    (out / "as_of.txt").write_text(as_of.isoformat(timespec="minutes"), encoding="utf-8")
    print(f"Wrote {len(tickets)} synthetic tickets for weeks {WEEKS.start}-{WEEKS[-1]} to {out}")


if __name__ == "__main__":
    main()
