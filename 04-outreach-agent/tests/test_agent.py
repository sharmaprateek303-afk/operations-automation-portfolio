import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rules  # noqa: E402
from agent import TicketWork, assign_bucket, check_schedule, make_draft, read_comments, send  # noqa: E402


def ticket(*comments):
    return {"comments": [{"author": a, "date": d, "text": t} for a, d, t in comments]}


class Contacts(unittest.TestCase):
    def test_latest_tags_minus_team_bots_and_never_list(self):
        w = TicketWork("t1", {}, ref="P1")
        read_comments(w, ticket(
            ("ops-anna", "2026-10-25T10:00", "@old-contact please check"),
            ("ops-ravi", "2026-10-26T10:00", "@sl-uk01-maya @ops-tom @label-sync @finance-lead please confirm"),
        ), "SEV-1")
        self.assertEqual(w.contacts, ["sl-uk01-maya"])
        self.assertEqual(w.excluded_tags, ["finance-lead"])
        self.assertEqual(w.team_copy, "ops-ravi")

    def test_rejection_levels(self):
        cases = {"Dispute rejected as per plan.": "all",
                 "Dispute rejected for Monday; the remaining date is open.": "partial",
                 "Request rejected. Partner asked to reopen.": "unclear"}
        for text, expected in cases.items():
            w = TicketWork("t", {}, ref="P1")
            read_comments(w, ticket(("ops-anna", "2026-10-26T10:00", f"@sl-a {text}")), "SEV-2")
            self.assertEqual(w.rejection, expected, text)


class Buckets(unittest.TestCase):
    def test_priority_order_and_reply_detection(self):
        no_contact = TicketWork("a", {}, ref="P1")
        assign_bucket(no_contact, [])
        self.assertEqual(no_contact.bucket, "Could not process")

        replied = TicketWork("b", {}, ref="P2", contacts=["sl-x"])
        history = [{"to": ["sl-x"], "text": "… https://tickets.example.com/P2/communication …", "replies_from": ["sl-x"]}]
        assign_bucket(replied, history)
        self.assertEqual(replied.bucket, "Already covered")

        team_reply_only = TicketWork("c", {}, ref="P3", contacts=["sl-y"])
        assign_bucket(team_reply_only, [{"to": ["sl-y"], "text": "https://tickets.example.com/P3/communication ",
                                         "replies_from": ["ops-anna"]}])
        self.assertEqual(team_reply_only.bucket, "Needs outreach")  # only a contact's reply counts


class Guardrails(unittest.TestCase):
    def test_unscheduled_run_refused(self):
        with self.assertRaises(ValueError):
            check_schedule("SEV-2", "follow-up")

    def test_draft_uses_locked_template_and_passes_checks(self):
        w = TicketWork("d", {}, ref="P9", contacts=["sl-z"], glimpse="ops-anna: …")
        d = make_draft(w, "first", set())
        self.assertEqual(d.text, rules.TEMPLATES["first"].format(link="https://tickets.example.com/P9/communication"))
        self.assertTrue(d.ok, d.checks)

    def test_nothing_sent_without_approval_and_never_list_blocked(self):
        w = TicketWork("e", {}, ref="P8", contacts=["sl-q"], glimpse="x")
        good = make_draft(w, "first", set())
        bad = make_draft(TicketWork("f", {}, ref="P7", contacts=["finance-lead"], glimpse="x"), "first", set())

        class Chat:
            sent = []
            def send_group_dm(self, users, text):
                self.sent.append(users)

        chat = Chat()
        self.assertEqual(send([good], chat, lambda d: False), [])
        results = send([good, bad], chat, lambda d: True)
        self.assertEqual([r["status"] for r in results], ["sent", "blocked"])
        self.assertEqual(chat.sent, [["sl-q"]])


if __name__ == "__main__":
    unittest.main()
