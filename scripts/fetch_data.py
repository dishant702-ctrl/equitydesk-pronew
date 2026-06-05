"""
fetch_data.py - EquityDesk Pro
Fetches UPCOMING data automatically from BSE + yfinance
"""
import json, time, datetime, re, xml.etree.ElementTree as ET
from pathlib import Path
import yfinance as yf
import requests
from bs4 import BeautifulSoup

IST      = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
Path("bse_data").mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
    'Accept': 'text/html,application/xhtml+xml,*/*',
    'Accept-Language': 'en-IN,en;q=0.9',
}

WATCHLIST = {
    "RELIANCE":   {"yf":"RELIANCE.NS",   "bse":"500325"},
    "TCS":        {"yf":"TCS.NS",        "bse":"532540"},
    "HDFCBANK":   {"yf":"HDFCBANK.NS",   "bse":"500180"},
    "INFY":       {"yf":"INFY.NS",       "bse":"500209"},
    "ICICIBANK":  {"yf":"ICICIBANK.NS",  "bse":"532174"},
    "BAJFINANCE": {"yf":"BAJFINANCE.NS", "bse":"500034"},
    "WIPRO":      {"yf":"WIPRO.NS",      "bse":"507685"},
    "SBIN":       {"yf":"SBIN.NS",       "bse":"500112"},
    "KOTAKBANK":  {"yf":"KOTAKBANK.NS",  "bse":"500247"},
    "MARUTI":     {"yf":"MARUTI.NS",     "bse":"532500"},
    "SUNPHARMA":  {"yf":"SUNPHARMA.NS",  "bse":"524715"},
    "TATAMOTORS": {"yf":"TATAMOTORS.NS", "bse":"500570"},
    "ULTRACEMCO": {"yf":"ULTRACEMCO.NS", "bse":"532538"},
    "NESTLEIND":  {"yf":"NESTLEIND.NS",  "bse":"500790"},
    "HCLTECH":    {"yf":"HCLTECH.NS",    "bse":"532281"},
    "AXISBANK":   {"yf":"AXISBANK.NS",   "bse":"532215"},
    "ITC":        {"yf":"ITC.NS",        "bse":"500875"},
    "TITAN":      {"yf":"TITAN.NS",      "bse":"500114"},
    "LT":         {"yf":"LT.NS",         "bse":"500510"},
    "ASIANPAINT": {"yf":"ASIANPAINT.NS", "bse":"500820"},
}

PORTFOLIO = {
    "RELIANCE":   {"qty":50,  "avg_cost":2640},
    "HDFCBANK":   {"qty":80,  "avg_cost":1580},
    "INFY":       {"qty":70,  "avg_cost":1680},
    "TCS":        {"qty":30,  "avg_cost":3820},
    "ITC":        {"qty":200, "avg_cost":420},
    "BAJFINANCE": {"qty":15,  "avg_cost":7200},
    "ICICIBANK":  {"qty":100, "avg_cost":940},
    "AXISBANK":   {"qty":90,  "avg_cost":1050},
}

SECTORS = {
    "RELIANCE":"Energy","TCS":"IT","HDFCBANK":"Banking","INFY":"IT",
    "ICICIBANK":"Banking","BAJFINANCE":"NBFC","WIPRO":"IT","SBIN":"Banking",
    "KOTAKBANK":"Banking","MARUTI":"Auto","SUNPHARMA":"Pharma",
    "TATAMOTORS":"Auto","ULTRACEMCO":"Cement","NESTLEIND":"FMCG",
    "HCLTECH":"IT","AXISBANK":"Banking","ITC":"FMCG","TITAN":"Consumer",
    "LT":"Infra","ASIANPAINT":"Paints",
}

def now_ist():
    return datetime.datetime.now(IST)

def save(fn, d):
    with open(DATA_DIR/fn, "w") as f:
        json.dump(d, f, indent=2)
    print(f"  💾 {fn}")


