"""
fetch_data.py - EquityDesk Pro
Calls the Cloudflare Worker to get real NSE/BSE data.
Worker URL: set WORKER_URL in GitHub Secrets.
"""
import json, time, datetime, re, os, xml.etree.ElementTree as ET
from pathlib import Path
import requests

IST      = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Your Cloudflare Worker URL — set this in GitHub Secrets as WORKER_URL
WORKER_URL = os.environ.get('WORKER_URL', '').rstrip('/')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
    'Accept': 'application/json',
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

def now_ist():
    return datetime.datetime.now(IST)

def save(fn, d):
    with open(DATA_DIR/fn, "w") as f:
        json.dump(d, f, indent=2)
    print(f"  💾 {fn}")

def worker_get(endpoint):
    """Call the Cloudflare Worker endpoint"""
    if not WORKER_URL:
        print(f"  ⚠️  WORKER_URL not set — skipping {endpoint}")
        return None
    try:
        r = requests.get(f"{WORKER_URL}{endpoint}", headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        print(f"  ⚠️  Worker {endpoint}: HTTP {r.status_code}")
        return None
    except Exception as e:
        print(f"  ⚠️  Worker {endpoint}: {e}")
        return None

# ── 1. INDICES ────────────────────────────────────────────────────────────────
def fetch_indices():
    print("\n📉 Fetching indices via Worker...")
    data = worker_get('/indices')
    if data and data.get('indices'):
        idx = data['indices']
        for name, vals in idx.items():
            if vals.get('price'):
                print(f"  ✅ {name}: {vals['price']:,.2f} ({vals.get('change_pct',0):+.2f}%)")
        save("indices.json", {
            "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
            "indices": idx
        })
        return idx
    print("  ⚠️  No index data from worker")
    save("indices.json", {"updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"), "indices": {}})
    return {}

# ── 2. STOCK PRICES ───────────────────────────────────────────────────────────
def fetch_prices():
    print("\n📈 Fetching stock prices via Worker...")
    data = worker_get('/prices')
    if data and data.get('prices'):
        px = data['prices']
        got = sum(1 for v in px.values() if v.get('price'))
        print(f"  ✅ {got}/{len(px)} stocks fetched")
        for sym, vals in px.items():
            if vals.get('price'):
                print(f"     {sym}: ₹{vals['price']:,.2f} ({vals.get('change_pct',0):+.2f}%)")
        save("prices.json", {
            "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
            "prices": px
        })
        return px
    print("  ⚠️  No price data from worker")
    save("prices.json", {"updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"), "prices": {}})
    return {}

# ── 3. UPCOMING EARNINGS ──────────────────────────────────────────────────────
def fetch_earnings():
    print("\n📅 Fetching upcoming earnings via Worker...")
    data = worker_get('/earnings')
    if data and data.get('earnings'):
        earn = data['earnings']
        print(f"  ✅ {len(earn)} upcoming result dates")
        for sym, info in earn.items():
            print(f"     {sym}: {info['date']} — {info.get('purpose','')[:40]}")
        save("earnings_dates.json", {
            "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
            "dates": earn
        })
        return earn
    print("  ⚠️  No earnings dates from worker")
    save("earnings_dates.json", {"updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"), "dates": {}})
    return {}

# ── 4. CORPORATE ACTIONS ──────────────────────────────────────────────────────
def fetch_corp_actions():
    print("\n🏦 Fetching corporate actions via Worker...")
    data = worker_get('/corp-actions')
    if data and data.get('actions'):
        acts  = data['actions']
        total = sum(len(v) for v in acts.values())
        print(f"  ✅ {total} corporate actions")
        save("corp_actions.json", {
            "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
            "actions": acts
        })
        return acts
    print("  ⚠️  No corp actions from worker")
    save("corp_actions.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "actions": {"dividends":[],"splits":[],"bonus":[],"buyback":[]}
    })
    return {"dividends":[],"splits":[],"bonus":[],"buyback":[]}

