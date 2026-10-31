"""Build the static demo site in docs/ (served by GitHub Pages).

    python build_site.py

Regenerates each project's synthetic data, runs the real project code, and
writes static pages:
  docs/index.html                  portfolio landing page
  docs/dashboard/                  live dispute SLA dashboard (static JSON)
  docs/reconciliation/             reconciliation results + sample workbooks
  docs/bridges/                    generated weekly business review document
"""
from __future__ import annotations

import html
import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
P1 = ROOT / "01-dispute-sla-dashboard"
P2 = ROOT / "02-invoice-reconciliation"
P3 = ROOT / "03-weekly-business-review-bridges"
REPO = "https://github.com/sharmaprateek303-afk/operations-automation-portfolio"
LINKEDIN = "https://www.linkedin.com/in/prateek-tiwari-377262135/"
EMAIL = "sharmaprateek303@gmail.com"
SHARED_MODULES = ("generate_sample_data", "run", "metrics", "recon", "report", "bridge", "narrative")


def run(script: str, cwd: Path) -> None:
    subprocess.run([sys.executable, script], cwd=cwd, check=True)


def use_project(path: Path):
    """Import a project's modules without clashing with same-named modules elsewhere."""
    for name in SHARED_MODULES:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(path))


def leave_project(path: Path) -> None:
    sys.path.remove(str(path))


