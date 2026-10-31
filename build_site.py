"""Build the static demo site in docs/ (served by GitHub Pages).

    python build_site.py

Regenerates each project's synthetic data, runs the real project code, and
writes interactive pages that replay what the automation does:
  docs/index.html            portfolio landing page
  docs/dashboard/            live dispute SLA dashboard
  docs/reconciliation/       reconciliation engine run, results and workbooks
  docs/bridges/              weekly business review bridge generation
  docs/outreach/             human-in-the-loop outreach agent run
"""
from __future__ import annotations

import html
import importlib
import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
P1 = ROOT / "01-dispute-sla-dashboard"
P2 = ROOT / "02-invoice-reconciliation"
P3 = ROOT / "03-weekly-business-review-bridges"
P4 = ROOT / "04-outreach-agent"
REPO = "https://github.com/sharmaprateek303-afk/operations-automation-portfolio"
LINKEDIN = "https://www.linkedin.com/in/prateek-tiwari-377262135/"
EMAIL = "sharmaprateek303@gmail.com"
CHART_JS = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>'
SHARED_MODULES = ("generate_sample_data", "run", "metrics", "recon", "report", "bridge", "narrative",
                  "rules", "agent", "mock_clients")


def run(script: str, cwd: Path, *args: str) -> None:
    subprocess.run([sys.executable, script, *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL)


def use_project(path: Path) -> None:
    for name in SHARED_MODULES:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(path))


def leave_project(path: Path) -> None:
    sys.path.remove(str(path))


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def js_data(obj) -> str:
    """JSON that is safe to embed inside a <script> tag."""
    return json.dumps(obj).replace("</", "<\\/")


CSS = r"""
:root{--bg:#f4f6fb;--card:#fff;--ink:#141b2d;--muted:#5b6475;--line:#e3e6ec;--accent:#2457c5;--accent2:#7c3aed;
--good:#1a7f37;--bad:#b42318;--blue:#1f5fa8;--warn:#9a6700}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
a{color:var(--accent)}a:focus-visible,button:focus-visible,summary:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
header.top{background:var(--card);border-bottom:1px solid var(--line);padding:12px 24px;display:flex;gap:18px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:5}
header.top .brand{font-weight:700;margin-right:auto;text-decoration:none;color:var(--ink)}
header.top a{text-decoration:none}
main{max-width:1180px;margin:0 auto;padding:26px 24px 56px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.grid{display:grid;gap:14px}.g2{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}.g3{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.stat .v{font-size:30px;font-weight:800;color:var(--accent);font-variant-numeric:tabular-nums}.stat .l{color:var(--muted);font-size:13px}
.muted{color:var(--muted)}h1{font-size:34px;line-height:1.15;margin:0 0 10px}h2{font-size:21px;margin:34px 0 12px}h3{font-size:16px;margin:18px 0 8px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);text-decoration:none;font:inherit;font-weight:600;cursor:pointer}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}.btn.light{background:#fff;color:#0f2a5c;border-color:#fff}
.btn.ghost{background:transparent;color:#fff;border-color:rgba(255,255,255,.5)}.btn[disabled]{opacity:.5;cursor:default}
.tag{display:inline-block;font-size:12px;padding:2px 9px;border-radius:10px;background:#eef2fb;color:var(--blue);margin:0 4px 4px 0}
table{border-collapse:collapse;width:100%;background:var(--card)}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}td.num,th.num{text-align:right}
.pill{display:inline-block;padding:1px 9px;border-radius:10px;font-size:12px;font-weight:600;white-space:nowrap}
.Y{background:#e6f4ea;color:var(--good)}.Yf{background:#e3eefb;color:var(--blue)}.N{background:#fde8e7;color:var(--bad)}.NA{background:#eee;color:var(--muted)}
details{background:var(--card);border:1px solid var(--line);border-radius:8px;margin-bottom:8px}
details summary{padding:10px 14px;cursor:pointer;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
details .body{padding:0 14px 14px;overflow-x:auto}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 14px;align-items:center}.filters button[aria-pressed=true]{background:var(--accent);color:#fff;border-color:var(--accent)}
.filters input{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:8px;min-width:220px}
.note{font-size:13px;color:var(--muted)}
footer{border-top:1px solid var(--line);padding:18px 24px;text-align:center;color:var(--muted);font-size:14px;background:var(--card)}
/* hero */
.hero{background:radial-gradient(1200px 400px at 90% -10%,#7c3aed55,transparent),linear-gradient(135deg,#0b1f4a,#1b3f94 55%,#2f6bea);color:#fff;border-radius:18px;padding:34px 34px 30px;margin-bottom:24px;position:relative;overflow:hidden}
.hero h1{color:#fff}.hero p.lead{color:#d7e3ff;font-size:17px;max-width:720px;margin:0 0 20px}
.hero .eyebrow{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;background:rgba(255,255,255,.14);padding:4px 10px;border-radius:20px;margin-bottom:14px}
.ba{display:grid;grid-template-columns:1fr auto 1fr;gap:14px;align-items:stretch;margin:6px 0 22px;max-width:820px}
.ba .box{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);border-radius:12px;padding:14px 16px}
.ba .box.after{background:rgba(255,255,255,.18);border-color:rgba(255,255,255,.4)}
.ba .k{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#b9cbff}.ba .big{font-size:30px;font-weight:800}.ba .s{color:#d7e3ff;font-size:13px}
.ba .arrow{display:grid;place-items:center;font-size:26px;color:#ffd166}
@media (max-width:640px){.ba{grid-template-columns:1fr}.ba .arrow{transform:rotate(90deg)}}
/* pipeline */
.pipeline{display:flex;align-items:center;flex-wrap:wrap;gap:0;margin:8px 0}
.node{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;min-width:135px;text-align:center;box-shadow:0 1px 2px #0000000d}
.node .n{font-size:24px;font-weight:800;color:var(--accent);font-variant-numeric:tabular-nums}.node .t{font-size:12px;color:var(--muted)}
.node.good .n{color:var(--good)}.node.bad .n{color:var(--bad)}
.flow{flex:1;min-width:26px;height:4px;margin:0 6px;border-radius:2px;background:repeating-linear-gradient(90deg,var(--accent) 0 10px,#c9d6f5 10px 20px);background-size:40px 4px;animation:flow 1s linear infinite}
.split{display:flex;flex-direction:column;gap:10px}
@keyframes flow{to{background-position:40px 0}}
/* run console */
.console{display:grid;grid-template-columns:1.1fr 1fr;gap:14px}@media (max-width:900px){.console{grid-template-columns:1fr}}
.counters{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}
.counter{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.counter .v{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums}.counter .l{font-size:12px;color:var(--muted)}
.progress{height:8px;background:var(--line);border-radius:6px;overflow:hidden;margin:6px 0 12px}.progress>div{height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .12s}
.terminal{font:13px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;background:#0b1220;color:#cbd5e1;border-radius:12px;padding:14px 16px;height:300px;overflow:hidden;position:relative}
.terminal .ln{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.terminal .ok{color:#4ade80}.terminal .fb{color:#60a5fa}.terminal .rv{color:#f87171}.terminal .dim{color:#64748b}.terminal .hd{color:#fbbf24}
.terminal::after{content:"";position:absolute;inset:auto 0 0 0;height:40px;background:linear-gradient(transparent,#0b1220)}
/* steps */
.steps{list-style:none;margin:0;padding:0}
.steps li{display:flex;gap:12px;align-items:flex-start;padding:9px 0;border-bottom:1px dashed var(--line);color:var(--muted);transition:color .2s}
.steps li:last-child{border-bottom:0}.steps .ic{flex:0 0 24px;height:24px;border-radius:50%;border:2px solid var(--line);display:grid;place-items:center;font-size:13px;font-weight:700}
.steps li.active{color:var(--ink)}.steps li.active .ic{border-color:var(--accent);border-top-color:transparent;animation:spin .8s linear infinite}
.steps li.done{color:var(--ink)}.steps li.done .ic{background:var(--good);border-color:var(--good);color:#fff}
.steps li.gate .ic{background:#fff4d6;border-color:var(--warn);color:var(--warn)}
.steps .d{font-size:13px;color:var(--muted)}
@keyframes spin{to{transform:rotate(360deg)}}
/* tabs */
.tabs{display:flex;gap:6px;margin:6px 0 14px;flex-wrap:wrap}.tabs button{border:1px solid var(--line);background:var(--card);padding:7px 16px;border-radius:20px;font:inherit;font-weight:600;cursor:pointer}
.tabs button[aria-selected=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
.chart-box{position:relative;height:300px}
.alert{border-left:4px solid var(--warn);background:#fffaeb}.alert.bad{border-left-color:var(--bad);background:#fff5f4}
.typed{font-size:16px;line-height:1.7;min-height:7em}.typed::after{content:"▍";color:var(--accent);animation:blink 1s step-end infinite}.typed.done::after{content:""}
@keyframes blink{50%{opacity:0}}
.hidden{display:none !important}.fade{animation:fade .5s ease both}@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
/* chat window */
.chat{background:#1a1d21;color:#d1d2d3;border-radius:12px;overflow:hidden;border:1px solid #2c2f33}
.chat .bar{background:#3f0e40;color:#fff;padding:10px 14px;font-weight:700;display:flex;justify-content:space-between}
.chat .feed{padding:10px 14px;height:420px;overflow-y:auto}
.msg{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid #2c2f33}.msg:last-child{border-bottom:0}
.avatar{flex:0 0 34px;height:34px;border-radius:8px;background:linear-gradient(135deg,#2457c5,#7c3aed);color:#fff;display:grid;place-items:center;font-weight:800;font-size:13px}
.msg .who{font-weight:700;color:#fff}.msg .to{font-size:12px;color:#9ca3af}.msg .txt{color:#e5e7eb}.msg .txt a{color:#7dd3fc}
.checks{display:flex;gap:3px}.checks span{width:14px;height:14px;border-radius:50%;background:var(--good);display:inline-block}.checks span.f{background:var(--bad)}
.gate{border:2px dashed var(--warn);background:#fffaeb}
.guard{display:flex;gap:12px;align-items:flex-start}.guard .gi{flex:0 0 36px;height:36px;border-radius:10px;background:#eef2fb;display:grid;place-items:center;font-size:18px}
.doc table{margin:8px 0 18px}.doc p{margin:10px 0}
@media (prefers-reduced-motion: reduce){.flow,.steps li.active .ic,.typed::after{animation:none}}
"""