# ── 5. BUILD CALENDAR ─────────────────────────────────────────────────────────
def build_calendar(earn_dates, corp_actions):
    print("\n📅 Building calendar...")
    cal = {}

    def add(date_str, t, label):
        if not date_str: return
        try:
            d   = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            key = str(d)
            if key not in cal: cal[key] = []
            if not any(e['l'] == label for e in cal[key]):
                cal[key].append({"t": t, "l": label})
        except: pass

    # Earnings dates from BSE (real upcoming dates)
    for sym, info in earn_dates.items():
        if info.get('date'):
            add(info['date'], "e", sym + " Results")

    # Corporate actions from BSE (real upcoming ex-dates)
    for div in corp_actions.get("dividends", []):
        if div.get('ex_date'):
            add(div['ex_date'], "c", div['symbol'] + " Div Ex")
    for sp in corp_actions.get("splits", []):
        if sp.get('ex_date'):
            add(sp['ex_date'], "c", sp['symbol'] + " Split")
    for bn in corp_actions.get("bonus", []):
        if bn.get('ex_date'):
            add(bn['ex_date'], "c", bn['symbol'] + " Bonus")
    for bb in corp_actions.get("buyback", []):
        if bb.get('ex_date'):
            add(bb['ex_date'], "c", bb['symbol'] + " Buyback")

    # Macro events (verified static monthly dates)
    macro = [
        ("2026-06-04","m","RBI MPC"),  ("2026-06-04","g","FOMC Min."),
        ("2026-06-06","g","US NFP"),   ("2026-06-10","m","CPI May"),
        ("2026-06-11","g","US CPI"),   ("2026-06-12","m","IIP Apr"),
        ("2026-06-12","g","ECB Rate"), ("2026-06-14","m","WPI May"),
        ("2026-06-18","m","GST Data"), ("2026-06-18","g","China IIP"),
        ("2026-06-21","g","G7 Summit"),("2026-06-25","m","GDP Final"),
        ("2026-06-25","g","FOMC Rate"),("2026-06-28","g","US PCE"),
        ("2026-06-30","m","Fiscal Def."),("2026-06-30","g","China PMI"),
        ("2026-07-04","m","RBI MPC"),  ("2026-07-04","g","US NFP"),
        ("2026-07-10","g","US CPI"),   ("2026-07-11","m","CPI June"),
        ("2026-07-15","g","China GDP"),("2026-07-18","m","GST Data"),
        ("2026-07-22","m","Trade Deficit"),("2026-07-25","g","FOMC Rate"),
        ("2026-07-28","g","US PCE"),   ("2026-07-31","m","Fiscal Deficit"),
        ("2026-07-31","g","BOJ Decision"),
    ]
    for date, t, label in macro:
        add(date, t, label)

    print(f"  ✅ {len(cal)} calendar dates built")
    save("calendar_events.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "events": cal
    })
    return cal

