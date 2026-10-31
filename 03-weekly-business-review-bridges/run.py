"""Build the weekly bridge document.

    python generate_sample_data.py
    python run.py                 # latest week in the data
    python run.py --week 42
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from bridge import anomalies, dispute_rate_bridge, invalid_rate_bridge, load_base, load_tickets, sla_bridge
from narrative import build_document

ROOT = Path(__file__).parent
TARGET_SLA = 0.95


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--week", type=int)
    a = p.parse_args()
    data = ROOT / "data"
    if not (data / "tickets.csv").exists():
        import generate_sample_data
        generate_sample_data.main()

    tickets = load_tickets(data / "tickets.csv")
    base = load_base(data / "base.csv")
    as_of = datetime.fromisoformat((data / "as_of.txt").read_text().strip())
    week = a.week or max(t["week"] for t in tickets)

    sections = []
    for line in sorted({t["business_line"] for t in tickets}):
        sections.append((dispute_rate_bridge(tickets, base, line, week),
                         invalid_rate_bridge(tickets, line, week),
                         sla_bridge(tickets, line, week, as_of)))

    doc = build_document(week, sections, anomalies(tickets, base, week), TARGET_SLA)
    out = ROOT / "output" / f"week_{week}_bridges.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"Wrote {out}")
    for rate, invalid, sla in sections:
        print(f"  {rate.line}: dispute rate {rate.change_bps:+d} bps, invalid {invalid.change_bps:+d} bps, "
              f"SLA {sla.rate:.1%} ({sla.missed} missed)")


if __name__ == "__main__":
    main()
