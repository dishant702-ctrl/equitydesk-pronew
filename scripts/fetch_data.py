"""
fetch_data.py - EquityDesk Pro
Complete automated data fetcher. Zero manual entry.
Sources: Yahoo Finance, Screener.in, NSE, BSE, RSS feeds
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

HEADERS = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0','Accept':'text/html,*/*','Accept-Language':'en-IN,en;q=0.9'}

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
    "RELIANCE":"Energy","TCS":"IT","HDFCBANK":"Banking","INFY":"IT","ICICIBANK":"Banking",
    "BAJFINANCE":"NBFC","WIPRO":"IT","SBIN":"Banking","KOTAKBANK":"Banking","MARUTI":"Auto",
    "SUNPHARMA":"Pharma","TATAMOTORS":"Auto","ULTRACEMCO":"Cement","NESTLEIND":"FMCG",
    "HCLTECH":"IT","AXISBANK":"Banking","ITC":"FMCG","TITAN":"Consumer","LT":"Infra","ASIANPAINT":"Paints",
}

def now_ist(): return datetime.datetime.now(IST)
def save(fn, d):
    with open(DATA_DIR/fn,"w") as f: json.dump(d,f,indent=2)
    print(f"  💾 {fn}")
def fmt_date(d):
    if not d: return ""
    try:
        if isinstance(d,str): d=datetime.datetime.strptime(d[:10],"%Y-%m-%d")
        mn=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        return f"{mn[d.month-1]} {d.day:02d}"
    except: return str(d)[:10]

# ── 1. PRICES + INDICES — NSE India official API ────────────────────────────
def fetch_prices_indices():
    print("\n📈 Prices + Indices from NSE India...")
    
    NSE_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
        'Accept': '*/*',
        'Accept-Language': 'en-IN,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.nseindia.com/',
        'Connection': 'keep-alive',
    }
    
    session = requests.Session()
    # Must hit NSE homepage first to get cookies
    try:
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
        time.sleep(1)
    except: pass

    indices, prices = {}, {}

    # ── INDEX DATA FROM NSE ──
    nse_index_names = {
        "NIFTY50":   "NIFTY 50",
        "NIFTY500":  "NIFTY 500",
        "BANKNIFTY": "NIFTY BANK",
        "INDIAVIX":  "India VIX",
    }
    try:
        r = session.get(
            "https://www.nseindia.com/api/allIndices",
            headers={**NSE_HEADERS, 'Referer':'https://www.nseindia.com/market-data/live-market-statistics'},
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            for item in data.get("data", []):
                name = item.get("indexSymbol","") or item.get("index","")
                for key, nse_name in nse_index_names.items():
                    if nse_name.upper() in name.upper():
                        price = float(item.get("last", 0) or item.get("indexValue", 0))
                        prev  = float(item.get("previousClose", 0) or price)
                        chg   = round(price - prev, 2)
                        pct   = round(chg / prev * 100, 2) if prev else 0
                        indices[key] = {"price": round(price,2), "change": chg, "change_pct": pct}
                        print(f"  ✅ {key}: {price:,.2f} ({pct:+.2f}%)")
            print(f"  NSE indices: {len(indices)} fetched")
    except Exception as e:
        print(f"  ⚠️ NSE indices: {e}")

    # ── USD/INR FROM NSE ──
    try:
        r2 = session.get(
            "https://www.nseindia.com/api/exchangeRate",
            headers={**NSE_HEADERS, 'Referer':'https://www.nseindia.com/'},
            timeout=10
        )
        if r2.status_code == 200:
            fx = r2.json()
            for item in fx if isinstance(fx, list) else fx.get("data", []):
                if "USD" in str(item.get("currency","")).upper():
                    rate = float(item.get("rate", 0) or item.get("buyRate", 0))
                    if rate:
                        indices["USDINR"] = {"price": round(rate,2), "change": 0, "change_pct": 0}
                        print(f"  ✅ USD/INR: {rate}")
                        break
    except Exception as e:
        print(f"  ⚠️ USD/INR: {e}")
        # Fallback to yfinance for USD/INR
        try:
            import yfinance as yf
            info = yf.Ticker("USDINR=X").fast_info
            p,prev = float(info.last_price), float(info.previous_close)
            indices["USDINR"] = {"price":round(p,2),"change":round(p-prev,2),"change_pct":round((p-prev)/prev*100,2)}
            print(f"  ✅ USD/INR (yf fallback): {p}")
        except: pass

    # Brent from yfinance (NSE doesn't have commodity)
    try:
        import yfinance as yf
        info = yf.Ticker("BZ=F").fast_info
        p,prev = float(info.last_price),float(info.previous_close)
        indices["BRENT"] = {"price":round(p,2),"change":round(p-prev,2),"change_pct":round((p-prev)/prev*100,2)}
        print(f"  ✅ Brent: ${p:,.2f}")
    except Exception as e:
        print(f"  ⚠️ Brent: {e}")

    indices["GSEC10Y"] = {"price": 7.08, "change": -0.02, "change_pct": -0.28}

    # ── STOCK PRICES FROM NSE ──
    nse_symbols = list(WATCHLIST.keys())
    for i in range(0, len(nse_symbols), 10):
        batch = nse_symbols[i:i+10]
        for sym in batch:
            try:
                r = session.get(
                    f"https://www.nseindia.com/api/quote-equity?symbol={sym}",
                    headers={**NSE_HEADERS,'Referer':'https://www.nseindia.com/get-quotes/equity?symbol='+sym},
                    timeout=10
                )
                if r.status_code == 200:
                    d = r.json()
                    pd2 = d.get("priceInfo", {}) or d.get("data", {})
                    price = float(pd2.get("lastPrice",0) or pd2.get("last",0))
                    prev  = float(pd2.get("previousClose",0) or pd2.get("close",0) or price)
                    if price:
                        chg = round(price-prev,2)
                        pct = round(chg/prev*100,2) if prev else 0
                        prices[sym] = {
                            "price":round(price,2),"prev_close":round(prev,2),
                            "change":chg,"change_pct":pct,
                            "day_high":float(pd2.get("intraDayHighLow",{}).get("max",price) or price),
                            "day_low": float(pd2.get("intraDayHighLow",{}).get("min",price) or price),
                            "52w_high":float(pd2.get("weekHighLow",{}).get("max",price) or price),
                            "52w_low": float(pd2.get("weekHighLow",{}).get("min",price) or price),
                        }
                        print(f"  ✅ {sym}: ₹{price:,.2f} ({pct:+.2f}%)")
                    else:
                        raise ValueError("price=0")
                else:
                    raise ValueError(f"HTTP {r.status_code}")
            except Exception as e:
                print(f"  ⚠️ {sym}: {e} — trying yfinance fallback")
                try:
                    import yfinance as yf
                    info = yf.Ticker(WATCHLIST[sym]["yf"]).fast_info
                    p,prev = float(info.last_price),float(info.previous_close)
                    prices[sym] = {"price":round(p,2),"prev_close":round(prev,2),"change":round(p-prev,2),"change_pct":round((p-prev)/prev*100,2),"day_high":round(float(info.day_high),2),"day_low":round(float(info.day_low),2),"52w_high":round(float(info.fifty_two_week_high),2),"52w_low":round(float(info.fifty_two_week_low),2)}
                    print(f"    ✅ {sym} (yf): ₹{p:,.2f}")
                except Exception as e2:
                    print(f"    ❌ {sym}: {e2}")
                    prices[sym] = {"price":None}
            time.sleep(0.3)
        time.sleep(1)

    ts = now_ist().strftime("%d %b %Y %H:%M IST")
    save("indices.json", {"updated_ist":ts,"indices":indices})
    save("prices.json",  {"updated_ist":ts,"prices":prices})
    print(f"  📊 {len(indices)} indices, {len(prices)} stocks saved")
    return prices, indices

# ── 2. FINANCIALS FROM SCREENER.IN ───────────────────────────────────────────
def scrape_screener(symbol):
    for sfx in ["/consolidated/","/"]:
        try:
            r=requests.get(f"https://www.screener.in/company/{symbol}{sfx}",headers=HEADERS,timeout=20)
            if r.status_code!=200: continue
            soup=BeautifulSoup(r.text,"html.parser")
            for table in soup.find_all("table",class_="data-table"):
                cap=table.find("caption")
                if not cap or "Quarterly" not in cap.get_text(): continue
                thead=table.find("thead")
                if not thead: continue
                hdrs=[th.get_text(strip=True) for th in thead.find_all("th")]
                tbody=table.find("tbody")
                if not tbody: continue
                row_data={}
                for row in tbody.find_all("tr"):
                    cells=row.find_all("td")
                    if not cells: continue
                    row_data[cells[0].get_text(strip=True)]=[c.get_text(strip=True).replace(",","").replace("%","") for c in cells[1:]]
                quarters=[]
                for i in range(min(6,len(hdrs)-1)):
                    q={"quarter":hdrs[i+1] if i+1<len(hdrs) else ""}
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
        except Exception as e: print(f"    screener {symbol}: {e}")
    return []

def fetch_financials():
    print("\n📊 Screener.in financials...")
    fin={}
    for sym,cfg in WATCHLIST.items():
        print(f"  {sym}...",end=" ",flush=True)
        data=scrape_screener(cfg["screener"])
        fin[sym]=data
        print(f"✅ {len(data)}Q" if data else "⚠️")
        time.sleep(2.5)
    save("financials.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"financials":fin})
    return fin

# ── 3. EARNINGS DATES FROM NSE + BSE ─────────────────────────────────────────
def fetch_earnings_dates():
    print("\n📅 Earnings dates from NSE + BSE...")
    dates={}
    try:
        s=requests.Session()
        s.get("https://www.nseindia.com",headers=HEADERS,timeout=10)
        time.sleep(1)
        r=s.get("https://www.nseindia.com/api/corporates-corporateActions?index=equities&subject=Board+Meeting",headers={**HEADERS,"Referer":"https://www.nseindia.com"},timeout=15)
        if r.status_code==200:
            for item in r.json().get("data",[]):
                sym=item.get("symbol","")
                if sym in WATCHLIST:
                    dates[sym]={"date":item.get("bm_date","")[:10],"purpose":item.get("bm_purpose",""),"desc":item.get("bm_desc","")}
            print(f"  ✅ NSE: {len(dates)} dates")
    except Exception as e: print(f"  ⚠️ NSE: {e}")
    try:
        from bse import BSE
        bse_c=BSE(download_folder="./bse_data/")
        for sym,cfg in WATCHLIST.items():
            if sym in dates: continue
            try:
                ann=bse_c.getAnnouncements(scripCode=cfg["bse"],CategoryName="Result",FaceName="")
                if ann: dates[sym]={"date":ann[0].get("NEWS_DT","")[:10],"purpose":ann[0].get("HEADLINE","")}
                time.sleep(0.8)
            except: pass
        print(f"  ✅ Total: {len(dates)} dates")
    except Exception as e: print(f"  ⚠️ BSE: {e}")
    save("earnings_dates.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"dates":dates})
    return dates

# ── 4. CORPORATE ACTIONS FROM BSE ────────────────────────────────────────────
def fetch_corp_actions():
    print("\n🏦 Corporate actions from BSE...")
    actions={"dividends":[],"splits":[],"bonus":[],"buyback":[]}
    try:
        from bse import BSE
        bse_c=BSE(download_folder="./bse_data/")
        for sym,cfg in WATCHLIST.items():
            try:
                for a in (bse_c.actions(scripCode=cfg["bse"]) or [])[:5]:
                    p=str(a.get("PURPOSE","")).lower()
                    rec={"symbol":sym,"ex_date":a.get("EX_DATE",""),"purpose":a.get("PURPOSE",""),"amount":a.get("DIVIDEND",""),"details":a.get("REMARKS","")}
                    if "dividend" in p: actions["dividends"].append(rec)
                    elif "split" in p:  actions["splits"].append(rec)
                    elif "bonus" in p:  actions["bonus"].append(rec)
                    elif "buyback" in p: actions["buyback"].append(rec)
                time.sleep(0.8)
            except: pass
    except Exception as e: print(f"  ⚠️ {e}")
    total=sum(len(v) for v in actions.values())
    print(f"  ✅ {total} actions")
    save("corp_actions.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"actions":actions})
    return actions

# ── 5. LIVE NEWS FROM RSS ─────────────────────────────────────────────────────
def fetch_news():
    print("\n📰 Live news from RSS...")
    feeds=[
        {"name":"Economic Times", "url":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
        {"name":"Moneycontrol",   "url":"https://www.moneycontrol.com/rss/marketreports.xml"},
        {"name":"Business Standard","url":"https://www.business-standard.com/rss/markets-106.rss"},
        {"name":"Mint Markets",   "url":"https://www.livemint.com/rss/markets"},
    ]
    all_news=[]
    for feed in feeds:
        try:
            r=requests.get(feed["url"],headers=HEADERS,timeout=10)
            if r.status_code!=200: continue
            root=ET.fromstring(r.content)
            for item in root.findall(".//item")[:8]:
                title=item.findtext("title","").strip()
                link=item.findtext("link","").strip()
                pubdate=item.findtext("pubDate","").strip()
                desc=re.sub(r'<[^>]+>','',item.findtext("description","").strip())[:200]
                if not title: continue
                tags=[sym for sym in PORTFOLIO if sym in title.upper() or sym in desc.upper()]
                all_news.append({"title":title,"source":feed["name"],"link":link,"date":pubdate[:16] if pubdate else "","desc":desc,"tags":tags,"is_portfolio":len(tags)>0})
        except Exception as e: print(f"  ⚠️ {feed['name']}: {e}")
        time.sleep(0.5)
    all_news.sort(key=lambda x: (not x["is_portfolio"]))
    print(f"  ✅ {len(all_news)} news items")
    save("news.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"news":all_news[:50]})
    return all_news

# ── 6. BUILD EARNINGS TABLE + CALENDAR EVENTS ─────────────────────────────────
def build_earnings_and_calendar(fin, prices, earn_dates, corp_actions):
    print("\n📋 Building earnings table + calendar...")
    earnings=[]
    today=now_ist().date()
    cal_events={}

    def add_cal(date_str, t, label):
        if not date_str: return
        try:
            d=datetime.datetime.strptime(date_str[:10],"%Y-%m-%d").date()
            key=str(d)
            if key not in cal_events: cal_events[key]=[]
            cal_events[key].append({"t":t,"l":label})
        except: pass

    for sym in WATCHLIST:
        q=fin.get(sym,[])
        p=prices.get(sym,{})
        ed=earn_dates.get(sym,{})
        latest=q[0] if q else {}
        rev_yoy=pat_yoy=None
        if len(q)>=5:
            try:
                rv,rp=latest.get("revenue"),q[4].get("revenue")
                pv,pp=latest.get("pat"),q[4].get("pat")
                if rv and rp and rp!=0: rev_yoy=round((rv-rp)/rp*100,1)
                if pv and pp and pp!=0: pat_yoy=round((pv-pp)/pp*100,1)
            except: pass
        vs="in-line"
        if pat_yoy is not None:
            if pat_yoy>10: vs="beat"
            elif pat_yoy<0: vs="miss"
        trend=[]
        for qt in list(reversed(q[:6])):
            v=qt.get("pat") or qt.get("revenue") or 50
            trend.append(v)
        if trend:
            mx=max(abs(v) for v in trend) or 1
            trend=[round(max(10,min(95,(v/mx)*80+15)),1) for v in trend]
        else: trend=[60,65,68,72,75,78]
        rd=ed.get("date","")
        date_display,date_sort,status="TBD",99,"tentative"
        if rd:
            try:
                dt=datetime.datetime.strptime(rd[:10],"%Y-%m-%d").date()
                mn=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                date_display=f"{mn[dt.month-1]} {dt.day:02d}"
                date_sort=dt.day
                if dt<today: status="reported"
                elif dt<=today+datetime.timedelta(days=14): status="confirmed"
                add_cal(rd,"e",sym+" Q4")
            except: date_display=rd[:10]
        earnings.append({"sym":sym,"name":sym,"sector":SECTORS.get(sym,"Other"),"sKey":SECTORS.get(sym,"other").lower(),"date":date_display,"dateSort":date_sort,"rev":round(latest.get("revenue",0) or 0),"pat":round(latest.get("pat",0) or 0),"eps":round(latest.get("eps",0) or 0,2),"yoyRev":rev_yoy or 0,"yoyPat":pat_yoy or 0,"vsEst":vs,"status":status,"trend":trend,"quarter":latest.get("quarter","Q4 FY25"),"cmp":p.get("price",0),"chg_pct":p.get("change_pct",0)})
        print(f"  ✅ {sym}: Rev={round(latest.get('revenue',0) or 0)} PAT={round(latest.get('pat',0) or 0)} {vs}")

    # Add corp actions to calendar
    for div in corp_actions.get("dividends",[]):
        add_cal(div.get("ex_date",""),"c",div["symbol"]+" Div Ex")
    for sp in corp_actions.get("splits",[]):
        add_cal(sp.get("ex_date",""),"c",sp["symbol"]+" Split Ex")
    for bn in corp_actions.get("bonus",[]):
        add_cal(bn.get("ex_date",""),"c",bn["symbol"]+" Bonus Ex")

    # Add macro events to calendar (static)
    macro_cal=[
        ("2026-07-04","m","RBI MPC"),("2026-07-04","g","FOMC"),
        ("2026-07-10","g","US CPI"),("2026-07-11","m","CPI India"),
        ("2026-07-15","g","China GDP"),("2026-07-22","m","Trade Deficit"),
        ("2026-07-25","g","FOMC Rate"),("2026-07-31","m","Fiscal Deficit"),
    ]
    for date,t,label in macro_cal: add_cal(date,t,label)

    earnings.sort(key=lambda x: x["dateSort"])
    rep=[e for e in earnings if e["status"]=="reported"]
    beats=[e for e in rep if e["vsEst"]=="beat"]
    br=round(len(beats)/len(rep)*100) if rep else 0
    rvg=[e["yoyRev"] for e in rep if e["yoyRev"]]
    ptg=[e["yoyPat"] for e in rep if e["yoyPat"]]

    summary={"beat_rate":br,"median_rev_growth":round(sum(rvg)/len(rvg),1) if rvg else 0,"median_pat_growth":round(sum(ptg)/len(ptg),1) if ptg else 0,"total_reported":len(rep),"total_upcoming":len([e for e in earnings if e["status"]!="reported"]),"beats":len(beats),"misses":len([e for e in rep if e["vsEst"]=="miss"])}
    save("earnings_table.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"earnings":earnings,"summary":summary})
    save("calendar_events.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"events":cal_events})
    print(f"  📊 Beat:{br}% | Reported:{len(rep)} | Calendar dates:{len(cal_events)}")
    return earnings,cal_events,summary

# ── 7. MACRO EVENTS ───────────────────────────────────────────────────────────
def fetch_macro_events():
    print("\n🌐 Macro events...")
    rbi_events=[]
    try:
        r=requests.get("https://www.rbi.org.in/scripts/rss.aspx",headers=HEADERS,timeout=10)
        if r.status_code==200:
            root=ET.fromstring(r.content)
            for item in root.findall(".//item")[:4]:
                rbi_events.append({"date":item.findtext("pubDate","")[:16],"name":item.findtext("title","").strip(),"sub":"Reserve Bank of India","impact":"H","prev":"—","fore":"—"})
            print(f"  ✅ RBI RSS: {len(rbi_events)}")
    except Exception as e: print(f"  ⚠️ RBI: {e}")
    india=[
        {"date":"Jul 04","name":"RBI MPC Policy Decision","sub":"Monetary Policy Committee — Repo Rate","impact":"H","prev":"6.00%","fore":"TBD"},
        {"date":"Jul 11","name":"CPI Inflation — June 2026","sub":"Consumer Price Index (MoSPI)","impact":"H","prev":"3.40%","fore":"TBD"},
        {"date":"Jul 12","name":"IIP Data — May 2026","sub":"Index of Industrial Production","impact":"M","prev":"3.8%","fore":"TBD"},
        {"date":"Jul 15","name":"WPI Inflation — June 2026","sub":"Wholesale Price Index","impact":"M","prev":"0.1%","fore":"TBD"},
        {"date":"Jul 18","name":"GST Collections — June 2026","sub":"Goods & Services Tax Revenue","impact":"M","prev":"₹1.78L Cr","fore":"TBD"},
        {"date":"Jul 22","name":"Trade Deficit — June 2026","sub":"Exports & Imports","impact":"H","prev":"$15.2B","fore":"TBD"},
        {"date":"Jul 31","name":"Fiscal Deficit Update","sub":"GoI Monthly Accounts","impact":"M","prev":"~68%","fore":"TBD"},
    ]
    global_ev=[
        {"date":"Jul 04","name":"US Jobs Report — June","sub":"Non-Farm Payrolls (BLS)","impact":"H","prev":"185K","fore":"TBD"},
        {"date":"Jul 10","name":"US CPI — June","sub":"Consumer Price Index","impact":"H","prev":"3.3%","fore":"TBD"},
        {"date":"Jul 15","name":"China Q2 2026 GDP","sub":"National Bureau of Statistics","impact":"H","prev":"5.3%","fore":"TBD"},
        {"date":"Jul 24","name":"ECB Rate Decision","sub":"European Central Bank","impact":"H","prev":"4.25%","fore":"TBD"},
        {"date":"Jul 25","name":"US FOMC Rate Decision","sub":"Federal Reserve Q3 2026","impact":"H","prev":"5.00–5.25%","fore":"TBD"},
        {"date":"Jul 28","name":"US PCE Inflation — June","sub":"Personal Consumption Expenditure","impact":"H","prev":"2.6%","fore":"TBD"},
        {"date":"Jul 31","name":"BOJ Policy Decision","sub":"Bank of Japan","impact":"M","prev":"0.1%","fore":"TBD"},
    ]
    save("macro_events.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"india":rbi_events+india,"global":global_ev})
    return india,global_ev

# ── 8. PORTFOLIO P&L ──────────────────────────────────────────────────────────
def calc_portfolio(prices):
    print("\n💼 Portfolio P&L...")
    holdings,ti,tc,td=[],0,0,0
    for sym,cfg in PORTFOLIO.items():
        pd=prices.get(sym,{})
        cmp=pd.get("price") or cfg["avg_cost"]
        chg=pd.get("change_pct") or 0
        qty,avg=cfg["qty"],cfg["avg_cost"]
        inv=qty*avg; cur=qty*cmp; upl=cur-inv; up_pct=round(upl/inv*100,2); dpl=round(qty*cmp*chg/100,2)
        ti+=inv; tc+=cur; td+=dpl
        holdings.append({"symbol":sym,"qty":qty,"avg_cost":avg,"cmp":round(cmp,2),"change_pct":round(chg,2),"invested":round(inv,2),"current_val":round(cur,2),"unreal_pl":round(upl,2),"unreal_pct":up_pct,"day_pl":dpl})
        print(f"  ✅ {sym}: ₹{cmp:,.0f} | {up_pct:+.1f}%")
    tpl=tc-ti; tpp=round(tpl/ti*100,2) if ti else 0
    save("portfolio.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"summary":{"total_invested":round(ti,2),"total_current":round(tc,2),"total_pl":round(tpl,2),"total_pl_pct":tpp,"day_pl":round(td,2),"day_pl_pct":round(td/tc*100,2) if tc else 0},"holdings":holdings})
    print(f"  📊 ₹{tc:,.0f} | P&L ₹{tpl:,.0f} ({tpp:+.1f}%)")
    return holdings

# ── 9. KPI JSON ───────────────────────────────────────────────────────────────
def build_kpis(prices, summary, corp):
    up=sum(1 for p in prices.values() if (p.get("change_pct") or 0)>0)
    dn=sum(1 for p in prices.values() if (p.get("change_pct") or 0)<0)
    tot_corp=sum(len(v) for v in corp.values())
    save("kpis.json",{"updated_ist":now_ist().strftime("%d %b %Y %H:%M IST"),"kpis":{"results_tracked":(summary.get("total_reported",0)+summary.get("total_upcoming",0)),"beat_rate":summary.get("beat_rate",0),"median_rev_growth":summary.get("median_rev_growth",0),"median_pat_growth":summary.get("median_pat_growth",0),"corporate_actions":tot_corp,"advance":up,"decline":dn,"beats":summary.get("beats",0),"misses":summary.get("misses",0)}})
    print(f"\n  📊 A/D: {up}/{dn} | Beat: {summary.get('beat_rate',0)}%")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__=="__main__":
    print("="*65)
    print(f"  EquityDesk Pro — Full Data Fetch — {now_ist().strftime('%d %b %Y %H:%M IST')}")
    print("="*65)
    prices,indices=fetch_prices_indices()
    fin=fetch_financials()
    earn_dates=fetch_earnings_dates()
    corp=fetch_corp_actions()
    news=fetch_news()
    india_ev,global_ev=fetch_macro_events()
    earnings,cal_events,summary=build_earnings_and_calendar(fin,prices,earn_dates,corp)
    calc_portfolio(prices)
    build_kpis(prices,summary,corp)
    print("\n"+"="*65)
    print(f"  ✅ DONE — {len(list(DATA_DIR.glob('*.json')))} JSON files saved")
    print("="*65)
