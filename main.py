# ============================================================
# MASTER DAILY COMPLETE FINAL
# 永続運用対応版（EXIT + REL強化 + Gmail通知）
# Git操作はGitHubActions側で実施
# 全銘柄今日分確認型DLスキップ版 + DailyLog追加（追加のみ・削除ゼロ方針）
# ============================================================

import os
import sys
import json
import pandas as pd
import yfinance as yf
import warnings
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

warnings.filterwarnings("ignore")

# ==========================
# 設定
# ==========================

CODES_FILE = "codes.csv"
CACHE_DIR = "price_cache"
MARKET_CODE = "1306.T"

DAILY_LOG = "daily_log_MASTER.csv"   # ★追加
TRADE_LOG = "trade_log_MASTER.csv"
PORT_FILE = "portfolio_state.json"
REGIME_FILE = "market_regime.csv"

INITIAL_CASH = 6_000_000
BASE_INVEST = 350_000
MAX_POSITIONS = 5

RSI_MIN = 40
STOP, TRAIL, REL, RSI_MAX, PULL_MIN, PULL_MAX, MA75_DIST, VOL_MULT = \
(0.07,0.2,0.5,55,0.02,0.08,0.07,1.2)

CHUNK_SIZE = 200
CONFIRM_DAYS = 5

os.makedirs(CACHE_DIR, exist_ok=True)

# ==========================
# Gmail
# ==========================

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO   = os.getenv("EMAIL_TO")

def send_mail(subject, body):
    if not EMAIL_USER:
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

# ==========================
# 全銘柄DL済みチェック
# ==========================

def already_updated_today(codes):

    today = datetime.now().date()

    for code in codes:

        path = os.path.join(CACHE_DIR, f"{code}.csv")

        if not os.path.exists(path):
            return False

        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if len(df) == 0:
                return False

            last_date = df.index.max().date()

            if last_date < today:
                return False

        except:
            return False

    return True

# ==========================
# Portfolio 永続化
# ==========================

def load_portfolio():
    if not os.path.exists(PORT_FILE):
        return {}, INITIAL_CASH, {}, INITIAL_CASH
    with open(PORT_FILE,"r") as f:
        d=json.load(f)
    return d["portfolio"], d["cash"], d["peak_price"], d["peak_equity"]

def save_portfolio(portfolio,cash,peak_price,peak_equity):
    with open(PORT_FILE,"w") as f:
        json.dump({
            "portfolio":portfolio,
            "cash":cash,
            "peak_price":peak_price,
            "peak_equity":peak_equity
        },f)

# ==========================
# Daily Log 追加
# ==========================

def append_daily_log(date, market_condition,
                     trend_pass, madist_pass, pull_pass,
                     rsi_pass, candle_pass, volume_pass,
                     break_pass, rel_pool_count,
                     final_candidate_count,
                     final_candidate_codes,
                     position_count, cash,
                     total_equity, drawdown):

    row = [
        date,
        market_condition,
        trend_pass,
        madist_pass,
        pull_pass,
        rsi_pass,
        candle_pass,
        volume_pass,
        break_pass,
        rel_pool_count,
        final_candidate_count,
        ",".join(final_candidate_codes),
        position_count,
        cash,
        total_equity,
        drawdown
    ]

    cols = [
        "Date","MarketCondition","TrendPass","MADistPass",
        "PullPass","RSIPass","CandlePass","VolumePass",
        "BreakPass","RelPoolCount","FinalCandidateCount",
        "FinalCandidateCodes","PositionCount","Cash",
        "TotalEquity","Drawdown"
    ]

    df = pd.DataFrame([row], columns=cols)

    if os.path.exists(DAILY_LOG):
        df.to_csv(DAILY_LOG, mode="a", header=False, index=False)
    else:
        df.to_csv(DAILY_LOG, index=False)

# ==========================
# DL / Regime / 指標 / Equity / TradeLog
# ==========================

def progress(i,total,prefix=""):
    pct=(i/total)*100
    sys.stdout.write(f"\r{prefix} {i}/{total} ({pct:.1f}%)")
    sys.stdout.flush()

def bulk_download(codes):
    return yf.download(
        tickers=" ".join(codes),
        period="3d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False
    )

