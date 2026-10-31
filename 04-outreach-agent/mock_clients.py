"""In-memory stand-ins for the ticketing system and the chat platform.

The agent only talks to these two interfaces, so swapping in real clients
(ticketing API, chat API) does not change the agent logic.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class MockTicketClient:
    def __init__(self, path: Path, fail_ids: set[str] | None = None):
        self.tickets = {t["ticket_id"]: t for t in json.loads(path.read_text(encoding="utf-8"))}
        self.fail_ids = fail_ids or set()
        self.calls: dict[str, int] = {}

    def get_ticket(self, ticket_id: str) -> dict:
        self.calls[ticket_id] = self.calls.get(ticket_id, 0) + 1
        if ticket_id in self.fail_ids or ticket_id not in self.tickets:
            raise TimeoutError("ticket service did not respond")
        return self.tickets[ticket_id]


class MockChatClient:
    def __init__(self, path: Path):
        self.history = json.loads(path.read_text(encoding="utf-8"))
        self.outbox: list[dict] = []

    def history_since(self, since: datetime) -> list[dict]:
        return [m for m in self.history if datetime.fromisoformat(m["sent_at"]) >= since]

    def send_group_dm(self, users: list[str], text: str) -> dict:
        msg = {"to": list(users), "text": text, "sent_at": datetime.now().isoformat(timespec="minutes")}
        self.outbox.append(msg)
        return msg