# ── 1. INDICES via yfinance bulk download ─────────────────────────────────────
def fetch_indices():
    print("\n📉 Fetching indices...")
    IDX = {
        "NIFTY50":"^NSEI","NIFTY500":"^CRSLDX","BANKNIFTY":"^NSEBANK",
        "INDIAVIX":"^INDIAVIX","USDINR":"USDINR=X","BRENT":"BZ=F"
    }
    indices = {}
    try:
        import pandas as pd
        raw = yf.download(
            tickers=" ".join(IDX.values()),
            period="5d", interval="1d",
            group_by="ticker", auto_adjust=True,
            progress=False, threads=True
        )
        for name, sym in IDX.items():
            try:
                closes = raw[sym]["Close"].dropna() if sym in raw.columns.get_level_values(0) else pd.Series()
                if len(closes) >= 2:
                    p, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                elif len(closes) == 1:
                    p = prev = float(closes.iloc[-1])
                else:
                    raise ValueError("no data")
                chg = round(p-prev,2); pct = round(chg/prev*100,2) if prev else 0
                indices[name] = {"price":round(p,2),"change":chg,"change_pct":pct}
                print(f"  ✅ {name}: {p:,.2f} ({pct:+.2f}%)")
            except Exception as e:
                print(f"  ⚠️  {name}: {e}")
                indices[name] = {"price":None}
    except Exception as e:
        print(f"  ❌ Bulk download failed: {e}")
        for name, sym in IDX.items():
            try:
                h = yf.Ticker(sym).history(period="2d")
                if len(h) >= 2:
                    p, prev = float(h['Close'].iloc[-1]), float(h['Close'].iloc[-2])
                    chg = round(p-prev,2); pct = round(chg/prev*100,2)
                    indices[name] = {"price":round(p,2),"change":chg,"change_pct":pct}
                    print(f"  ✅ {name}: {p:,.2f}")
                else:
                    indices[name] = {"price":None}
            except:
                indices[name] = {"price":None}
            time.sleep(0.3)

    indices["GSEC10Y"] = {"price":7.08,"change":-0.02,"change_pct":-0.28}
    save("indices.json", {"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"indices":indices})
    return indices


# ── 2. UPCOMING BOARD MEETINGS from BSE ───────────────────────────────────────
def fetch_upcoming_results():
    """
    Fetch upcoming board meetings (result dates) from BSE.
    BSE announces these 7-14 days in advance.
    Returns dict: {symbol: {date, purpose, scrip_code}}
    """
    print("\n📅 Fetching upcoming board meetings from BSE...")
    upcoming = {}
    today    = now_ist().date()
    look_ahead = today + datetime.timedelta(days=90)

    try:
        from bse import BSE
        bse_c = BSE(download_folder="./bse_data/")

        # Use correct BSE API signature
        ann = bse_c.announcements(
            from_date=datetime.datetime.combine(today, datetime.time.min),
            to_date=datetime.datetime.combine(look_ahead, datetime.time.min),
            category='-1',
        )

        # ann is a dict with keys like 'data' or similar
        items = []
        if isinstance(ann, dict):
            for v in ann.values():
                if isinstance(v, list):
                    items.extend(v)
        elif isinstance(ann, list):
            items = ann

        for item in items:
            # Look for result-related announcements
            category = str(item.get('CATEGORYNAME','') or item.get('category','')).lower()
            headline = str(item.get('HEADLINE','') or item.get('headline','')).lower()
            if 'result' in category or 'financial result' in headline or 'board meeting' in category:
                scrip = str(item.get('SCRIP_CD','') or item.get('scrip_cd',''))
                # Find which stock this is
                for sym, cfg in WATCHLIST.items():
                    if cfg['bse'] == scrip:
                        date_str = str(item.get('NEWS_DT','') or item.get('date',''))[:10]
                        if date_str:
                            upcoming[sym] = {
                                "date":    date_str,
                                "purpose": item.get('HEADLINE','Q Results'),
                                "status":  "confirmed"
                            }
                        break

        print(f"  ✅ Found {len(upcoming)} upcoming result announcements")
        if upcoming:
            for sym, v in upcoming.items():
                print(f"     {sym}: {v['date']}")

    except Exception as e:
        print(f"  ⚠️  BSE announcements: {e}")

    # Fallback: Try BSE result calendar directly
    if len(upcoming) < 5:
        try:
            from bse import BSE
            bse_c = BSE(download_folder="./bse_data/")
            cal = bse_c.resultCalendar()
            if cal:
                for item in cal:
                    scrip = str(item.get('SCRIP_CD',''))
                    for sym, cfg in WATCHLIST.items():
                        if cfg['bse'] == scrip:
                            date_str = str(item.get('BOARD_MEETING_DATE',''))[:10]
                            if date_str and sym not in upcoming:
                                upcoming[sym] = {
                                    "date":    date_str,
                                    "purpose": "Q Results",
                                    "status":  "confirmed"
                                }
                            break
                print(f"  ✅ resultCalendar added: {len(upcoming)} total")
        except Exception as e:
            print(f"  ⚠️  resultCalendar: {e}")

    save("earnings_dates.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "dates": upcoming
    })
    return upcoming


# ── 3. UPCOMING CORPORATE ACTIONS from BSE ────────────────────────────────────
def fetch_corp_actions():
    print("\n🏦 Fetching upcoming corporate actions from BSE...")
    actions = {"dividends":[],"splits":[],"bonus":[],"buyback":[]}
    today   = now_ist().date()
    future  = today + datetime.timedelta(days=90)

    try:
        from bse import BSE
        bse_c = BSE(download_folder="./bse_data/")
        acts  = bse_c.actions(
            from_date=datetime.datetime.combine(today, datetime.time.min),
            to_date=datetime.datetime.combine(future, datetime.time.min),
            by_date='ex'
        )
        for a in (acts or []):
            purpose = str(a.get('PURPOSE','') or a.get('purpose','')).lower()
            scrip   = str(a.get('SCRIP_CD','') or a.get('scrip_cd',''))
            ex_date = str(a.get('EX_DATE','') or a.get('ex_date',''))[:10]

            # Find symbol name
            sym_name = scrip
            for sym, cfg in WATCHLIST.items():
                if cfg['bse'] == scrip:
                    sym_name = sym
                    break

            rec = {
                "symbol":  sym_name,
                "ex_date": ex_date,
                "purpose": a.get('PURPOSE',''),
                "amount":  str(a.get('DIVIDEND','') or a.get('dividend','')),
                "details": str(a.get('REMARKS','') or ''),
            }
            if 'dividend' in purpose:   actions["dividends"].append(rec)
            elif 'split' in purpose:    actions["splits"].append(rec)
            elif 'bonus' in purpose:    actions["bonus"].append(rec)
            elif 'buyback' in purpose:  actions["buyback"].append(rec)
            elif 'right' in purpose:    actions["buyback"].append(rec)

        total = sum(len(v) for v in actions.values())
        print(f"  ✅ {total} upcoming corporate actions")
        for cat, items in actions.items():
            if items:
                print(f"     {cat}: {len(items)}")
                for item in items[:2]:
                    print(f"       {item['symbol']}: {item['ex_date']} — {item['purpose'][:40]}")

    except Exception as e:
        print(f"  ⚠️  {e}")

    save("corp_actions.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "actions": actions
    })
    return actions


