"""Turn computed bridges into a review-ready Markdown document.

Three audiences, one source of numbers:
  1. Leadership bridge  - short paragraphs: what moved, why, what we are doing
  2. Speakable version  - plain sentences someone can read out in the meeting
  3. Supporting tables  - drivers, SLA misses, repeat sites, data anomalies
"""
from __future__ import annotations

from bridge import RateBridge, SlaBridge


def pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def signed_bps(v: int | None) -> str:
    return "n/a" if v is None else f"{v:+d} bps"


def direction(v: int | None, higher_is_bad: bool = True) -> str:
    if not v:
        return "was flat"
    up = v > 0
    word = "rose" if up else "fell"
    return f"{word} {abs(v)} bps"


def _top_drivers(b: RateBridge, n: int = 2) -> str:
    moving = [d for d in b.drivers if d.contribution_bps][:n]
    if not moving:
        return "no single driver stood out"
    parts = [f"{d.name or 'Unspecified'} ({d.prev} to {d.cur}, {d.contribution_bps:+d} bps)" for d in moving]
    return " and ".join(parts)


def leadership(rate: RateBridge, invalid: RateBridge, sla: SlaBridge, target: float) -> str:
    causes = {}
    for m in sla.misses:
        causes[m.cause] = causes.get(m.cause, 0) + 1
    cause_txt = ", ".join(f"{n} {c.lower()}" for c, n in sorted(causes.items(), key=lambda kv: -kv[1])) or "none"
    repeat = sla.repeat_sites()
    repeat_txt = (" Site " + ", ".join(f"{s} ({n} misses)" for s, n in repeat) +
                  " held tickets waiting on its input and is flagged for follow-up.") if repeat else ""
    sla_rate = sla.rate
    gap = "above" if sla_rate is not None and sla_rate >= target else "below"
    return (
        f"**{rate.line}.** The dispute rate {direction(rate.change_bps)} week over week to {pct(rate.cur_rate)} "
        f"({rate.cur_n} disputes on {rate.cur_base} eligible combinations), driven by {_top_drivers(rate)}. "
        f"The invalid rate {direction(invalid.change_bps)} to {pct(invalid.cur_rate)}; the main rejection reasons "
        f"moving were {_top_drivers(invalid)}. "
        f"SLA performance was {pct(sla_rate)}, {gap} the {pct(target)} target "
        f"({sla.met} met, {sla.missed} missed, {sla.open_in_sla} still open within SLA). "
        f"Missed tickets break down as {cause_txt}.{repeat_txt}"
    )


def speakable(rate: RateBridge, sla: SlaBridge) -> str:
    top = next((d for d in rate.drivers if d.contribution_bps), None)
    driver = f" mostly from {top.name.lower()}" if top else ""
    return (f"For {rate.line}, the dispute rate {direction(rate.change_bps)} to {pct(rate.cur_rate)}{driver}. "
            f"We resolved {pct(sla.rate)} of disputes within SLA, with {sla.missed} misses this week.")


def driver_table(b: RateBridge) -> str:
    rows = [f"| {d.name or 'Unspecified'} | {d.prev} | {d.cur} | {d.contribution_bps:+d} |" for d in b.drivers]
    total = f"| **Total** | **{b.prev_n}** | **{b.cur_n}** | **{signed_bps(b.change_bps)}** |"
    return "\n".join([f"| Driver | Prev wk | This wk | Contribution (bps) |", "|---|---:|---:|---:|", *rows, total])


def miss_table(sla: SlaBridge) -> str:
    if not sla.misses:
        return "_No SLA misses._"
    rows = [f"| {m.ticket_id} | {m.station} | {m.partner} | {m.cause} | {m.hours_late} |" for m in sla.misses]
    return "\n".join(["| Ticket | Site | Partner | Root cause | Hours late |", "|---|---|---|---|---:|", *rows])


def build_document(week: int, sections: list[tuple[RateBridge, RateBridge, SlaBridge]],
                   notes: list[str], target: float) -> str:
    out = [f"# Weekly Business Review: dispute bridges, week {week}", "",
           "_Generated from synthetic demo data._", "", "## 1. Leadership bridge", ""]
    for rate, invalid, sla in sections:
        out += [leadership(rate, invalid, sla, target), ""]
    out += ["## 2. Speakable version", ""]
    out += [speakable(rate, sla) for rate, _, sla in sections]
    out += ["", "## 3. Supporting tables", ""]
    for rate, invalid, sla in sections:
        out += [f"### {rate.line}", "", "**Dispute rate drivers (by use case)**", "", driver_table(rate), "",
                "**Invalid disputes by rejection reason**", "", driver_table(invalid), "",
                f"**SLA misses, week {week}**", "", miss_table(sla), ""]
    out += ["## 4. Anomalies and data notes", ""]
    out += [f"- {n}" for n in notes] or ["- None found."]
    return "\n".join(out) + "\n"
