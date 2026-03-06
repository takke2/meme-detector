# ============================================================
# data_loader_bulk.py（初回3年DL＋2回目以降1日DL・NaN極力なし版）
# ============================================================

import os
import pandas as pd
import yfinance as yf

CACHE_DIR = "price_cache"
os.makedirs(CACHE_DIR, exist_ok=True)


# ------------------------------------------------------------
# 指標計算（欠損日補完＋min_periods=1 で初期も埋める）
# ------------------------------------------------------------
def preprocess_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # 日付順に並べておく
    df = df.sort_index()

    # 日付を連続化して欠損日を前日値で埋める
    df = df.asfreq("D")
    df = df.ffill()

    # MA（最初の1日目から計算させる）
    df["MA25"] = df["Close"].rolling(25, min_periods=1).mean()
    df["MA75"] = df["Close"].rolling(75, min_periods=1).mean()

    # RSI（これも min_periods=1 で初期から値を出す）
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14, min_periods=1).mean()
    avg_loss = loss.rolling(14, min_periods=1).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # 損失ゼロのときは RSI=100、残りは欠損を50で埋める
    rsi[avg_loss == 0] = 100
    df["RSI14"] = rsi.fillna(50)

    # 52週高安（ここは min_periods=1 でOK）
    df["52w_high"] = df["Close"].rolling(252, min_periods=1).max()
    df["52w_low"] = df["Close"].rolling(252, min_periods=1).min()

    return df


# ------------------------------------------------------------
# キャッシュ読み込み
# ------------------------------------------------------------
def load_from_cache(code):
    path = f"{CACHE_DIR}/{code}.csv"
    if os.path.exists(path):
        return pd.read_csv(path, index_col=0, parse_dates=True)
    return None


# ------------------------------------------------------------
# キャッシュ保存
# ------------------------------------------------------------
def save_to_cache(code, df):
    path = f"{CACHE_DIR}/{code}.csv"
    df.to_csv(path)


# ------------------------------------------------------------
# 初回DL（3年分）
# ------------------------------------------------------------
def bulk_download_full(codes):
    try:
        df = yf.download(
            tickers=codes,
            period="6y",
            group_by="ticker",
            auto_adjust=False,
            threads=True
        )
        return df
    except Exception as e:
        print("FULL DL Error:", e)
        return None


def bulk_download_today(codes, chunk_size=200):

    all_data = []

    for i in range(0, len(codes), chunk_size):
        chunk = codes[i:i+chunk_size]

        try:
            df = yf.download(
                tickers=chunk,
                period="1d",
                group_by="ticker",
                auto_adjust=False,
                threads=True
            )
            all_data.append(df)
        except Exception as e:
            print("Chunk error:", e)

    if not all_data:
        return None

    return pd.concat(all_data, axis=1)


# ------------------------------------------------------------
# キャッシュ更新（初回 or 追加）
# ------------------------------------------------------------
def update_cache_with_full(df_bulk, codes):
    for code in codes:
        if code not in df_bulk.columns.get_level_values(0):
            continue

        df = df_bulk[code].copy()
        df.index.name = "Date"

        df = preprocess_indicators(df)
        save_to_cache(code, df)


def update_cache_with_today(df_today, codes):
    for code in codes:
        if code not in df_today.columns.get_level_values(0):
            continue

        df_new = df_today[code].copy()
        df_new.index.name = "Date"

        df_old = load_from_cache(code)

        if df_old is None:
            # 初回は main 側で full DL するのでここでは触らない
            continue

        df_all = pd.concat([df_old, df_new])
        df_all = df_all[~df_all.index.duplicated(keep="last")]
        df_all = preprocess_indicators(df_all)

        save_to_cache(code, df_all)


# ------------------------------------------------------------
# 個別銘柄のデータ取得
# ------------------------------------------------------------
def load_price(code):
    return load_from_cache(code)