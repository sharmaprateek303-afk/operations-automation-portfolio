"""Excel output: Summary sheet first, then one sheet per invoice.

Each invoice sheet has the raw invoice on the left and the automated
validation on the right, colour-coded so a reviewer can see at a glance which
lines need attention:
  green = matched, blue = matched via fallback rule, red = needs review.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from recon import InvoiceResult

GREEN = PatternFill("solid", fgColor="C6EFCE")
RED = PatternFill("solid", fgColor="FFC7CE")
BLUE = PatternFill("solid", fgColor="BDD7EE")
YELLOW = PatternFill("solid", fgColor="FFF2CC")
HEADER = PatternFill("solid", fgColor="1F4E78")
BOLD = Font(bold=True)
WHITE_BOLD = Font(bold=True, color="FFFFFF")
STATUS_FILL = {"Y": GREEN, "Y (fallback)": BLUE, "N": RED}


def _sheet_name(inv: dict, used: set[str]) -> str:
    base = f"{inv['station']}-{inv['partner']}-{inv['invoice_id'][-4:]}"[:31]
    name, n = base, 2
    while name in used:
        name = f"{base[:28]}~{n}"
        n += 1
    used.add(name)
    return name


def _write_summary(wb: Workbook, results: list[InvoiceResult]) -> None:
    ws = wb.active
    ws.title = "Summary"
    heads = ["Country", "Station", "Partner", "Invoice", "Status", "Lines to review", "Notes"]
    for c, h in enumerate(heads, 1):
        cell = ws.cell(1, c, h)
        cell.font, cell.fill = WHITE_BOLD, HEADER
    for r, res in enumerate(results, 2):
        inv = res.invoice
        notes = "; ".join(f"{l.reason}: {l.evidence}" for l in res.open_lines)
        vals = [inv["country"], inv["station"], inv["partner_name"], inv["invoice_id"], res.status, len(res.open_lines), notes]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(r, c, v)
            cell.fill = STATUS_FILL.get(res.status, YELLOW)
    for col, width in zip("ABCDEFG", [9, 10, 24, 18, 13, 15, 80]):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{len(results) + 1}"


def _write_invoice(ws, res: InvoiceResult) -> None:
    inv = res.invoice
    ws.cell(1, 1, f"{inv['invoice_id']}  |  {inv['station']} / {inv['partner_name']}  |  {inv['week']}").font = BOLD
    # Left: raw invoice lines.
    for c, h in enumerate(["Reason", "Date", "Qty", "Rate", "Amount"], 1):
        cell = ws.cell(2, c, h)
        cell.font, cell.fill = BOLD, YELLOW
    r = 3
    for line in inv["lines"]:
        for c, v in enumerate([line["reason"], line["date"], line["qty"], line["rate"], line["amount"]], 1):
            ws.cell(r, c, v)
        r += 1
    ws.cell(r, 1, "Total").font = BOLD
    ws.cell(r, 5, round(sum(l["amount"] for l in inv["lines"]), 2)).font = BOLD

    # Right: validation by service type.
    for c, h in enumerate(["Line", "Invoiced", "Evidence", "Result"], 7):
        cell = ws.cell(2, c, h)
        cell.font, cell.fill = BOLD, YELLOW
    for i, line in enumerate(res.lines, 3):
        result = "NA" if line.matched is None else ("Matched (fallback)" if line.used_fallback else "Matched" if line.matched else "Review")
        for c, v in enumerate([line.reason, line.invoiced, line.evidence, result], 7):
            ws.cell(i, c, v)
        if line.matched is not None:
            fill = BLUE if line.used_fallback else GREEN if line.matched else RED
            for c in range(7, 11):
                ws.cell(i, c).fill = fill
    for col, width in {1: 44, 2: 11, 3: 8, 4: 9, 5: 11, 7: 44, 8: 10, 9: 52, 10: 18}.items():
        ws.column_dimensions[get_column_letter(col)].width = width
    for row in ws.iter_rows(min_row=3, min_col=8, max_col=8):
        for cell in row:
            cell.alignment = Alignment(horizontal="right")
    ws.freeze_panes = "A3"
    if res.status == "N":
        ws.sheet_properties.tabColor = "C00000"
    elif res.status.startswith("Y"):
        ws.sheet_properties.tabColor = "00B050"


def write_workbook(results: list[InvoiceResult], path: Path) -> Path:
    results = sorted(results, key=lambda r: (r.invoice["country"], r.invoice["station"], r.invoice["partner"]))
    wb = Workbook()
    _write_summary(wb, results)
    used: set[str] = set()
    for res in results:
        _write_invoice(wb.create_sheet(_sheet_name(res.invoice, used)), res)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def split_for_reviewers(results: list[InvoiceResult], reviewers: list[str]) -> dict[str, list[InvoiceResult]]:
    """Balance manual review by workload (open lines), not just invoice count."""
    queues = {name: [] for name in reviewers}
    load = {name: 0 for name in reviewers}
    for res in sorted(results, key=lambda r: len(r.open_lines), reverse=True):
        name = min(reviewers, key=lambda n: (load[n], len(queues[n])))
        queues[name].append(res)
        load[name] += len(res.open_lines)
    return queues