def page(title: str, body: str, depth: int = 1, head: str = "") -> str:
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | Prateek Tiwari</title><meta name="description" content="Operations automation portfolio by Prateek Tiwari">
<link rel="stylesheet" href="{up}assets/site.css">{head}</head>
<body><header class="top"><a class="brand" href="{up}">Prateek Tiwari · Operations Automation</a>
<a href="{up}dashboard/">SLA dashboard</a><a href="{up}reconciliation/">Reconciliation</a><a href="{up}bridges/">WBR bridges</a>
<a href="{up}outreach/">Outreach agent</a><a href="{REPO}">Code</a></header>
<main>{body}</main>
<footer>All data is synthetic. · <a href="{LINKEDIN}">LinkedIn</a> · <a href="mailto:{EMAIL}">{EMAIL}</a> · <a href="{REPO}">Source code</a></footer>
</body></html>"""


def hero(eyebrow: str, title: str, lead: str, before: tuple[str, str, str], after: tuple[str, str, str],
         buttons: str) -> str:
    return f"""<section class="hero"><span class="eyebrow">{esc(eyebrow)}</span><h1>{esc(title)}</h1><p class="lead">{esc(lead)}</p>
<div class="ba"><div class="box"><div class="k">{esc(before[0])}</div><div class="big">{esc(before[1])}</div><div class="s">{esc(before[2])}</div></div>
<div class="arrow" aria-hidden="true">➜</div>
<div class="box after"><div class="k">{esc(after[0])}</div><div class="big">{esc(after[1])}</div><div class="s">{esc(after[2])}</div></div></div>
<p>{buttons}</p></section>"""


COMMON_JS = r"""
const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const sleep = ms => new Promise(r => setTimeout(r, reduce ? 0 : ms));
const $ = s => document.querySelector(s);
const escH = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function countTo(el, target, ms = 700, suffix = '') {
  if (reduce) { el.textContent = target + suffix; return; }
  const start = performance.now();
  const tick = now => { const p = Math.min(1, (now - start) / ms); el.textContent = Math.round(target * p) + suffix; if (p < 1) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}
function termLine(term, html, max = 14) {
  const d = document.createElement('div'); d.className = 'ln'; d.innerHTML = html; term.appendChild(d);
  while (term.children.length > max) term.removeChild(term.firstChild);
}
async function typeText(el, text, cps = 220) {
  el.classList.remove('done'); el.textContent = '';
  if (reduce) { el.textContent = text; el.classList.add('done'); return; }
  const step = Math.max(1, Math.round(cps / 60));
  for (let i = 0; i < text.length; i += step) { el.textContent = text.slice(0, i + step); await new Promise(r => requestAnimationFrame(r)); }
  el.classList.add('done');
}
"""


# ================================================================ landing
PROJECTS = [
    ("dashboard/", "01-dispute-sla-dashboard", "Dispute SLA Dashboard", "📊",
     "Live KPI dashboard tracking partner-payment disputes against a 3-business-day SLA, refreshed every 2 hours, "
     "with an at-risk queue so breaches are caught before they happen.", ["Python", "REST API", "JavaScript", "Chart.js"],
     "~5 hrs/week of manual reporting removed"),
    ("reconciliation/", "02-invoice-reconciliation", "Invoice Reconciliation Engine", "🧾",
     "Rule engine that validates every invoice line against five operational feeds and routes only the exceptions to "
     "reviewers, balanced by workload.", ["Python", "Rules engine", "Excel automation"],
     "~80% auto-cleared · ~50 → ~12 hrs/week"),
    ("bridges/", "03-weekly-business-review-bridges", "Weekly Business Review Bridges", "📈",
     "Explains every week-over-week metric move by driver, root-causes each SLA miss and writes the leadership "
     "narrative automatically.", ["Python", "Root-cause analysis", "Automated reporting"],
     "~7 hrs → ~30 min per week"),
    ("outreach/", "04-outreach-agent", "Human-in-the-Loop Outreach Agent", "🤖",
     "AI agent that chases sites for dispute inputs three times a day: reads tickets, finds contacts, checks chat, "
     "drafts messages and waits for approval, inside hard guardrails.", ["AI agent", "LLM guardrails", "Chat-ops"],
     "~1.5 hrs/day → ~15 min review"),
]


def build_landing() -> None:
    cards = "".join(f"""<article class="card"><div style="font-size:30px" aria-hidden="true">{icon}</div><h3 style="margin-top:6px">{esc(t)}</h3><p>{esc(d)}</p>
<p>{''.join(f'<span class="tag">{esc(x)}</span>' for x in tags)}</p><p><strong>Impact:</strong> {esc(imp)}</p>
<p><a class="btn primary" href="{href}">▶ Open live demo</a> <a class="btn" href="{REPO}/tree/main/{folder}">View code</a></p></article>"""
                    for href, folder, t, icon, d, tags, imp in PROJECTS)
    stats = [("~2,700", "analyst hours saved per year"), ("~1.4", "full-time roles redeployed to higher-value work"),
             ("~80%", "of invoices cleared with no manual review"), ("4", "automations running in production")]
    stat_html = "".join(f'<div class="card stat"><div class="v">{v}</div><div class="l">{esc(l)}</div></div>' for v, l in stats)
    body = f"""<section class="hero"><span class="eyebrow">Operations analytics &amp; automation</span>
<h1>Prateek Tiwari</h1><p class="lead">I turn manual, spreadsheet-heavy operations work into reliable automated systems:
live dashboards, rule engines, auto-written leadership reports and an AI agent with a human in the loop. Built for
partner-payment operations in a large last-mile delivery network.</p>
<p><a class="btn light" href="#projects">See the projects</a> <a class="btn ghost" href="{LINKEDIN}">LinkedIn</a>
<a class="btn ghost" href="mailto:{EMAIL}">Email me</a></p></section>
<div class="grid g4">{stat_html}</div>
<h2 id="projects">Projects: click a demo to watch it run</h2><div class="grid g2">{cards}</div>
<p class="note" style="margin-top:24px">These are clean re-implementations built for this portfolio. Every site, partner,
person, ticket and number in the demos is synthetic. Impact figures are rounded estimates of time saved in the original work.</p>"""
    (DOCS / "index.html").write_text(page("Portfolio", body, depth=0), encoding="utf-8")


# ================================================================ 1. dashboard
def build_dashboard() -> None:
    run("generate_sample_data.py", P1)
    use_project(P1)
    metrics = importlib.import_module("metrics")
    payload = metrics.build_payload(json.loads((P1 / "data" / "tickets.json").read_text(encoding="utf-8")))
    leave_project(P1)
    out = DOCS / "dashboard"
    out.mkdir(parents=True, exist_ok=True)
    (out / "data.json").write_text(json.dumps(payload), encoding="utf-8")
    src = (P1 / "static" / "index.html").read_text(encoding="utf-8")
    src = src.replace('fetch("/api/data"', 'fetch("data.json"').replace("setInterval(load, 60000);", "")
    src = re.sub(r"<header>\s*<h1>", '<header>\n  <a class="btn" href="../">&larr; Portfolio</a>\n  <h1>', src, count=1)
    (out / "index.html").write_text(src, encoding="utf-8")


# ================================================================ 2. reconciliation
def build_reconciliation() -> None:
    run("generate_sample_data.py", P2)
    use_project(P2)
    recon = importlib.import_module("recon")
    report = importlib.import_module("report")
    t0 = time.perf_counter()
    feeds = recon.Feeds(P2 / "data" / "feeds")
    results = recon.reconcile(recon.load_invoices(P2 / "data" / "invoices.json"), feeds)
    runtime = time.perf_counter() - t0
    out = DOCS / "reconciliation"
    dl = out / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    matched = [r for r in results if r.status.startswith("Y")]
    unmatched = [r for r in results if r.status == "N"]
    report.write_workbook(matched, dl / "Matched.xlsx")
    queues = report.split_for_reviewers(unmatched, ["Reviewer A", "Reviewer B"])
    for name, q in queues.items():
        report.write_workbook(q, dl / f"Unmatched - {name}.xlsx")
    owner = {r.invoice["invoice_id"]: n for n, q in queues.items() for r in q}
    leave_project(P2)

    feed_rows = sum(sum(1 for _ in open(f, encoding="utf-8")) - 1 for f in (P2 / "data" / "feeds").glob("*.csv"))
    kind_names = {"capacity": "Capacity routes", "late_cancel": "Late cancellations", "coverage": "Coverage bonus",
                  "training": "Training days"}
    by_kind = {}
    for r in results:
        for l in r.lines:
            if l.matched is None:
                continue
            k = by_kind.setdefault(kind_names[l.kind], {"matched": 0, "fallback": 0, "review": 0})
            k["fallback" if l.used_fallback else "matched" if l.matched else "review"] += 1
    code = {"Y": "Y", "Y (fallback)": "Yf", "N": "N"}
    invoices = []
    for r in sorted(results, key=lambda x: (x.status != "N", x.invoice["country"], x.invoice["station"])):
        inv = r.invoice
        invoices.append({
            "id": inv["invoice_id"], "country": inv["country"], "station": inv["station"], "partner": inv["partner_name"],
            "status": r.status, "code": code[r.status], "reviewer": owner.get(inv["invoice_id"]),
            "open": [f"{l.reason}: {l.evidence}" for l in r.open_lines],
            "lines": [{"reason": l.reason, "qty": l.invoiced, "evidence": l.evidence,
                       "res": "NA" if l.matched is None else "Yf" if l.used_fallback else "Y" if l.matched else "N"}
                      for l in r.lines]})
    lines = [l for r in results for l in r.lines if l.matched is not None]
    data = {"invoices": invoices, "by_kind": by_kind, "runtime": round(runtime, 3), "feed_rows": feed_rows,
            "lines": len(lines), "lines_auto": sum(bool(l.matched) for l in lines),
            "queues": [{"name": n, "invoices": len(q), "lines": sum(len(x.open_lines) for x in q)} for n, q in queues.items()],
            "counts": dict(Counter(r.status for r in results))}
    n_auto = len(matched)

    body = hero("Project 2 · Rules engine", "Invoice Reconciliation Engine",
                "Every line on every partner invoice, checked against five evidence feeds in one run. "
                "Reviewers only see what genuinely needs a human, split evenly by workload.",
                ("Before", "~50 hrs/week", "line-by-line checks across five separate logs"),
                ("After", "~12 hrs/week", "~80% of invoices auto-cleared, people handle exceptions"),
                '<button class="btn light" id="run" type="button">▶ Run the engine</button> '
                f'<a class="btn ghost" href="{REPO}/tree/main/02-invoice-reconciliation">View code</a>')
    body += f"""
<h2>How one run works</h2>
<div class="pipeline" aria-label="Reconciliation pipeline">
  <div class="node"><div class="n">{len(results)}</div><div class="t">invoices in</div></div><div class="flow"></div>
  <div class="node"><div class="n">{len(lines)}</div><div class="t">lines classified</div></div><div class="flow"></div>
  <div class="node"><div class="n">{feed_rows:,}</div><div class="t">evidence rows, 5 feeds</div></div><div class="flow"></div>
  <div class="split"><div class="node good"><div class="n">{n_auto}</div><div class="t">auto-cleared</div></div>
  <div class="node bad"><div class="n">{len(unmatched)}</div><div class="t">to reviewers</div></div></div>
</div>

<h2>Live run</h2>
<div class="console">
  <div>
    <div class="counters">
      <div class="counter"><div class="v" id="c-done">0</div><div class="l">invoices processed</div></div>
      <div class="counter"><div class="v" id="c-y" style="color:var(--good)">0</div><div class="l">auto-cleared</div></div>
      <div class="counter"><div class="v" id="c-yf" style="color:var(--blue)">0</div><div class="l">cleared by fallback rule</div></div>
      <div class="counter"><div class="v" id="c-n" style="color:var(--bad)">0</div><div class="l">sent to review</div></div>
    </div>
    <div class="progress" role="progressbar" aria-label="Run progress" aria-valuemin="0" aria-valuemax="100"><div id="bar"></div></div>
    <div class="terminal" id="term" aria-live="off"></div>
  </div>
  <div class="card"><h3 style="margin-top:0">Outcome</h3><div class="chart-box"><canvas id="ch-out" role="img" aria-label="Invoice outcome split"></canvas></div>
  <p class="note" id="runnote">Press "Run the engine" to replay the run.</p></div>
</div>

<div class="grid g2 hidden" id="results" style="margin-top:14px">
  <div class="card"><h3 style="margin-top:0">Where the exceptions are</h3><div class="chart-box"><canvas id="ch-kind" role="img" aria-label="Line outcomes by line type"></canvas></div></div>
  <div class="card"><h3 style="margin-top:0">Review queues, balanced by workload</h3><div class="chart-box"><canvas id="ch-q" role="img" aria-label="Lines to review per reviewer"></canvas></div>
  <p class="note">Exceptions are assigned by number of open lines, not invoice count, so each reviewer gets an equal share of the effort.</p></div>
</div>

<h2>Explore every invoice</h2>
<div class="filters" role="group" aria-label="Filter invoices">
  <button class="btn" type="button" data-f="all" aria-pressed="true">All</button>
  <button class="btn" type="button" data-f="N" aria-pressed="false">Needs review</button>
  <button class="btn" type="button" data-f="Y" aria-pressed="false">Auto-cleared</button>
  <button class="btn" type="button" data-f="Yf" aria-pressed="false">Cleared by fallback</button>
  <label class="muted">Search <input id="q" type="search" placeholder="invoice, site, partner"></label>
</div>
<div id="list"></div>

<h2>The workbooks reviewers get</h2>
<p class="muted">The same run writes Excel files: a Summary sheet first, then one colour-coded sheet per invoice with the raw invoice
on the left and the validation on the right.</p>
<p><a class="btn" href="downloads/Matched.xlsx" download>⬇ Matched.xlsx</a> <a class="btn" href="downloads/Unmatched - Reviewer A.xlsx" download>⬇ Unmatched - Reviewer A.xlsx</a>
<a class="btn" href="downloads/Unmatched - Reviewer B.xlsx" download>⬇ Unmatched - Reviewer B.xlsx</a></p>

<script>const DATA = {js_data(data)};</script>
<script>{COMMON_JS}
const LABEL = {{Y: 'Matched', Yf: 'Matched (fallback)', N: 'Review', NA: 'Not validated'}};
let outChart;
function drawOutcome(y, yf, n) {{
  const d = [y, yf, n];
  if (outChart) {{ outChart.data.datasets[0].data = d; outChart.update('none'); return; }}
  outChart = new Chart($('#ch-out'), {{ type: 'doughnut',
    data: {{ labels: ['Auto-cleared', 'Cleared by fallback', 'Sent to review'], datasets: [{{ data: d, backgroundColor: ['#1a7f37', '#2f6bea', '#d92d20'], borderWidth: 0 }}] }},
    options: {{ maintainAspectRatio: false, cutout: '62%', animation: {{ duration: reduce ? 0 : 300 }}, plugins: {{ legend: {{ position: 'bottom' }} }} }} }});
}}
function drawResults() {{
  $('#results').classList.remove('hidden'); $('#results').classList.add('fade');
  const kinds = Object.keys(DATA.by_kind);
  new Chart($('#ch-kind'), {{ type: 'bar',
    data: {{ labels: kinds, datasets: [
      {{ label: 'Matched', data: kinds.map(k => DATA.by_kind[k].matched), backgroundColor: '#1a7f37' }},
      {{ label: 'Matched by fallback', data: kinds.map(k => DATA.by_kind[k].fallback), backgroundColor: '#2f6bea' }},
      {{ label: 'Review', data: kinds.map(k => DATA.by_kind[k].review), backgroundColor: '#d92d20' }}] }},
    options: {{ indexAxis: 'y', maintainAspectRatio: false, scales: {{ x: {{ stacked: true }}, y: {{ stacked: true }} }}, plugins: {{ legend: {{ position: 'bottom' }} }} }} }});
  new Chart($('#ch-q'), {{ type: 'bar',
    data: {{ labels: DATA.queues.map(q => q.name), datasets: [
      {{ label: 'Lines to review', data: DATA.queues.map(q => q.lines), backgroundColor: '#7c3aed' }},
      {{ label: 'Invoices', data: DATA.queues.map(q => q.invoices), backgroundColor: '#c4b5fd' }}] }},
    options: {{ maintainAspectRatio: false, plugins: {{ legend: {{ position: 'bottom' }} }} }} }});
}}
let ran = false;
async function runEngine() {{
  const btn = $('#run'); btn.disabled = true; btn.textContent = 'Running…';
  const term = $('#term'); term.innerHTML = '';
  const c = {{ Y: 0, Yf: 0, N: 0 }}; let done = 0;
  termLine(term, '<span class="hd">$ python run.py --reviewers "Reviewer A,Reviewer B"</span>');
  termLine(term, `<span class="dim">loading ${{DATA.feed_rows.toLocaleString()}} evidence rows from 5 feeds…</span>`);
  await sleep(500);
  const order = [...DATA.invoices].sort(() => Math.random() - .5);
  for (const inv of order) {{
    done++; c[inv.code]++;
    $('#c-done').textContent = done; $('#c-y').textContent = c.Y; $('#c-yf').textContent = c.Yf; $('#c-n').textContent = c.N;
    $('#bar').style.width = (100 * done / order.length) + '%';
    const ok = inv.lines.filter(l => l.res !== 'NA').length;
    if (inv.code === 'Y') termLine(term, `<span class="ok">✓</span> ${{escH(inv.id)}} · ${{escH(inv.station)}} · ${{ok}}/${{ok}} lines matched`);
    else if (inv.code === 'Yf') termLine(term, `<span class="fb">✓</span> ${{escH(inv.id)}} · coverage pending QC added by fallback rule`);
    else termLine(term, `<span class="rv">⚑</span> ${{escH(inv.id)}} · ${{escH(inv.open[0] || '')}} → ${{escH(inv.reviewer)}}`);
    drawOutcome(c.Y, c.Yf, c.N);
    await sleep(70);
  }}
  termLine(term, `<span class="hd">done: ${{DATA.lines_auto}}/${{DATA.lines}} lines (${{Math.round(100 * DATA.lines_auto / DATA.lines)}}%) validated automatically · workbooks written</span>`);
  $('#runnote').textContent = `The real engine processed this run in ${{DATA.runtime}} s. The replay is slowed down so you can watch it.`;
  btn.disabled = false; btn.textContent = '↻ Run again';
  if (!ran) {{ drawResults(); ran = true; }}
}}
function renderList() {{
  const f = document.querySelector('[data-f][aria-pressed=true]').dataset.f, q = $('#q').value.trim().toLowerCase();
  $('#list').innerHTML = DATA.invoices.filter(i => (f === 'all' || i.code === f) &&
      (!q || [i.id, i.station, i.partner, i.country].join(' ').toLowerCase().includes(q))).map(i => `
    <details><summary><span class="pill ${{i.code}}">${{escH(i.status)}}</span><strong>${{escH(i.id)}}</strong>
    <span class="muted">${{escH(i.country)}} · ${{escH(i.station)}} · ${{escH(i.partner)}}</span>
    ${{i.reviewer ? `<span class="muted">→ ${{escH(i.reviewer)}}</span>` : ''}}</summary><div class="body"><table>
    <thead><tr><th scope="col">Invoice line</th><th scope="col" class="num">Invoiced</th><th scope="col">Evidence found</th><th scope="col">Result</th></tr></thead>
    <tbody>${{i.lines.map(l => `<tr><td>${{escH(l.reason)}}</td><td class="num">${{l.qty.toLocaleString()}}</td><td>${{escH(l.evidence)}}</td>
    <td><span class="pill ${{l.res}}">${{LABEL[l.res]}}</span></td></tr>`).join('')}}</tbody></table></div></details>`).join('');
}}
document.querySelectorAll('[data-f]').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('[data-f]').forEach(x => x.setAttribute('aria-pressed', x === b)); renderList(); }}));
$('#q').addEventListener('input', renderList);
$('#run').addEventListener('click', runEngine);
renderList(); drawOutcome(0, 0, 0);
setTimeout(runEngine, 700);
</script>"""
    (out / "index.html").write_text(page("Invoice Reconciliation Engine", body, head=CHART_JS), encoding="utf-8")


# ================================================================ 3. bridges
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
            level = min(len(line) - len(line.lstrip("#")) + 1, 6)
            out.append(f"<h{level}>{inline(line.lstrip('#').strip())}</h{level}>")
            i += 1
        elif line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, align, rows = block[0], block[1], block[2:]
            right = [a.endswith(":") for a in align]
            th = "".join(f'<th scope="col"{" class=num" if right[k] else ""}>{inline(c)}</th>' for k, c in enumerate(head))
            tb = "".join("<tr>" + "".join(f'<td{" class=num" if right[k] else ""}>{inline(c)}</td>' for k, c in enumerate(r)) + "</tr>"
                         for r in rows)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>")
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
    use_project(P3)
    bridge = importlib.import_module("bridge")
    narrative = importlib.import_module("narrative")
    t0 = time.perf_counter()
    tickets = bridge.load_tickets(P3 / "data" / "tickets.csv")
    base = bridge.load_base(P3 / "data" / "base.csv")
    as_of = datetime.fromisoformat((P3 / "data" / "as_of.txt").read_text().strip())
    week = max(t["week"] for t in tickets)
    target = 0.95
    sections, lines_out = [], []
    for line in sorted({t["business_line"] for t in tickets}):
        rate = bridge.dispute_rate_bridge(tickets, base, line, week)
        invalid = bridge.invalid_rate_bridge(tickets, line, week)
        sla = bridge.sla_bridge(tickets, line, week, as_of)
        sections.append((rate, invalid, sla))
        lead = re.sub(r"\*\*(.+?)\*\*", r"\1", narrative.leadership(rate, invalid, sla, target))
        lines_out.append({
            "line": line,
            "rate": {"prev": rate.prev_rate, "cur": rate.cur_rate, "bps": rate.change_bps, "n": rate.cur_n, "base": rate.cur_base,
                     "drivers": [{"name": d.name, "prev": d.prev, "cur": d.cur, "bps": d.contribution_bps} for d in rate.drivers]},
            "invalid": {"prev": invalid.prev_rate, "cur": invalid.cur_rate, "bps": invalid.change_bps,
                        "drivers": [{"name": d.name or "Unspecified", "prev": d.prev, "cur": d.cur, "bps": d.contribution_bps}
                                    for d in invalid.drivers]},
            "sla": {"rate": sla.rate, "prev": sla.prev_rate, "met": sla.met, "missed": sla.missed, "open": sla.open_in_sla,
                    "causes": dict(Counter(m.cause for m in sla.misses)), "repeat": sla.repeat_sites(),
                    "misses": [{"id": m.ticket_id, "site": m.station, "cause": m.cause, "late": m.hours_late} for m in sla.misses[:8]]},
            "leadership": lead, "speakable": narrative.speakable(rate, sla)})
    notes = bridge.anomalies(tickets, base, week)
    doc = narrative.build_document(week, sections, notes, target)
    runtime = time.perf_counter() - t0
    leave_project(P3)
    n_drivers = sum(len(l["rate"]["drivers"]) + len(l["invalid"]["drivers"]) for l in lines_out)
    n_miss = sum(l["sla"]["missed"] for l in lines_out)
    data = {"week": week, "target": target, "tickets": len(tickets), "lines": lines_out, "notes": notes,
            "runtime": round(runtime, 3), "drivers": n_drivers, "misses": n_miss}

    body = hero("Project 3 · Automated reporting", "Weekly Business Review Bridges",
                "Leadership doesn't just want the number, they want why it moved. This engine reads every ticket, "
                "splits each change into the drivers behind it, root-causes every SLA miss and writes the narrative.",
                ("Before", "~7 hours", "reading tickets by hand before every weekly review"),
                ("After", "~30 min", "generated bridge, narrative and tables, reviewed and sent"),
                '<button class="btn light" id="gen" type="button">▶ Generate this week\'s bridge</button> '
                f'<a class="btn ghost" href="{REPO}/tree/main/03-weekly-business-review-bridges">View code</a>')
    body += f"""