# ── 4. BUILD CALENDAR from real upcoming data ─────────────────────────────────
def build_calendar(earn_dates, corp_actions):
    print("\n📅 Building calendar from real data...")
    cal = {}

    def add(date_str, t, label):
        if not date_str: return
        try:
            d   = datetime.datetime.strptime(date_str[:10],"%Y-%m-%d").date()
            key = str(d)
            if key not in cal: cal[key] = []
            # Avoid duplicates
            if not any(e['l'] == label for e in cal[key]):
                cal[key].append({"t":t,"l":label})
        except: pass

    # Add earnings dates
    for sym, info in earn_dates.items():
        if info.get('date'):
            add(info['date'], "e", sym + " Results")

    # Add corporate actions
    for div in corp_actions.get("dividends",[]):
        if div.get('ex_date'):
            add(div['ex_date'], "c", div['symbol']+" Div Ex")
    for sp in corp_actions.get("splits",[]):
        if sp.get('ex_date'):
            add(sp['ex_date'], "c", sp['symbol']+" Split")
    for bn in corp_actions.get("bonus",[]):
        if bn.get('ex_date'):
            add(bn['ex_date'], "c", bn['symbol']+" Bonus")
    for bb in corp_actions.get("buyback",[]):
        if bb.get('ex_date'):
            add(bb['ex_date'], "c", bb['symbol']+" Buyback")

    # Add macro events (static monthly)
    macro_events = [
        # June 2026
        ("2026-06-04","m","RBI MPC"),("2026-06-04","g","FOMC Min."),
        ("2026-06-06","g","US NFP"),("2026-06-10","m","CPI May"),
        ("2026-06-11","g","US CPI"),("2026-06-12","m","IIP Apr"),
        ("2026-06-12","g","ECB Rate"),("2026-06-14","m","WPI May"),
        ("2026-06-18","m","GST Data"),("2026-06-18","g","China IIP"),
        ("2026-06-21","g","G7 Summit"),("2026-06-25","m","GDP Final"),
        ("2026-06-25","g","FOMC Rate"),("2026-06-28","g","US PCE"),
        ("2026-06-30","m","Fiscal Def."),("2026-06-30","g","China PMI"),
        # July 2026
        ("2026-07-04","m","RBI MPC"),("2026-07-04","g","US NFP"),
        ("2026-07-10","g","US CPI"),("2026-07-11","m","CPI June"),
        ("2026-07-15","g","China GDP"),("2026-07-18","m","GST Data"),
        ("2026-07-22","m","Trade Deficit"),("2026-07-25","g","FOMC Rate"),
        ("2026-07-28","g","US PCE"),("2026-07-31","m","Fiscal Deficit"),
        ("2026-07-31","g","BOJ Decision"),
    ]
    for date, t, label in macro_events:
        add(date, t, label)

    print(f"  ✅ {len(cal)} calendar dates with real events")
    save("calendar_events.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "events": cal
    })
    return cal