# ── 6. EARNINGS TABLE ─────────────────────────────────────────────────────────
def build_earnings_table(earn_dates, prices):
    print("\n📋 Building earnings table...")
    today = now_ist().date()
    SECTORS = {
        "RELIANCE":"Energy","TCS":"IT","HDFCBANK":"Banking","INFY":"IT",
        "ICICIBANK":"Banking","BAJFINANCE":"NBFC","WIPRO":"IT","SBIN":"Banking",
        "KOTAKBANK":"Banking","MARUTI":"Auto","SUNPHARMA":"Pharma",
        "TATAMOTORS":"Auto","ULTRACEMCO":"Cement","NESTLEIND":"FMCG",
        "HCLTECH":"IT","AXISBANK":"Banking","ITC":"FMCG","TITAN":"Consumer",
        "LT":"Infra","ASIANPAINT":"Paints",
    }
    earnings = []
    for sym in SECTORS:
        ed   = earn_dates.get(sym, {})
        rd   = ed.get("date","")
        px   = prices.get(sym, {})
        status = "tentative"
        date_display = "TBD"
        date_sort    = 99
        if rd:
            try:
                dt = datetime.datetime.strptime(rd[:10],"%Y-%m-%d").date()
                mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                date_display = f"{mn[dt.month-1]} {dt.day:02d}"
                date_sort    = dt.day
                status       = "reported" if dt < today else "confirmed"
            except: pass

        earnings.append({
            "sym":      sym, "name": sym,
            "sector":   SECTORS[sym], "sKey": SECTORS[sym].lower(),
            "date":     date_display, "dateSort": date_sort,
            "rev":0,"pat":0,"eps":0,"yoyRev":0,"yoyPat":0,
            "vsEst":"upcoming","status":status,
            "trend":[60,65,68,72,75,78],"quarter":"Q1 FY26",
            "cmp":      px.get("price",0),
            "chg_pct":  px.get("change_pct",0),
        })

    earnings.sort(key=lambda x: x["dateSort"])
    upcoming = len([e for e in earnings if e["status"]!="reported"])
    save("earnings_table.json", {
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "earnings": earnings,
        "summary": {
            "beat_rate":0,"median_rev_growth":0,"median_pat_growth":0,
            "total_reported":0,"total_upcoming":upcoming,"beats":0,"misses":0,
        }
    })
    return earnings

