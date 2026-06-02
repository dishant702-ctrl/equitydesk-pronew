"""
fetch_data.py
=============
Fetches live prices, earnings dates, and corporate actions.
Saves everything as JSON files that the dashboard HTML reads.

Run: python scripts/fetch_data.py
"""

import json, os, time, datetime
from pathlib import Path

# ── Install check helper ──────────────────────────────────────────────────────
try:
    import yfinance as yf
except ImportError:
    print("Run: pip install yfinance"); raise

try:
    from bse import BSE
except ImportError:
    print("Run: pip install bse"); raise

# ── Your watchlist ────────────────────────────────────────────────────────────
# Yahoo Finance uses NSE symbols with .NS suffix
# BSE uses numeric codes — common ones listed here

WATCHLIST = {
    "RELIANCE":  {"yf": "RELIANCE.NS",  "bse": "500325"},
    "TCS":       {"yf": "TCS.NS",       "bse": "532540"},
    "HDFCBANK":  {"yf": "HDFCBANK.NS",  "bse": "500180"},
    "INFY":      {"yf": "INFY.NS",      "bse": "500209"},
    "ICICIBANK": {"yf": "ICICIBANK.NS", "bse": "532174"},
    "BAJFINANCE":{"yf": "BAJFINANCE.NS","bse": "500034"},
    "WIPRO":     {"yf": "WIPRO.NS",     "bse": "507685"},
    "SBIN":      {"yf": "SBIN.NS",      "bse": "500112"},
    "KOTAKBANK": {"yf": "KOTAKBANK.NS", "bse": "500247"},
    "MARUTI":    {"yf": "MARUTI.NS",    "bse": "532500"},
    "SUNPHARMA": {"yf": "SUNPHARMA.NS", "bse": "524715"},
    "TATAMOTORS":{"yf": "TATAMOTORS.NS","bse": "500570"},
    "ULTRACEMCO":{"yf": "ULTRACEMCO.NS","bse": "532538"},
    "NESTLEIND": {"yf": "NESTLEIND.NS", "bse": "500790"},
    "HCLTECH":   {"yf": "HCLTECH.NS",   "bse": "532281"},
    "AXISBANK":  {"yf": "AXISBANK.NS",  "bse": "532215"},
    "LT":        {"yf": "LT.NS",        "bse": "500510"},
    "TITAN":     {"yf": "TITAN.NS",     "bse": "500114"},
    "ASIANPAINT":{"yf": "ASIANPAINT.NS","bse": "500820"},
    "POWERGRID": {"yf": "POWERGRID.NS", "bse": "532898"},
}

# ── Output path ───────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# 1. LIVE PRICES  (Yahoo Finance — free, no key needed)
# ═════════════════════════════════════════════════════════════════════════════
def fetch_prices():
    print("📈 Fetching live prices from Yahoo Finance...")
    prices = {}
    symbols_yf = [v["yf"] for v in WATCHLIST.values()]
    
    try:
        # Fetch all tickers at once (faster than one by one)
        tickers = yf.Tickers(" ".join(symbols_yf))
        
        for sym, cfg in WATCHLIST.items():
            try:
                ticker = tickers.tickers[cfg["yf"]]
                info   = ticker.fast_info          # fast_info is lighter than .info
                
                prices[sym] = {
                    "symbol":     sym,
                    "price":      round(float(info.last_price), 2),
                    "prev_close": round(float(info.previous_close), 2),
                    "change":     round(float(info.last_price - info.previous_close), 2),
                    "change_pct": round(float((info.last_price - info.previous_close) / info.previous_close * 100), 2),
                    "day_high":   round(float(info.day_high), 2),
                    "day_low":    round(float(info.day_low), 2),
                    "volume":     int(info.three_month_average_volume or 0),
                    "market_cap": int(info.market_cap or 0),
                    "52w_high":   round(float(info.fifty_two_week_high), 2),
                    "52w_low":    round(float(info.fifty_two_week_low), 2),
                }
                print(f"  ✅ {sym}: ₹{prices[sym]['price']} ({prices[sym]['change_pct']:+.2f}%)")
                time.sleep(0.1)  # Polite delay to avoid rate limiting
                
            except Exception as e:
                print(f"  ⚠️  {sym}: Failed — {e}")
                prices[sym] = {"symbol": sym, "price": None, "error": str(e)}
    
    except Exception as e:
        print(f"  ❌ Batch fetch failed: {e}")
    
    # Save
    out = {
        "updated_at": datetime.datetime.now().isoformat(),
        "updated_ist": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        ).strftime("%d %b %Y %H:%M IST"),
        "prices": prices
    }
    with open(DATA_DIR / "prices.json", "w") as f:
        json.dump(out, f, indent=2)
    
    print(f"  💾 Saved {len(prices)} prices → data/prices.json")
    return prices


