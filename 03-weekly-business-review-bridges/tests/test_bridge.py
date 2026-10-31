import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge import dispute_rate_bridge, miss_cause, sla_bridge  # noqa: E402


def t(week, use_case="Late cancellation", created="2026-10-19T09:00", resolved="2026-10-20T09:00",
      first="2026-10-19T12:00", waiting="ops", reopened=False):
    return {"ticket_id": f"D-{week}-{use_case}", "week": week, "business_line": "Line A", "station": "UK01",
            "partner": "Partner UK01-X", "use_case": use_case, "quantity": 1, "classification": "valid",
            "rejection_reason": "", "waiting_on": waiting, "reopened": reopened,
            "created_at": datetime.fromisoformat(created),
            "first_response_at": datetime.fromisoformat(first) if first else None,
            "resolved_at": datetime.fromisoformat(resolved) if resolved else None}


class Decomposition(unittest.TestCase):
    def test_contributions_reconcile_to_total(self):
        tickets = [t(42), t(42, "Rate mismatch"), t(43), t(43), t(43), t(43, "Missing route")]
        base = {(42, "Line A"): 100, (43, "Line A"): 100}
        b = dispute_rate_bridge(tickets, base, "Line A", 43)
        self.assertEqual(b.change_bps, 200)  # 2% -> 4%
        self.assertEqual(sum(d.contribution_bps for d in b.drivers), b.change_bps)
        self.assertEqual(b.drivers[0].name, "Late cancellation")


class RootCause(unittest.TestCase):
    deadline = datetime(2026, 10, 22, 9)

    def test_order_of_causes(self):
        self.assertEqual(miss_cause(t(43, first=None), self.deadline), "Late first response")
        self.assertEqual(miss_cause(t(43, reopened=True), self.deadline), "Reopened after resolution")
        self.assertEqual(miss_cause(t(43, waiting="site"), self.deadline), "Waiting on site input")
        self.assertEqual(miss_cause(t(43), self.deadline), "Resolved after deadline")

    def test_sla_counts(self):
        tickets = [t(43), t(43, resolved="2026-10-23T09:00", waiting="site"), t(43, resolved=None)]
        s = sla_bridge(tickets, "Line A", 43, as_of=datetime(2026, 10, 21, 9))
        self.assertEqual((s.met, s.missed, s.open_in_sla), (1, 1, 1))
        self.assertEqual(s.misses[0].cause, "Waiting on site input")


if __name__ == "__main__":
    unittest.main()