<div class="console" style="margin-top:4px">
  <div class="card"><h3 style="margin-top:0">What the engine does, step by step</h3>
    <ol class="steps" id="steps">
      <li><span class="ic">1</span><div><strong>Load raw tickets</strong><div class="d">{len(tickets):,} tickets across {len(lines_out)} business lines, week {week} vs {week - 1}</div></div></li>
      <li><span class="ic">2</span><div><strong>Compute the three review metrics</strong><div class="d">dispute rate, invalid rate, SLA rate, for each line</div></div></li>
      <li><span class="ic">3</span><div><strong>Decompose every change into drivers</strong><div class="d">{n_drivers} driver contributions that add up exactly to each headline change</div></div></li>
      <li><span class="ic">4</span><div><strong>Root-cause every SLA miss</strong><div class="d">{n_miss} misses, one accountable cause each; repeat sites flagged</div></div></li>
      <li><span class="ic">5</span><div><strong>Run data-quality checks</strong><div class="d">{len(notes)} issue(s) found and listed before anything reaches leadership</div></div></li>
      <li><span class="ic">6</span><div><strong>Write the leadership narrative</strong><div class="d">paragraph, speakable version and supporting tables</div></div></li>
    </ol>
    <p class="note" id="gennote">The real engine runs all six steps in {runtime:.2f} s.</p>
  </div>
  <div class="card"><h3 style="margin-top:0">Leadership bridge <span class="muted" id="lead-line"></span></h3>
    <p class="typed done" id="typed">Press "Generate this week's bridge" to watch it being written.</p>
    <h3>Speakable version</h3><p class="muted" id="speak">–</p></div>
