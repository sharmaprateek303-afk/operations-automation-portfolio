"""Generate a synthetic ticket dataset for the dashboard demo.

Every station, partner, ticket ID and person here is made up. Volumes and the
SLA mix are tuned to look realistic, not to match any real operation.

    python generate_sample_data.py            # 12 weeks ending today
    python generate_sample_data.py --weeks 8 --seed 7
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from metrics import add_business_days

REGIONS = {
    "North": {"stations": 12, "weekly": 60},
    "South": {"stations": 9, "weekly": 45},
    "East": {"stations": 6, "weekly": 25},
    "West": {"stations": 5, "weekly": 20},
}
DISPUTE_TYPES = [
    ("Late cancellation", 0.28),
    ("Rate mismatch", 0.18),
    ("Missing route", 0.16),
    ("Duration mismatch", 0.14),
    ("Training day", 0.12),
    ("Coverage bonus", 0.12),
]
RESOLVERS = ["ops-analyst-1", "ops-analyst-2", "ops-analyst-3", "site-lead"]


def pick_type(rng: random.Random) -> str:
    r, acc = rng.random(), 0.0
    for name, weight in DISPUTE_TYPES:
        acc += weight
        if r <= acc:
            return name
    return DISPUTE_TYPES[-1][0]


def resolution_time(rng: random.Random, created: datetime, region: str) -> datetime:
    """Most tickets close well inside SLA; a tail runs late (waiting on site input)."""
    late_share = {"North": 0.05, "South": 0.08, "East": 0.12, "West": 0.06}[region]
    if rng.random() < late_share:
        return add_business_days(created, 3) + timedelta(hours=rng.randint(2, 60))
    return created + timedelta(hours=rng.uniform(2, 60))


def generate(weeks: int, seed: int, as_of: datetime) -> dict:
    rng = random.Random(seed)
    tickets = []
    seq = 1000
    start = as_of - timedelta(weeks=weeks)
    for region, cfg in REGIONS.items():
        stations = [f"{region[0]}{i:02d}" for i in range(1, cfg["stations"] + 1)]
        for w in range(weeks + 1):
            week_start = start + timedelta(weeks=w)
            volume = max(5, int(rng.gauss(cfg["weekly"], cfg["weekly"] * 0.12)))
            for _ in range(volume):
                created = week_start + timedelta(minutes=rng.randint(0, 7 * 24 * 60 - 1))
                if created > as_of:
                    continue
                resolved = resolution_time(rng, created, region)
                seq += 1
                station = rng.choice(stations)
                ticket = {
                    "ticket_id": f"T-{seq:06d}",
                    "region": region,
                    "station": station,
                    "partner": f"Partner {station}-{rng.choice('ABC')}",
                    "dispute_type": pick_type(rng),
                    "kind": "re-dispute" if rng.random() < 0.09 else "initial",
                    "created_at": created.isoformat(timespec="minutes"),
                    "resolved_at": resolved.isoformat(timespec="minutes") if resolved <= as_of else None,
                    "last_updated_by": rng.choice(RESOLVERS),
                }
                tickets.append(ticket)
    return {"as_of": as_of.isoformat(timespec="minutes"), "tickets": tickets}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weeks", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    as_of = datetime.now().replace(second=0, microsecond=0)
    data = generate(args.weeks, args.seed, as_of)
    out = Path(__file__).parent / "data" / "tickets.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"Wrote {len(data['tickets'])} synthetic tickets to {out}")


if __name__ == "__main__":
    main()