def esc(value) -> str:
    return html.escape(str(value), quote=True)


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2433;--muted:#5b6475;--line:#e3e6ec;--accent:#2457c5;
--good:#1a7f37;--bad:#b42318;--blue:#1f5fa8}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
a{color:var(--accent)}a:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
header.top{background:var(--card);border-bottom:1px solid var(--line);padding:14px 24px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header.top .brand{font-weight:600;margin-right:auto;text-decoration:none;color:var(--ink)}
main{max-width:1180px;margin:0 auto;padding:28px 24px 48px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px}
.grid{display:grid;gap:14px}.g4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}.g3{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.stat .v{font-size:30px;font-weight:700;color:var(--accent)}.stat .l{color:var(--muted);font-size:13px}
.muted{color:var(--muted)}h1{font-size:30px;margin:0 0 6px}h2{font-size:20px;margin:28px 0 12px}h3{font-size:16px;margin:20px 0 8px}
.btn{display:inline-block;padding:8px 14px;border-radius:7px;border:1px solid var(--line);background:var(--card);color:var(--ink);text-decoration:none;font:inherit;cursor:pointer}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.tag{display:inline-block;font-size:12px;padding:2px 8px;border-radius:10px;background:#eef2fb;color:var(--blue);margin:0 4px 4px 0}
table{border-collapse:collapse;width:100%;background:var(--card)}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}td.num,th.num{text-align:right}
.pill{display:inline-block;padding:1px 9px;border-radius:10px;font-size:12px;font-weight:600}
.Y{background:#e6f4ea;color:var(--good)}.Yf{background:#e3eefb;color:var(--blue)}.N{background:#fde8e7;color:var(--bad)}.NA{background:#eee;color:var(--muted)}
details{background:var(--card);border:1px solid var(--line);border-radius:8px;margin-bottom:8px}
details summary{padding:10px 14px;cursor:pointer;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
details .body{padding:0 14px 14px;overflow-x:auto}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 14px}.filters button[aria-pressed=true]{background:var(--accent);color:#fff;border-color:var(--accent)}
.doc{max-width:900px}.doc table{margin:8px 0 18px}.doc p{margin:10px 0}.note{font-size:13px;color:var(--muted)}
footer{border-top:1px solid var(--line);padding:18px 24px;text-align:center;color:var(--muted);font-size:14px}
"""


def page(title: str, body: str, depth: int = 1) -> str:
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | Prateek Tiwari</title><link rel="stylesheet" href="{up}assets/site.css"></head>
<body><header class="top"><a class="brand" href="{up}">Prateek Tiwari · Operations Automation</a>
<a href="{up}dashboard/">Dashboard</a><a href="{up}reconciliation/">Reconciliation</a><a href="{up}bridges/">WBR bridges</a>
<a href="{REPO}">Code on GitHub</a></header>
<main>{body}</main>
<footer>All data is synthetic. · <a href="{LINKEDIN}">LinkedIn</a> · <a href="mailto:{EMAIL}">{EMAIL}</a></footer>
</body></html>"""


# ---------------------------------------------------------------- landing
def build_landing() -> None:
    projects = [
        ("dashboard/", "01-dispute-sla-dashboard", "Dispute SLA Dashboard",
         "Live KPI dashboard tracking partner-payment disputes against a 3-business-day SLA, with region tabs, "
         "trend vs target, dispute mix and an at-risk queue.", ["Python", "REST API", "JavaScript", "Chart.js"],
         "~5 hrs/week of manual reporting removed; breaches seen the same day"),
        ("reconciliation/", "02-invoice-reconciliation", "Invoice Reconciliation Engine",
         "Rule engine that validates every invoice line against five operational feeds and routes only the "
         "exceptions to reviewers, balanced by workload.", ["Python", "Rules engine", "openpyxl", "Excel automation"],
         "~80% of invoices cleared automatically; ~50 → ~12 hrs/week"),
        ("bridges/", "03-weekly-business-review-bridges", "Weekly Business Review Bridges",
         "Explains week-over-week metric moves by driver, finds the root cause of every SLA miss and writes the "
         "leadership narrative.", ["Python", "Root-cause analysis", "Automated reporting"],
         "Review prep cut from ~7 hours to ~30 minutes a week"),
    ]
    cards = "".join(f"""<article class="card"><h3 style="margin-top:0">{esc(t)}</h3><p>{esc(d)}</p>
<p>{''.join(f'<span class="tag">{esc(x)}</span>' for x in tags)}</p><p><strong>Impact:</strong> {esc(imp)}</p>
<p><a class="btn primary" href="{href}">Open live demo</a> <a class="btn" href="{REPO}/tree/main/{folder}">View code</a></p></article>"""
                    for href, folder, t, d, tags, imp in projects)
    stats = [("~2,400", "analyst hours saved per year"), ("~1.2", "full-time roles redeployed"),
             ("~80%", "invoices cleared without manual review"), ("30 min", "weekly review prep, down from ~7 hours")]
    stat_html = "".join(f'<div class="card stat"><div class="v">{v}</div><div class="l">{esc(l)}</div></div>' for v, l in stats)
    body = f"""<h1>Prateek Tiwari</h1>
<p class="muted" style="font-size:17px;max-width:760px">I turn manual, spreadsheet-heavy operations work into reliable automated
systems. These demos come from partner-payment operations in a large last-mile delivery network.</p>
<p><a class="btn primary" href="{LINKEDIN}">LinkedIn</a> <a class="btn" href="mailto:{EMAIL}">Email me</a>
<a class="btn" href="{REPO}">Source code</a></p>
<h2>Impact at a glance</h2><div class="grid g4">{stat_html}</div>
<h2>Projects</h2><div class="grid g3">{cards}</div>
<p class="note" style="margin-top:24px">These are clean re-implementations built for this portfolio. Every station, partner,
ticket and number in the demos is synthetic. Impact figures are rounded estimates of time saved in the original work.</p>"""
    (DOCS / "index.html").write_text(page("Portfolio", body, depth=0), encoding="utf-8")


# ---------------------------------------------------------------- 1. dashboard
def build_dashboard() -> None:
    run("generate_sample_data.py", P1)
    use_project(P1)
    metrics = importlib.import_module("metrics")
    raw = json.loads((P1 / "data" / "tickets.json").read_text(encoding="utf-8"))
    payload = metrics.build_payload(raw)
    leave_project(P1)

    out = DOCS / "dashboard"
    out.mkdir(parents=True, exist_ok=True)
    (out / "data.json").write_text(json.dumps(payload), encoding="utf-8")
    src = (P1 / "static" / "index.html").read_text(encoding="utf-8")
    src = src.replace('fetch("/api/data"', 'fetch("data.json"')
    src = re.sub(r"<header>\s*<h1>", '<header>\n  <a class="btn" href="../">&larr; Portfolio</a>\n  <h1>', src, count=1)
    src = src.replace("setInterval(load, 60000);", "")
    (out / "index.html").write_text(src, encoding="utf-8")


# ---------------------------------------------------------------- 2. reconciliation
def build_reconciliation() -> None:
    run("generate_sample_data.py", P2)
    use_project(P2)
    recon = importlib.import_module("recon")
    report = importlib.import_module("report")
    results = recon.reconcile(recon.load_invoices(P2 / "data" / "invoices.json"), recon.Feeds(P2 / "data" / "feeds"))
    out = DOCS / "reconciliation"
    dl = out / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    matched = [r for r in results if r.status.startswith("Y")]
    unmatched = [r for r in results if r.status == "N"]
    report.write_workbook(matched, dl / "Matched.xlsx")
    queues = report.split_for_reviewers(unmatched, ["Reviewer A", "Reviewer B"])
    for name, q in queues.items():
        report.write_workbook(q, dl / f"Unmatched - {name}.xlsx")
    leave_project(P2)

    lines = [l for r in results for l in r.lines if l.matched is not None]
    auto = sum(l.matched for l in lines)
    fallback = sum(r.status == "Y (fallback)" for r in results)
    stats = [(len(results), "invoices reconciled"), (f"{len(matched) / len(results):.0%}", "cleared automatically"),
             (f"{auto / len(lines):.0%}", f"of {len(lines)} lines matched to evidence"), (len(unmatched), "sent to reviewers")]
    stat_html = "".join(f'<div class="card stat"><div class="v">{v}</div><div class="l">{esc(l)}</div></div>' for v, l in stats)
    pill = {"Y": "Y", "Y (fallback)": "Yf", "N": "N"}

    rows = []
    for r in sorted(results, key=lambda x: (x.status != "N", x.invoice["country"], x.invoice["station"])):
        inv = r.invoice
        line_rows = "".join(
            f"<tr><td>{esc(l.reason)}</td><td class='num'>{l.invoiced}</td><td>{esc(l.evidence)}</td>"
            f"<td><span class='pill {'NA' if l.matched is None else 'Yf' if l.used_fallback else 'Y' if l.matched else 'N'}'>"
            f"{'Not validated' if l.matched is None else 'Matched (fallback)' if l.used_fallback else 'Matched' if l.matched else 'Review'}"
            f"</span></td></tr>" for l in r.lines)
        rows.append(f"""<details data-status="{esc(pill[r.status])}"><summary><span class="pill {pill[r.status]}">{esc(r.status)}</span>
<strong>{esc(inv['invoice_id'])}</strong><span class="muted">{esc(inv['country'])} · {esc(inv['station'])} · {esc(inv['partner_name'])}</span>
<span class="muted">{len(r.open_lines)} line(s) to review</span></summary><div class="body"><table>
<thead><tr><th scope="col">Invoice line</th><th scope="col" class="num">Invoiced</th><th scope="col">Evidence found</th><th scope="col">Result</th></tr></thead>
<tbody>{line_rows}</tbody></table></div></details>""")

    queue_txt = " · ".join(f"{esc(n)}: {len(q)} invoices, {sum(len(x.open_lines) for x in q)} lines" for n, q in queues.items())
    downloads = " ".join(f'<a class="btn" href="downloads/{esc(f)}" download>{esc(f)}</a>'
                         for f in ["Matched.xlsx", "Unmatched - Reviewer A.xlsx", "Unmatched - Reviewer B.xlsx"])
    body = f"""<h1>Invoice Reconciliation Engine</h1>
<p class="muted" style="max-width:780px">Every line on a partner's weekly invoice is matched against the operational feed that should
explain it: route capacity (netted for service-type conversions), late cancellations, coverage audit (with a quality-check
fallback) and training logs. Fully explained invoices clear automatically; the rest go to reviewers, split by workload.</p>
<div class="grid g4">{stat_html}</div>
<h2>Results by invoice</h2>
<p class="muted">{fallback} invoice(s) cleared only through the quality-check fallback rule. Review queues: {queue_txt}.</p>
<div class="filters" role="group" aria-label="Filter by status">
<button class="btn" type="button" data-f="all" aria-pressed="true">All</button>
<button class="btn" type="button" data-f="N" aria-pressed="false">Needs review</button>
<button class="btn" type="button" data-f="Y" aria-pressed="false">Matched</button>
<button class="btn" type="button" data-f="Yf" aria-pressed="false">Matched via fallback</button></div>
<div id="list">{''.join(rows)}</div>
<h2>Generated Excel workbooks</h2>
<p class="muted">The same run produces reviewer-ready workbooks: a Summary sheet, then one colour-coded sheet per invoice.</p>
<p>{downloads}</p>
<script>
document.querySelectorAll('[data-f]').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('[data-f]').forEach(x => x.setAttribute('aria-pressed', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('#list details').forEach(d => d.hidden = f !== 'all' && d.dataset.status !== f);
}}));
</script>"""
    (out / "index.html").write_text(page("Invoice Reconciliation", body), encoding="utf-8")


# ---------------------------------------------------------------- 3. bridges
def inline(text: str) -> str:
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"(?<![\w])_(.+?)_(?![\w])", r"<em>\1</em>", text)


def markdown_to_html(md: str) -> str:
    """Minimal converter for the subset the bridge document uses."""
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
            i += 1
        elif line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, align, rows = block[0], block[1], block[2:]
            right = [a.endswith(":") for a in align]
            th = "".join(f'<th scope="col"{" class=num" if right[k] else ""}>{inline(c)}</th>' for k, c in enumerate(head))
            body = "".join("<tr>" + "".join(f'<td{" class=num" if right[k] else ""}>{inline(c)}</td>' for k, c in enumerate(r)) + "</tr>"
                           for r in rows)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>")
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append(f"<ul>{''.join(items)}</ul>")
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "- ")):
                para.append(lines[i])
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def build_bridges() -> None:
    run("generate_sample_data.py", P3)
    run("run.py", P3)
    md = sorted((P3 / "output").glob("week_*_bridges.md"))[-1].read_text(encoding="utf-8")
    intro = f"""<p class="muted" style="max-width:780px">Generated end to end from raw synthetic tickets: each metric change is
split into drivers that add up exactly to the headline number, every SLA miss gets one root cause, repeat sites are flagged,
and data-quality issues are listed before anything reaches leadership. <a href="{REPO}/tree/main/03-weekly-business-review-bridges">How it works</a>.</p>"""
    body = f'<div class="doc">{intro}{markdown_to_html(md)}</div>'
    out = DOCS / "bridges"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page("Weekly Business Review Bridges", body), encoding="utf-8")


def main() -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "assets").mkdir(parents=True)
    (DOCS / "assets" / "site.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    build_landing()
    build_dashboard()
    build_reconciliation()
    build_bridges()
    print(f"Site built in {DOCS}")


if __name__ == "__main__":
    main()