</div>

<section id="analysis" class="hidden">
<h2>Week {week} analysis</h2>
<div class="tabs" role="tablist" aria-label="Business line" id="tabs"></div>
<div class="grid g4" id="kpis"></div>
<div class="grid g2" style="margin-top:14px">
  <div class="card"><h3 style="margin-top:0">Dispute rate bridge, week {week - 1} → {week}</h3>
    <div class="chart-box"><canvas id="ch-wf" role="img" aria-label="Waterfall of dispute rate change by driver"></canvas></div>
    <p class="note">Each bar is one driver's contribution in percentage points. They reconcile exactly to the headline change.</p></div>
  <div class="card"><h3 style="margin-top:0">Why SLAs were missed</h3>
    <div class="chart-box"><canvas id="ch-sla" role="img" aria-label="SLA misses by root cause"></canvas></div>
    <div id="repeat"></div></div>
</div>
<h2>Caught before it reached leadership</h2>
<div class="grid g2" id="notes"></div>
<h2>The generated document</h2>
<details><summary><strong>Open the full week {week} review document</strong> <span class="muted">exactly as the engine wrote it</span></summary>
<div class="body doc">{markdown_to_html(doc)}</div></details>
</section>

<script>const DATA = {js_data(data)};</script>
<script>{COMMON_JS}
const pct = v => v == null ? 'n/a' : (v * 100).toFixed(1) + '%';
const sbps = v => (v > 0 ? '+' : '') + v + ' bps';
let cur = 0, wf, sl;
function kpi(label, value, delta, good) {{
  return `<div class="card stat"><div class="l">${{label}}</div><div class="v">${{value}}</div>
  <div class="l" style="color:${{good ? 'var(--good)' : 'var(--bad)'}}">${{delta}}</div></div>`;
}}
function renderLine(i) {{
  cur = i; const L = DATA.lines[i];
  document.querySelectorAll('#tabs button').forEach((b, k) => b.setAttribute('aria-selected', k === i));
  $('#kpis').innerHTML =
    kpi('Dispute rate', pct(L.rate.cur), sbps(L.rate.bps) + ' WoW', L.rate.bps <= 0) +
    kpi('Invalid rate', pct(L.invalid.cur), sbps(L.invalid.bps) + ' WoW', L.invalid.bps <= 0) +
    kpi('SLA rate', pct(L.sla.rate), (L.sla.rate >= DATA.target ? 'above' : 'below') + ' the ' + pct(DATA.target) + ' target', L.sla.rate >= DATA.target) +
    kpi('SLA misses', L.sla.missed, Object.keys(L.sla.causes).length + ' root cause(s) identified', L.sla.missed === 0);
  const drivers = L.rate.drivers.filter(d => d.bps !== 0);
  let run = L.rate.prev * 100; const labels = ['Week ' + (DATA.week - 1)], bars = [[0, run]], colors = ['#64748b'];
  for (const d of drivers) {{ const nxt = run + d.bps / 100; labels.push(d.name); bars.push([run, nxt]); colors.push(d.bps > 0 ? '#d92d20' : '#1a7f37'); run = nxt; }}
  labels.push('Week ' + DATA.week); bars.push([0, L.rate.cur * 100]); colors.push('#2457c5');
  const lo = Math.max(0, Math.floor(Math.min(...bars.flat().filter(v => v > 0)) - 1));
  wf?.destroy();
  wf = new Chart($('#ch-wf'), {{ type: 'bar', data: {{ labels, datasets: [{{ data: bars, backgroundColor: colors, borderSkipped: false, borderRadius: 4 }}] }},
    options: {{ maintainAspectRatio: false, plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: c => {{
      const [a, b] = c.raw; return c.dataIndex === 0 || c.dataIndex === labels.length - 1 ? b.toFixed(2) + '%' : ((b - a) > 0 ? '+' : '') + ((b - a) * 100).toFixed(0) + ' bps'; }} }} }} }},
      scales: {{ y: {{ min: lo, ticks: {{ callback: v => v + '%' }} }}, x: {{ ticks: {{ maxRotation: 40, minRotation: 0 }} }} }} }} }});
  const causes = Object.keys(L.sla.causes);
  sl?.destroy();
  sl = new Chart($('#ch-sla'), {{ type: 'doughnut', data: {{ labels: causes.length ? causes : ['No misses'],
      datasets: [{{ data: causes.length ? causes.map(c => L.sla.causes[c]) : [1], backgroundColor: ['#f59e0b', '#d92d20', '#7c3aed', '#64748b'], borderWidth: 0 }}] }},
    options: {{ maintainAspectRatio: false, cutout: '60%', plugins: {{ legend: {{ position: 'bottom' }} }} }} }});
  $('#repeat').innerHTML = L.sla.repeat.map(([s, n]) => `<div class="card alert bad" style="margin-top:10px"><strong>⚑ Site ${{escH(s)}}</strong>:
    ${{n}} tickets missed SLA while waiting on this site's input. Flagged for follow-up with the site lead.</div>`).join('');
}}
async function setStep(i, state) {{
  const li = document.querySelectorAll('#steps li')[i]; li.className = state;
  li.querySelector('.ic').textContent = state === 'done' ? '✓' : state === 'active' ? '' : i + 1;
}}
async function generate() {{
  const btn = $('#gen'); btn.disabled = true; btn.textContent = 'Generating…';
  for (let i = 0; i < 6; i++) setStep(i, '');
  for (let i = 0; i < 6; i++) {{ await setStep(i, 'active'); await sleep(550); await setStep(i, 'done');
    if (i === 3 && $('#analysis').classList.contains('hidden')) {{ $('#analysis').classList.remove('hidden'); $('#analysis').classList.add('fade'); renderLine(cur); }} }}
  for (let i = 0; i < DATA.lines.length; i++) {{
    renderLine(i); $('#lead-line').textContent = '· ' + DATA.lines[i].line;
    await typeText($('#typed'), DATA.lines[i].leadership); $('#speak').textContent = DATA.lines[i].speakable;
    await sleep(1400);
  }}
  btn.disabled = false; btn.textContent = '↻ Generate again';
}}
$('#tabs').innerHTML = DATA.lines.map((l, i) => `<button type="button" role="tab" aria-selected="${{i === 0}}">${{escH(l.line)}}</button>`).join('');
document.querySelectorAll('#tabs button').forEach((b, i) => b.addEventListener('click', () => {{
  renderLine(i); $('#lead-line').textContent = '· ' + DATA.lines[i].line; $('#typed').textContent = DATA.lines[i].leadership;
  $('#typed').classList.add('done'); $('#speak').textContent = DATA.lines[i].speakable; }}));