def update_today_only(codes):

    print("📥 直近3日DL")

    total=len(codes)
    for i in range(0,total,CHUNK_SIZE):

        chunk=codes[i:i+CHUNK_SIZE]
        df_new=bulk_download(chunk)

        if df_new is None or df_new.empty:
            continue

        for code in chunk:

            if code not in df_new.columns.get_level_values(0):
                continue

            path=f"{CACHE_DIR}/{code}.csv"
            new=df_new[code].dropna(how="all")
            if new.empty:
                continue

            if os.path.exists(path):
                old=pd.read_csv(path,index_col=0,parse_dates=True)
                merged=pd.concat([old,new])
                merged=merged[~merged.index.duplicated(keep="last")]
            else:
                merged=new

            merged.to_csv(path)

        progress(min(i+CHUNK_SIZE,total),total,"DL")
    print()

def generate_regime():

    path = os.path.join(CACHE_DIR, f"{MARKET_CODE}.csv")
    df = pd.read_csv(path,index_col=0,parse_dates=True).sort_index()

    df["MA50"]=df["Close"].rolling(50).mean()
    df["MA200"]=df["Close"].rolling(200).mean()

    regimes=[]
    current="RANGE"
    bull_c=bear_c=0

    for i in range(len(df)):

        if pd.isna(df["MA200"].iloc[i]):
            regimes.append("NONE")
            continue

        close=df["Close"].iloc[i]
        ma50=df["MA50"].iloc[i]
        ma200=df["MA200"].iloc[i]

        bull=(close>ma200) and (ma50>ma200)
        bear=(close<ma200) and (ma50<ma200)

        if bull:
            bull_c+=1; bear_c=0
        elif bear:
            bear_c+=1; bull_c=0
        else:
            bull_c=bear_c=0

        if bull_c>=CONFIRM_DAYS:
            current="BULL"
        elif bear_c>=CONFIRM_DAYS:
            current="BEAR"
        else:
            current="RANGE"

        regimes.append(current)

    df["Regime"]=regimes
    df = df[df["Close"].notna()]
    df[["Close","MA50","MA200","Regime"]].to_csv(REGIME_FILE)

    return df["Regime"].iloc[-1]

def compute_indicators(df):

    df=df.sort_index()

    df["MA20"]=df["Close"].rolling(20).mean()
    df["MA75"]=df["Close"].rolling(75).mean()
    df["MA200"]=df["Close"].rolling(200).mean()

    df["MA75_slope"]=df["MA75"].diff(5)
    df["MA200_slope"]=df["MA200"].diff(5)

    delta=df["Close"].diff()
    gain=delta.clip(lower=0)
    loss=-delta.clip(upper=0)
    rs=gain.rolling(14).mean()/loss.rolling(14).mean()
    df["RSI14"]=(100-(100/(1+rs))).fillna(50)

    df["Ret60"]=df["Close"].pct_change(60)
    df["High20"]=df["Close"].rolling(20).max()

    df["PrevHigh"]=df["High"].shift(1)
    df["PrevClose"]=df["Close"].shift(1)
    df["PrevOpen"]=df["Open"].shift(1)
    df["PrevVolume"]=df["Volume"].shift(1)

    return df

def calculate_equity(portfolio,data,today,cash):

    value=0
    for code,pos in portfolio.items():
        if code in data and today in data[code].index:
            price=data[code].loc[today,"Close"]
            value+=price*pos["shares"]

    total=cash+value
    return value,total

def append_trade(date,code,action,price,shares,reason,
                 portfolio,data,cash,peak_equity):

    port_val,total=calculate_equity(portfolio,data,date,cash)

    peak_equity=max(peak_equity,total)
    dd=(total-peak_equity)/peak_equity

    row=[date,code,action,price,shares,reason,
         cash,port_val,total,peak_equity,dd]

    cols=["Date","Code","Action","Price","Shares","Reason",
          "CashAfter","PortfolioValue","TotalEquity",
          "PeakEquity","Drawdown"]

    df=pd.DataFrame([row],columns=cols)

    if os.path.exists(TRADE_LOG):
        df.to_csv(TRADE_LOG,mode="a",header=False,index=False)
    else:
        df.to_csv(TRADE_LOG,index=False)

    return peak_equity

# ==========================
# メイン
# ==========================

