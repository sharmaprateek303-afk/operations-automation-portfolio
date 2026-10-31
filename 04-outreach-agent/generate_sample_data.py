"""Generate a synthetic outreach scenario: queue export, tickets with comments, chat history.

Every name, site, partner and ticket is made up. The scenario deliberately
includes the edge cases the guardrails exist for: duplicates, a failed lookup,
no tagged contact, a never-message person tagged, bots and team members
tagged, full / partial / unclear rejections, and contacts who already replied.

    python generate_sample_data.py
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

RUN_DAY = "2026-10-28"
YESTERDAY = "2026-10-27"
FIRST_NAMES = ["maya", "jon", "ines", "omar", "lea", "sam", "nina", "ali", "eva", "raj", "zoe", "ben", "ana", "leo"]
TEAM = ["ops-anna", "ops-ravi", "ops-meera", "ops-tom"]
ASKS = [
    "could you please confirm the routes for {d1} and {d2}? The partner has disputed {n} routes as late cancellations.",
    "please share the planned vs actual duration for {d1}; the partner says {n} blocks ran longer than planned.",
    "can you confirm whether the {n} training days on {d1} were approved by the site?",
    "the partner is asking for coverage bonus on {d1}. Could you confirm the {n} extra routes were requested by the site?",
]
SCENARIOS = (["outreach"] * 11 + ["never_tag", "never_tag", "team_and_bot", "rejected", "rejected", "partial",
             "unclear", "replied", "replied", "replied", "no_reply_yesterday", "no_reply_yesterday",
             "no_contact", "lookup_fail"])


def main() -> None:
    rng = random.Random(28)
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    rows, tickets, history = [], [], []
    for i, scenario in enumerate(SCENARIOS):
        tid = f"7f3a{i:04d}-demo-4c1e-9b2d-{rng.randint(10**11, 10**12 - 1)}"
        ref = f"P{rng.randint(100000000, 999999999)}"
        country = rng.choice(["UK", "DE", "FR", "IT", "ES"])
        station = f"{country}{rng.randint(1, 30):02d}"
        partner = f"Demo Logistics P{rng.randint(100, 999)}"
        contacts = [f"sl-{station.lower()}-{n}" for n in rng.sample(FIRST_NAMES, rng.choice([1, 1, 2]))]
        author = rng.choice(TEAM)
        d1, d2 = f"2026-10-{rng.randint(18, 22)}", f"2026-10-{rng.randint(23, 24)}"
        ask = rng.choice(ASKS).format(d1=d1, d2=d2, n=rng.randint(2, 9))
        tags = " ".join(f"@{c}" for c in contacts)
        comments = [{"author": "bot-intake", "date": "2026-10-24T09:00", "text": "Ticket created from partner dispute form."}]

        if scenario == "never_tag":
            tags += " @finance-lead"
        if scenario == "team_and_bot":
            tags += " @ops-ravi @label-sync"
        if scenario == "no_contact":
            comments.append({"author": author, "date": "2026-10-26T11:20", "text": "Checking the route plan for this week; will update."})
        else:
            comments.append({"author": author, "date": "2026-10-26T11:20", "text": f"Hi {tags}, {ask}"})
        if scenario == "rejected":
            comments.append({"author": author, "date": "2026-10-27T16:05",
                             "text": "Dispute rejected as per the route plan: no adjustment is due for any of the disputed dates."})
        if scenario == "partial":
            comments.append({"author": author, "date": "2026-10-27T16:05",
                             "text": f"Dispute rejected for {d1}. The remaining date {d2} is still open, {tags} please confirm."})
        if scenario == "unclear":
            comments.append({"author": author, "date": "2026-10-27T10:00", "text": "Request rejected, no supporting evidence."})
            comments.append({"author": "partner-portal", "date": "2026-10-27T18:30",
                             "text": "Partner asked to reopen with new evidence attached."})

        link = f"https://tickets.example.com/{ref}/communication"
        if scenario == "replied":
            history.append({"to": contacts, "text": f"Hi, hope you are having a great day! ... {link} ...",
                            "sent_at": f"{YESTERDAY}T14:02", "replies_from": [contacts[0]]})
        if scenario == "no_reply_yesterday":
            history.append({"to": contacts, "text": f"Hi, hope you are having a great day! ... {link} ...",
                            "sent_at": f"{YESTERDAY}T14:02", "replies_from": []})

        row = {"Severity": "SEV-1", "Ticket ID": tid, "Week": "Wk 43", "Status": "Open", "Category": "Station",
               "Site": station, "Partner": partner, "Invoice ID": f"INV-{country}-{20000 + i}", "Country": country,
               "Qty": 1, "Updated By": author, "Age (Days)": rng.randint(1, 3), "Created": "2026-10-24", "URL": link}
        rows.append(row)
        if scenario != "lookup_fail":
            tickets.append({"ticket_id": tid, "ref": ref, "station": station, "partner": partner,
                            "country": country, "comments": comments})

    rows += [dict(rows[3]), dict(rows[8])]  # two duplicate export rows
    for k in range(5):                       # other severities are filtered out
        rows.append({**rows[k], "Severity": "SEV-2", "Ticket ID": f"sev2-demo-{k}"})
    rng.shuffle(rows)

    with (out / "queue.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out / "tickets.json").write_text(json.dumps(tickets, indent=1), encoding="utf-8")
    (out / "chat_history.json").write_text(json.dumps(history, indent=1), encoding="utf-8")
    print(f"Wrote {len(rows)} queue rows, {len(tickets)} tickets, {len(history)} chat messages to {out}")


if __name__ == "__main__":
    main()
