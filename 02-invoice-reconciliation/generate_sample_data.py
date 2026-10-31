"""Generate synthetic invoices and evidence feeds for the reconciliation demo.

All stations, partners and associates are made up. About a quarter of the
invoices get an injected discrepancy so the engine has something to catch.

    python generate_sample_data.py --invoices 60 --seed 3
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SERVICES = ["Standard Parcel", "Large Van", "Same Day", "Low Emission Van"]
DURATIONS = [(8, 0), (8, 15), (8, 45), (9, 0), (4, 0)]
COUNTRIES = ["UK", "DE", "FR", "IT", "ES"]
WEEK_START = date(2026, 10, 18)


def block(h: int, m: int) -> str:
    return f"Block of {h} Hours" + (f" {m} Minutes" if m else "")


def code(h: int, m: int) -> str:
    return f"{h}H{m}M" if m else f"{h}H"


def generate(n_invoices: int, seed: int, out_dir: Path) -> None:
    rng = random.Random(seed)
    feeds = {name: [] for name in ["capacity_log", "conversions", "late_cancellations", "coverage_audit", "training_log"]}
    invoices = []

    for i in range(n_invoices):
        country = rng.choice(COUNTRIES)
        station = f"{country}{rng.randint(1, 30):02d}"
        partner = f"P{100 + i}"  # unique per invoice so feeds never collide
        inv = {"invoice_id": f"INV-{country}-{10000 + i}", "country": country, "station": station,
               "partner": partner, "partner_name": f"Demo Logistics {partner}", "week": "2026-W43", "lines": []}
        days = [WEEK_START + timedelta(days=d) for d in range(7)]
        defect = rng.random() < 0.28
        defect_kind = rng.choice(["capacity", "late_cancel", "coverage_short", "training"]) if defect else None
        qc_fallback = rng.random() < 0.15  # coverage pending QC: the fallback rule should clear it

        # Capacity lines: one route per capacity-log row.
        for service in rng.sample(SERVICES, rng.randint(1, 3)):
            h, m = rng.choice(DURATIONS)
            for day in days:
                routes = rng.randint(3, 25)
                for _ in range(routes):
                    feeds["capacity_log"].append({"date": day.isoformat(), "station": station, "partner": partner,
                                                  "service_type": service, "planned_duration": code(h, m)})
                inv["lines"].append({"date": day.isoformat(), "reason": f"{service} - {block(h, m)}",
                                     "qty": routes, "rate": round(rng.uniform(150, 260), 2)})
        # Some routes were converted to a ride-along service: invoice shows them under the new type.
        if rng.random() < 0.3:
            h, m = DURATIONS[0]
            converted = rng.randint(1, 3)
            for _ in range(converted):
                feeds["capacity_log"].append({"date": days[2].isoformat(), "station": station, "partner": partner,
                                              "service_type": "Standard Parcel", "planned_duration": code(h, m)})
                feeds["conversions"].append({"date": days[2].isoformat(), "station": station, "partner": partner,
                                             "from_service": "Standard Parcel", "to_service": "Ride Along",
                                             "planned_duration": code(h, m)})
            inv["lines"].append({"date": days[2].isoformat(), "reason": f"Ride Along - {block(h, m)}",
                                 "qty": converted, "rate": 120.0})

        # Late cancellations.
        lc = rng.randint(0, 12)
        if lc:
            feeds["late_cancellations"].append({"date": days[1].isoformat(), "station": station, "partner": partner, "count": lc})
            inv["lines"].append({"date": days[1].isoformat(), "reason": "Late Cancellation - weekday", "qty": lc, "rate": 90.0})

        # Coverage bonus.
        cov = rng.randint(5, 40)
        pending = rng.randint(1, 8) if qc_fallback else 0
        feeds["coverage_audit"].append({"date": days[0].isoformat(), "station": station, "partner": partner,
                                        "to_be_added": cov, "added_to_system": cov, "quality_check": "TRUE"})
        if pending:
            feeds["coverage_audit"].append({"date": days[0].isoformat(), "station": station, "partner": partner,
                                            "to_be_added": pending, "added_to_system": 0, "quality_check": "FALSE"})
        inv["lines"].append({"date": days[0].isoformat(), "reason": "Coverage Bonus - weekend", "qty": cov + pending, "rate": 15.0})

        # Training days.
        trained = rng.randint(0, 6)
        for k in range(trained):
            feeds["training_log"].append({"date": days[3].isoformat(), "station": station, "partner": partner,
                                          "associate_id": f"A-{i:03d}-{k}"})
        if trained:
            inv["lines"].append({"date": days[3].isoformat(), "reason": "Training Day - Block of 8 Hours", "qty": trained, "rate": 140.0})

        # Fuel allowance: excluded from validation.
        inv["lines"].append({"date": days[6].isoformat(), "reason": "Fuel Allowance", "qty": rng.randint(5000, 40000), "rate": 0.01})

        # Inject one discrepancy (the partner billed more than the evidence shows).
        if defect_kind == "capacity":
            inv["lines"][0]["qty"] += rng.randint(1, 3)
        elif defect_kind == "late_cancel":
            inv["lines"].append({"date": days[4].isoformat(), "reason": "Late Cancellation - weekend", "qty": rng.randint(1, 4), "rate": 90.0})
        elif defect_kind == "coverage_short":
            next(l for l in inv["lines"] if l["reason"].startswith("Coverage"))["qty"] += rng.randint(2, 9)
        elif defect_kind == "training":
            inv["lines"].append({"date": days[5].isoformat(), "reason": "Training Day - Block of 8 Hours", "qty": 1, "rate": 140.0})

        for line in inv["lines"]:
            line["amount"] = round(line["qty"] * line["rate"], 2)
        invoices.append(inv)

    feed_dir = out_dir / "feeds"
    feed_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "capacity_log": ["date", "station", "partner", "service_type", "planned_duration"],
        "conversions": ["date", "station", "partner", "from_service", "to_service", "planned_duration"],
        "late_cancellations": ["date", "station", "partner", "count"],
        "coverage_audit": ["date", "station", "partner", "to_be_added", "added_to_system", "quality_check"],
        "training_log": ["date", "station", "partner", "associate_id"],
    }
    for name, rows in feeds.items():
        with (feed_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=headers[name])
            w.writeheader()
            w.writerows(rows)
    (out_dir / "invoices.json").write_text(json.dumps(invoices, indent=1), encoding="utf-8")
    print(f"Wrote {len(invoices)} invoices and {sum(len(v) for v in feeds.values())} feed rows to {out_dir}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--invoices", type=int, default=60)
    p.add_argument("--seed", type=int, default=3)
    a = p.parse_args()
    generate(a.invoices, a.seed, Path(__file__).parent / "data")


if __name__ == "__main__":
    main()
