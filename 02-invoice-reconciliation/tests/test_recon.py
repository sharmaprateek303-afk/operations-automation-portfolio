import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recon import Feeds, classify, duration_code, reconcile  # noqa: E402


def write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


class Parsing(unittest.TestCase):
    def test_duration_code(self):
        self.assertEqual(duration_code("Standard Parcel - Block of 8 Hours 15 Minutes"), "8H15M")
        self.assertEqual(duration_code("Large Van - Block of 9 Hours"), "9H")

    def test_classify(self):
        self.assertEqual(classify("Fuel Allowance"), "fuel")
        self.assertEqual(classify("Coverage Bonus - weekend"), "coverage")
        self.assertEqual(classify("Standard Parcel - Block of 9 Hours"), "capacity")


class Reconcile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        write(d / "capacity_log.csv", ["date", "station", "partner", "service_type", "planned_duration"],
              [["2026-10-18", "S1", "P1", "Standard Parcel", "8H"]] * 5)
        write(d / "conversions.csv", ["date", "station", "partner", "from_service", "to_service", "planned_duration"],
              [["2026-10-18", "S1", "P1", "Standard Parcel", "Ride Along", "8H"]])
        write(d / "late_cancellations.csv", ["date", "station", "partner", "count"], [["2026-10-19", "S1", "P1", 3]])
        write(d / "coverage_audit.csv", ["date", "station", "partner", "to_be_added", "added_to_system", "quality_check"],
              [["2026-10-18", "S1", "P1", 10, 10, "TRUE"], ["2026-10-18", "S1", "P1", 4, 0, "FALSE"]])
        write(d / "training_log.csv", ["date", "station", "partner", "associate_id"], [["2026-10-20", "S1", "P1", "A1"]])
        self.feeds = Feeds(d)

    def tearDown(self):
        self.tmp.cleanup()

    def invoice(self, lines):
        return [{"invoice_id": "INV-1", "country": "UK", "station": "S1", "partner": "P1",
                 "partner_name": "Demo", "week": "2026-W43", "lines": [{"reason": r, "qty": q} for r, q in lines]}]

    def test_all_match_with_conversion_and_fallback(self):
        res = reconcile(self.invoice([
            ("Standard Parcel - Block of 8 Hours", 4),   # 5 routes - 1 converted
            ("Ride Along - Block of 8 Hours", 1),        # the converted route
            ("Late Cancellation - weekday", 3),
            ("Coverage Bonus - weekend", 14),            # 10 added + 4 pending QC
            ("Training Day - Block of 8 Hours", 1),
            ("Fuel Allowance", 9999),
        ]), self.feeds)[0]
        self.assertEqual(res.status, "Y (fallback)")
        self.assertEqual(res.open_lines, [])

    def test_unexplained_line_goes_to_review(self):
        res = reconcile(self.invoice([("Late Cancellation - weekday", 3), ("Late Cancellation - weekend", 2)]), self.feeds)[0]
        self.assertEqual(res.status, "N")
        self.assertEqual(res.open_lines[0].found, 3)


if __name__ == "__main__":
    unittest.main()