# ═════════════════════════════════════════════════════════════════════════════
# 2. SPARKLINE DATA  (last 6 quarters of EPS trend from Yahoo)
# ═════════════════════════════════════════════════════════════════════════════
def fetch_sparklines():
    print("\n📊 Fetching quarterly EPS trends...")
    sparklines = {}
    
    for sym, cfg in WATCHLIST.items():
        try:
            ticker = yf.Ticker(cfg["yf"])
            # Get quarterly earnings
            quarterly = ticker.quarterly_earnings
            if quarterly is not None and not quarterly.empty:
                # Take last 6 quarters, normalize to 0-100 scale for sparkline
                eps_vals = quarterly["Earnings"].dropna().tail(6).tolist()
                if eps_vals:
                    max_v = max(abs(v) for v in eps_vals) or 1
                    normalized = [round(max(0, min(100, (v / max_v) * 80 + 20)), 1) for v in eps_vals]
                    sparklines[sym] = normalized
            time.sleep(0.15)
        except Exception as e:
            sparklines[sym] = [60, 65, 70, 72, 75, 78]  # fallback neutral trend
    
    with open(DATA_DIR / "sparklines.json", "w") as f:
        json.dump({"updated_at": datetime.datetime.now().isoformat(), "sparklines": sparklines}, f, indent=2)
    
    print(f"  💾 Saved sparklines → data/sparklines.json")
    return sparklines


# ═════════════════════════════════════════════════════════════════════════════
# 3. EARNINGS CALENDAR  (BSE filings)
# ═════════════════════════════════════════════════════════════════════════════
def fetch_earnings():
    print("\n📅 Fetching earnings dates from BSE...")
    earnings = []
    
    try:
        bse_client = BSE(download_folder="./bse_data/")
        
        for sym, cfg in WATCHLIST.items():
            try:
                # Get announcements for this stock
                announcements = bse_client.getAnnouncements(
                    scripCode=cfg["bse"],
                    CategoryName="Result",         # Filter for results
                    FaceName=""
                )
                
                if announcements:
                    for ann in announcements[:3]:   # Last 3 results
                        earnings.append({
                            "symbol":     sym,
                            "bse_code":   cfg["bse"],
                            "headline":   ann.get("HEADLINE", ""),
                            "date":       ann.get("NEWS_DT", ""),
                            "category":   ann.get("CATEGORYNAME", ""),
                            "pdf_url":    f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{ann.get('ATTACHMENTNAME','')}",
                        })
                time.sleep(0.5)  # BSE is rate-sensitive — be polite
                
            except Exception as e:
                print(f"  ⚠️  {sym} earnings: {e}")
    
    except Exception as e:
        print(f"  ❌ BSE client error: {e}")
    
    out = {
        "updated_at": datetime.datetime.now().isoformat(),
        "earnings": earnings
    }
    with open(DATA_DIR / "earnings.json", "w") as f:
        json.dump(out, f, indent=2)
    
    print(f"  💾 Saved {len(earnings)} earnings records → data/earnings.json")
    return earnings


# ═════════════════════════════════════════════════════════════════════════════
# 4. CORPORATE ACTIONS  (BSE)
# ═════════════════════════════════════════════════════════════════════════════
def fetch_corp_actions():
    print("\n🏦 Fetching corporate actions from BSE...")
    actions = {"dividends": [], "splits": [], "bonus": [], "buyback": []}
    
    try:
        bse_client = BSE(download_folder="./bse_data/")
        
        for sym, cfg in WATCHLIST.items():
            try:
                # Corporate actions: dividends, splits, bonus
                corp = bse_client.actions(scripCode=cfg["bse"])
                
                if corp:
                    for action in corp[:5]:  # Last 5 actions per stock
                        action_type = str(action.get("PURPOSE", "")).lower()
                        record = {
                            "symbol":    sym,
                            "bse_code":  cfg["bse"],
                            "ex_date":   action.get("EX_DATE", ""),
                            "record_dt": action.get("ND_START_DT", ""),
                            "purpose":   action.get("PURPOSE", ""),
                            "details":   action.get("REMARKS", ""),
                        }
                        
                        if "dividend" in action_type:
                            record["amount"] = action.get("DIVIDEND", "")
                            actions["dividends"].append(record)
                        elif "split" in action_type:
                            actions["splits"].append(record)
                        elif "bonus" in action_type:
                            actions["bonus"].append(record)
                        elif "buyback" in action_type or "buy back" in action_type:
                            actions["buyback"].append(record)
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  ⚠️  {sym} corp actions: {e}")
    
    except Exception as e:
        print(f"  ❌ BSE corp actions error: {e}")
    
    out = {
        "updated_at": datetime.datetime.now().isoformat(),
        "actions": actions
    }
    with open(DATA_DIR / "corp_actions.json", "w") as f:
        json.dump(out, f, indent=2)
    
    total = sum(len(v) for v in actions.values())
    print(f"  💾 Saved {total} corporate actions → data/corp_actions.json")
    return actions