$('#notes').innerHTML = DATA.notes.map(n => `<div class="card alert">⚠ ${{escH(n)}}</div>`).join('') || '<div class="card">No data issues found.</div>';
$('#gen').addEventListener('click', generate);
setTimeout(generate, 700);
</script>"""
    (DOCS / "bridges").mkdir(parents=True, exist_ok=True)
    (DOCS / "bridges" / "index.html").write_text(page("Weekly Business Review Bridges", body, head=CHART_JS), encoding="utf-8")


# ================================================================ 4. outreach agent
def build_outreach() -> None:
    run("generate_sample_data.py", P4)
    use_project(P4)
    agent = importlib.import_module("agent")
    mocks = importlib.import_module("mock_clients")
    rules = importlib.import_module("rules")
    data_dir = P4 / "data"
    raw_rows = sum(1 for _ in open(data_dir / "queue.csv", encoding="utf-8")) - 1
    tickets = mocks.MockTicketClient(data_dir / "tickets.json")
    chat = mocks.MockChatClient(data_dir / "chat_history.json")
    t0 = time.perf_counter()
    result = agent.run_agent(data_dir / "queue.csv", "SEV-1", "first", tickets, chat,
                             window_start=datetime(2026, 10, 27), run_start=datetime(2026, 10, 28, 14))
    result.sent = agent.send(result.drafts, chat, lambda d: True)
    runtime = time.perf_counter() - t0
    leave_project(P4)

    work = result.work
    counts = result.bucket_counts()
    fetched = sum(1 for w in work if w.ref)
    failed = [w for w in work if not w.ref]
    history = [m for m in chat.history]
    data = {
        "runtime": round(runtime, 3), "raw_rows": raw_rows, "sev_rows": result.total + result.duplicates_removed,
        "total": result.total, "dupes": result.duplicates_removed, "fetched": fetched, "fetch_failed": len(failed),
        "retries": sum(1 for w in failed),
        "contacts": sum(len(w.contacts) for w in work), "excluded": sum(len(w.excluded_tags) for w in work),
        "dropped": sum(len(w.dropped_tags) for w in work), "history": len(history),
        "replied": counts["Already covered"],
        "no_reply": sum(1 for w in work if w.reason == "Messaged before, no reply yet"),
        "rejections": {k: sum(1 for w in work if w.rejection == k) for k in ("all", "partial", "unclear")},
        "counts": counts, "buckets": list(rules.BUCKETS),
        "flags": [{"site": w.station, "flag": f} for w in work for f in w.flags],
        "parked": [{"site": w.station or "unknown", "bucket": w.bucket, "reason": w.reason, "glimpse": w.glimpse}
                   for w in work if w.bucket in ("Could not process", "Rejected", "Already covered")],
        "drafts": [{"site": d.work.station, "country": d.work.country, "partner": d.work.partner, "to": d.recipients,
                    "excluded": d.work.excluded_tags, "copy": d.work.team_copy, "glimpse": d.work.glimpse,
                    "reason": d.work.reason, "checks": list(d.checks.values()), "text": d.text} for d in result.drafts],
        "check_names": list(result.drafts[0].checks) if result.drafts else [],
        "sent": sum(1 for s in result.sent if s["status"] == "sent"),
    }

    guards = [("🛑", "Never sends without approval", "The send step takes an approval callback and does nothing without it."),
              ("🚫", "Never-message list", "Enforced when drafting and again immediately before every send, @mentions included."),
              ("🤔", "Never guesses a contact", "No tagged contact means 'please advise', never a best guess."),
              ("🧮", "Never drops a ticket", "Every ticket lands in exactly one bucket; the run fails if counts don't reconcile."),
              ("🔒", "Never rewords a template", "Only the link changes; text is checked against the template exactly."),
              ("🙋", "Never decides unclear cases", "Reopened or ambiguous rejections are flagged for a human.")]
    guard_html = "".join(f'<div class="card guard"><div class="gi" aria-hidden="true">{i}</div><div><strong>{esc(t)}</strong>'
                         f'<div class="muted">{esc(d)}</div></div></div>' for i, t, d in guards)
    body = hero("Project 4 · AI agent with a human in the loop", "Human-in-the-Loop Outreach Agent",
                "Disputes stall when the site with the answer doesn't reply. Three times a day this agent reads every waiting "
                "ticket, works out who to chase, checks who already replied, drafts the messages, and waits for a human to approve.",
                ("Before", "~1.5 hrs/day", "opening each ticket, reading threads, chasing in chat by hand"),
                ("After", "~15 min/day", "the agent prepares everything; a person reviews and approves"),
                '<button class="btn light" id="go" type="button">▶ Run the 2 PM SEV-1 run</button> '
                f'<a class="btn ghost" href="{REPO}/tree/main/04-outreach-agent">View code</a>')
    body += f"""
