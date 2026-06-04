"""
fetch_data.py — EquityDesk Pro
================================
Fetches ALL live data:
- Index prices (Nifty 50, 500, Bank Nifty, VIX, USD/INR, Brent, G-Sec)
- Stock prices + change % for all watchlist stocks
- Earnings dates from BSE
- Corporate actions (dividends, splits, bonus, buyback) from BSE
- Macro events calendar (static monthly update)
- Portfolio P&L calculations

Saves everything as JSON in data/ folder.
GitHub Actions reads these and commits back to repo.
Dashboard HTML fetches these JSON files every 5 minutes.
"""

import json, os, time, datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("Run: pip install yfinance"); raise

try:
    from bse import BSE
except ImportError:
    print("Run: pip install bse"); raise

# ── YOUR PORTFOLIO ─────────────────────────────────────────────────────────────
# Update avg_cost with your actual buy prices
PORTFOLIO = {
    "RELIANCE":   {"qty": 50,  "avg_cost": 2640},
    "HDFCBANK":   {"qty": 80,  "avg_cost": 1580},
    "INFY":       {"qty": 70,  "avg_cost": 1680},
    "TCS":        {"qty": 30,  "avg_cost": 3820},
    "ITC":        {"qty": 200, "avg_cost": 420},
    "BAJFINANCE": {"qty": 15,  "avg_cost": 7200},
    "ICICIBANK":  {"qty": 100, "avg_cost": 940},
    "AXISBANK":   {"qty": 90,  "avg_cost": 1050},
}

# ── WATCHLIST ──────────────────────────────────────────────────────────────────
WATCHLIST = {
    "RELIANCE":   {"yf": "RELIANCE.NS",   "bse": "500325"},
    "TCS":        {"yf": "TCS.NS",        "bse": "532540"},
    "HDFCBANK":   {"yf": "HDFCBANK.NS",   "bse": "500180"},
    "INFY":       {"yf": "INFY.NS",       "bse": "500209"},
    "ICICIBANK":  {"yf": "ICICIBANK.NS",  "bse": "532174"},
    "BAJFINANCE": {"yf": "BAJFINANCE.NS", "bse": "500034"},
    "WIPRO":      {"yf": "WIPRO.NS",      "bse": "507685"},
    "SBIN":       {"yf": "SBIN.NS",       "bse": "500112"},
    "KOTAKBANK":  {"yf": "KOTAKBANK.NS",  "bse": "500247"},
    "MARUTI":     {"yf": "MARUTI.NS",     "bse": "532500"},
    "SUNPHARMA":  {"yf": "SUNPHARMA.NS",  "bse": "524715"},
    "TATAMOTORS": {"yf": "TATAMOTORS.NS", "bse": "500570"},
    "ULTRACEMCO": {"yf": "ULTRACEMCO.NS", "bse": "532538"},
    "NESTLEIND":  {"yf": "NESTLEIND.NS",  "bse": "500790"},
    "HCLTECH":    {"yf": "HCLTECH.NS",    "bse": "532281"},
    "AXISBANK":   {"yf": "AXISBANK.NS",   "bse": "532215"},
    "LT":         {"yf": "LT.NS",         "bse": "500510"},
    "TITAN":      {"yf": "TITAN.NS",      "bse": "500114"},
    "ASIANPAINT": {"yf": "ASIANPAINT.NS", "bse": "500820"},
    "ITC":        {"yf": "ITC.NS",        "bse": "500875"},
    "POWERGRID":  {"yf": "POWERGRID.NS",  "bse": "532898"},
    "COALINDIA":  {"yf": "COALINDIA.NS",  "bse": "533278"},
}

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def now_ist():
    return datetime.datetime.now(IST)