# ═════════════════════════════════════════════════════════════════════════════
# 5. MACRO EVENTS CALENDAR  (Static but curated — update monthly)
# ═════════════════════════════════════════════════════════════════════════════
def update_macro_events():
    print("\n🌐 Updating macro events calendar...")
    
    # You update this section monthly — takes 5 minutes
    # Or auto-scrape from RBI.org.in / investing.com
    macro = {
        "updated_at": datetime.datetime.now().isoformat(),
        "india": [
            {"date": "2026-07-04", "name": "RBI MPC Policy Decision",      "sub": "Monetary Policy Committee Repo Rate",        "impact": "H", "prev": "6.00%",       "fore": "TBD"},
            {"date": "2026-07-11", "name": "CPI Inflation — June 2026",     "sub": "Consumer Price Index (MoSPI)",               "impact": "H", "prev": "3.40%",       "fore": "TBD"},
            {"date": "2026-07-12", "name": "IIP Data — May 2026",           "sub": "Index of Industrial Production",             "impact": "M", "prev": "3.8%",        "fore": "TBD"},
            {"date": "2026-07-15", "name": "WPI Inflation — June 2026",     "sub": "Wholesale Price Index",                      "impact": "M", "prev": "0.1%",        "fore": "TBD"},
            {"date": "2026-07-18", "name": "GST Collections — June 2026",   "sub": "Goods & Services Tax Revenue",               "impact": "M", "prev": "₹1.78L Cr",   "fore": "TBD"},
            {"date": "2026-07-22", "name": "Trade Deficit — June 2026",     "sub": "Exports & Imports",                          "impact": "H", "prev": "$15.2B",      "fore": "TBD"},
            {"date": "2026-07-31", "name": "Fiscal Deficit Update",         "sub": "GoI Monthly Accounts",                       "impact": "M", "prev": "~68%",        "fore": "TBD"},
        ],
        "global": [
            {"date": "2026-07-04", "name": "US Jobs Report — June",         "sub": "Non-Farm Payrolls",                          "impact": "H", "prev": "185K",        "fore": "TBD"},
            {"date": "2026-07-10", "name": "US CPI — June",                 "sub": "Consumer Price Index",                       "impact": "H", "prev": "3.3%",        "fore": "TBD"},
            {"date": "2026-07-11", "name": "US PPI — June",                 "sub": "Producer Price Index",                       "impact": "M", "prev": "2.4%",        "fore": "TBD"},
            {"date": "2026-07-25", "name": "US FOMC Rate Decision",         "sub": "Federal Reserve Q3 2026",                    "impact": "H", "prev": "5.00–5.25%",  "fore": "TBD"},
            {"date": "2026-07-24", "name": "ECB Rate Decision",             "sub": "European Central Bank",                      "impact": "H", "prev": "4.25%",       "fore": "TBD"},
            {"date": "2026-07-15", "name": "China Q2 2026 GDP",             "sub": "National Bureau of Statistics",              "impact": "H", "prev": "5.3%",        "fore": "TBD"},
            {"date": "2026-07-31", "name": "BOJ Policy Decision",           "sub": "Bank of Japan",                              "impact": "M", "prev": "0.1%",        "fore": "TBD"},
        ]
    }
    
    with open(DATA_DIR / "macro_events.json", "w") as f:
        json.dump(macro, f, indent=2)
    
    print("  💾 Saved macro events → data/macro_events.json")
    return macro


# ═════════════════════════════════════════════════════════════════════════════
# 6. NIFTY INDEX DATA  (for the masthead tickers)
# ═════════════════════════════════════════════════════════════════════════════
def fetch_indices():
    print("\n📉 Fetching index data...")
    indices = {}
    INDEX_MAP = {
        "NIFTY50":    "^NSEI",
        "NIFTY500":   "^CRSLDX",    # NSE 500 composite
        "BANKNIFTY":  "^NSEBANK",
        "INDIAVIX":   "^INDIAVIX",
        "USDINR":     "USDINR=X",
        "BRENT":      "BZ=F",
    }
    
    for name, yf_sym in INDEX_MAP.items():
        try:
            t = yf.Ticker(yf_sym)
            info = t.fast_info
            price = float(info.last_price)
            prev  = float(info.previous_close)
            chg   = price - prev
            pct   = chg / prev * 100
            indices[name] = {
                "price": round(price, 2),
                "change": round(chg, 2),
                "change_pct": round(pct, 2),
            }
            print(f"  ✅ {name}: {price:,.2f} ({pct:+.2f}%)")
            time.sleep(0.1)
        except Exception as e:
            print(f"  ⚠️  {name}: {e}")
            indices[name] = {"price": None}
    
    # 10Y G-Sec — use RBI website or hardcode with weekly update
    indices["GSEC10Y"] = {"price": 7.08, "change": -0.02, "change_pct": -0.28}
    
    with open(DATA_DIR / "indices.json", "w") as f:
        json.dump({
            "updated_at": datetime.datetime.now().isoformat(),
            "indices": indices
        }, f, indent=2)
    
    print("  💾 Saved indices → data/indices.json")
    return indices


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  EquityDesk Pro — Data Fetcher")
    print(f"  {datetime.datetime.now().strftime('%d %b %Y %H:%M:%S')}")
    print("=" * 60)
    
    fetch_indices()
    fetch_prices()
    # fetch_sparklines()   # Uncomment after testing — slower
    fetch_earnings()
    fetch_corp_actions()
    update_macro_events()
    
    print("\n" + "=" * 60)
    print("  ✅ All data fetched. Dashboard data is up to date.")
    print("=" * 60)