<div class="console">
  <div class="card"><h3 style="margin-top:0">Agent run</h3>
    <ol class="steps" id="steps">
      <li><span class="ic">1</span><div><strong>Load the queue</strong><div class="d" id="d0">filter to SEV-1, remove duplicates</div></div></li>
      <li><span class="ic">2</span><div><strong>Fetch ticket details</strong><div class="d" id="d1">retry once, never drop silently</div></div></li>
      <li><span class="ic">3</span><div><strong>Read every comment thread</strong><div class="d" id="d2">tagged contacts, latest comment, rejections</div></div></li>
      <li><span class="ic">4</span><div><strong>Check chat history</strong><div class="d" id="d3">who was chased, and who replied</div></div></li>
      <li><span class="ic">5</span><div><strong>Sort every ticket into one bucket</strong><div class="d" id="d4">counts must reconcile to the total</div></div></li>
      <li class="" id="gate1"><span class="ic">✋</span><div><strong>Checkpoint: human review</strong><div class="d">the agent stops here and waits</div></div></li>
      <li><span class="ic">6</span><div><strong>Draft messages + 7 safety checks each</strong><div class="d" id="d6">locked templates only</div></div></li>
      <li class="" id="gate2"><span class="ic">✋</span><div><strong>Approval: nothing is sent without it</strong><div class="d">"approve all", or edit</div></div></li>
      <li><span class="ic">7</span><div><strong>Send + write the audit log</strong><div class="d" id="d8">never-message list re-checked before every send</div></div></li>
    </ol>
  </div>
  <div class="terminal" id="term" style="height:auto;min-height:420px" aria-live="off"></div>