def run():

    codes=pd.read_csv(CODES_FILE).iloc[:,0].astype(str)+".T"
    codes=list(codes)
    if MARKET_CODE not in codes:
        codes.append(MARKET_CODE)

    if already_updated_today(codes):
        print("✅ 全銘柄本日分DL済みのためスキップ")
    else:
        update_today_only(codes)

    print("📊 指標計算")

    data={}
    for i,code in enumerate(codes,1):

        path=f"{CACHE_DIR}/{code}.csv"
        if not os.path.exists(path):
            continue

        df=pd.read_csv(path,index_col=0,parse_dates=True)
        if len(df)==0:
            continue

        df=compute_indicators(df)
        data[code]=df
        progress(i,len(codes),"指標")
    print()

    regime=generate_regime()
    print("📈 Regime:",regime)

    portfolio,cash,peak_price,peak_equity=load_portfolio()

    market_df=data[MARKET_CODE]
    # ★ 修正ここ
    today = market_df["Close"].last_valid_index()

    if pd.isna(today):
        print("today取得失敗")
        return
    market_ret60=market_df.loc[today,"Ret60"]

    sell_msgs=[]
    buy_msgs=[]

    trend_pass=madist_pass=pull_pass=rsi_pass=0
    candle_pass=volume_pass=break_pass=0

    # ===== EXIT =====

    for code,pos in list(portfolio.items()):

        if today not in data[code].index:
            continue

        price=data[code].loc[today,"Close"]
        entry=pos["entry"]
        peak_price[code]=max(peak_price.get(code,price),price)

        ret=(price-entry)/entry
        reason=None

        if ret<=-STOP:
            reason="STOP"
        elif price<=peak_price[code]*(1-TRAIL):
            reason="TRAIL"
        elif price<data[code].loc[today,"MA75"]:
            reason="MA75_BREAK"

        if reason:
            cash+=price*pos["shares"]
            peak_equity=append_trade(
                today,code,"SELL",price,pos["shares"],reason,
                portfolio,data,cash,peak_equity
            )
            sell_msgs.append(f"{code} SELL {reason}")
            del portfolio[code]
            del peak_price[code]

    # ===== ENTRY =====

    candidates=[]

    if regime=="BULL":

        for code,df in data.items():

            if code==MARKET_CODE or code in portfolio:
                continue

            if today not in df.index:
                continue

            row=df.loc[today]

            if not (row["MA20"]>row["MA75"]>row["MA200"]):
                continue
            trend_pass+=1

            if not (row["MA75_slope"]>0 and row["MA200_slope"]>0):
                continue

            if abs(row["Close"]-row["MA75"])/row["MA75"]>MA75_DIST:
                continue
            madist_pass+=1

            pull=(row["High20"]-row["Close"])/row["High20"]
            if not (PULL_MIN<=pull<=PULL_MAX):
                continue
            pull_pass+=1

            if not (RSI_MIN<=row["RSI14"]<=RSI_MAX):
                continue
            rsi_pass+=1

            if not (row["PrevClose"]<row["PrevOpen"]):
                continue
            candle_pass+=1

            if not (row["Volume"]>row["PrevVolume"]*VOL_MULT):
                continue
            volume_pass+=1

            if not (row["Close"]>row["PrevHigh"]):
                continue
            break_pass+=1

            rel=row["Ret60"]-market_ret60
            candidates.append((code,rel))

    rel_pool_count=len(candidates)

    final_candidate_count=0
    final_candidate_codes=[]

    if candidates:

        df_c=pd.DataFrame(candidates,columns=["Code","Rel"])
        df_c=df_c.sort_values("Rel",ascending=False)

        top_n=max(1,int(len(df_c)*REL))
        df_c=df_c.head(top_n)
        df_c=df_c.head(MAX_POSITIONS-len(portfolio))

        for _,r in df_c.iterrows():

            price=data[r["Code"]].loc[today,"Close"]
            invest=min(BASE_INVEST,cash)
            shares=int(invest/price)
            if shares<=0:
                continue

            cash-=shares*price
            portfolio[r["Code"]]={"entry":price,"shares":shares}
            peak_price[r["Code"]]=price

            peak_equity=append_trade(
                today,r["Code"],"BUY",price,shares,"ENTRY",
                portfolio,data,cash,peak_equity
            )
            buy_msgs.append(f"{r['Code']} BUY")

        final_candidate_count=len(df_c)
        final_candidate_codes=list(df_c["Code"])

    save_portfolio(portfolio,cash,peak_price,peak_equity)

    port_val,total_equity=calculate_equity(portfolio,data,today,cash)
    drawdown=(total_equity-peak_equity)/peak_equity if peak_equity>0 else 0

    append_daily_log(
        today,
        regime=="BULL",
        trend_pass,madist_pass,pull_pass,
        rsi_pass,candle_pass,volume_pass,
        break_pass,rel_pool_count,
        final_candidate_count,
        final_candidate_codes,
        len(portfolio),
        cash,total_equity,drawdown
    )

    if sell_msgs or buy_msgs:
        message="\n".join(sell_msgs+buy_msgs)
        send_mail("売買シグナル通知",message)

    print("✅ 完了")

if __name__=="__main__":
    run()