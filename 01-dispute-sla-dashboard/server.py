"""Zero-dependency backend for the dispute SLA dashboard.

    python server.py            # http://127.0.0.1:8080
    python server.py --port 9000

GET /api/data re-reads data/tickets.json on every request and recomputes all
KPIs, so a pipeline only has to overwrite that file to refresh the dashboard.
No restart, no code change.
"""
from __future__ import annotations

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import generate_sample_data
from metrics import build_payload

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "tickets.json"


def load_raw() -> dict:
    """The only function to change when swapping in a real data source."""
    if not DATA_FILE.exists():
        generate_sample_data.main()
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        if self.path.split("?")[0] == "/api/data":
            try:
                body = json.dumps(build_payload(load_raw())).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            except Exception as exc:  # keep the server up and report the problem
                body = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        pass  # quiet console


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    handler = partial(Handler, directory=str(ROOT / "static"))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Dashboard running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