</div>

<section id="checkpoint" class="hidden" style="margin-top:16px">
  <div class="card gate"><h3 style="margin-top:0">✋ Checkpoint: the agent is waiting for you</h3>
    <div class="grid g4" id="bucketcards"></div>
    <div id="flags" style="margin-top:12px"></div>
    <details style="margin-top:12px"><summary><strong>Tickets the agent will not message, and why</strong></summary><div class="body"><table>
      <thead><tr><th scope="col">Site</th><th scope="col">Bucket</th><th scope="col">Reason</th><th scope="col">Latest comment</th></tr></thead><tbody id="parked"></tbody></table></div></details>
    <p style="margin-top:14px"><button class="btn primary" id="cont" type="button">Looks right: draft the messages</button></p>
  </div>
</section>

<section id="draftsec" class="hidden" style="margin-top:16px">
  <div class="card gate"><h3 style="margin-top:0">✋ Approval: <span id="ndrafts"></span> drafts, all checks shown</h3>
    <p class="muted" id="checklegend"></p>
    <div style="overflow-x:auto"><table><thead><tr><th scope="col">Site</th><th scope="col">Message to</th><th scope="col">Excluded tags</th>
      <th scope="col">Latest comment (shown to approver)</th><th scope="col">7 checks</th></tr></thead><tbody id="drafts"></tbody></table></div>
    <p style="margin-top:14px"><strong>Good to send?</strong> <button class="btn primary" id="approve" type="button">✅ Approve all</button></p>
  </div>
</section>

<section id="sendsec" class="hidden" style="margin-top:16px">
  <div class="grid g2">
    <div class="chat"><div class="bar"><span># group DMs · outreach agent</span><span id="sentcount">0 sent</span></div><div class="feed" id="feed"></div></div>
    <div class="card"><h3 style="margin-top:0">Audit log</h3><div id="log" class="muted">writing…</div></div>
  </div>
</section>

<h2>Guardrails the agent can't talk its way around</h2>
<div class="grid g3">{guard_html}</div>

