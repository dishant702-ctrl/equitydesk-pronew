"""
generate_pdf.py
===============
Generates a professional daily equity briefing PDF.
Uses fpdf2 (free, no external dependencies needed).

Run: python scripts/generate_pdf.py
"""

import json, os, datetime
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("Run: pip install fpdf2"); raise

# ── Load data files ────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
OUT_DIR  = Path("output")
OUT_DIR.mkdir(exist_ok=True)

def load(filename):
    try:
        with open(DATA_DIR / filename) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"  ⚠️  {filename} not found — run fetch_data.py first")
        return {}

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY_DARK  = (5,  14,  30)
NAVY_MID   = (7,  20,  40)
NAVY_CARD  = (13, 30,  56)
NAVY_ROW1  = (8,  21,  40)
NAVY_ROW2  = (11, 26,  48)
GOLD       = (232, 184, 75)
GOLD_DIM   = (180, 140, 55)
GREEN      = (34,  200, 120)
RED        = (255, 92,  106)
TEXT_WHITE = (240, 245, 255)
TEXT_MID   = (196, 212, 238)
TEXT_DIM   = (86,  112, 153)
TEXT_MUTED = (56,  80,  110)


class EquityDeskPDF(FPDF):

    def header(self):
        # Dark header bar
        self.set_fill_color(*NAVY_MID)
        self.rect(0, 0, self.w, 20, "F")
        # Gold accent line
        self.set_fill_color(*GOLD)
        self.rect(0, 20, self.w, 0.6, "F")
        # Logo text
        self.set_xy(10, 5)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*TEXT_WHITE)
        self.cell(0, 8, "EquityDesk Pro", ln=0)
        # Subtitle
        self.set_xy(10, 12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*TEXT_DIM)
        self.cell(0, 5, "DAILY BRIEFING  |  NIFTY 500 INSTITUTIONAL RESEARCH")
        # Date on right
        now   = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        dstr  = now.strftime("%d %b %Y  %H:%M IST")
        self.set_xy(-80, 5)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*TEXT_MID)
        self.cell(70, 6, dstr, align="R")
        self.set_xy(-80, 11)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*TEXT_MUTED)
        self.cell(70, 5, "For research only  |  Not investment advice", align="R")

    def footer(self):
        self.set_y(-10)
        self.set_fill_color(*NAVY_MID)
        self.rect(0, self.h - 10, self.w, 10, "F")
        self.set_fill_color(*GOLD)
        self.rect(0, self.h - 10, self.w, 0.4, "F")
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*TEXT_DIM)
        self.set_x(10)
        self.cell(0, 8, "EquityDesk Pro  ·  Data: BSE / NSE / RBI  ·  AI: Google Gemini  ·  Not investment advice", ln=0)
        self.set_x(-30)
        self.cell(20, 8, f"Page {self.page_no()}", align="R")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def section_title(self, title):
        """Gold-accented section heading."""
        y = self.get_y() + 4
        self.set_fill_color(*GOLD)
        self.rect(10, y, 2, 6, "F")
        self.set_xy(14, y)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*TEXT_WHITE)
        self.cell(0, 6, title)
        self.ln(9)

    def kpi_row(self, kpis):
        """Renders a row of KPI boxes. kpis = list of (label, value, color)."""
        x_start = 10
        box_w   = (self.w - 20) / len(kpis)
        box_h   = 14
        y       = self.get_y()
        for i, (label, value, color) in enumerate(kpis):
            x = x_start + i * box_w
            self.set_fill_color(*NAVY_CARD)
            self.rect(x + 0.5, y, box_w - 1, box_h, "F")
            # Label
            self.set_xy(x + 2, y + 2)
            self.set_font("Helvetica", "B", 7)
            self.set_text_color(*TEXT_DIM)
            self.cell(box_w - 4, 4, label.upper())
            # Value
            self.set_xy(x + 2, y + 6)
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*color)
            self.cell(box_w - 4, 7, value)
        self.ln(box_h + 4)

    def table_header(self, headers, col_widths):
        """Renders a dark table header row."""
        self.set_fill_color(*NAVY_MID)
        total_w = sum(col_widths)
        self.rect(10, self.get_y(), total_w, 7, "F")
        x = 10
        for h, w in zip(headers, col_widths):
            self.set_xy(x + 1.5, self.get_y())
            self.set_font("Helvetica", "B", 7)
            self.set_text_color(*TEXT_DIM)
            self.cell(w - 1.5, 7, h.upper())
            x += w
        self.ln(7)

    def table_row(self, cells, col_widths, row_idx, cell_colors=None):
        """Renders a table row with alternating background."""
        bg = NAVY_ROW1 if row_idx % 2 == 0 else NAVY_ROW2
        total_w = sum(col_widths)
        y = self.get_y()
        self.set_fill_color(*bg)
        self.rect(10, y, total_w, 7, "F")
        x = 10
        for i, (cell, w) in enumerate(zip(cells, col_widths)):
            color = cell_colors[i] if cell_colors and i < len(cell_colors) else TEXT_MID
            self.set_xy(x + 1.5, y)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*color)
            self.cell(w - 1.5, 7, str(cell)[:int(w/1.8)])   # Truncate to fit
            x += w
        self.ln(7)

    def coloured_badge(self, x, y, text, bg_color, text_color):
        self.set_fill_color(*bg_color)
        self.rect(x, y + 1, len(text) * 1.8 + 4, 5, "F")
        self.set_xy(x + 2, y + 1)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(*text_color)
        self.cell(len(text) * 1.8, 5, text)