# ── 7. NEWS from RSS ──────────────────────────────────────────────────────────
def fetch_news():
    print("\n📰 Fetching news from RSS...")
    feeds = [
        {"name":"Economic Times","url":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
        {"name":"Moneycontrol",  "url":"https://www.moneycontrol.com/rss/marketreports.xml"},
        {"name":"Business Standard","url":"https://www.business-standard.com/rss/markets-106.rss"},
        {"name":"Mint",          "url":"https://www.livemint.com/rss/markets"},
    ]
    all_news = []
    for feed in feeds:
        try:
            r = requests.get(feed["url"], headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
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
    save("news.json", {"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"news":all_news[:50]})

# ── 8. MACRO EVENTS ───────────────────────────────────────────────────────────
def save_macro():
    india = [
        {"date":"Jul 04","name":"RBI MPC Policy Decision",    "sub":"Monetary Policy Committee","impact":"H","prev":"6.00%","fore":"TBD"},
        {"date":"Jul 11","name":"CPI Inflation — June 2026",  "sub":"Consumer Price Index",     "impact":"H","prev":"3.40%","fore":"TBD"},
        {"date":"Jul 12","name":"IIP Data — May 2026",        "sub":"Industrial Production",    "impact":"M","prev":"3.8%", "fore":"TBD"},
        {"date":"Jul 15","name":"WPI Inflation — June 2026",  "sub":"Wholesale Price Index",    "impact":"M","prev":"0.1%", "fore":"TBD"},
        {"date":"Jul 18","name":"GST Collections — June 2026","sub":"GST Revenue",              "impact":"M","prev":"₹1.78L Cr","fore":"TBD"},
        {"date":"Jul 22","name":"Trade Deficit — June 2026",  "sub":"Exports & Imports",        "impact":"H","prev":"$15.2B","fore":"TBD"},
        {"date":"Jul 31","name":"Fiscal Deficit Update",      "sub":"GoI Monthly Accounts",     "impact":"M","prev":"~68%","fore":"TBD"},
    ]
    global_ev = [
        {"date":"Jul 04","name":"US Jobs Report — June", "sub":"Non-Farm Payrolls",    "impact":"H","prev":"185K","fore":"TBD"},
        {"date":"Jul 10","name":"US CPI — June",          "sub":"Consumer Price Index","impact":"H","prev":"3.3%","fore":"TBD"},
        {"date":"Jul 15","name":"China Q2 2026 GDP",      "sub":"NBS Statistics",      "impact":"H","prev":"5.3%","fore":"TBD"},
        {"date":"Jul 24","name":"ECB Rate Decision",      "sub":"European Central Bank","impact":"H","prev":"4.25%","fore":"TBD"},
        {"date":"Jul 25","name":"US FOMC Rate Decision",  "sub":"Federal Reserve",     "impact":"H","prev":"5.00–5.25%","fore":"TBD"},
        {"date":"Jul 28","name":"US PCE Inflation",       "sub":"Fed Preferred Measure","impact":"H","prev":"2.6%","fore":"TBD"},
        {"date":"Jul 31","name":"BOJ Policy Decision",    "sub":"Bank of Japan",       "impact":"M","prev":"0.1%","fore":"TBD"},
    ]
    save("macro_events.json", {
        "updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),
        "india":india,"global":global_ev
    })

# ── 9. PORTFOLIO ──────────────────────────────────────────────────────────────
def calc_portfolio(prices):
    holdings = []
    ti = tc = td = 0
    for sym, cfg in PORTFOLIO.items():
        px  = prices.get(sym, {})
        cmp = px.get("price") or cfg["avg_cost"]
        chg = px.get("change_pct") or 0
        qty, avg = cfg["qty"], cfg["avg_cost"]
        inv = qty*avg; cur=qty*cmp; upl=cur-inv
        up_pct = round(upl/inv*100,2)
        dpl    = round(qty*cmp*chg/100,2)
        ti+=inv; tc+=cur; td+=dpl
        holdings.append({
            "symbol":sym,"qty":qty,"avg_cost":avg,
            "cmp":round(cmp,2),"change_pct":round(chg,2),
            "invested":round(inv,2),"current_val":round(cur,2),
            "unreal_pl":round(upl,2),"unreal_pct":up_pct,"day_pl":dpl
        })
    tpl = tc-ti; tpp = round(tpl/ti*100,2) if ti else 0
    save("portfolio.json", {
        "updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),
        "summary":{
            "total_invested":round(ti,2),"total_current":round(tc,2),
            "total_pl":round(tpl,2),"total_pl_pct":tpp,
            "day_pl":round(td,2),"day_pl_pct":round(td/tc*100,2) if tc else 0
        },
        "holdings":holdings
    })
    print(f"\n  💼 Portfolio: ₹{tc:,.0f} | P&L ₹{tpl:,.0f} ({tpp:+.1f}%)")

# ── 10. KPIS ─────────────────────────────────────────────────────────────────
def save_kpis(earn_dates, corp, prices):
    up  = sum(1 for p in prices.values() if (p.get("change_pct") or 0) > 0)
    dn  = sum(1 for p in prices.values() if (p.get("change_pct") or 0) < 0)
    tot = sum(len(v) for v in corp.values())
    save("kpis.json", {
        "updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),
        "kpis":{
            "results_tracked":len(earn_dates),
            "beat_rate":0,"median_rev_growth":0,"median_pat_growth":0,
            "corporate_actions":tot,"advance":up,"decline":dn,"beats":0,"misses":0,
        }
    })

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*65)
    print(f"  EquityDesk Pro — {now_ist().strftime('%d %b %Y %H:%M IST')}")
    if WORKER_URL:
        print(f"  Worker: {WORKER_URL}")
    else:
        print("  ⚠️  WORKER_URL not set in environment!")
    print("="*65)

    indices    = fetch_indices()
    prices     = fetch_prices()
    earn_dates = fetch_earnings()
    corp       = fetch_corp_actions()
    cal        = build_calendar(earn_dates, corp)
    build_earnings_table(earn_dates, prices)
    fetch_news()
    save_macro()
    calc_portfolio(prices)
    save_kpis(earn_dates, corp, prices)

    print("\n"+"="*65)
    print(f"  ✅ DONE — {len(list(DATA_DIR.glob('*.json')))} JSON files saved")
    print(f"  📅 Earnings dates: {len(earn_dates)}")
    print(f"  🏦 Corp actions: {sum(len(v) for v in corp.values())}")
    print("="*65)