<script>const DATA = {js_data(data)};</script>
<script>{COMMON_JS}
const term = $('#term');
const steps = () => document.querySelectorAll('#steps li');
function step(i, state, detail) {{
  const li = steps()[i]; li.className = state; const ic = li.querySelector('.ic');
  if (state === 'done') ic.textContent = '✓'; if (state === 'active') ic.textContent = '';
  if (state === 'gate') ic.textContent = '✋';
  if (detail) li.querySelector('.d').innerHTML = detail;
}}
const log = (h, cls = '') => termLine(term, cls ? `<span class="${{cls}}">${{h}}</span>` : h, 30);
async function phase1() {{
  $('#go').disabled = true; term.innerHTML = ''; steps().forEach((li, i) => {{ li.className = ''; }});
  log('$ agent run --severity SEV-1 --run first   # 14:00 slot ✓ matches schedule', 'hd');
  step(0, 'active'); await sleep(600);
  log(`queue: ${{DATA.raw_rows}} rows → ${{DATA.sev_rows}} SEV-1 → ${{DATA.total}} unique (${{DATA.dupes}} duplicates removed)`);
  step(0, 'done', `${{DATA.total}} tickets, ${{DATA.dupes}} duplicates removed`);
  step(1, 'active'); await sleep(700);
  log(`fetched ${{DATA.fetched}}/${{DATA.total}} tickets`);
  if (DATA.fetch_failed) log(`✗ ${{DATA.fetch_failed}} lookup failed twice → "Could not process" (not dropped)`, 'rv');
  step(1, 'done', `${{DATA.fetched}} fetched · ${{DATA.fetch_failed}} parked after retry`);
  step(2, 'active'); await sleep(800);
  log(`contacts found: ${{DATA.contacts}} · team/bot tags dropped: ${{DATA.dropped}}`);
  log(`🚫 never-message tags excluded: ${{DATA.excluded}}`, 'rv');
  log(`rejections: ${{DATA.rejections.all}} full · ${{DATA.rejections.partial}} partial · ${{DATA.rejections.unclear}} unclear (flagged)`);
  step(2, 'done', `${{DATA.contacts}} contacts · ${{DATA.excluded}} excluded · ${{DATA.rejections.all + DATA.rejections.partial + DATA.rejections.unclear}} rejections read`);
  step(3, 'active'); await sleep(600);
  log(`chat since yesterday: ${{DATA.history}} messages · ${{DATA.replied}} contacts already replied · ${{DATA.no_reply}} chased without reply`);
  step(3, 'done', `${{DATA.replied}} already replied · ${{DATA.no_reply}} to chase again`);
  step(4, 'active'); await sleep(600);
  const c = DATA.counts, sum = Object.values(c).reduce((a, b) => a + b, 0);
  log(`buckets: ${{DATA.buckets.map(b => b + ' ' + c[b]).join(' · ')}} = ${{sum}} ✓ reconciles`, 'ok');
  step(4, 'done', DATA.buckets.map(b => `${{b}} ${{c[b]}}`).join(' · '));
  step(5, 'gate'); log('⏸ checkpoint: waiting for human review', 'hd');
  $('#bucketcards').innerHTML = DATA.buckets.map(b => `<div class="card stat"><div class="v">${{c[b]}}</div><div class="l">${{b}}</div></div>`).join('');
  $('#flags').innerHTML = DATA.flags.map(f => `<div class="card alert" style="margin-top:8px">⚑ <strong>${{escH(f.site)}}</strong>: ${{escH(f.flag)}}</div>`).join('');
  $('#parked').innerHTML = DATA.parked.map(p => `<tr><td>${{escH(p.site)}}</td><td>${{escH(p.bucket)}}</td><td>${{escH(p.reason)}}</td><td class="muted">${{escH(p.glimpse)}}</td></tr>`).join('');
  $('#checkpoint').classList.remove('hidden'); $('#checkpoint').classList.add('fade');
  $('#checkpoint').scrollIntoView({{ behavior: reduce ? 'auto' : 'smooth', block: 'start' }});
}}
async function phase2() {{
  $('#cont').disabled = true; step(5, 'done'); log('✓ human approved the buckets', 'ok');
  step(6, 'active'); await sleep(700);
  const passed = DATA.drafts.filter(d => d.checks.every(Boolean)).length;
  log(`drafted ${{DATA.drafts.length}} messages from locked templates · ${{passed}}/${{DATA.drafts.length}} passed all 7 checks`, 'ok');
  step(6, 'done', `${{DATA.drafts.length}} drafts · ${{passed}} passed all 7 checks`);
  step(7, 'gate'); log('⏸ approval: nothing will be sent until a person approves', 'hd');
  $('#ndrafts').textContent = DATA.drafts.length;
  $('#checklegend').textContent = 'Checks: ' + DATA.check_names.map((n, i) => (i + 1) + ') ' + n).join(' · ');
  $('#drafts').innerHTML = DATA.drafts.map(d => `<tr><td><strong>${{escH(d.site)}}</strong><div class="muted">${{escH(d.reason)}}</div></td>
    <td>${{d.to.map(escH).join(', ')}}${{d.copy ? `<div class="muted">team copy: ${{escH(d.copy)}}</div>` : ''}}</td>
    <td>${{d.excluded.length ? `<span class="pill N">${{d.excluded.map(escH).join(', ')}}</span>` : '<span class="muted">none</span>'}}</td>
    <td class="muted" style="max-width:360px">${{escH(d.glimpse)}}</td>
    <td><span class="checks" aria-label="${{d.checks.filter(Boolean).length}} of 7 checks passed">${{d.checks.map(ok => `<span class="${{ok ? '' : 'f'}}"></span>`).join('')}}</span></td></tr>`).join('');
  $('#draftsec').classList.remove('hidden'); $('#draftsec').classList.add('fade');
  $('#draftsec').scrollIntoView({{ behavior: reduce ? 'auto' : 'smooth', block: 'start' }});
}}
async function phase3() {{
  $('#approve').disabled = true; step(7, 'done'); log('✓ approved: "approve all"', 'ok');
  step(8, 'active');
  $('#sendsec').classList.remove('hidden'); $('#sendsec').classList.add('fade');
  $('#sendsec').scrollIntoView({{ behavior: reduce ? 'auto' : 'smooth', block: 'start' }});
  const feed = $('#feed'); let n = 0;
  for (const d of DATA.drafts) {{
    const link = d.text.match(/https:\\S+/)[0];
    const div = document.createElement('div'); div.className = 'msg fade';
    div.innerHTML = `<div class="avatar">OA</div><div><div class="who">Outreach Agent <span class="to">to ${{d.to.map(escH).join(', ')}}</span></div>
      <div class="txt">${{escH(d.text).replace(escH(link), `<a href="#" onclick="return false">${{escH(link)}}</a>`)}}</div></div>`;
    feed.appendChild(div); feed.scrollTop = feed.scrollHeight;
    n++; $('#sentcount').textContent = n + ' sent';
    log(`→ sent to ${{d.to.join(', ')}} (${{d.site}})`);
    await sleep(260);
  }}
  const c = DATA.counts;
  $('#log').innerHTML = `<table><tbody>
    <tr><td>Tickets in run</td><td class="num">${{DATA.total}}</td></tr><tr><td>Duplicates removed</td><td class="num">${{DATA.dupes}}</td></tr>
    ${{DATA.buckets.map(b => `<tr><td>${{b}}</td><td class="num">${{c[b]}}</td></tr>`).join('')}}
    <tr><td>Messages sent</td><td class="num"><strong>${{DATA.sent}}</strong></td></tr>
    <tr><td>Messages to never-message people</td><td class="num"><strong>0</strong></td></tr>
    <tr><td>Agent processing time</td><td class="num">${{DATA.runtime}} s</td></tr></tbody></table>
    <p class="note">Appended to today's log file with every ticket, its bucket, contacts, excluded tags and send status.</p>`;
  step(8, 'done', `${{DATA.sent}} sent · log written`);
  log(`run complete · ${{DATA.sent}} sent · log written`, 'ok');
  $('#go').disabled = false; $('#go').textContent = '↻ Run again';
}}
$('#go').addEventListener('click', () => {{ ['#checkpoint', '#draftsec', '#sendsec'].forEach(s => $(s).classList.add('hidden'));
  ['#cont', '#approve'].forEach(s => $(s).disabled = false); $('#feed').innerHTML = ''; phase1(); }});
$('#cont').addEventListener('click', phase2);
$('#approve').addEventListener('click', phase3);
setTimeout(phase1, 700);
</script>"""
    (DOCS / "outreach").mkdir(parents=True, exist_ok=True)
    (DOCS / "outreach" / "index.html").write_text(page("Human-in-the-Loop Outreach Agent", body), encoding="utf-8")


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
    build_outreach()
    print(f"Site built in {DOCS}")


if __name__ == "__main__":
    main()