# ═════════════════════════════════════════════════════════════════════════════
# BUILD PDF
# ═════════════════════════════════════════════════════════════════════════════
def generate_pdf():
    # Load all data
    prices_data  = load("prices.json")
    earn_data    = load("earnings.json")
    corp_data    = load("corp_actions.json")
    macro_data   = load("macro_events.json")
    indices_data = load("indices.json")

    prices  = prices_data.get("prices", {})
    indices = indices_data.get("indices", {})
    actions = corp_data.get("actions", {})
    india_ev = macro_data.get("india", [])
    global_ev = macro_data.get("global", [])

    # Static earnings for now (replace with live data as it comes)
    # In production these come from your BSE scraper + AI analysis
    EARNINGS = [
        ("RELIANCE",   "Energy",  "Jun 07", "2,39,000", "19,400", "28.6",  "+8.2%",  "+11.4%", "Beat"),
        ("TCS",        "IT",      "Jun 10", "62,000",   "12,700", "34.8",  "+6.1%",  "+8.9%",  "Beat"),
        ("HDFCBANK",   "Banking", "Jun 12", "89,400",   "17,200", "22.4",  "+14.2%", "+10.8%", "In-line"),
        ("INFY",       "IT",      "Jun 14", "38,900",   "7,200",  "17.3",  "+5.8%",  "+7.1%",  "Miss"),
        ("ICICIBANK",  "Banking", "Jun 16", "47,200",   "11,600", "16.5",  "+17.4%", "+15.2%", "Beat"),
        ("BAJFINANCE", "NBFC",    "Jun 19", "17,400",   "4,100",  "66.4",  "+22.1%", "+18.7%", "Beat"),
        ("WIPRO",      "IT",      "Jun 21", "22,900",   "3,200",  "6.2",   "+2.1%",  "-3.4%",  "Miss"),
        ("SBIN",       "Banking", "Jun 24", "1,28,000", "21,400", "24.0",  "+9.8%",  "+24.1%", "Beat"),
    ]

    pdf = EquityDeskPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_fill_color(*NAVY_DARK)

    # ── PAGE 1: Overview + Earnings ────────────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*NAVY_DARK)
    pdf.rect(0, 0, pdf.w, pdf.h, "F")
    pdf.set_y(24)

    # KPI Strip
    n50   = indices.get("NIFTY50", {})
    n500  = indices.get("NIFTY500", {})
    bnk   = indices.get("BANKNIFTY", {})
    vix   = indices.get("INDIAVIX", {})
    usdinr= indices.get("USDINR", {})

    def fmt_price(d):
        p = d.get("price")
        return f"{p:,.2f}" if p else "N/A"

    def fmt_chg(d):
        c = d.get("change_pct")
        return (f"+{c:.2f}%" if c and c >= 0 else f"{c:.2f}%") if c else "—"

    pdf.kpi_row([
        ("Nifty 50",     fmt_price(n50),   GREEN if (n50.get("change_pct") or 0) >= 0 else RED),
        ("Nifty 500",    fmt_price(n500),  GREEN if (n500.get("change_pct") or 0) >= 0 else RED),
        ("Bank Nifty",   fmt_price(bnk),   GREEN if (bnk.get("change_pct") or 0) >= 0 else RED),
        ("India VIX",    fmt_price(vix),   RED   if (vix.get("change_pct") or 0) >= 0 else GREEN),
        ("USD/INR",      fmt_price(usdinr),(147, 197, 253)),
        ("Beat Rate Q4", "64%",           GREEN),
        ("Portfolio Alerts", "3",         RED),
    ])

    # Earnings Table
    pdf.section_title("Q4 FY25 Earnings Calendar — Nifty 500")
    headers = ["Symbol", "Sector", "Date", "Revenue ₹Cr", "PAT ₹Cr", "EPS", "Rev YoY", "PAT YoY", "vs Est.", "Live Price", "Chg%"]
    col_w   = [20, 18, 16, 24, 18, 14, 16, 16, 18, 22, 16]

    pdf.table_header(headers, col_w)

    for i, row in enumerate(EARNINGS):
        sym, sector, date, rev, pat, eps, yoy_rev, yoy_pat, vs_est = row
        price_info = prices.get(sym, {})
        live_price = f"₹{price_info.get('price', '—'):,}" if price_info.get('price') else "—"
        chg_pct    = f"{price_info.get('change_pct', 0):+.1f}%" if price_info.get('price') else "—"

        vs_color = GREEN if vs_est == "Beat" else (RED if vs_est == "Miss" else TEXT_DIM)
        rev_color= GREEN if "+" in yoy_rev else RED
        pat_color= GREEN if "+" in yoy_pat else RED
        chg_color= GREEN if "+" in chg_pct else RED

        cells = [sym, sector, date, rev, pat, eps, yoy_rev, yoy_pat, vs_est, live_price, chg_pct]
        colors= [TEXT_WHITE, TEXT_DIM, TEXT_MID, TEXT_MID, TEXT_MID, (147,197,253), rev_color, pat_color, vs_color, TEXT_WHITE, chg_color]
        pdf.table_row(cells, col_w, i, colors)

    # ── PAGE 2: Corporate Actions + Macro ─────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*NAVY_DARK)
    pdf.rect(0, 0, pdf.w, pdf.h, "F")
    pdf.set_y(24)

    # Corporate Actions — Dividends
    pdf.section_title("Corporate Actions — June 2026")
    div_headers = ["Symbol", "Company", "Action", "Amount", "Ex-Date"]
    div_col_w   = [20, 58, 50, 28, 22]
    pdf.table_header(div_headers, div_col_w)

    div_rows = actions.get("dividends", []) or [
        {"symbol":"TCS",      "purpose":"Final Dividend",   "amount":"₹29.00/sh","ex_date":"09 Jun"},
        {"symbol":"INFY",     "purpose":"Final Dividend",   "amount":"₹21.00/sh","ex_date":"13 Jun"},
        {"symbol":"HCLTECH",  "purpose":"Interim Dividend", "amount":"₹12.00/sh","ex_date":"18 Jun"},
        {"symbol":"WIPRO",    "purpose":"Final Dividend",   "amount":"₹1.00/sh", "ex_date":"20 Jun"},
        {"symbol":"COALINDIA","purpose":"Final Dividend",   "amount":"₹5.25/sh", "ex_date":"25 Jun"},
        {"symbol":"POWERGRID","purpose":"Final Dividend",   "amount":"₹7.50/sh", "ex_date":"27 Jun"},
    ]
    co_names = {"TCS":"Tata Consultancy Services","INFY":"Infosys","HCLTECH":"HCL Technologies",
                "WIPRO":"Wipro","COALINDIA":"Coal India","POWERGRID":"Power Grid Corp"}

    for i, d in enumerate(div_rows[:6]):
        sym = d.get("symbol","")
        cells  = [sym, co_names.get(sym, sym), d.get("purpose",""), d.get("amount",""), d.get("ex_date","")]
        colors = [TEXT_WHITE, TEXT_MID, TEXT_DIM, GREEN, TEXT_DIM]
        pdf.table_row(cells, div_col_w, i, colors)

    pdf.ln(4)

    # Macro Events
    pdf.section_title("India Macro Events")
    mac_headers = ["Date", "Event", "Detail", "Previous", "Forecast", "Impact"]
    mac_col_w   = [20, 58, 60, 24, 22, 16]
    pdf.table_header(mac_headers, mac_col_w)

    ev_list = india_ev if india_ev else [
        {"date":"04 Jun","name":"RBI MPC Decision",     "sub":"Repo Rate",                  "prev":"6.25%","fore":"6.00%","impact":"H"},
        {"date":"10 Jun","name":"CPI Inflation — May",  "sub":"Consumer Price Index",        "prev":"3.16%","fore":"3.40%","impact":"H"},
        {"date":"20 Jun","name":"Trade Deficit — May",  "sub":"Commerce Ministry",           "prev":"$14.8B","fore":"$15.2B","impact":"H"},
        {"date":"25 Jun","name":"Q4 FY25 GDP Final",    "sub":"Gross Domestic Product (NSO)","prev":"8.4%","fore":"7.8%","impact":"H"},
    ]

    for i, ev in enumerate(ev_list[:7]):
        impact_color = RED if ev.get("impact")=="H" else (GOLD if ev.get("impact")=="M" else GREEN)
        cells  = [ev.get("date",""), ev.get("name",""), ev.get("sub",""), ev.get("prev",""), ev.get("fore",""), ev.get("impact","")]
        colors = [TEXT_DIM, TEXT_WHITE, TEXT_DIM, TEXT_MID, (147,197,253), impact_color]
        pdf.table_row(cells, mac_col_w, i, colors)

    pdf.ln(4)

    # Global Events
    pdf.section_title("Global Events")
    pdf.table_header(mac_headers, mac_col_w)

    gev_list = global_ev if global_ev else [
        {"date":"04 Jun","name":"US FOMC Minutes",      "sub":"Federal Reserve",            "prev":"5.25-5.50%","fore":"No change","impact":"H"},
        {"date":"06 Jun","name":"US Non-Farm Payrolls", "sub":"Bureau of Labor Statistics", "prev":"175K","fore":"185K","impact":"H"},
        {"date":"12 Jun","name":"ECB Rate Decision",    "sub":"European Central Bank",      "prev":"4.50%","fore":"4.25%","impact":"H"},
        {"date":"25 Jun","name":"US FOMC Rate Decision","sub":"Federal Reserve Q2",         "prev":"5.25-5.50%","fore":"5.00-5.25%","impact":"H"},
    ]

    for i, ev in enumerate(gev_list[:6]):
        impact_color = RED if ev.get("impact")=="H" else (GOLD if ev.get("impact")=="M" else GREEN)
        cells  = [ev.get("date",""), ev.get("name",""), ev.get("sub",""), ev.get("prev",""), ev.get("fore",""), ev.get("impact","")]
        colors = [TEXT_DIM, TEXT_WHITE, TEXT_DIM, TEXT_MID, (147,197,253), impact_color]
        pdf.table_row(cells, mac_col_w, i, colors)

    # ── Save ──────────────────────────────────────────────────────────────────
    now   = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    fname = f"EquityDesk-Briefing-{now.strftime('%Y-%m-%d')}.pdf"
    fpath = OUT_DIR / fname

    pdf.output(str(fpath))
    print(f"\n  ✅ PDF saved → {fpath}")
    return str(fpath)


if __name__ == "__main__":
    print("=" * 50)
    print("  EquityDesk Pro — PDF Generator")
    print("=" * 50)
    path = generate_pdf()
    print(f"\n  Open: {path}")
