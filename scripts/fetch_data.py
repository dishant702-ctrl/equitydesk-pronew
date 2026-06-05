"""
fetch_data.py — EquityDesk Pro
================================
GitHub Actions fetches ONLY what it can access:
✅ Indices (Nifty 50/500/BankNifty/VIX/USD-INR/Brent) via yfinance download
✅ Earnings financials from Screener.in
✅ Earnings dates from BSE
✅ Corporate actions from BSE  
✅ News from RSS feeds
✅ Portfolio P&L
✅ KPIs

Stock prices come from RapidAPI called directly in the browser.
"""
import json, time, datetime, re, xml.etree.ElementTree as ET
from pathlib import Path
import requests
from bs4 import BeautifulSoup

IST      = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
Path("bse_data").mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
    'Accept':     'text/html,*/*',
    'Accept-Language': 'en-IN,en;q=0.9',
}

WATCHLIST = {
    "RELIANCE":   {"yf":"RELIANCE.NS",   "bse":"500325","screener":"RELIANCE"},
    "TCS":        {"yf":"TCS.NS",        "bse":"532540","screener":"TCS"},
    "HDFCBANK":   {"yf":"HDFCBANK.NS",   "bse":"500180","screener":"HDFCBANK"},
    "INFY":       {"yf":"INFY.NS",       "bse":"500209","screener":"INFY"},
    "ICICIBANK":  {"yf":"ICICIBANK.NS",  "bse":"532174","screener":"ICICIBANK"},
    "BAJFINANCE": {"yf":"BAJFINANCE.NS", "bse":"500034","screener":"BAJFINANCE"},
    "WIPRO":      {"yf":"WIPRO.NS",      "bse":"507685","screener":"WIPRO"},
    "SBIN":       {"yf":"SBIN.NS",       "bse":"500112","screener":"SBIN"},
    "KOTAKBANK":  {"yf":"KOTAKBANK.NS",  "bse":"500247","screener":"KOTAKBANK"},
    "MARUTI":     {"yf":"MARUTI.NS",     "bse":"532500","screener":"MARUTI"},
    "SUNPHARMA":  {"yf":"SUNPHARMA.NS",  "bse":"524715","screener":"SUNPHARMA"},
    "TATAMOTORS": {"yf":"TATAMOTORS.NS", "bse":"500570","screener":"TATAMOTORS"},
    "ULTRACEMCO": {"yf":"ULTRACEMCO.NS", "bse":"532538","screener":"ULTRACEMCO"},
    "NESTLEIND":  {"yf":"NESTLEIND.NS",  "bse":"500790","screener":"NESTLEIND"},
    "HCLTECH":    {"yf":"HCLTECH.NS",    "bse":"532281","screener":"HCLTECH"},
    "AXISBANK":   {"yf":"AXISBANK.NS",   "bse":"532215","screener":"AXISBANK"},
    "ITC":        {"yf":"ITC.NS",        "bse":"500875","screener":"ITC"},
    "TITAN":      {"yf":"TITAN.NS",      "bse":"500114","screener":"TITAN"},
    "LT":         {"yf":"LT.NS",         "bse":"500510","screener":"LT"},
    "ASIANPAINT": {"yf":"ASIANPAINT.NS", "bse":"500820","screener":"ASIANPAINT"},
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

def now_ist(): return datetime.datetime.now(IST)
def save(fn, d):
    with open(DATA_DIR/fn,"w") as f: json.dump(d,f,indent=2)
    print(f"  💾 {fn}")


# ══════════════════════════════════════════════════════════════════════════════
# 1. INDICES — yfinance bulk download (works on GitHub Actions)
# ══════════════════════════════════════════════════════════════════════════════
def fetch_indices():
    print("\n📉 Fetching indices via yfinance...")
    import yfinance as yf
    import pandas as pd

    IDX = {
        "NIFTY50":   "^NSEI",
        "NIFTY500":  "^CRSLDX",
        "BANKNIFTY": "^NSEBANK",
        "INDIAVIX":  "^INDIAVIX",
        "USDINR":    "USDINR=X",
        "BRENT":     "BZ=F",
    }
    indices = {}

    try:
        syms = list(IDX.values())
        raw  = yf.download(
            tickers=" ".join(syms),
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        for name, sym in IDX.items():
            try:
                if len(syms) == 1:
                    closes = raw["Close"].dropna()
                else:
                    closes = raw[sym]["Close"].dropna() if sym in raw.columns.get_level_values(0) else pd.Series()
                if len(closes) >= 2:
                    price = float(closes.iloc[-1])
                    prev  = float(closes.iloc[-2])
                elif len(closes) == 1:
                    price = prev = float(closes.iloc[-1])
                else:
                    raise ValueError("no data")
                chg = round(price-prev,2); pct=round(chg/prev*100,2) if prev else 0
                indices[name] = {"price":round(price,2),"change":chg,"change_pct":pct}
                print(f"  ✅ {name}: {price:,.2f} ({pct:+.2f}%)")
            except Exception as e:
                print(f"  ⚠️  {name}: {e}")
                indices[name] = {"price":None}
    except Exception as e:
        print(f"  ❌ Bulk download failed: {e}")
        # Individual fallback
        for name, sym in IDX.items():
            try:
                info = yf.Ticker(sym).history(period="2d")
                if len(info) >= 2:
                    price = float(info['Close'].iloc[-1])
                    prev  = float(info['Close'].iloc[-2])
                    chg   = round(price-prev,2); pct=round(chg/prev*100,2)
                    indices[name] = {"price":round(price,2),"change":chg,"change_pct":pct}
                    print(f"  ✅ {name}: {price:,.2f}")
            except Exception as e2:
                print(f"  ⚠️  {name}: {e2}")
                indices[name] = {"price":None}
            time.sleep(0.3)

    indices["GSEC10Y"] = {"price":7.08,"change":-0.02,"change_pct":-0.28}

    save("indices.json",{
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "indices": indices
    })
    got = sum(1 for v in indices.values() if v.get("price"))
    print(f"  📊 {got}/{len(IDX)+1} indices saved")
    return indices


# ══════════════════════════════════════════════════════════════════════════════
# 2. QUARTERLY FINANCIALS — Screener.in
# ══════════════════════════════════════════════════════════════════════════════
def scrape_screener(symbol):
    for sfx in ["/consolidated/","/"]:
        try:
            r = requests.get(f"https://www.screener.in/company/{symbol}{sfx}", headers=HEADERS, timeout=20)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text,"html.parser")
            for table in soup.find_all("table", class_="data-table"):
                cap = table.find("caption")
                if not cap or "Quarterly" not in cap.get_text(): continue
                thead = table.find("thead")
                if not thead: continue
                hdrs = [th.get_text(strip=True) for th in thead.find_all("th")]
                tbody = table.find("tbody")
                if not tbody: continue
                row_data = {}
                for row in tbody.find_all("tr"):
                    cells = row.find_all("td")
                    if not cells: continue
                    row_data[cells[0].get_text(strip=True)] = [
                        c.get_text(strip=True).replace(",","").replace("%","") for c in cells[1:]
                    ]
                quarters = []
                for i in range(min(6,len(hdrs)-1)):
                    q = {"quarter": hdrs[i+1] if i+1<len(hdrs) else ""}
                    for rk in ["Sales","Revenue","Net Sales","Total Revenue"]:
                        if rk in row_data and i<len(row_data[rk]):
                            try: q["revenue"]=float(row_data[rk][i]); break
                            except: pass
                    for rk in ["Net Profit","PAT","Profit after tax","Net profit"]:
                        if rk in row_data and i<len(row_data[rk]):
                            try: q["pat"]=float(row_data[rk][i]); break
                            except: pass
                    for rk in ["EPS in Rs","EPS","Basic EPS"]:
                        if rk in row_data and i<len(row_data[rk]):
                            try: q["eps"]=float(row_data[rk][i]); break
                            except: pass
                    quarters.append(q)
                if quarters: return quarters
        except Exception as e:
            print(f"    screener {symbol}: {e}")
    return []

def fetch_financials():
    print("\n📊 Financials from Screener.in...")
    fin = {}
    for sym,cfg in WATCHLIST.items():
        print(f"  {sym}...",end=" ",flush=True)
        data = scrape_screener(cfg["screener"])
        fin[sym] = data
        print(f"✅ {len(data)}Q" if data else "⚠️  blocked")
        time.sleep(2.5)
    save("financials.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"financials":fin})
    return fin


# ══════════════════════════════════════════════════════════════════════════════
# 3. EARNINGS DATES — BSE
# ══════════════════════════════════════════════════════════════════════════════
def fetch_earnings_dates():
    print("\n📅 Earnings dates from BSE...")
    dates = {}
    try:
        from bse import BSE
        bse_c = BSE(download_folder="./bse_data/")
        for sym,cfg in WATCHLIST.items():
            try:
                ann = bse_c.getAnnouncements(scripCode=cfg["bse"],CategoryName="Result",FaceName="")
                if ann:
                    dates[sym] = {"date":ann[0].get("NEWS_DT","")[:10],"purpose":ann[0].get("HEADLINE","")}
                time.sleep(0.8)
            except: pass
        print(f"  ✅ {len(dates)} dates")
    except Exception as e:
        print(f"  ⚠️  {e}")
    save("earnings_dates.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"dates":dates})
    return dates


# ══════════════════════════════════════════════════════════════════════════════
# 4. CORPORATE ACTIONS — BSE
# ══════════════════════════════════════════════════════════════════════════════
def fetch_corp_actions():
    print("\n🏦 Corporate actions from BSE...")
    actions = {"dividends":[],"splits":[],"bonus":[],"buyback":[]}
    try:
        from bse import BSE
        bse_c = BSE(download_folder="./bse_data/")
        for sym,cfg in WATCHLIST.items():
            try:
                for a in (bse_c.actions(scripCode=cfg["bse"]) or [])[:5]:
                    p   = str(a.get("PURPOSE","")).lower()
                    rec = {"symbol":sym,"ex_date":a.get("EX_DATE",""),"purpose":a.get("PURPOSE",""),"amount":a.get("DIVIDEND",""),"details":a.get("REMARKS","")}
                    if "dividend" in p:  actions["dividends"].append(rec)
                    elif "split" in p:   actions["splits"].append(rec)
                    elif "bonus" in p:   actions["bonus"].append(rec)
                    elif "buyback" in p: actions["buyback"].append(rec)
                time.sleep(0.8)
            except: pass
    except Exception as e:
        print(f"  ⚠️  {e}")
    total = sum(len(v) for v in actions.values())
    print(f"  ✅ {total} actions")
    save("corp_actions.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"actions":actions})
    return actions


# ══════════════════════════════════════════════════════════════════════════════
# 5. NEWS — RSS feeds
# ══════════════════════════════════════════════════════════════════════════════
def fetch_news():
    print("\n📰 News from RSS...")
    feeds = [
        {"name":"Economic Times","url":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
        {"name":"Moneycontrol",  "url":"https://www.moneycontrol.com/rss/marketreports.xml"},
        {"name":"Business Standard","url":"https://www.business-standard.com/rss/markets-106.rss"},
        {"name":"Mint",          "url":"https://www.livemint.com/rss/markets"},
    ]
    all_news = []
    for feed in feeds:
        try:
            r = requests.get(feed["url"],headers=HEADERS,timeout=10)
            if r.status_code != 200: continue
            root  = ET.fromstring(r.content)
            for item in root.findall(".//item")[:8]:
                title   = item.findtext("title","").strip()
                link    = item.findtext("link","").strip()
                pubdate = item.findtext("pubDate","").strip()
                desc    = re.sub(r'<[^>]+>','',item.findtext("description",""))[:200]
                if not title: continue
                tags = [s for s in PORTFOLIO if s in title.upper() or s in desc.upper()]
                all_news.append({"title":title,"source":feed["name"],"link":link,"date":pubdate[:16],"desc":desc,"tags":tags,"is_portfolio":len(tags)>0})
        except Exception as e:
            print(f"  ⚠️  {feed['name']}: {e}")
        time.sleep(0.5)
    all_news.sort(key=lambda x: not x["is_portfolio"])
    print(f"  ✅ {len(all_news)} items")
    save("news.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"news":all_news[:50]})
    return all_news


# ══════════════════════════════════════════════════════════════════════════════
# 6. BUILD EARNINGS TABLE + CALENDAR
# ══════════════════════════════════════════════════════════════════════════════
def build_earnings_and_calendar(fin, earn_dates, corp_actions):
    print("\n📋 Building earnings table + calendar...")
    earnings   = []
    today      = now_ist().date()
    cal_events = {}

    def add_cal(date_str, t, label):
        if not date_str: return
        try:
            d = datetime.datetime.strptime(date_str[:10],"%Y-%m-%d").date()
            k = str(d)
            if k not in cal_events: cal_events[k] = []
            cal_events[k].append({"t":t,"l":label})
        except: pass

    for sym in WATCHLIST:
        q      = fin.get(sym,[])
        ed     = earn_dates.get(sym,{})
        latest = q[0] if q else {}
        rev_yoy = pat_yoy = None
        if len(q) >= 5:
            try:
                rv,rp = latest.get("revenue"), q[4].get("revenue")
                pv,pp = latest.get("pat"),     q[4].get("pat")
                if rv and rp and rp!=0: rev_yoy=round((rv-rp)/rp*100,1)
                if pv and pp and pp!=0: pat_yoy=round((pv-pp)/pp*100,1)
            except: pass
        vs = "in-line"
        if pat_yoy is not None:
            if pat_yoy>10: vs="beat"
            elif pat_yoy<0: vs="miss"
        trend = []
        for qt in list(reversed(q[:6])):
            v = qt.get("pat") or qt.get("revenue") or 50
            trend.append(v)
        if trend:
            mx=max(abs(v) for v in trend) or 1
            trend=[round(max(10,min(95,(v/mx)*80+15)),1) for v in trend]
        else: trend=[60,65,68,72,75,78]

        rd = ed.get("date","")
        date_display,date_sort,status = "TBD",99,"tentative"
        if rd:
            try:
                dt = datetime.datetime.strptime(rd[:10],"%Y-%m-%d").date()
                mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                date_display = f"{mn[dt.month-1]} {dt.day:02d}"
                date_sort    = dt.day
                if dt<today: status="reported"
                elif dt<=today+datetime.timedelta(days=14): status="confirmed"
                add_cal(rd,"e",sym+" Q4")
            except: date_display=rd[:10]

        earnings.append({
            "sym":sym,"name":sym,"sector":SECTORS.get(sym,"Other"),
            "sKey":SECTORS.get(sym,"other").lower(),
            "date":date_display,"dateSort":date_sort,
            "rev":round(latest.get("revenue",0) or 0),
            "pat":round(latest.get("pat",0) or 0),
            "eps":round(latest.get("eps",0) or 0,2),
            "yoyRev":rev_yoy or 0,"yoyPat":pat_yoy or 0,
            "vsEst":vs,"status":status,"trend":trend,
            "quarter":latest.get("quarter","Q4 FY25"),
        })
        print(f"  ✅ {sym}: Rev={round(latest.get('revenue',0) or 0):,} PAT={round(latest.get('pat',0) or 0):,} [{vs}]")

    # Add corp actions to calendar
    for div in corp_actions.get("dividends",[]):
        add_cal(div.get("ex_date",""),"c",div["symbol"]+" Div Ex")
    for sp in corp_actions.get("splits",[]):
        add_cal(sp.get("ex_date",""),"c",sp["symbol"]+" Split")
    for bn in corp_actions.get("bonus",[]):
        add_cal(bn.get("ex_date",""),"c",bn["symbol"]+" Bonus")

    # Static macro events for calendar
    for date,t,label in [
        ("2026-07-04","m","RBI MPC"),("2026-07-04","g","FOMC"),
        ("2026-07-10","g","US CPI"),("2026-07-11","m","CPI India"),
        ("2026-07-15","g","China GDP"),("2026-07-22","m","Trade Deficit"),
        ("2026-07-25","g","FOMC Rate"),("2026-07-31","m","Fiscal Deficit"),
    ]:
        add_cal(date,t,label)

    earnings.sort(key=lambda x: x["dateSort"])
    rep   = [e for e in earnings if e["status"]=="reported"]
    beats = [e for e in rep if e["vsEst"]=="beat"]
    br    = round(len(beats)/len(rep)*100) if rep else 0
    rvg   = [e["yoyRev"] for e in rep if e["yoyRev"]]
    ptg   = [e["yoyPat"] for e in rep if e["yoyPat"]]
    summary = {
        "beat_rate":br,
        "median_rev_growth":round(sum(rvg)/len(rvg),1) if rvg else 0,
        "median_pat_growth":round(sum(ptg)/len(ptg),1) if ptg else 0,
        "total_reported":len(rep),
        "total_upcoming":len([e for e in earnings if e["status"]!="reported"]),
        "beats":len(beats),
        "misses":len([e for e in rep if e["vsEst"]=="miss"]),
    }
    save("earnings_table.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"earnings":earnings,"summary":summary})
    save("calendar_events.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"events":cal_events})
    print(f"  📊 Beat:{br}% | Reported:{len(rep)} | Calendar:{len(cal_events)} dates")
    return earnings,cal_events,summary


# ══════════════════════════════════════════════════════════════════════════════
# 7. MACRO EVENTS
# ══════════════════════════════════════════════════════════════════════════════
def fetch_macro_events():
    print("\n🌐 Macro events...")
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
    save("macro_events.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"india":india,"global":global_ev})


# ══════════════════════════════════════════════════════════════════════════════
# 8. PORTFOLIO P&L (uses last known prices from indices run)
# ══════════════════════════════════════════════════════════════════════════════
def calc_portfolio():
    print("\n💼 Portfolio (placeholder P&L — live prices from RapidAPI in browser)...")
    # We save avg costs so the browser can compute real P&L with live RapidAPI prices
    holdings = []
    for sym,cfg in PORTFOLIO.items():
        holdings.append({
            "symbol":   sym,
            "qty":      cfg["qty"],
            "avg_cost": cfg["avg_cost"],
            "cmp":      0,   # filled by browser via RapidAPI
        })
    save("portfolio.json",{
        "updated_ist": now_ist().strftime("%d %b %Y %H:%M IST"),
        "holdings":    holdings,
        "summary":     {"total_invested":0,"total_current":0,"total_pl":0,"total_pl_pct":0,"day_pl":0,"day_pl_pct":0}
    })


# ══════════════════════════════════════════════════════════════════════════════
# 9. KPIS
# ══════════════════════════════════════════════════════════════════════════════
def build_kpis(summary, corp):
    tot = sum(len(v) for v in corp.values())
    save("kpis.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"kpis":{
        "results_tracked": (summary.get("total_reported",0)+summary.get("total_upcoming",0)),
        "beat_rate":        summary.get("beat_rate",0),
        "median_rev_growth":summary.get("median_rev_growth",0),
        "median_pat_growth":summary.get("median_pat_growth",0),
        "corporate_actions":tot,
        "advance":0,"decline":0,
        "beats":   summary.get("beats",0),
        "misses":  summary.get("misses",0),
    }})


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("="*65)
    print(f"  EquityDesk Pro — {now_ist().strftime('%d %b %Y %H:%M IST')}")
    print("="*65)
    indices    = fetch_indices()
    fin        = fetch_financials()
    earn_dates = fetch_earnings_dates()
    corp       = fetch_corp_actions()
    fetch_news()
    fetch_macro_events()
    earnings,cal,summary = build_earnings_and_calendar(fin,earn_dates,corp)
    calc_portfolio()
    build_kpis(summary,corp)
    print("\n"+"="*65)
    print(f"  ✅ DONE — {len(list(DATA_DIR.glob('*.json')))} JSON files saved")
    print("="*65)
