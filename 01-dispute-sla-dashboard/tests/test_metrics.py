import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metrics import add_business_days, build_payload, sla_status  # noqa: E402


def ticket(created, resolved=None, kind="initial", region="North"):
    return {"ticket_id": "T-1", "region": region, "station": "N01", "partner": "Partner N01-A",
            "dispute_type": "Rate mismatch", "kind": kind, "created_at": created, "resolved_at": resolved}


class BusinessDays(unittest.TestCase):
    def test_skips_weekend(self):
        # Thursday + 3 business days = Tuesday
        self.assertEqual(add_business_days(datetime(2026, 10, 1, 9), 3), datetime(2026, 10, 6, 9))

    def test_from_saturday(self):
        self.assertEqual(add_business_days(datetime(2026, 10, 3, 9), 3), datetime(2026, 10, 7, 9))


class SlaStatus(unittest.TestCase):
    as_of = datetime(2026, 10, 9, 12)

    def test_met_and_missed(self):
        self.assertEqual(sla_status(ticket("2026-10-01T09:00", "2026-10-06T08:00"), self.as_of), "met")
        self.assertEqual(sla_status(ticket("2026-10-01T09:00", "2026-10-06T10:00"), self.as_of), "missed")

    def test_open_states(self):
        self.assertEqual(sla_status(ticket("2026-10-01T09:00"), self.as_of), "missed")
        self.assertEqual(sla_status(ticket("2026-10-07T10:00"), self.as_of), "on_track")
        self.assertEqual(sla_status(ticket("2026-10-06T14:00"), self.as_of), "at_risk")


class Payload(unittest.TestCase):
    def test_rate_excludes_open_in_sla(self):
        raw = {"as_of": "2026-10-09T12:00", "tickets": [
            ticket("2026-10-05T09:00", "2026-10-06T09:00"),
            ticket("2026-10-05T09:00", "2026-10-09T10:00"),
            ticket("2026-10-08T09:00"),
            ticket("2026-10-05T10:00", "2026-10-06T10:00", kind="re-dispute"),
        ]}
        week = next(m for m in build_payload(raw)["metrics"] if m["region"] == "All")
        self.assertEqual((week["met"], week["missed"], week["open_in_sla"]), (1, 1, 1))
        self.assertEqual(week["resolution_rate_in_sla"], 0.5)
        self.assertEqual(week["re_dispute_rate"], round(1 / 3, 4))


if __name__ == "__main__":
    unittest.main()