# ── 5. BUILD EARNINGS TABLE ───────────────────────────────────────────────────
def build_earnings_table(earn_dates):
    """
    Build earnings table from upcoming dates.
    Financial data (Rev/PAT) will be empty until results are announced.
    Status: confirmed/tentative based on BSE announcement.
    """
    print("\n📋 Building earnings table...")
    today    = now_ist().date()
    earnings = []

    for sym in WATCHLIST:
        ed     = earn_dates.get(sym, {})
        rd     = ed.get("date","")
        status = "tentative"
        date_display = "TBD"
        date_sort    = 99

        if rd:
            try:
                dt = datetime.datetime.strptime(rd[:10],"%Y-%m-%d").date()
                mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                date_display = f"{mn[dt.month-1]} {dt.day:02d}"
                date_sort    = dt.day
                if dt < today:
                    status = "reported"
                elif ed.get("status") == "confirmed":
                    status = "confirmed"
                else:
                    status = "confirmed"  # BSE announcements are always confirmed
            except:
                date_display = rd[:10]

        earnings.append({
            "sym":      sym,
            "name":     sym,
            "sector":   SECTORS.get(sym,"Other"),
            "sKey":     SECTORS.get(sym,"other").lower(),
            "date":     date_display,
            "dateSort": date_sort,
            "rev":      0,  # Will be updated after results are announced
            "pat":      0,
            "eps":      0,
            "yoyRev":   0,
            "yoyPat":   0,
            "vsEst":    "upcoming",
            "status":   status,
            "trend":    [60,65,68,72,75,78],
            "quarter":  "Q1 FY26",
        })

    earnings.sort(key=lambda x: x["dateSort"])
    confirmed = [e for e in earnings if e["status"]=="confirmed"]
    upcoming  = [e for e in earnings if e["status"]!="reported"]

    save("earnings_table.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "earnings":    earnings,
        "summary": {
            "beat_rate":         0,
            "median_rev_growth": 0,
            "median_pat_growth": 0,
            "total_reported":    len([e for e in earnings if e["status"]=="reported"]),
            "total_upcoming":    len(upcoming),
            "beats":  0,
            "misses": 0,
        }
    })
    print(f"  ✅ {len(confirmed)} confirmed dates, {len(upcoming)} upcoming")
    return earnings


# ── 6. NEWS from RSS ──────────────────────────────────────────────────────────
def fetch_news():
    print("\n📰 Fetching news from RSS...")
    feeds = [
        {"name":"Economic Times", "url":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
        {"name":"Moneycontrol",   "url":"https://www.moneycontrol.com/rss/marketreports.xml"},
        {"name":"Business Standard","url":"https://www.business-standard.com/rss/markets-106.rss"},
        {"name":"Mint",           "url":"https://www.livemint.com/rss/markets"},
    ]
    all_news = []
    for feed in feeds:
        try:
            r = requests.get(feed["url"], headers=HEADERS, timeout=10)
            if r.status_code != 200: continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:8]:
                title   = item.findtext("title","").strip()
                link    = item.findtext("link","").strip()
                pubdate = item.findtext("pubDate","").strip()
                desc    = re.sub(r'<[^>]+>','',item.findtext("description",""))[:200]
                if not title: continue
                tags = [s for s in PORTFOLIO if s in title.upper() or s in desc.upper()]
                all_news.append({
                    "title":title,"source":feed["name"],"link":link,
                    "date":pubdate[:16],"desc":desc,"tags":tags,
                    "is_portfolio":len(tags)>0
                })
        except Exception as e:
            print(f"  ⚠️  {feed['name']}: {e}")
        time.sleep(0.5)
    all_news.sort(key=lambda x: not x["is_portfolio"])
    print(f"  ✅ {len(all_news)} news items")
    save("news.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "news": all_news[:50]
    })
    return all_news


