"""Run the outreach agent on the synthetic scenario.

    python generate_sample_data.py
    python run.py                  # stops at the checkpoint and asks for approval
    python run.py --approve-all    # demo mode: approve every draft that passed its checks
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from agent import run_agent, send, write_log
from mock_clients import MockChatClient, MockTicketClient

ROOT = Path(__file__).parent
DATA = ROOT / "data"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--severity", default="SEV-1")
    p.add_argument("--run", default="first", choices=["first", "follow-up"])
    p.add_argument("--approve-all", action="store_true")
    a = p.parse_args()
    if not (DATA / "queue.csv").exists():
        import generate_sample_data
        generate_sample_data.main()

    chat = MockChatClient(DATA / "chat_history.json")
    result = run_agent(DATA / "queue.csv", a.severity, a.run, MockTicketClient(DATA / "tickets.json"), chat,
                       window_start=datetime(2026, 10, 27), run_start=datetime(2026, 10, 28, 14))

    print(f"\n{a.severity} {a.run} run: {result.total} tickets ({result.duplicates_removed} duplicates removed)")
    print("CHECKPOINT: buckets")
    for bucket, n in result.bucket_counts().items():
        print(f"  {bucket:<18} {n}")
    for w in result.work:
        for f in w.flags:
            print(f"  ! {w.ticket_id[:13]}… {w.station}: {f}")

    print(f"\nDRAFTS ({len(result.drafts)})")
    for d in result.drafts:
        mark = "OK " if d.ok else "BLOCKED"
        print(f"  [{mark}] {d.work.station:<5} to {', '.join(d.recipients)}"
              + (f"  (excluded: {', '.join(d.work.excluded_tags)})" if d.work.excluded_tags else ""))

    def approve(drafts):
        if a.approve_all:
            return True
        return input("\nGood to send? Type 'approve all' to send: ").strip().lower() == "approve all"

    result.sent = send(result.drafts, chat, approve)
    log = write_log(result, ROOT / "output" / f"{datetime.now():%Y-%m-%d}_outreach.md", datetime.now())
    print(f"\nSent {sum(s['status'] == 'sent' for s in result.sent)} messages. Log: {log}")


if __name__ == "__main__":
    main()
