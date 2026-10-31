"""Run the reconciliation end to end.

    python generate_sample_data.py
    python run.py --reviewers "Reviewer A,Reviewer B"

Writes to output/:
  Matched.xlsx                 invoices fully explained by the feeds
  Unmatched - <reviewer>.xlsx  the rest, split evenly by review workload
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from recon import Feeds, load_invoices, reconcile
from report import split_for_reviewers, write_workbook

ROOT = Path(__file__).parent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=ROOT / "data")
    p.add_argument("--out", type=Path, default=ROOT / "output")
    p.add_argument("--reviewers", default="Reviewer A,Reviewer B")
    a = p.parse_args()

    if not (a.data / "invoices.json").exists():
        import generate_sample_data
        generate_sample_data.main()

    results = reconcile(load_invoices(a.data / "invoices.json"), Feeds(a.data / "feeds"))
    matched = [r for r in results if r.status.startswith("Y")]
    unmatched = [r for r in results if r.status == "N"]

    write_workbook(matched, a.out / "Matched.xlsx")
    reviewers = [n.strip() for n in a.reviewers.split(",") if n.strip()]
    for name, queue in split_for_reviewers(unmatched, reviewers).items():
        write_workbook(queue, a.out / f"Unmatched - {name}.xlsx")
        print(f"  {name}: {len(queue)} invoices, {sum(len(r.open_lines) for r in queue)} lines to review")

    status = Counter(r.status for r in results)
    lines = [l for r in results for l in r.lines if l.matched is not None]
    print(f"Invoices: {len(results)} | " + " | ".join(f"{k}: {v}" for k, v in sorted(status.items())))
    print(f"Lines validated automatically: {sum(l.matched for l in lines)}/{len(lines)} "
          f"({sum(l.matched for l in lines) / len(lines):.0%})")
    print(f"Output written to {a.out}")


if __name__ == "__main__":
    main()
