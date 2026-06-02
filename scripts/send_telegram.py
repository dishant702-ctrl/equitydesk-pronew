"""
send_telegram.py
================
Sends the daily PDF briefing + summary message to your Telegram group.

Run: python scripts/send_telegram.py
Requires: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as env variables
          (set in GitHub Secrets, or in a .env file locally)
"""

import os, json, datetime, glob
from pathlib import Path

try:
    import requests
except ImportError:
    print("Run: pip install requests"); raise


# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError(
        "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as environment variables.\n"
        "Locally: export TELEGRAM_BOT_TOKEN=your_token\n"
        "GitHub Actions: add as repository secrets"
    )

DATA_DIR = Path("data")
OUT_DIR  = Path("output")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── Load data ─────────────────────────────────────────────────────────────────
def load(filename):
    try:
        with open(DATA_DIR / filename) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# ── Build summary message ─────────────────────────────────────────────────────
def build_message():
    prices_data  = load("prices.json")
    indices_data = load("indices.json")
    corp_data    = load("corp_actions.json")

    prices  = prices_data.get("prices", {})
    indices = indices_data.get("indices", {})

    now  = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    date = now.strftime("%d %b %Y")
    time = now.strftime("%H:%M IST")

    def idx_line(name, key, invert=False):
        d = indices.get(key, {})
        p = d.get("price")
        c = d.get("change_pct")
        if p is None:
            return f"  {name}: —"
        arrow = "🔴" if (c or 0) < 0 else "🟢"
        if invert:
            arrow = "🟢" if (c or 0) < 0 else "🔴"
        sign = "+" if (c or 0) >= 0 else ""
        return f"  {arrow} *{name}:* `{p:,.2f}` ({sign}{c:.2f}%)"

    def stock_line(sym):
        d = prices.get(sym, {})
        p = d.get("price")
        c = d.get("change_pct")
        if p is None:
            return f"  {sym}: —"
        arrow = "📈" if (c or 0) >= 0 else "📉"
        sign  = "+" if (c or 0) >= 0 else ""
        return f"  {arrow} *{sym}:* `₹{p:,.2f}` ({sign}{c:.2f}%)"

    # Count upcoming events
    divs     = len(corp_data.get("actions", {}).get("dividends", []))
    splits   = len(corp_data.get("actions", {}).get("splits", []))

    lines = [
        f"📊 *EquityDesk Daily Briefing*",
        f"🗓 *{date}* | ⏰ {time}",
        f"",
        f"━━━━━━━━━━━━━━━━━",
        f"🏦 *MARKET SNAPSHOT*",
        f"━━━━━━━━━━━━━━━━━",
        idx_line("Nifty 50",   "NIFTY50"),
        idx_line("Nifty 500",  "NIFTY500"),
        idx_line("Bank Nifty", "BANKNIFTY"),
        idx_line("India VIX",  "INDIAVIX",  invert=True),
        idx_line("USD/INR",    "USDINR"),
        idx_line("Brent",      "BRENT"),
        f"",
        f"━━━━━━━━━━━━━━━━━",
        f"📈 *PORTFOLIO WATCHLIST*",
        f"━━━━━━━━━━━━━━━━━",
        stock_line("RELIANCE"),
        stock_line("TCS"),
        stock_line("HDFCBANK"),
        stock_line("INFY"),
        stock_line("ICICIBANK"),
        stock_line("BAJFINANCE"),
        f"",
        f"━━━━━━━━━━━━━━━━━",
        f"🗓 *UPCOMING EVENTS*",
        f"━━━━━━━━━━━━━━━━━",
        f"  📋 *Earnings:* RELIANCE (Jun 07), TCS (Jun 10), HDFCBANK (Jun 12)",
        f"  💰 *Dividends:* {divs} ex-dates this month",
        f"  ✂️ *Splits:* {splits} upcoming this month",
        f"  🏛 *RBI MPC:* Jun 04 — Rate decision expected",
        f"  🇺🇸 *FOMC:* Jun 25 — Potential rate cut",
        f"",
        f"━━━━━━━━━━━━━━━━━",
        f"📄 *Full PDF briefing attached above* ↑",
        f"🔬 AI-powered analysis available on the dashboard",
        f"",
        f"_EquityDesk Pro · Research only · Not investment advice_",
    ]

    return "\n".join(lines)


# ── Telegram API calls ────────────────────────────────────────────────────────
def send_message(text):
    """Send a text message."""
    r = requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id":    CHAT_ID,
            "text":       text,
            "parse_mode": "Markdown",
        },
        timeout=30
    )
    r.raise_for_status()
    return r.json()


def send_pdf(pdf_path):
    """Send the PDF file."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"  ❌ PDF not found: {pdf_path}")
        return None

    print(f"  📤 Uploading {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)...")

    now  = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    caption = (
        f"📊 *EquityDesk Daily Briefing* — {now.strftime('%d %b %Y')}\n"
        f"Nifty 500 · Earnings · Corp Actions · Macro Events\n"
        f"_For research only. Not investment advice._"
    )

    with open(pdf_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/sendDocument",
            data={
                "chat_id":    CHAT_ID,
                "caption":    caption,
                "parse_mode": "Markdown",
            },
            files={"document": (pdf_path.name, f, "application/pdf")},
            timeout=60
        )
    r.raise_for_status()
    print(f"  ✅ PDF sent successfully")
    return r.json()


def send_divider():
    """Send a clean section separator."""
    send_message("─" * 25)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  EquityDesk Pro — Telegram Sender")
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    print(f"  {now.strftime('%d %b %Y %H:%M IST')}")
    print("=" * 50)

    # 1. Find the latest PDF
    pdfs = sorted(OUT_DIR.glob("EquityDesk-Briefing-*.pdf"), reverse=True)
    if not pdfs:
        print("  ❌ No PDF found in output/. Run generate_pdf.py first.")
        return

    latest_pdf = pdfs[0]
    print(f"\n  📄 Using PDF: {latest_pdf.name}")

    # 2. Send PDF first
    print("\n  Step 1: Sending PDF...")
    send_pdf(latest_pdf)

    # 3. Send summary message
    print("\n  Step 2: Sending summary message...")
    msg = build_message()
    send_message(msg)

    print("\n  ✅ All sent to Telegram group!")
    print("=" * 50)


if __name__ == "__main__":
    main()