# ── 7. MACRO EVENTS ───────────────────────────────────────────────────────────
def save_macro_events():
    print("\n🌐 Saving macro events...")
    india = [
        {"date":"Jul 04","name":"RBI MPC Policy Decision",    "sub":"Monetary Policy Committee","impact":"H","prev":"6.00%","fore":"TBD"},
        {"date":"Jul 11","name":"CPI Inflation — June 2026",   "sub":"Consumer Price Index",     "impact":"H","prev":"3.40%","fore":"TBD"},
        {"date":"Jul 12","name":"IIP Data — May 2026",         "sub":"Industrial Production",    "impact":"M","prev":"3.8%", "fore":"TBD"},
        {"date":"Jul 15","name":"WPI Inflation — June 2026",   "sub":"Wholesale Price Index",    "impact":"M","prev":"0.1%", "fore":"TBD"},
        {"date":"Jul 18","name":"GST Collections — June 2026", "sub":"GST Revenue",              "impact":"M","prev":"₹1.78L Cr","fore":"TBD"},
        {"date":"Jul 22","name":"Trade Deficit — June 2026",   "sub":"Exports & Imports",        "impact":"H","prev":"$15.2B","fore":"TBD"},
        {"date":"Jul 31","name":"Fiscal Deficit Update",       "sub":"GoI Monthly Accounts",     "impact":"M","prev":"~68%","fore":"TBD"},
    ]
    global_ev = [
        {"date":"Jul 04","name":"US Jobs Report — June","sub":"Non-Farm Payrolls",    "impact":"H","prev":"185K","fore":"TBD"},
        {"date":"Jul 10","name":"US CPI — June",         "sub":"Consumer Price Index","impact":"H","prev":"3.3%","fore":"TBD"},
        {"date":"Jul 15","name":"China Q2 2026 GDP",     "sub":"NBS Statistics",      "impact":"H","prev":"5.3%","fore":"TBD"},
        {"date":"Jul 24","name":"ECB Rate Decision",     "sub":"European Central Bank","impact":"H","prev":"4.25%","fore":"TBD"},
        {"date":"Jul 25","name":"US FOMC Rate Decision", "sub":"Federal Reserve",     "impact":"H","prev":"5.00–5.25%","fore":"TBD"},
        {"date":"Jul 28","name":"US PCE Inflation",      "sub":"Fed Preferred Measure","impact":"H","prev":"2.6%","fore":"TBD"},
        {"date":"Jul 31","name":"BOJ Policy Decision",   "sub":"Bank of Japan",       "impact":"M","prev":"0.1%","fore":"TBD"},
    ]
    save("macro_events.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "india": india, "global": global_ev
    })


# ── 8. PORTFOLIO ─────────────────────────────────────────────────────────────
def save_portfolio():
    print("\n💼 Saving portfolio structure...")
    holdings = []
    for sym, cfg in PORTFOLIO.items():
        holdings.append({
            "symbol":   sym,
            "qty":      cfg["qty"],
            "avg_cost": cfg["avg_cost"],
            "cmp":      0,
        })
    save("portfolio.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "holdings":    holdings,
        "summary": {
            "total_invested": sum(v["qty"]*v["avg_cost"] for v in PORTFOLIO.values()),
            "total_current":0,"total_pl":0,"total_pl_pct":0,
            "day_pl":0,"day_pl_pct":0
        }
    })


# ── 9. KPIS ──────────────────────────────────────────────────────────────────
def save_kpis(earn_dates, corp_actions):
    total_corp = sum(len(v) for v in corp_actions.values())
    save("kpis.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "kpis": {
            "results_tracked":   len(earn_dates),
            "beat_rate":         0,
            "median_rev_growth": 0,
            "median_pat_growth": 0,
            "corporate_actions": total_corp,
            "advance":           0,
            "decline":           0,
            "beats":             0,
            "misses":            0,
        }
    })


# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*65)
    print(f"  EquityDesk Pro — {now_ist().strftime('%d %b %Y %H:%M IST')}")
    print("="*65)

    indices     = fetch_indices()
    earn_dates  = fetch_upcoming_results()
    corp        = fetch_corp_actions()
    cal         = build_calendar(earn_dates, corp)
    earnings    = build_earnings_table(earn_dates)
    fetch_news()
    save_macro_events()
    save_portfolio()
    save_kpis(earn_dates, corp)

    print("\n"+"="*65)
    print(f"  ✅ DONE — {len(list(DATA_DIR.glob('*.json')))} JSON files saved")
    print(f"  📅 Upcoming result dates found: {len(earn_dates)}")
    print(f"  🏦 Corporate actions found: {sum(len(v) for v in corp.values())}")
    print("="*65)