def save(filename, data):
    with open(DATA_DIR / filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  💾 Saved → data/{filename}")


# ══════════════════════════════════════════════════════════════════════════════
# 1. INDICES
# ══════════════════════════════════════════════════════════════════════════════
def fetch_indices():
    print("\n📉 Fetching indices...")
    INDEX_MAP = {
        "NIFTY50":   "^NSEI",
        "NIFTY500":  "^CRSLDX",
        "BANKNIFTY": "^NSEBANK",
        "INDIAVIX":  "^INDIAVIX",
        "USDINR":    "USDINR=X",
        "BRENT":     "BZ=F",
    }
    indices = {}
    for name, sym in INDEX_MAP.items():
        try:
            t    = yf.Ticker(sym)
            info = t.fast_info
            p    = float(info.last_price)
            prev = float(info.previous_close)
            chg  = round(p - prev, 2)
            pct  = round((p - prev) / prev * 100, 2)
            indices[name] = {"price": round(p, 2), "change": chg, "change_pct": pct}
            print(f"  ✅ {name}: {p:,.2f} ({pct:+.2f}%)")
            time.sleep(0.15)
        except Exception as e:
            print(f"  ⚠️  {name}: {e}")
            indices[name] = {"price": None}

    # 10Y G-Sec — approximate from NSEI or hardcode weekly
    indices["GSEC10Y"] = {"price": 7.08, "change": -0.02, "change_pct": -0.28}

    save("indices.json", {
        "updated_at":  now_ist().isoformat(),
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "indices":     indices
    })
    return indices


# ══════════════════════════════════════════════════════════════════════════════
# 2. STOCK PRICES
# ══════════════════════════════════════════════════════════════════════════════
def fetch_prices():
    print("\n📈 Fetching stock prices...")
    prices = {}
    for sym, cfg in WATCHLIST.items():
        try:
            t    = yf.Ticker(cfg["yf"])
            info = t.fast_info
            p    = float(info.last_price)
            prev = float(info.previous_close)
            chg  = round(p - prev, 2)
            pct  = round((p - prev) / prev * 100, 2)
            prices[sym] = {
                "price":      round(p, 2),
                "prev_close": round(prev, 2),
                "change":     chg,
                "change_pct": pct,
                "day_high":   round(float(info.day_high), 2),
                "day_low":    round(float(info.day_low), 2),
                "52w_high":   round(float(info.fifty_two_week_high), 2),
                "52w_low":    round(float(info.fifty_two_week_low), 2),
                "market_cap": int(info.market_cap or 0),
            }
            print(f"  ✅ {sym}: ₹{p:,.2f} ({pct:+.2f}%)")
            time.sleep(0.1)
        except Exception as e:
            print(f"  ⚠️  {sym}: {e}")
            prices[sym] = {"price": None, "error": str(e)}

    save("prices.json", {
        "updated_at":  now_ist().isoformat(),
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "prices":      prices
    })
    return prices


# ══════════════════════════════════════════════════════════════════════════════
# 3. PORTFOLIO P&L
# ══════════════════════════════════════════════════════════════════════════════
def calculate_portfolio(prices):
    print("\n💼 Calculating portfolio P&L...")
    holdings   = []
    total_inv  = 0
    total_curr = 0
    total_day  = 0

    for sym, cfg in PORTFOLIO.items():
        p_data = prices.get(sym, {})
        cmp    = p_data.get("price") or cfg["avg_cost"]
        chg    = p_data.get("change_pct") or 0
        qty    = cfg["qty"]
        avg    = cfg["avg_cost"]

        invested    = qty * avg
        curr_val    = qty * cmp
        unreal_pl   = curr_val - invested
        unreal_pct  = round((unreal_pl / invested) * 100, 2)
        day_pl      = round(qty * cmp * chg / 100, 2)

        total_inv  += invested
        total_curr += curr_val
        total_day  += day_pl

        holdings.append({
            "symbol":       sym,
            "qty":          qty,
            "avg_cost":     avg,
            "cmp":          round(cmp, 2),
            "change_pct":   round(chg, 2),
            "invested":     round(invested, 2),
            "current_val":  round(curr_val, 2),
            "unreal_pl":    round(unreal_pl, 2),
            "unreal_pct":   unreal_pct,
            "day_pl":       day_pl,
        })
        print(f"  ✅ {sym}: ₹{cmp:,.2f} | P&L: {unreal_pct:+.1f}%")

    total_pl     = total_curr - total_inv
    total_pl_pct = round((total_pl / total_inv) * 100, 2) if total_inv else 0
    day_pct      = round((total_day / total_curr) * 100, 2) if total_curr else 0

    summary = {
        "total_invested":    round(total_inv, 2),
        "total_current":     round(total_curr, 2),
        "total_pl":          round(total_pl, 2),
        "total_pl_pct":      total_pl_pct,
        "day_pl":            round(total_day, 2),
        "day_pl_pct":        day_pct,
    }

    save("portfolio.json", {
        "updated_at":  now_ist().isoformat(),
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "summary":     summary,
        "holdings":    holdings
    })
    print(f"  📊 Total P&L: ₹{total_pl:,.0f} ({total_pl_pct:+.1f}%)")
    return summary, holdings


# ══════════════════════════════════════════════════════════════════════════════
# 4. EARNINGS DATA FROM BSE
# ══════════════════════════════════════════════════════════════════════════════
def fetch_earnings():
    print("\n📅 Fetching earnings from BSE...")
    earnings = []
    try:
        bse_client = BSE(download_folder="./bse_data/")
        for sym, cfg in WATCHLIST.items():
            try:
                ann = bse_client.getAnnouncements(
                    scripCode=cfg["bse"],
                    CategoryName="Result",
                    FaceName=""
                )
                if ann:
                    for a in ann[:2]:
                        earnings.append({
                            "symbol":   sym,
                            "headline": a.get("HEADLINE", ""),
                            "date":     a.get("NEWS_DT", "")[:10],
                            "category": a.get("CATEGORYNAME", ""),
                            "pdf_url":  "https://www.bseindia.com/xml-data/corpfiling/AttachLive/" + a.get("ATTACHMENTNAME", ""),
                        })
                time.sleep(0.8)
            except Exception as e:
                print(f"  ⚠️  {sym}: {e}")
    except Exception as e:
        print(f"  ❌ BSE error: {e}")

    save("earnings.json", {
        "updated_at": now_ist().isoformat(),
        "earnings":   earnings
    })
    print(f"  ✅ {len(earnings)} earnings records saved")
    return earnings


# ══════════════════════════════════════════════════════════════════════════════
# 5. CORPORATE ACTIONS FROM BSE
# ══════════════════════════════════════════════════════════════════════════════
def fetch_corp_actions():
    print("\n🏦 Fetching corporate actions from BSE...")
    actions = {"dividends": [], "splits": [], "bonus": [], "buyback": []}
    try:
        bse_client = BSE(download_folder="./bse_data/")
        for sym, cfg in WATCHLIST.items():
            try:
                corp = bse_client.actions(scripCode=cfg["bse"])
                if corp:
                    for a in corp[:5]:
                        purpose = str(a.get("PURPOSE", "")).lower()
                        record  = {
                            "symbol":  sym,
                            "ex_date": a.get("EX_DATE", ""),
                            "purpose": a.get("PURPOSE", ""),
                            "details": a.get("REMARKS", ""),
                            "amount":  a.get("DIVIDEND", ""),
                        }
                        if "dividend" in purpose:
                            actions["dividends"].append(record)
                        elif "split" in purpose:
                            actions["splits"].append(record)
                        elif "bonus" in purpose:
                            actions["bonus"].append(record)
                        elif "buyback" in purpose or "buy back" in purpose:
                            actions["buyback"].append(record)
                time.sleep(0.8)
            except Exception as e:
                print(f"  ⚠️  {sym}: {e}")
    except Exception as e:
        print(f"  ❌ BSE corp actions error: {e}")

    total = sum(len(v) for v in actions.values())
    save("corp_actions.json", {
        "updated_at": now_ist().isoformat(),
        "actions":    actions
    })
    print(f"  ✅ {total} corporate actions saved")
    return actions


# ══════════════════════════════════════════════════════════════════════════════
# 6. KPI SUMMARY (derived from real data)
# ══════════════════════════════════════════════════════════════════════════════
def calculate_kpis(prices, portfolio_summary, corp_actions):
    print("\n📊 Calculating KPIs...")
    # Count stocks with positive day change = proxy for market breadth
    up_stocks   = sum(1 for p in prices.values() if (p.get("change_pct") or 0) > 0)
    down_stocks = sum(1 for p in prices.values() if (p.get("change_pct") or 0) < 0)
    total_corp  = sum(len(v) for v in corp_actions.values())

    kpis = {
        "results_this_week":   47,   # Update manually each results season
        "beat_rate":           64,   # Update manually each results season
        "median_rev_growth":   9.4,  # Update manually each results season
        "median_pat_growth":   12.1, # Update manually each results season
        "corporate_actions":   total_corp,
        "high_impact_events":  8,    # From macro calendar
        "portfolio_alerts":    3,    # Count of H-alert holdings
        "up_stocks":           up_stocks,
        "down_stocks":         down_stocks,
        "advance_decline":     f"{up_stocks}/{down_stocks}",
    }

    save("kpis.json", {
        "updated_at": now_ist().isoformat(),
        "kpis":       kpis
    })
    print(f"  ✅ KPIs saved — Up: {up_stocks} / Down: {down_stocks}")
    return kpis


# ══════════════════════════════════════════════════════════════════════════════
# 7. MACRO EVENTS (update dates monthly — takes 5 min)
# ══════════════════════════════════════════════════════════════════════════════
def update_macro_events():
    print("\n🌐 Updating macro events...")
    macro = {
        "updated_at": now_ist().isoformat(),
        "india": [
            {"date":"2026-07-04","name":"RBI MPC Policy Decision",      "sub":"Monetary Policy Committee",           "impact":"H","prev":"6.00%",       "fore":"TBD"},
            {"date":"2026-07-11","name":"CPI Inflation — June 2026",     "sub":"Consumer Price Index (MoSPI)",        "impact":"H","prev":"3.40%",       "fore":"TBD"},
            {"date":"2026-07-12","name":"IIP Data — May 2026",           "sub":"Index of Industrial Production",      "impact":"M","prev":"3.8%",        "fore":"TBD"},
            {"date":"2026-07-15","name":"WPI Inflation — June 2026",     "sub":"Wholesale Price Index",               "impact":"M","prev":"0.1%",        "fore":"TBD"},
            {"date":"2026-07-18","name":"GST Collections — June 2026",   "sub":"Goods & Services Tax Revenue",        "impact":"M","prev":"₹1.78L Cr",   "fore":"TBD"},
            {"date":"2026-07-22","name":"Trade Deficit — June 2026",     "sub":"Exports & Imports",                   "impact":"H","prev":"$15.2B",      "fore":"TBD"},
            {"date":"2026-07-31","name":"Fiscal Deficit Update",         "sub":"GoI Monthly Accounts",                "impact":"M","prev":"~68%",        "fore":"TBD"},
        ],
        "global": [
            {"date":"2026-07-04","name":"US Jobs Report — June",         "sub":"Non-Farm Payrolls",                   "impact":"H","prev":"185K",        "fore":"TBD"},
            {"date":"2026-07-10","name":"US CPI — June",                 "sub":"Consumer Price Index",                "impact":"H","prev":"3.3%",        "fore":"TBD"},
            {"date":"2026-07-15","name":"China Q2 2026 GDP",             "sub":"National Bureau of Statistics",       "impact":"H","prev":"5.3%",        "fore":"TBD"},
            {"date":"2026-07-24","name":"ECB Rate Decision",             "sub":"European Central Bank",               "impact":"H","prev":"4.25%",       "fore":"TBD"},
            {"date":"2026-07-25","name":"US FOMC Rate Decision",         "sub":"Federal Reserve Q3 2026",             "impact":"H","prev":"5.00–5.25%",  "fore":"TBD"},
            {"date":"2026-07-28","name":"US PCE Inflation — June",       "sub":"Personal Consumption Expenditure",    "impact":"H","prev":"2.6%",        "fore":"TBD"},
            {"date":"2026-07-31","name":"BOJ Policy Decision",           "sub":"Bank of Japan",                       "impact":"M","prev":"0.1%",        "fore":"TBD"},
        ]
    }
    save("macro_events.json", macro)
    return macro


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  EquityDesk Pro — Full Data Fetcher")
    print(f"  {now_ist().strftime('%d %b %Y %H:%M IST')}")
    print("=" * 60)

    indices  = fetch_indices()
    prices   = fetch_prices()
    summary, holdings = calculate_portfolio(prices)
    earnings = fetch_earnings()
    corp     = fetch_corp_actions()
    kpis     = calculate_kpis(prices, summary, corp)
    update_macro_events()

    print("\n" + "=" * 60)
    print("  ✅ All data fetched and saved!")
    print(f"  📊 Portfolio Value: ₹{summary['total_current']:,.0f}")
    print(f"  📈 Total P&L: ₹{summary['total_pl']:,.0f} ({summary['total_pl_pct']:+.1f}%)")
    print(f"  📅 Earnings records: {len(earnings)}")
    print("=" * 60)
